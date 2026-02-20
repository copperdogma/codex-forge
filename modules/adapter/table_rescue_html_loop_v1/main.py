#!/usr/bin/env python3
"""
Iterative table rescue loop that re-OCRs pages until table structure is recovered.
"""
import argparse
import base64
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

try:
    from modules.common.openai_client import OpenAI
except Exception as exc:  # pragma: no cover - environment dependency
    OpenAI = None
    _OPENAI_IMPORT_ERROR = exc
else:
    _OPENAI_IMPORT_ERROR = None

from modules.common.utils import read_jsonl, save_jsonl, ensure_dir, ProgressLogger
from modules.extract.ocr_ai_gpt51_v1.main import (
    build_system_prompt,
    sanitize_html,
    _extract_code_fence,
    _extract_ocr_metadata,
    extract_image_metadata,
)


RESCUE_INSTRUCTIONS = """Table recovery focus:
- Preserve the exact wording, spelling, punctuation, and numbers as printed.
- Represent tables as proper <table> grids with correct rows and columns.
- Do NOT merge multiple entries into one cell. If a cell contains multiple lines, use <br>.
- Do NOT drop empty cells; preserve column alignment.
- Keep running heads and page numbers using the provided classed <p> tags when present.
"""

MONTH_RE = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\b")
YEAR_RE = re.compile(r"\b\d{4}\b")
CONCAT_NAME_RE = re.compile(r"\b[A-Z][a-z]{2,}[A-Z][a-z]{2,}\b")
DIGIT_UPPER_RE = re.compile(r"\d[A-Z]")


@dataclass
class TableQuality:
    table_count: int
    tr_count: int
    td_count: int
    suspect_cells: int
    reasons: List[str]


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "jpeg"
    return f"data:image/{ext};base64,{b64}"


def _build_prompt(ocr_hints: Optional[str], rescue_hints: Optional[str]) -> str:
    prompt = build_system_prompt(ocr_hints)
    prompt += "\n\n" + RESCUE_INSTRUCTIONS.strip() + "\n"
    if rescue_hints:
        prompt += "\nRecipe hints:\n" + rescue_hints.strip() + "\n"
    return prompt


def _cell_has_concat_signal(text: str) -> bool:
    if not text:
        return False
    if CONCAT_NAME_RE.search(text):
        return True
    if DIGIT_UPPER_RE.search(text):
        return True
    if re.search(r"\d{4}[A-Za-z]", text):
        return True
    return False


def _cell_has_multiple_dates(text: str, has_break: bool) -> bool:
    if not text or has_break:
        return False
    if len(MONTH_RE.findall(text)) >= 2:
        return True
    if len(YEAR_RE.findall(text)) >= 2:
        return True
    return False


def _table_quality(html: str) -> TableQuality:
    soup = BeautifulSoup(html or "", "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return TableQuality(table_count=0, tr_count=0, td_count=0, suspect_cells=0, reasons=[])

    total_tr = 0
    total_td = 0
    suspect_cells = 0
    reasons: List[str] = []

    for table in tables:
        rows = table.find_all("tr")
        total_tr += len(rows)
        for row in rows:
            cells = row.find_all(["td", "th"])
            total_td += len(cells)
            for cell in cells:
                text = cell.get_text(" ", strip=True)
                has_break = cell.find("br") is not None or "<br" in str(cell)
                if _cell_has_concat_signal(text):
                    suspect_cells += 1
                if _cell_has_multiple_dates(text, has_break):
                    suspect_cells += 1

    if total_tr <= 1 and total_td >= 6:
        reasons.append("table_single_row_many_cells")
    if suspect_cells >= 2:
        reasons.append("suspect_cell_concatenation")

    return TableQuality(
        table_count=len(tables),
        tr_count=total_tr,
        td_count=total_td,
        suspect_cells=suspect_cells,
        reasons=reasons,
    )


def _needs_rescue(quality: TableQuality) -> bool:
    if quality.table_count == 0:
        return False
    return bool(quality.reasons)


def _call_ocr(model: str, prompt: str, image_data: str, temperature: float, max_tokens: int) -> Tuple[str, Optional[Any], Optional[str]]:
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
                {"role": "system", "content": [{"type": "input_text", "text": prompt}]},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Return only HTML."},
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
                        {"type": "text", "text": "Return only HTML."},
                        {"type": "image_url", "image_url": {"url": image_data}},
                    ],
                },
            ],
        )
        raw = resp.choices[0].message.content or ""
    return raw, usage, request_id


def _resolve_default_outdir(input_path: Path, module_id: str) -> Path:
    cur = input_path.parent
    for parent in [cur] + list(cur.parents):
        if (parent / "pipeline_state.json").exists():
            return parent / f"{module_id}"
    return input_path.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Iteratively re-OCR pages to recover table structure.")
    parser.add_argument("--pages", help="Input pages_html.jsonl")
    parser.add_argument("--inputs", nargs="*", help="Driver-provided inputs")
    parser.add_argument("--outdir", help="Output directory")
    parser.add_argument("--out", default="pages_html_rescued.jsonl")
    parser.add_argument("--report", default="table_rescue_report.jsonl")
    parser.add_argument("--model", default="gpt-5.1")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-output-tokens", dest="max_output_tokens", type=int, default=4096)
    parser.add_argument("--max_output_tokens", dest="max_output_tokens", type=int, default=4096)
    parser.add_argument("--ocr-hints", dest="ocr_hints")
    parser.add_argument("--ocr_hints", dest="ocr_hints")
    parser.add_argument("--rescue-hints", dest="rescue_hints")
    parser.add_argument("--rescue_hints", dest="rescue_hints")
    parser.add_argument("--max-passes", dest="max_passes", type=int, default=3)
    parser.add_argument("--max_passes", dest="max_passes", type=int, default=3)
    parser.add_argument("--max-pages", dest="max_pages", type=int, default=20)
    parser.add_argument("--max_pages", dest="max_pages", type=int, default=20)
    parser.add_argument("--budget-pages", dest="budget_pages", type=int, default=None)
    parser.add_argument("--budget_pages", dest="budget_pages", type=int, default=None)
    parser.add_argument("--pages-list", dest="pages_list", help="Comma-separated page_numbers to force rescue")
    parser.add_argument("--fail-on-unresolved", dest="fail_on_unresolved", action="store_true", default=True)
    parser.add_argument("--no-fail-on-unresolved", dest="fail_on_unresolved", action="store_false")
    parser.add_argument("--dry-run", action="store_true")
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
        args.outdir = str(_resolve_default_outdir(input_path, "table_rescue_html_loop_v1"))
    outdir_path = Path(args.outdir).expanduser()
    if not outdir_path.is_absolute():
        outdir_path = (Path.cwd() / outdir_path).resolve()
    ensure_dir(str(outdir_path))

    if os.path.isabs(args.out) or os.path.sep in args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = (Path.cwd() / out_path).resolve()
    else:
        out_path = outdir_path / args.out
    if os.path.isabs(args.report) or os.path.sep in args.report:
        report_path = Path(args.report)
        if not report_path.is_absolute():
            report_path = (Path.cwd() / report_path).resolve()
    else:
        report_path = outdir_path / args.report

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
        message="Table rescue loop started",
        artifact=str(out_path),
        module_id="table_rescue_html_loop_v1",
        schema_version="page_html_v1",
    )

    explicit_pages: List[int] = []
    if args.pages_list:
        explicit_pages = [int(p.strip()) for p in args.pages_list.split(",") if p.strip()]

    prompt = _build_prompt(args.ocr_hints, args.rescue_hints)
    prompt_hash = re.sub(r"[^a-z0-9]", "", str(abs(hash(prompt))))[:12]

    remaining_budget = args.budget_pages if args.budget_pages is not None else None
    report_rows: List[Dict[str, Any]] = []

    def page_number(row: Dict[str, Any]) -> int:
        return int(row.get("page_number") or row.get("page") or 0)

    for pass_idx in range(1, max(1, args.max_passes) + 1):
        candidates: List[Tuple[int, TableQuality]] = []
        for row in rows:
            pn = page_number(row)
            html = row.get("html") or row.get("raw_html") or ""
            quality = _table_quality(html)
            if explicit_pages:
                if pn in explicit_pages:
                    candidates.append((pn, quality))
                continue
            if _needs_rescue(quality):
                candidates.append((pn, quality))

        if not candidates:
            break

        candidates.sort(key=lambda item: (item[1].suspect_cells, item[1].td_count, item[1].tr_count), reverse=True)
        cap = args.max_pages
        if remaining_budget is not None:
            cap = min(cap, remaining_budget)
        selected = {pn for pn, _ in candidates[:cap]}

        if not selected:
            break

        for idx, row in enumerate(rows, start=1):
            pn = page_number(row)
            if pn not in selected:
                continue
            html = row.get("html") or row.get("raw_html") or ""
            before = _table_quality(html)
            if args.dry_run:
                report_rows.append({
                    "page_number": pn,
                    "pass": pass_idx,
                    "attempted": False,
                    "dry_run": True,
                    "before": before.__dict__,
                    "after": before.__dict__,
                })
                continue
            image_path = row.get("image")
            if not image_path or not os.path.exists(image_path):
                report_rows.append({
                    "page_number": pn,
                    "pass": pass_idx,
                    "attempted": True,
                    "error": "missing_image",
                    "before": before.__dict__,
                    "after": before.__dict__,
                })
                continue

            image_data = _encode_image(image_path)
            raw, usage, request_id = _call_ocr(
                args.model,
                prompt,
                image_data,
                args.temperature,
                args.max_output_tokens,
            )
            raw = _extract_code_fence(raw)
            cleaned_raw, meta, meta_tag, meta_warning = _extract_ocr_metadata(raw)
            cleaned = sanitize_html(cleaned_raw)

            row["module_id"] = "table_rescue_html_loop_v1"
            if meta:
                row.update({k: v for k, v in meta.items() if v is not None})
            if meta_warning:
                row["ocr_metadata_warning"] = meta_warning
            if meta_tag and not all(v is not None for v in meta.values()):
                row["ocr_metadata_tag"] = meta_tag
            if not meta_tag:
                row["ocr_metadata_missing"] = True
            row["html"] = cleaned
            row["raw_html"] = raw

            images = extract_image_metadata(cleaned)
            if images:
                row["images"] = images

            after = _table_quality(cleaned)
            report_rows.append({
                "page_number": pn,
                "pass": pass_idx,
                "attempted": True,
                "model": args.model,
                "prompt_hash": prompt_hash,
                "usage": usage,
                "request_id": request_id,
                "before": before.__dict__,
                "after": after.__dict__,
            })

            if remaining_budget is not None:
                remaining_budget -= 1

            if idx % 10 == 0:
                logger.log(
                    "adapter",
                    "running",
                    current=idx,
                    total=total,
                    message=f"Table rescue pass {pass_idx} progress {idx}/{total}",
                    artifact=str(out_path),
                    module_id="table_rescue_html_loop_v1",
                    schema_version="page_html_v1",
                )

        if remaining_budget is not None and remaining_budget <= 0:
            break

    save_jsonl(str(out_path), rows)
    if report_rows:
        save_jsonl(str(report_path), report_rows)

    unresolved = []
    for row in rows:
        html = row.get("html") or row.get("raw_html") or ""
        quality = _table_quality(html)
        if _needs_rescue(quality):
            unresolved.append({"page_number": page_number(row), "reasons": quality.reasons, "quality": quality.__dict__})

    logger.log(
        "table_rescue",
        "done",
        current=total,
        total=total,
        message=f"Table rescue loop complete: unresolved={len(unresolved)}",
        artifact=str(out_path),
        module_id="table_rescue_html_loop_v1",
        schema_version="page_html_v1",
        extra={"summary_metrics": {"tables_unresolved_count": len(unresolved)}},
    )

    if unresolved and args.fail_on_unresolved:
        raise SystemExit(f"Unresolved table issues after rescue loop: {len(unresolved)} pages")


if __name__ == "__main__":
    main()
