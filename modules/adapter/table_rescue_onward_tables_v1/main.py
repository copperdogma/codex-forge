#!/usr/bin/env python3
"""
Onward-specific table re-OCR for genealogy pages.
Re-OCRs any page containing a table with NAME/BORN/MARRIED/SPOUSE/BOY/GIRL/DIED headers,
then strips page-number/running-head tags from the resulting HTML while preserving
printed_page_number fields already extracted.
"""
import argparse
import base64
import json
import os
import re
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


EXPECTED_HEADERS = ["name", "born", "married", "spouse", "boy", "girl", "died"]

PROMPT_HINTS = """
Genealogy tables extraction (Onward-specific):
- Output HTML only; preserve exact wording, spelling, punctuation, and numbers.
- Do not normalize names or dates.
- Represent genealogy tables as HTML <table> with a header row.
- Use separate columns for BOY and GIRL. Do not merge them.
- CRITICAL: One visual line in the source must map to one <tr> row in the table.
- Do not use <br> inside table cells; use additional rows instead.
- Preserve column alignment from the original page.
- Keep running heads and page numbers using <p class=\"running-head\"> and <p class=\"page-number\">.
""".strip()


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "jpeg"
    return f"data:image/{ext};base64,{b64}"


def _call_ocr(model: str, prompt: str, image_data: str, temperature: float, max_tokens: int,
              timeout_seconds: Optional[float]) -> Tuple[str, Optional[Any], Optional[str]]:
    if OpenAI is None:  # pragma: no cover
        raise RuntimeError("openai package required") from _OPENAI_IMPORT_ERROR
    client = OpenAI(timeout=timeout_seconds) if timeout_seconds else OpenAI()
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


def _normalize_token(text: str) -> str:
    return re.sub(r"[^a-z]", "", (text or "").lower())


def _header_match_score(cell: str, token: str) -> float:
    cell_norm = _normalize_token(cell)
    if not cell_norm:
        return 0.0
    if token in cell_norm:
        return 1.0
    # Fuzzy match via simple ratio
    try:
        from difflib import SequenceMatcher

        return SequenceMatcher(None, cell_norm, token).ratio()
    except Exception:
        return 0.0


def _table_has_headers(html: str, threshold: float) -> bool:
    soup = BeautifulSoup(html or "", "html.parser")
    for table in soup.find_all("table"):
        header_cells: List[str] = []
        thead = table.find("thead")
        if thead:
            header_cells = [c.get_text(" ", strip=True) for c in thead.find_all(["th", "td"])]
        if not header_cells:
            first_row = table.find("tr")
            if first_row:
                header_cells = [c.get_text(" ", strip=True) for c in first_row.find_all(["th", "td"])]
        if not header_cells:
            continue

        matched = set()
        for cell in header_cells:
            cell_norm = _normalize_token(cell)
            for token in EXPECTED_HEADERS:
                score = _header_match_score(cell_norm, token)
                if score >= threshold:
                    matched.add(token)
            # allow combined boy/girl header
            if "boy" in cell_norm and "girl" in cell_norm:
                matched.add("boy")
                matched.add("girl")

        if all(t in matched for t in EXPECTED_HEADERS):
            return True
    return False


def _split_boy_girl_headers(table: BeautifulSoup, soup: BeautifulSoup) -> None:
    header_row = None
    thead = table.find("thead")
    if thead:
        header_row = thead.find("tr")
    if header_row is None:
        header_row = table.find("tr")
    if header_row is None:
        return

    header_cells = header_row.find_all(["th", "td"])
    for idx, cell in enumerate(header_cells):
        text_norm = _normalize_token(cell.get_text(" ", strip=True))
        if "boy" in text_norm and "girl" in text_norm:
            boy = soup.new_tag("th")
            boy.string = "BOY"
            girl = soup.new_tag("th")
            girl.string = "GIRL"
            cell.replace_with(boy)
            boy.insert_after(girl)

            # Split data cells in the same column.
            body_rows = []
            if table.find("tbody"):
                body_rows = table.find("tbody").find_all("tr")
            else:
                body_rows = table.find_all("tr")[1:]
            for row in body_rows:
                cells = row.find_all(["td", "th"])
                if idx >= len(cells):
                    continue
                raw = cells[idx].get_text(" ", strip=True)
                nums = re.findall(r"\\d+", raw)
                if len(nums) >= 2:
                    boy_val = nums[0]
                    girl_val = nums[1]
                else:
                    parts = [p for p in re.split(r"\\s+", raw) if p]
                    boy_val = parts[0] if parts else ""
                    girl_val = " ".join(parts[1:]) if len(parts) > 1 else ""
                new_boy = soup.new_tag("td")
                if boy_val:
                    new_boy.append(boy_val)
                new_girl = soup.new_tag("td")
                if girl_val:
                    new_girl.append(girl_val)
                cells[idx].replace_with(new_boy)
                new_boy.insert_after(new_girl)
            return


def _split_table_row_br(table: BeautifulSoup, soup: BeautifulSoup) -> None:
    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
    if not rows:
        return
    for row in list(rows):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        cell_lines: List[List[str]] = []
        for cell in cells:
            lines = [s.strip() for s in cell.stripped_strings if s.strip()]
            if not lines:
                lines = [""]
            cell_lines.append(lines)
        max_lines = max(len(lines) for lines in cell_lines)
        if max_lines <= 1:
            continue
        new_rows = []
        for line_idx in range(max_lines):
            new_row = soup.new_tag("tr")
            for lines in cell_lines:
                text = lines[line_idx] if line_idx < len(lines) else ""
                td = soup.new_tag("td")
                td.string = text
                new_row.append(td)
            new_rows.append(new_row)
        for new_row in new_rows[::-1]:
            row.insert_after(new_row)
        row.decompose()


def _split_boy_girl_cells(table: BeautifulSoup) -> None:
    header_row = None
    thead = table.find("thead")
    if thead:
        header_row = thead.find("tr")
    if header_row is None:
        header_row = table.find("tr")
    if header_row is None:
        return

    header_cells = header_row.find_all(["th", "td"])
    headers = [_normalize_token(c.get_text(" ", strip=True)) for c in header_cells]
    if "boy" not in headers or "girl" not in headers:
        return
    boy_idx = headers.index("boy")
    girl_idx = headers.index("girl")

    body_rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")[1:]
    for row in body_rows:
        cells = row.find_all(["td", "th"])
        if boy_idx >= len(cells) or girl_idx >= len(cells):
            continue
        boy_text = cells[boy_idx].get_text(" ", strip=True)
        girl_text = cells[girl_idx].get_text(" ", strip=True)
        if girl_text:
            continue
        nums = re.findall(r"\\d+", boy_text)
        if len(nums) >= 2:
            cells[boy_idx].clear()
            cells[boy_idx].append(nums[0])
            cells[girl_idx].clear()
            cells[girl_idx].append(nums[1])


def _strip_page_markers(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        _split_boy_girl_headers(table, soup)
        _split_table_row_br(table, soup)
        _split_boy_girl_cells(table)
    for tag in soup.find_all(class_="page-number"):
        tag.decompose()
    for tag in soup.find_all(class_="running-head"):
        tag.decompose()
    return soup.decode_contents()


def _enforce_boy_girl_split(html: str) -> str:
    if not html:
        return ""
    html = html.replace("&nbsp;", " ")
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        _split_boy_girl_cells(table)
    cleaned = soup.decode_contents()
    cleaned = re.sub(
        r"<td>\\s*(\\d+)\\s+(\\d+)\\s*</td>\\s*<td>\\s*</td>",
        r"<td>\\1</td><td>\\2</td>",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def _resolve_default_outdir(input_path: Path, module_id: str) -> Path:
    cur = input_path.parent
    for parent in [cur] + list(cur.parents):
        if (parent / "pipeline_state.json").exists():
            return parent / f"{module_id}"
    return input_path.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Onward-specific table re-OCR for genealogy pages.")
    parser.add_argument("--pages", help="Input pages_html.jsonl")
    parser.add_argument("--inputs", nargs="*", help="Driver-provided inputs")
    parser.add_argument("--outdir", help="Output directory")
    parser.add_argument("--out", default="pages_html_onward_tables.jsonl")
    parser.add_argument("--report", default="table_rescue_onward_report.jsonl")
    parser.add_argument("--model", default="gpt-5.1")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-output-tokens", dest="max_output_tokens", type=int, default=4096)
    parser.add_argument("--max_output_tokens", dest="max_output_tokens", type=int, default=4096)
    parser.add_argument("--max-pages", dest="max_pages", type=int, default=200)
    parser.add_argument("--max_pages", dest="max_pages", type=int, default=200)
    parser.add_argument("--pages-list", dest="pages_list", help="Comma-separated page_numbers to force rescue")
    parser.add_argument("--header-threshold", dest="header_threshold", type=float, default=0.8)
    parser.add_argument("--fail-on-unresolved", dest="fail_on_unresolved", action="store_true", default=False)
    parser.add_argument("--no-fail-on-unresolved", dest="fail_on_unresolved", action="store_false")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    parser.add_argument("--progress-every", type=int, default=None,
                        help="Log progress every N pages (default: 1 if <=50 pages else 10)")
    parser.add_argument("--timeout-seconds", type=float, default=120.0,
                        help="Per-page OCR request timeout (seconds)")
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
        args.outdir = str(_resolve_default_outdir(input_path, "table_rescue_onward_tables_v1"))
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
            report_path = (Path.cwd() / args.report).resolve()
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
        message="Onward table rescue started",
        artifact=str(out_path),
        module_id="table_rescue_onward_tables_v1",
        schema_version="page_html_v1",
    )

    explicit_pages: List[int] = []
    if args.pages_list:
        explicit_pages = [int(p.strip()) for p in args.pages_list.split(",") if p.strip()]

    prompt = build_system_prompt(PROMPT_HINTS)

    candidates: List[int] = []
    for row in rows:
        pn = int(row.get("page_number") or row.get("page") or 0)
        html = row.get("html") or row.get("raw_html") or ""
        if explicit_pages:
            if pn in explicit_pages:
                candidates.append(pn)
            continue
        if _table_has_headers(html, args.header_threshold):
            candidates.append(pn)

    candidates = list(dict.fromkeys(candidates))
    candidates = candidates[: args.max_pages]

    report_rows: List[Dict[str, Any]] = []
    unresolved: List[int] = []
    log_every = args.progress_every
    if not log_every or log_every <= 0:
        log_every = 1 if total <= 50 else 10

    for idx, row in enumerate(rows, start=1):
        pn = int(row.get("page_number") or row.get("page") or 0)
        html = row.get("html") or row.get("raw_html") or ""
        row["module_id"] = "table_rescue_onward_tables_v1"

        should_rescue = pn in candidates
        if not should_rescue:
            report_rows.append({"page_number": pn, "rescued": False, "reason": "not_selected"})
            continue

        if args.dry_run:
            report_rows.append({"page_number": pn, "rescued": False, "reason": "dry_run"})
            continue

        image_path = row.get("image")
        if not image_path or not os.path.exists(image_path):
            report_rows.append({"page_number": pn, "rescued": False, "reason": "missing_image"})
            unresolved.append(pn)
            continue

        logger.log(
            "adapter",
            "running",
            current=idx,
            total=total,
            message=f"Onward table rescue page {pn} ({idx}/{total})",
            artifact=str(out_path),
            module_id="table_rescue_onward_tables_v1",
            schema_version="page_html_v1",
        )

        image_data = _encode_image(image_path)
        try:
            raw, usage, request_id = _call_ocr(
                args.model,
                prompt,
                image_data,
                args.temperature,
                args.max_output_tokens,
                args.timeout_seconds,
            )
        except Exception as exc:
            report_rows.append({
                "page_number": pn,
                "rescued": False,
                "reason": "ocr_error",
                "error": str(exc),
            })
            unresolved.append(pn)
            continue
        raw = _extract_code_fence(raw)
        cleaned_raw, meta, meta_tag, meta_warning = _extract_ocr_metadata(raw)
        cleaned = sanitize_html(cleaned_raw)
        cleaned = _strip_page_markers(cleaned)
        cleaned = _enforce_boy_girl_split(cleaned)
        cleaned = re.sub(
            r"<td>\s*(\d+)\s+(\d+)\s*</td>\s*<td>\s*</td>",
            r"<td>\1</td><td>\2</td>",
            cleaned,
            flags=re.IGNORECASE,
        )

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

        # If headers are still missing after re-OCR, mark unresolved.
        if not _table_has_headers(cleaned, args.header_threshold):
            unresolved.append(pn)

        report_rows.append({
            "page_number": pn,
            "rescued": True,
            "model": args.model,
            "request_id": request_id,
            "usage": usage,
        })

        if idx % log_every == 0:
            logger.log(
                "adapter",
                "running",
                current=idx,
                total=total,
                message=f"Onward table rescue progress {idx}/{total}",
                artifact=str(out_path),
                module_id="table_rescue_onward_tables_v1",
                schema_version="page_html_v1",
            )

    save_jsonl(str(out_path), rows)
    if report_rows:
        save_jsonl(str(report_path), report_rows)

    logger.log(
        "table_rescue",
        "done",
        current=total,
        total=total,
        message=f"Onward table rescue complete: attempted={len(candidates)}, unresolved={len(unresolved)}",
        artifact=str(out_path),
        module_id="table_rescue_onward_tables_v1",
        schema_version="page_html_v1",
        extra={"summary_metrics": {"tables_attempted_count": len(candidates), "tables_unresolved_count": len(unresolved)}},
    )

    if unresolved and args.fail_on_unresolved:
        raise SystemExit(f"Unresolved table headers after Onward rescue: {len(unresolved)} pages")


if __name__ == "__main__":
    main()
