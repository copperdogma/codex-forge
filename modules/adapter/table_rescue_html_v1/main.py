import argparse
import base64
import hashlib
import io
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

# Allow large page images from high-resolution scans.
Image.MAX_IMAGE_PIXELS = None

from modules.common.utils import read_jsonl, append_jsonl, ensure_dir, ProgressLogger, log_llm_usage
from modules.extract.ocr_ai_gpt51_v1.main import SYSTEM_PROMPT, sanitize_html

try:
    from openai import OpenAI
except Exception as exc:  # pragma: no cover - environment dependency
    OpenAI = None
    _OPENAI_IMPORT_ERROR = exc


RESCUE_INSTRUCTIONS = """You are fixing collapsed tables in OCR output.

Task:
- Focus on the table/grid region in the provided image crop.
- Output ONLY a single <table> that preserves the grid structure.
- If no table is present in the crop, return an empty string.

Rules:
- Use only allowed tags from the main OCR prompt.
- Preserve text exactly as printed.
- Do not add commentary, Markdown, or extra wrappers.
"""


@dataclass
class HtmlStats:
    table_count: int
    tr_count: int
    td_count: int
    turn_to_count: int
    number_count: int
    text: str


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def extract_code_fence(text: str) -> str:
    if "```" not in text:
        return text
    parts = text.split("```")
    if len(parts) >= 3:
        return parts[1].strip()
    return text.replace("```", "").strip()


def build_prompt(ocr_hints: Optional[str], rescue_hints: Optional[str]) -> str:
    prompt = SYSTEM_PROMPT + "\n\nRescue instructions:\n" + RESCUE_INSTRUCTIONS.strip() + "\n"
    hints = []
    if ocr_hints:
        hints.append(ocr_hints.strip())
    if rescue_hints:
        hints.append(rescue_hints.strip())
    if hints:
        prompt += "\nRecipe hints:\n" + "\n".join(hints) + "\n"
    return prompt


def html_stats(html: str) -> HtmlStats:
    table_count = len(re.findall(r"<table\b", html, flags=re.IGNORECASE))
    tr_count = len(re.findall(r"<tr\b", html, flags=re.IGNORECASE))
    td_count = len(re.findall(r"<(td|th)\b", html, flags=re.IGNORECASE))
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    text_lower = text.lower()
    turn_to_count = len(re.findall(r"\bturn\s+to\s+\d{1,3}\b", text_lower))
    number_count = len(re.findall(r"\b\d{1,3}\b", text_lower))
    return HtmlStats(
        table_count=table_count,
        tr_count=tr_count,
        td_count=td_count,
        turn_to_count=turn_to_count,
        number_count=number_count,
        text=text,
    )


def detect_collapsed_table(stats: HtmlStats) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    if stats.table_count > 0:
        if stats.tr_count <= 1 and stats.td_count >= 6:
            reasons.append("table_single_row_many_cells")
        if stats.tr_count <= 1 and stats.turn_to_count >= 3:
            reasons.append("table_single_row_many_turns")
    else:
        if stats.turn_to_count >= 4 and stats.number_count >= 6:
            reasons.append("no_table_many_turns")
    return (len(reasons) > 0), reasons


def encode_crop(image_path: str, crop_top: float, crop_bottom: float) -> Tuple[str, Dict[str, float]]:
    with Image.open(image_path) as img:
        width, height = img.size
        top_px = max(0, int(height * crop_top))
        bottom_px = min(height, int(height * crop_bottom))
        if bottom_px <= top_px:
            bottom_px = min(height, top_px + int(height * 0.25))
        box = (0, top_px, width, bottom_px)
        cropped = img.crop(box)
        buffer = io.BytesIO()
        cropped.save(buffer, format="PNG")
        data = base64.b64encode(buffer.getvalue()).decode("utf-8")
    crop_meta = {
        "top": crop_top,
        "bottom": crop_bottom,
        "left": 0.0,
        "right": 1.0,
        "unit": "ratio",
        "pixel_box": [0, top_px, width, bottom_px],
    }
    return f"data:image/png;base64,{data}", crop_meta


def extract_table(html: str) -> str:
    match = re.search(r"<table\b.*?</table>", html, flags=re.IGNORECASE | re.DOTALL)
    return match.group(0) if match else ""


def replace_or_insert_table(html: str, new_table: str) -> Tuple[str, bool, bool]:
    if not new_table:
        return html, False, False
    if re.search(r"<table\b.*?</table>", html, flags=re.IGNORECASE | re.DOTALL):
        updated = re.sub(r"<table\b.*?</table>", new_table, html, count=1, flags=re.IGNORECASE | re.DOTALL)
        return updated, True, False

    # Insert before first paragraph containing "Turn to" (if present), else prepend to HTML.
    match = re.search(r"<p>.*?turn\s+to\s+\d{1,3}.*?</p>", html, flags=re.IGNORECASE | re.DOTALL)
    if match:
        start = match.start()
        updated = html[:start] + new_table + "\n" + html[start:]
        return updated, False, True

    return new_table + "\n" + html, False, True


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]


def call_rescue(model: str, prompt: str, image_data: str, temperature: float, max_tokens: int) -> Tuple[str, Optional[Any], Optional[str]]:
    if OpenAI is None:  # pragma: no cover
        raise RuntimeError("openai package required") from _OPENAI_IMPORT_ERROR
    client = OpenAI()
    raw = ""
    usage = None
    request_id = None
    if hasattr(client, "responses"):
        resp = client.responses.create(
            model=model,
            temperature=temperature,
            max_output_tokens=max_tokens,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": prompt}],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Return only a <table> or empty string."},
                        {"type": "input_image", "image_url": image_data},
                    ],
                },
            ],
        )
        raw = resp.output_text or ""
        usage = getattr(resp, "usage", None)
        request_id = getattr(resp, "id", None)
    else:
        resp = client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Return only a <table> or empty string."},
                        {"type": "image_url", "image_url": {"url": image_data}},
                    ],
                },
            ],
        )
        raw = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        request_id = getattr(resp, "id", None)
    return raw, usage, request_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Rescue collapsed tables via targeted OCR")
    parser.add_argument("--pages", help="Input pages_html.jsonl")
    parser.add_argument("--inputs", nargs="*", help="Driver-provided inputs")
    parser.add_argument("--outdir", help="Output directory")
    parser.add_argument("--out", default="pages_html_rescued.jsonl")
    parser.add_argument("--model", default="gpt-5.1")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-output-tokens", dest="max_output_tokens", type=int, default=1024)
    parser.add_argument("--max_output_tokens", dest="max_output_tokens", type=int, default=1024)
    parser.add_argument("--ocr-hints", dest="ocr_hints")
    parser.add_argument("--ocr_hints", dest="ocr_hints")
    parser.add_argument("--rescue-hints", dest="rescue_hints")
    parser.add_argument("--rescue_hints", dest="rescue_hints")
    parser.add_argument("--max-pages", dest="max_pages", type=int, default=10)
    parser.add_argument("--max_pages", dest="max_pages", type=int, default=10)
    parser.add_argument("--budget-pages", dest="budget_pages", type=int, default=None)
    parser.add_argument("--budget_pages", dest="budget_pages", type=int, default=None)
    parser.add_argument("--pages-list", dest="pages_list", help="Comma-separated page_numbers to rescue")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--crop-top", dest="crop_top", type=float, default=0.0)
    parser.add_argument("--crop_top", dest="crop_top", type=float, default=0.0)
    parser.add_argument("--crop-bottom", dest="crop_bottom", type=float, default=0.42)
    parser.add_argument("--crop_bottom", dest="crop_bottom", type=float, default=0.42)
    parser.add_argument("--fallback-crop-top", dest="fallback_crop_top", type=float, default=0.35)
    parser.add_argument("--fallback_crop_top", dest="fallback_crop_top", type=float, default=0.35)
    parser.add_argument("--fallback-crop-bottom", dest="fallback_crop_bottom", type=float, default=0.85)
    parser.add_argument("--fallback_crop_bottom", dest="fallback_crop_bottom", type=float, default=0.85)
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    input_path = None
    if args.pages:
        input_path = Path(args.pages)
    elif args.inputs:
        input_path = Path(args.inputs[0])
    else:
        raise SystemExit("Missing --pages or --inputs")

    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")

    if not args.outdir:
        args.outdir = str(input_path.parent)
    ensure_dir(args.outdir)
    out_path = Path(args.outdir) / args.out if not os.path.isabs(args.out) else Path(args.out)
    if out_path.exists():
        out_path.unlink()

    rows = list(read_jsonl(str(input_path)))
    total = len(rows)
    if total == 0:
        raise SystemExit(f"Input is empty: {input_path}")

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log(
        "adapter",
        "running",
        current=0,
        total=total,
        message="Table rescue scan started",
        artifact=str(out_path),
        module_id="table_rescue_html_v1",
        schema_version="page_html_v1",
    )

    prompt = build_prompt(args.ocr_hints, args.rescue_hints)
    prompt_sig = prompt_hash(prompt)

    explicit_pages: List[int] = []
    if args.pages_list:
        explicit_pages = [int(p.strip()) for p in args.pages_list.split(",") if p.strip()]

    candidates: List[Dict[str, Any]] = []
    for row in rows:
        page_number = row.get("page_number")
        html = row.get("html", "") or ""
        stats = html_stats(html)
        should_rescue, reasons = detect_collapsed_table(stats)
        if explicit_pages:
            should_rescue = page_number in explicit_pages
            reasons = ["explicit_pages"] if should_rescue else []
        if should_rescue:
            candidates.append(
                {
                    "page_number": page_number,
                    "reasons": reasons,
                    "turn_to_count": stats.turn_to_count,
                    "td_count": stats.td_count,
                    "number_count": stats.number_count,
                }
            )

    # Sort candidates by severity
    candidates.sort(
        key=lambda c: (c.get("turn_to_count", 0), c.get("td_count", 0), c.get("number_count", 0)),
        reverse=True,
    )

    cap = args.budget_pages if args.budget_pages is not None else args.max_pages
    selected_pages = {c["page_number"]: c for c in candidates[:cap]}
    skipped_pages = {c["page_number"]: c for c in candidates[cap:]}

    rescued = 0
    attempted = 0

    for idx, row in enumerate(rows, start=1):
        page_number = row.get("page_number")
        html = row.get("html", "") or ""
        prev_module_id = row.get("module_id")
        row["module_id"] = "table_rescue_html_v1"
        stats = html_stats(html)
        old_table = extract_table(html)
        old_tr = len(re.findall(r"<tr\b", old_table, flags=re.IGNORECASE)) if old_table else 0

        rescue_meta: Dict[str, Any] = {}
        if page_number in selected_pages:
            attempted += 1
            reasons = selected_pages[page_number]["reasons"]
            rescue_meta.update(
                {
                    "attempted": True,
                    "applied": False,
                    "reasons": reasons,
                    "model": args.model,
                    "prompt_hash": prompt_sig,
                    "prev_module_id": prev_module_id,
                }
            )
            if args.dry_run:
                rescue_meta["skipped_reason"] = "dry_run"
                row["rescue"] = rescue_meta
            else:
                image_path = row.get("image")
                if not image_path or not os.path.exists(image_path):
                    rescue_meta["skipped_reason"] = "missing_image"
                    row["rescue"] = rescue_meta
                else:
                    attempts: List[Dict[str, Any]] = []
                    image_data, crop_meta = encode_crop(image_path, args.crop_top, args.crop_bottom)
                    raw, usage, request_id = call_rescue(
                        args.model,
                        prompt,
                        image_data,
                        args.temperature,
                        args.max_output_tokens,
                    )
                    raw = extract_code_fence(raw)
                    cleaned = sanitize_html(raw)
                    new_table = extract_table(cleaned)
                    new_tr = len(re.findall(r"<tr\b", new_table, flags=re.IGNORECASE)) if new_table else 0
                    attempts.append(
                        {
                            "crop": crop_meta,
                            "table_tr": new_tr,
                            "table_chars": len(new_table),
                        }
                    )

                    if not new_table and args.fallback_crop_bottom > args.fallback_crop_top:
                        image_data, crop_meta = encode_crop(
                            image_path, args.fallback_crop_top, args.fallback_crop_bottom
                        )
                        raw, usage2, request_id2 = call_rescue(
                            args.model,
                            prompt,
                            image_data,
                            args.temperature,
                            args.max_output_tokens,
                        )
                        raw = extract_code_fence(raw)
                        cleaned = sanitize_html(raw)
                        new_table = extract_table(cleaned)
                        new_tr = len(re.findall(r"<tr\b", new_table, flags=re.IGNORECASE)) if new_table else 0
                        attempts.append(
                            {
                                "crop": crop_meta,
                                "table_tr": new_tr,
                                "table_chars": len(new_table),
                            }
                        )
                        if usage2:
                            usage = usage2
                            request_id = request_id2

                    rescue_meta.update(
                        {
                            "attempts": attempts,
                            "new_table_tr": new_tr,
                            "old_table_tr": old_tr,
                            "table_chars": len(new_table),
                            "table_preview": new_table[:200],
                        }
                    )
                    applied = False
                    replaced = False
                    inserted = False
                    if new_table and new_tr >= 2 and (old_tr <= 1 or new_tr > old_tr):
                        html, replaced, inserted = replace_or_insert_table(html, new_table)
                        row["html"] = html
                        applied = True
                        rescued += 1
                    rescue_meta.update(
                        {
                            "applied": applied,
                            "table_replaced": replaced,
                            "table_inserted": inserted,
                        }
                    )
                    row["rescue"] = rescue_meta

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
        elif page_number in skipped_pages:
            rescue_meta = {
                "attempted": False,
                "applied": False,
                "reasons": skipped_pages[page_number]["reasons"],
                "skipped_reason": "cap_reached",
                "model": args.model,
                "prompt_hash": prompt_sig,
                "prev_module_id": prev_module_id,
            }
            row["rescue"] = rescue_meta

        append_jsonl(str(out_path), row)

        if idx % 25 == 0:
            logger.log(
                "adapter",
                "running",
                current=idx,
                total=total,
                message=f"Table rescue progress {idx}/{total}",
                artifact=str(out_path),
                module_id="table_rescue_html_v1",
                schema_version="page_html_v1",
            )

    logger.log(
        "adapter",
        "done",
        current=total,
        total=total,
        message=f"Table rescue complete: attempted={attempted}, applied={rescued}",
        artifact=str(out_path),
        module_id="table_rescue_html_v1",
        schema_version="page_html_v1",
    )


if __name__ == "__main__":
    main()
