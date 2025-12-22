import argparse
import base64
import os
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional

from modules.common.utils import read_jsonl, ensure_dir, append_jsonl, ProgressLogger, log_llm_usage

try:
    from openai import OpenAI
except Exception as exc:  # pragma: no cover - environment dependency
    OpenAI = None
    _OPENAI_IMPORT_ERROR = exc


ALLOWED_TAGS = {
    "h1", "h2", "h3", "p", "strong", "em", "ol", "ul", "li",
    "table", "thead", "tbody", "tr", "th", "td", "caption",
    "img", "dl", "dt", "dd",
}

RUNNING_HEAD_CLASS = "running-head"
PAGE_NUMBER_CLASS = "page-number"

SYSTEM_PROMPT = """You are an OCR engine for scanned book pages.

Return ONLY minimal HTML that preserves text and basic structure.

Allowed tags (only):
- Structural: <h1>, <h2>, <h3>, <p>, <dl>, <dt>, <dd>
- Emphasis: <strong>, <em>
- Lists: <ol>, <ul>, <li>
- Tables: <table>, <thead>, <tbody>, <tr>, <th>, <td>, <caption>
- Running head / page number: <p class="running-head">, <p class="page-number">
- Images: <img alt="..."> (placeholder only, no src)

Rules:
- Preserve exact wording, punctuation, and numbers.
- Reflow paragraphs (no hard line breaks within a paragraph).
- Keep running heads and page numbers if present (use the classed <p> tags above).
- Use <h2> for section numbers when they are clearly section headers.
- Use <h1> only for true page titles/headings.
- Use <dl> with <dt>/<dd> for inline label/value blocks (e.g., creature name + SKILL/STAMINA).
- Do not invent <section>, <div>, or <span>.
- Use <img alt="..."> when an illustration appears (short, factual description).
- Tables must be represented as a single <table> with headers/rows (no splitting).
- If uncertain, default to <p> with plain text.

Output ONLY HTML, no Markdown, no code fences, no extra commentary."""


def build_system_prompt(hints: Optional[str]) -> str:
    if not hints:
        return SYSTEM_PROMPT
    return SYSTEM_PROMPT + "\n\nRecipe hints:\n" + hints.strip() + "\n"


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _extract_code_fence(text: str) -> str:
    if "```" not in text:
        return text
    parts = text.split("```")
    if len(parts) >= 3:
        return parts[1].strip()
    return text.replace("```", "").strip()


class TagSanitizer(HTMLParser):
    def __init__(self):
        super().__init__()
        self.out: List[str] = []

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        if tag not in ALLOWED_TAGS:
            return
        if tag == "img":
            alt = ""
            for k, v in attrs:
                if k.lower() == "alt":
                    alt = v or ""
                    break
            self.out.append(f"<img alt=\"{alt}\">")
            return
        if tag == "p":
            cls = None
            for k, v in attrs:
                if k.lower() == "class":
                    cls = v
                    break
            if cls in (RUNNING_HEAD_CLASS, PAGE_NUMBER_CLASS):
                self.out.append(f"<p class=\"{cls}\">")
            else:
                self.out.append("<p>")
            return
        self.out.append(f"<{tag}>")

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in ALLOWED_TAGS and tag != "img":
            self.out.append(f"</{tag}>")

    def handle_data(self, data: str):
        if data:
            self.out.append(data)

    def get_html(self) -> str:
        html = "".join(self.out)
        html = re.sub(r"\s+", " ", html)
        html = re.sub(r">\s+<", ">\n<", html)
        return html.strip() + "\n"


def sanitize_html(html: str) -> str:
    parser = TagSanitizer()
    parser.feed(html)
    return parser.get_html()


def resolve_manifest_path(args) -> Path:
    if args.pages:
        return Path(args.pages)
    if args.inputs:
        return Path(args.inputs[0])
    raise SystemExit("Missing --pages or --inputs manifest path")


def main() -> None:
    parser = argparse.ArgumentParser(description="GPT-5.1 OCR to per-page HTML")
    parser.add_argument("--pages", help="Path to page_image_v1 manifest JSONL")
    parser.add_argument("--pdf", help="Ignored (driver compatibility)")
    parser.add_argument("--images", help="Ignored (driver compatibility)")
    parser.add_argument("--inputs", nargs="*", help="Driver-provided inputs")
    parser.add_argument("--outdir", help="Output directory")
    parser.add_argument("--out", default="pages_html.jsonl", help="Output JSONL filename")
    parser.add_argument("--model", default="gpt-5.1")
    parser.add_argument("--max-output-tokens", dest="max_output_tokens", type=int, default=4096)
    parser.add_argument("--max_output_tokens", dest="max_output_tokens", type=int, default=4096)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--allow-empty", dest="allow_empty", action="store_true")
    parser.add_argument("--ocr-hints", dest="ocr_hints", help="Recipe-level OCR hints text")
    parser.add_argument("--ocr_hints", dest="ocr_hints", help="Recipe-level OCR hints text")
    parser.add_argument("--save-raw", dest="save_raw", action="store_true")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output")
    parser.add_argument("--resume", action="store_true", help="Skip pages already written (default)")
    parser.set_defaults(resume=True)
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    try:
        if OpenAI is None:  # pragma: no cover
            raise RuntimeError("openai package required") from _OPENAI_IMPORT_ERROR

        manifest_path = resolve_manifest_path(args)
        if not manifest_path.exists():
            raise SystemExit(f"Manifest not found: {manifest_path}")

        if not args.outdir:
            args.outdir = str(manifest_path.parent)
        ensure_dir(args.outdir)
        out_path = Path(args.outdir) / args.out if not os.path.isabs(args.out) else Path(args.out)

        rows = list(read_jsonl(str(manifest_path)))
        total = len(rows)
        if total == 0:
            raise SystemExit(f"Manifest is empty: {manifest_path}")

        logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
        logger.log(
            "ocr_ai",
            "running",
            current=0,
            total=total,
            message="Running GPT-5.1 OCR to HTML",
            artifact=str(out_path),
            module_id="ocr_ai_gpt51_v1",
            schema_version="page_html_v1",
        )

        client = OpenAI()
        system_prompt = build_system_prompt(args.ocr_hints)
        if out_path.exists() and args.force:
            out_path.unlink()

        completed_pages = set()
        if out_path.exists() and args.resume:
            try:
                for row in read_jsonl(str(out_path)):
                    pn = row.get("page_number")
                    if pn is not None:
                        completed_pages.add(pn)
            except Exception:
                completed_pages = set()

        for idx, page in enumerate(rows, start=1):
            image_path = page.get("image")
            if not image_path or not os.path.exists(image_path):
                raise SystemExit(f"Missing image for page: {page}")

            page_number = page.get("page_number")
            if page_number in completed_pages:
                logger.log(
                    "extract",
                    "running",
                    current=idx,
                    total=total,
                    message=f"Skipping page {page_number} (already completed)",
                    artifact=str(out_path),
                    module_id="ocr_ai_gpt51_v1",
                    schema_version="page_html_v1",
                )
                continue

            mime = "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"
            b64 = base64.b64encode(Path(image_path).read_bytes()).decode("utf-8")

            try:
                if hasattr(client, "responses"):
                    resp = client.responses.create(
                        model=args.model,
                        temperature=args.temperature,
                        max_output_tokens=args.max_output_tokens,
                        input=[
                            {
                                "role": "system",
                                "content": [{"type": "input_text", "text": system_prompt}],
                            },
                            {
                                "role": "user",
                                "content": [
                                    {"type": "input_text", "text": "Return HTML only."},
                                    {"type": "input_image", "image_url": f"data:{mime};base64,{b64}"},
                                ],
                            },
                        ],
                    )
                    raw = resp.output_text or ""
                    usage = getattr(resp, "usage", None)
                    request_id = getattr(resp, "id", None)
                else:
                    resp = client.chat.completions.create(
                        model=args.model,
                        temperature=args.temperature,
                        max_completion_tokens=args.max_output_tokens,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "Return HTML only."},
                                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                                ],
                            },
                        ],
                    )
                    raw = resp.choices[0].message.content or ""
                    usage = getattr(resp, "usage", None)
                    request_id = getattr(resp, "id", None)
            except Exception as exc:
                logger.log(
                    "extract",
                    "failed",
                    current=idx,
                    total=total,
                    message=f"OCR failed on page {page_number}: {exc}",
                    artifact=str(out_path),
                    module_id="ocr_ai_gpt51_v1",
                    schema_version="page_html_v1",
                )
                raise
            raw = _extract_code_fence(raw)
            cleaned = sanitize_html(raw)
            if not cleaned.strip():
                msg = f"Empty HTML output for page {page.get('page_number')}"
                if args.allow_empty:
                    cleaned = ""
                else:
                    raise SystemExit(msg)

            row = {
                "schema_version": "page_html_v1",
                "module_id": "ocr_ai_gpt51_v1",
                "run_id": args.run_id,
                "created_at": _utc(),
                "page": page.get("page"),
                "page_number": page.get("page_number"),
                "original_page_number": page.get("original_page_number"),
                "image": image_path,
                "spread_side": page.get("spread_side"),
                "html": cleaned,
            }
            if args.save_raw:
                row["raw_html"] = raw

            append_jsonl(str(out_path), row)

            if usage:
                prompt_tokens = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None)
                completion_tokens = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", None)
                if prompt_tokens is not None and completion_tokens is not None:
                    log_llm_usage(
                        model=args.model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        provider="openai",
                        request_id=request_id,
                        run_id=args.run_id,
                    )

            logger.log(
                "extract",
                "running",
                current=idx,
                total=total,
                message=f"OCR HTML for page {page.get('page_number')}",
                artifact=str(out_path),
                module_id="ocr_ai_gpt51_v1",
                schema_version="page_html_v1",
            )

            if idx % 25 == 0:
                logger.log(
                    "extract",
                    "running",
                    current=idx,
                    total=total,
                    message=f"Heartbeat: {idx}/{total} pages processed",
                    artifact=str(out_path),
                    module_id="ocr_ai_gpt51_v1",
                    schema_version="page_html_v1",
                )

        logger.log(
            "ocr_ai",
            "done",
            current=total,
            total=total,
            message="GPT-5.1 OCR HTML complete",
            artifact=str(out_path),
            module_id="ocr_ai_gpt51_v1",
            schema_version="page_html_v1",
            extra={"summary_metrics": {"pages_processed_count": total}},
        )
    except Exception as exc:
        logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
        logger.log(
            "ocr_ai",
            "failed",
            message=f"Unhandled OCR failure: {exc}",
            module_id="ocr_ai_gpt51_v1",
            schema_version="page_html_v1",
        )
        raise


if __name__ == "__main__":
    main()
