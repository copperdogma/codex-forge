#!/usr/bin/env python3
"""
Onward-specific table re-OCR for genealogy pages.
Re-OCRs any page containing a table with NAME/BORN/MARRIED/SPOUSE/BOY/GIRL/DIED headers,
then strips page-number/running-head tags from the resulting HTML while preserving
printed_page_number fields already extracted.
"""
import argparse
import base64
import os
import re
from copy import deepcopy
from dataclasses import asdict, dataclass
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
- If adjacent genealogy blocks use the same columns and form one continuous hierarchy, keep them in one table.
- Use internal heading rows for subgroup labels instead of starting a new table unless the table identity or columns clearly change.
- Use separate columns for BOY and GIRL. Do not merge them.
- CRITICAL: One visual line in the source must map to one <tr> row in the table.
- Do not use <br> inside table cells; use additional rows instead.
- Preserve column alignment from the original page.
- If current extracted HTML/text is provided, use it only as a clue for exact wording and row content. Trust the image for final structure.
- Keep running heads and page numbers using <p class=\"running-head\"> and <p class=\"page-number\">.
""".strip()

SUMMARY_LABELS = ("TOTAL DESCENDANTS", "LIVING", "DECEASED")
MONTH_RE = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\b", re.IGNORECASE)
FAMILY_HEADING_RE = re.compile(r"\b[A-Z][A-Z'’\-]+(?:\s+[A-Z][A-Z'’\-]+)*\s+FAMILY\b")
GENERATION_CONTEXT_RE = re.compile(r"\b(?:great\s+grandchildren|grandchildren|children)\b", re.IGNORECASE)
SLASH_COUNT_RE = re.compile(r"\b\d+\s*/\s*\d+\b")
COMBINED_BOY_GIRL_RE = re.compile(r"\bBOY\s*/?\s*GIRL\b", re.IGNORECASE)
GENEALOGY_HEADER_TOKEN_SETS = {
    tuple(EXPECTED_HEADERS),
    ("name", "born", "married", "spouse", "boygirl", "died"),
}


@dataclass
class RescueQuality:
    table_count: int
    header_table_count: int
    row_count: int
    family_heading_count: int
    inline_family_heading_count: int
    summary_count: int
    outside_table_data_lines: int
    combined_boy_girl_headers: int
    slash_count_cells: int
    score: int


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _model_to_dict(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return obj


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "jpeg"
    return f"data:image/{ext};base64,{b64}"


def _supports_temperature(model: str) -> bool:
    return not (model or "").casefold().startswith("gpt-5")


def _call_ocr(model: str, prompt: str, image_data: str, temperature: float, max_tokens: int,
              timeout_seconds: Optional[float], user_text: Optional[str] = None) -> Tuple[str, Optional[Any], Optional[str]]:
    if OpenAI is None:  # pragma: no cover
        raise RuntimeError("openai package required") from _OPENAI_IMPORT_ERROR
    client = OpenAI(timeout=timeout_seconds) if timeout_seconds else OpenAI()
    raw = ""
    usage = None
    request_id = None
    request_kwargs: Dict[str, Any] = {
        "model": model,
    }
    if _supports_temperature(model):
        request_kwargs["temperature"] = temperature
    user_text = (user_text or "Return only HTML.").strip()
    if hasattr(client, "responses"):
        resp = client.responses.create(
            **request_kwargs,
            max_output_tokens=max_tokens,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": prompt}]},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_text},
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
            **request_kwargs,
            max_completion_tokens=max_tokens,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": image_data}},
                    ],
                },
            ],
        )
        raw = resp.choices[0].message.content or ""
    return raw, usage, request_id


def _normalize_token(text: str) -> str:
    return re.sub(r"[^a-z]", "", (text or "").lower())


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("’", "'").strip())


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


def _count_header_tables(soup: BeautifulSoup, threshold: float) -> int:
    count = 0
    for table in soup.find_all("table"):
        if _table_has_headers(str(table), threshold):
            count += 1
    return count


def _extract_family_labels(text: str) -> List[str]:
    normalized = _normalize_text(text).upper()
    return list(dict.fromkeys(FAMILY_HEADING_RE.findall(normalized)))


def _row_family_heading_text(row: Any) -> Optional[str]:
    cells = row.find_all(["th", "td"], recursive=False)
    if len(cells) != 1:
        return None
    raw_text = re.sub(r"\s+", " ", cells[0].get_text(" ", strip=True)).strip()
    if not raw_text:
        return None
    labels = _extract_family_labels(raw_text)
    if len(labels) != 1:
        return None
    if labels[0] != _normalize_text(raw_text).upper():
        return None
    return raw_text


def _row_single_cell_text(row: Any) -> Optional[str]:
    cells = row.find_all(["th", "td"], recursive=False)
    if len(cells) != 1:
        return None
    text = re.sub(r"\s+", " ", cells[0].get_text(" ", strip=True)).strip()
    return text or None


def _is_generation_context_text(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized or len(normalized) > 120:
        return False
    if _extract_family_labels(normalized):
        return False
    upper = normalized.upper()
    if any(label in upper for label in SUMMARY_LABELS):
        return False
    return bool(GENERATION_CONTEXT_RE.search(normalized))


def _table_header_tokens(table: Any) -> List[str]:
    header_row = None
    thead = table.find("thead", recursive=False)
    if thead is not None:
        header_row = thead.find("tr", recursive=False)
    if header_row is None:
        header_row = table.find("tr", recursive=False)
    if header_row is None:
        return []
    return [
        _normalize_token(cell.get_text(" ", strip=True))
        for cell in header_row.find_all(["th", "td"], recursive=False)
    ]


def _row_header_tokens(row: Any) -> List[str]:
    return [
        _normalize_token(cell.get_text(" ", strip=True))
        for cell in row.find_all(["th", "td"], recursive=False)
    ]


def _is_expected_genealogy_table(table: Any) -> bool:
    return _table_header_tokens(table) == EXPECTED_HEADERS


def _is_genealogy_table_header(table: Any) -> bool:
    tokens = tuple(_table_header_tokens(table))
    return tokens in {
        tuple(EXPECTED_HEADERS),
        ("name", "born", "married", "spouse", "boygirl", "died"),
    }


def _table_has_subgroup_rows(table: Any) -> bool:
    return bool(table.find("tr", class_="genealogy-subgroup-heading"))


def _table_column_count(table: Any) -> int:
    counts = [len(_table_header_tokens(table))]
    tbody = table.find("tbody", recursive=False)
    rows = tbody.find_all("tr", recursive=False) if tbody is not None else table.find_all("tr", recursive=False)
    for row in rows:
        cells = row.find_all(["th", "td"], recursive=False)
        if cells:
            counts.append(len(cells))
    return max(counts) if counts else len(EXPECTED_HEADERS)


def _is_compatible_genealogy_run_table(table: Any, expected_cols: int) -> bool:
    if _is_genealogy_table_header(table):
        return True
    if table.find("thead", recursive=False) is not None:
        return False

    tbody = table.find("tbody", recursive=False)
    rows = tbody.find_all("tr", recursive=False) if tbody is not None else table.find_all("tr", recursive=False)
    if not rows:
        return False

    saw_cells = False
    for row in rows:
        cells = row.find_all(["th", "td"], recursive=False)
        if not cells:
            continue
        saw_cells = True
        if len(cells) > expected_cols:
            return False
    return saw_cells


def _significant_next_sibling(node: Any) -> Any:
    sibling = node.next_sibling
    while sibling is not None:
        if getattr(sibling, "name", None) is not None:
            return sibling
        if str(sibling).strip():
            return sibling
        sibling = sibling.next_sibling
    return None


def _significant_previous_sibling(node: Any) -> Any:
    sibling = node.previous_sibling
    while sibling is not None:
        if getattr(sibling, "name", None) is not None:
            return sibling
        if str(sibling).strip():
            return sibling
        sibling = sibling.previous_sibling
    return None


def _heading_lines_from_tag(tag: Any) -> List[str]:
    if tag is None:
        return []
    return [
        line.strip()
        for line in tag.get_text("\n", strip=True).split("\n")
        if line.strip()
    ]


def _heading_has_generation_context(tag: Any) -> bool:
    return any(_is_generation_context_text(line) for line in _heading_lines_from_tag(tag))


def _is_outside_table_data_line(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized or len(normalized) > 140:
        return False
    upper = normalized.upper()
    if _extract_family_labels(normalized):
        return False
    if any(label in upper for label in SUMMARY_LABELS):
        return False
    if not (MONTH_RE.search(normalized) or re.search(r"\b\d{1,4}\b", normalized)):
        return False
    return len(normalized.split()) >= 2


def _page_rescue_quality(html: str, threshold: float) -> RescueQuality:
    soup = BeautifulSoup(html or "", "html.parser")
    table_count = len(soup.find_all("table"))
    header_table_count = _count_header_tables(soup, threshold)
    row_count = 0
    family_labels = set()
    inline_family_heading_count = 0
    summary_labels = set()
    outside_table_data_lines = 0
    combined_boy_girl_headers = 0
    slash_count_cells = 0

    for tag in soup.find_all(["p", "h1", "h2", "h3", "th", "td", "li"]):
        text = _normalize_text(tag.get_text(" ", strip=True))
        if not text:
            continue
        family_labels.update(_extract_family_labels(text))
        upper = text.upper()
        for label in SUMMARY_LABELS:
            if label in upper:
                summary_labels.add(label)
        if tag.name in {"th", "td"}:
            if SLASH_COUNT_RE.search(text):
                slash_count_cells += len(SLASH_COUNT_RE.findall(text))
            if tag.name == "th" and COMBINED_BOY_GIRL_RE.search(text):
                combined_boy_girl_headers += 1
        if tag.name in {"p", "h1", "h2", "h3", "li"} and tag.find_parent("table") is None:
            if _is_outside_table_data_line(text):
                outside_table_data_lines += 1

    for table in soup.find_all("table"):
        row_count += len(table.find_all("tr"))
    for table in soup.find_all("table"):
        body_rows = table.find("tbody").find_all("tr", recursive=False) if table.find("tbody") else table.find_all("tr")[1:]
        heading_sequence_has_context = False
        pending_family_rows = 0
        for row in body_rows:
            text = _row_single_cell_text(row)
            if not text:
                inline_family_heading_count += pending_family_rows
                pending_family_rows = 0
                heading_sequence_has_context = False
                continue
            if "genealogy-subgroup-heading" in (row.get("class") or []):
                pending_family_rows = 0
                if _is_generation_context_text(text):
                    heading_sequence_has_context = True
                continue
            if _is_generation_context_text(text):
                heading_sequence_has_context = True
                continue
            if _row_family_heading_text(row):
                if heading_sequence_has_context:
                    continue
                pending_family_rows += 1
                continue
            inline_family_heading_count += pending_family_rows
            pending_family_rows = 0
            heading_sequence_has_context = False
        inline_family_heading_count += pending_family_rows

    score = (
        header_table_count * 120
        + row_count * 10
        + len(family_labels) * 15
        + len(summary_labels) * 25
        - outside_table_data_lines * 18
        - inline_family_heading_count * 45
        - combined_boy_girl_headers * 40
        - slash_count_cells * 12
    )
    return RescueQuality(
        table_count=table_count,
        header_table_count=header_table_count,
        row_count=row_count,
        family_heading_count=len(family_labels),
        inline_family_heading_count=inline_family_heading_count,
        summary_count=len(summary_labels),
        outside_table_data_lines=outside_table_data_lines,
        combined_boy_girl_headers=combined_boy_girl_headers,
        slash_count_cells=slash_count_cells,
        score=score,
    )


def _should_accept_rescue(existing_html: str, candidate_html: str, threshold: float,
                          min_score_gain: int) -> Tuple[bool, str, RescueQuality, RescueQuality]:
    existing_quality = _page_rescue_quality(existing_html, threshold)
    candidate_quality = _page_rescue_quality(candidate_html, threshold)

    if candidate_quality.header_table_count == 0 and existing_quality.header_table_count > 0:
        return False, "candidate_lost_header_table", existing_quality, candidate_quality
    if existing_quality.header_table_count == 0 and candidate_quality.header_table_count > 0:
        return True, "candidate_recovered_header_table", existing_quality, candidate_quality
    if candidate_quality.score >= existing_quality.score + min_score_gain:
        return True, "candidate_score_improved", existing_quality, candidate_quality
    return False, "candidate_score_not_improved", existing_quality, candidate_quality


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
            body_rows = []
            if table.find("tbody"):
                body_rows = table.find("tbody").find_all("tr")
            else:
                body_rows = table.find_all("tr")[1:]
            already_split_body = any(
                len(row.find_all(["td", "th"])) >= len(header_cells) + 1
                for row in body_rows
            )

            boy = soup.new_tag("th")
            boy.string = "BOY"
            girl = soup.new_tag("th")
            girl.string = "GIRL"
            cell.replace_with(boy)
            boy.insert_after(girl)

            # Split data cells in the same column.
            if already_split_body:
                return
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


def _pad_expected_genealogy_columns(table: BeautifulSoup, soup: BeautifulSoup) -> None:
    header_row = None
    thead = table.find("thead")
    if thead:
        header_row = thead.find("tr")
    if header_row is None:
        header_row = table.find("tr")
    if header_row is None:
        return

    header_cells = header_row.find_all(["th", "td"], recursive=False)
    header_tokens = [_normalize_token(cell.get_text(" ", strip=True)) for cell in header_cells]
    if not header_tokens or len(header_tokens) >= len(EXPECTED_HEADERS):
        return
    if header_tokens != EXPECTED_HEADERS[: len(header_tokens)]:
        return

    for token in EXPECTED_HEADERS[len(header_tokens):]:
        cell = soup.new_tag("th")
        cell.string = token.upper()
        header_row.append(cell)

    body_rows = table.find("tbody").find_all("tr", recursive=False) if table.find("tbody") else table.find_all("tr")[1:]
    for row in body_rows:
        if _row_family_heading_text(row):
            continue
        cells = row.find_all(["td", "th"], recursive=False)
        while len(cells) < len(EXPECTED_HEADERS):
            new_cell = soup.new_tag("td")
            row.append(new_cell)
            cells.append(new_cell)


def _table_contextual_heading_lines(table: Any) -> List[str]:
    thead = table.find("thead", recursive=False)
    if thead is None:
        return []
    rows = thead.find_all("tr", recursive=False)
    if not any(tuple(_row_header_tokens(row)) in GENEALOGY_HEADER_TOKEN_SETS for row in rows):
        return []

    lines: List[str] = []
    for row in rows:
        tokens = _row_header_tokens(row)
        if tuple(tokens) in GENEALOGY_HEADER_TOKEN_SETS:
            break
        row_lines = _heading_lines_from_tag(row)
        if not row_lines:
            continue
        lines.extend(row_lines)
    return lines


def _build_external_heading_nodes(heading_lines: List[str], soup: BeautifulSoup,
                                  family_tag: str = "h2") -> List[Any]:
    if not heading_lines:
        return []

    family_line = heading_lines[-1] if _extract_family_labels(heading_lines[-1]) else None
    context_lines = heading_lines[:-1] if family_line else heading_lines
    nodes: List[Any] = []

    for line in context_lines:
        p = soup.new_tag("p")
        p["class"] = "genealogy-context"
        p.string = line
        nodes.append(p)

    if family_line:
        heading = soup.new_tag(family_tag)
        heading.string = family_line
        nodes.append(heading)

    return nodes


def _insert_heading_nodes_before(anchor: Any, heading_lines: List[str], soup: BeautifulSoup,
                                 family_tag: str = "h2") -> Any:
    last_node = None
    for node in _build_external_heading_nodes(heading_lines, soup, family_tag):
        anchor.insert_before(node)
        last_node = node
    return last_node


def _promote_contextual_thead_rows(table: Any, soup: BeautifulSoup) -> None:
    heading_lines = _table_contextual_heading_lines(table)
    if not heading_lines:
        return

    _insert_heading_nodes_before(table, heading_lines, soup)

    thead = table.find("thead", recursive=False)
    if thead is None:
        return
    for row in list(thead.find_all("tr", recursive=False)):
        tokens = _row_header_tokens(row)
        if tuple(tokens) in GENEALOGY_HEADER_TOKEN_SETS:
            break
        row.decompose()


def _clone_table_with_rows(table: Any, rows: List[Any], soup: BeautifulSoup) -> Any:
    new_table = soup.new_tag("table")
    new_table.attrs.update(deepcopy(table.attrs))

    caption = table.find("caption", recursive=False)
    if caption is not None:
        new_table.append(deepcopy(caption))
    colgroup = table.find("colgroup", recursive=False)
    if colgroup is not None:
        new_table.append(deepcopy(colgroup))

    thead = table.find("thead", recursive=False)
    if thead is not None:
        header_rows = []
        for row in thead.find_all("tr", recursive=False):
            tokens = _row_header_tokens(row)
            if tuple(tokens) in GENEALOGY_HEADER_TOKEN_SETS:
                header_rows.append(deepcopy(row))
        if header_rows:
            new_thead = soup.new_tag("thead")
            for row in header_rows:
                new_thead.append(row)
            new_table.append(new_thead)
        else:
            new_table.append(deepcopy(thead))
    else:
        first_row = table.find("tr", recursive=False)
        if first_row is not None:
            new_table.append(deepcopy(first_row))

    tbody = soup.new_tag("tbody")
    for row in rows:
        tbody.append(deepcopy(row))
    new_table.append(tbody)
    return new_table


def _split_inline_family_tables(soup: BeautifulSoup) -> None:
    for table in list(soup.find_all("table")):
        tbody = table.find("tbody", recursive=False)
        if tbody is None:
            continue

        body_rows = list(tbody.find_all("tr", recursive=False))
        if not body_rows:
            continue

        original_rows: List[Any] = []
        section_heading: Optional[str] = None
        section_rows: List[Any] = []
        sections: List[Tuple[str, List[Any]]] = []

        for row in body_rows:
            family_heading = _row_family_heading_text(row)
            if family_heading:
                if section_heading is not None and section_rows:
                    sections.append((section_heading, section_rows))
                section_heading = family_heading
                section_rows = []
                continue

            if section_heading is None:
                original_rows.append(row)
            else:
                section_rows.append(row)

        if section_heading is not None and section_rows:
            sections.append((section_heading, section_rows))

        # Only rewrite when the table already contains real rows before the split;
        # otherwise we risk replacing a legitimate family table wrapper.
        if not original_rows or not sections:
            continue

        initial_heading_lines = _table_contextual_heading_lines(table)

        first_table = _clone_table_with_rows(table, original_rows, soup)
        table.insert_before(first_table)
        anchor = first_table
        _insert_heading_nodes_before(first_table, initial_heading_lines, soup)

        for heading, rows in sections:
            heading_tag = soup.new_tag("h2")
            heading_tag.string = heading
            anchor.insert_after(heading_tag)
            anchor = heading_tag

            split_table = _clone_table_with_rows(table, rows, soup)
            anchor.insert_after(split_table)
            anchor = split_table

        table.decompose()


def _split_external_multiline_headings(soup: BeautifulSoup) -> None:
    for tag in list(soup.find_all(["h1", "h2", "h3"])):
        heading_lines = _heading_lines_from_tag(tag)
        if len(heading_lines) <= 1:
            continue
        if tag.get("data-context-moved") != "true":
            continue
        if not (_extract_family_labels(heading_lines[-1]) or all(_is_generation_context_text(line) for line in heading_lines)):
            continue

        family_tag = "h2" if _extract_family_labels(heading_lines[-1]) else tag.name
        nodes = _build_external_heading_nodes(heading_lines, soup, family_tag)
        if not nodes:
            continue
        for node in nodes[::-1]:
            tag.insert_after(node)
        tag.decompose()


def _merge_trailing_context_rows_into_next_heading(soup: BeautifulSoup) -> None:
    for table in list(soup.find_all("table")):
        tbody = table.find("tbody", recursive=False)
        if tbody is None:
            continue

        rows = list(tbody.find_all("tr", recursive=False))
        if not rows:
            continue

        trailing_rows: List[Any] = []
        trailing_lines: List[str] = []
        for row in reversed(rows):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) != 1:
                break
            text = re.sub(r"\s+", " ", cells[0].get_text(" ", strip=True)).strip()
            if not _is_generation_context_text(text):
                break
            trailing_rows.append(row)
            trailing_lines.append(text)

        if not trailing_rows:
            continue

        next_heading = table.next_sibling
        while next_heading is not None and getattr(next_heading, "name", None) is None:
            next_heading = next_heading.next_sibling
        if next_heading is None or next_heading.name not in {"h1", "h2", "h3"}:
            continue

        existing_lines = [
            line.strip()
            for line in next_heading.get_text("\n", strip=True).split("\n")
            if line.strip()
        ]
        merged_lines: List[str] = []
        seen = set()
        for line in list(reversed(trailing_lines)) + existing_lines:
            key = _normalize_text(line).lower()
            if key and key not in seen:
                seen.add(key)
                merged_lines.append(line)

        next_heading.clear()
        for idx, line in enumerate(merged_lines):
            if idx:
                next_heading.append(soup.new_tag("br"))
            next_heading.append(line)
        next_heading["data-context-moved"] = "true"

        for row in trailing_rows:
            row.decompose()


def _build_subgroup_heading_row(line: str, colspan: int, soup: BeautifulSoup) -> Any:
    row = soup.new_tag("tr")
    row["class"] = "genealogy-subgroup-heading"
    cell = soup.new_tag("th", colspan=str(colspan))
    cell.string = line
    row.append(cell)
    return row


def _clone_run_row(row: Any, col_count: int, soup: BeautifulSoup) -> Any:
    cloned = deepcopy(row)
    if "genealogy-subgroup-heading" in (cloned.get("class") or []):
        cells = cloned.find_all(["th", "td"], recursive=False)
        if len(cells) == 1:
            cells[0]["colspan"] = str(col_count)
        return cloned

    cells = cloned.find_all(["td", "th"], recursive=False)
    while len(cells) < col_count:
        new_cell = soup.new_tag("td")
        cloned.append(new_cell)
        cells.append(new_cell)
    return cloned


def _prepend_heading_rows(base_table: Any, heading_lines: List[str], soup: BeautifulSoup) -> None:
    if not heading_lines:
        return

    base_tbody = base_table.find("tbody", recursive=False)
    if base_tbody is None:
        base_tbody = soup.new_tag("tbody")
        base_table.append(base_tbody)

    colspan = _table_column_count(base_table)
    first_row = base_tbody.find("tr", recursive=False)
    for line in reversed(heading_lines):
        row = _build_subgroup_heading_row(line, colspan, soup)
        if first_row is not None:
            first_row.insert_before(row)
        else:
            base_tbody.append(row)


def _append_heading_rows_and_data(base_table: Any, heading_lines: List[str], source_table: Any, soup: BeautifulSoup) -> None:
    base_tbody = base_table.find("tbody", recursive=False)
    if base_tbody is None:
        base_tbody = soup.new_tag("tbody")
        base_table.append(base_tbody)

    colspan = _table_column_count(base_table)
    for line in heading_lines:
        base_tbody.append(_build_subgroup_heading_row(line, colspan, soup))

    source_tbody = source_table.find("tbody", recursive=False)
    if source_tbody is None:
        return
    for row in list(source_tbody.find_all("tr", recursive=False)):
        base_tbody.append(_clone_run_row(row, colspan, soup))


def _merge_contextual_genealogy_tables(soup: BeautifulSoup) -> None:
    for table in list(soup.find_all("table")):
        if not _is_expected_genealogy_table(table):
            continue

        while True:
            heading_tag = None
            next_node = _significant_next_sibling(table)
            if next_node is not None and getattr(next_node, "name", None) in {"h1", "h2", "h3"}:
                heading_tag = next_node
                next_node = _significant_next_sibling(next_node)

            if getattr(next_node, "name", None) != "table" or not _is_expected_genealogy_table(next_node):
                break

            if heading_tag is None or heading_tag.get("data-context-moved") != "true":
                break
            heading_lines = _heading_lines_from_tag(heading_tag)
            if not heading_lines:
                break

            _append_heading_rows_and_data(table, heading_lines, next_node, soup)
            if heading_tag is not None:
                heading_tag.decompose()
            next_node.decompose()


def _merge_genealogy_table_runs(soup: BeautifulSoup) -> None:
    for base_table in list(soup.find_all("table")):
        if base_table.parent is None or not _is_genealogy_table_header(base_table):
            continue

        run_pairs: List[Tuple[Any, Any]] = []
        cursor = base_table
        expected_cols = _table_column_count(base_table)
        while True:
            heading_tag = _significant_next_sibling(cursor)
            if getattr(heading_tag, "name", None) not in {"h1", "h2", "h3"}:
                break
            next_table = _significant_next_sibling(heading_tag)
            if getattr(next_table, "name", None) != "table":
                break
            if not _is_compatible_genealogy_run_table(next_table, expected_cols):
                break
            run_pairs.append((heading_tag, next_table))
            cursor = next_table

        if not run_pairs:
            continue

        has_subgroups = _table_has_subgroup_rows(base_table) or any(
            _table_has_subgroup_rows(table) for _, table in run_pairs
        )
        contextual_heading_count = sum(
            1 for heading_tag, _ in run_pairs if _heading_has_generation_context(heading_tag)
        )
        headerless_table_count = sum(
            1 for _, table in run_pairs if table.find("thead", recursive=False) is None
        )

        should_merge = has_subgroups or (
            contextual_heading_count >= 2 and headerless_table_count >= 2
        )
        if not should_merge:
            continue

        if not has_subgroups and contextual_heading_count >= 2 and headerless_table_count >= 2:
            base_heading = _significant_previous_sibling(base_table)
            if getattr(base_heading, "name", None) in {"h2", "h3"}:
                _prepend_heading_rows(base_table, _heading_lines_from_tag(base_heading), soup)
                base_heading.decompose()

        for heading_tag, next_table in run_pairs:
            _append_heading_rows_and_data(
                base_table,
                _heading_lines_from_tag(heading_tag),
                next_table,
                soup,
            )
            heading_tag.decompose()
            next_table.decompose()


def _strip_page_markers(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        _split_boy_girl_headers(table, soup)
        _split_table_row_br(table, soup)
        _split_boy_girl_cells(table)
    for table in soup.find_all("table"):
        _promote_contextual_thead_rows(table, soup)
    _split_inline_family_tables(soup)
    _merge_trailing_context_rows_into_next_heading(soup)
    for table in soup.find_all("table"):
        _pad_expected_genealogy_columns(table, soup)
    _merge_contextual_genealogy_tables(soup)
    _merge_genealogy_table_runs(soup)
    _split_external_multiline_headings(soup)
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


def _normalize_rescue_html(html: str) -> str:
    cleaned = sanitize_html(html or "")
    cleaned = _strip_page_markers(cleaned)
    cleaned = _enforce_boy_girl_split(cleaned)
    cleaned = re.sub(
        r"<td>\s*(\d+)\s+(\d+)\s*</td>\s*<td>\s*</td>",
        r"<td>\1</td><td>\2</td>",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def _should_apply_normalized_existing(existing_quality: RescueQuality,
                                      normalized_quality: RescueQuality) -> bool:
    collapse_to_single_table = (
        existing_quality.table_count > 1
        and normalized_quality.table_count == 1
        and normalized_quality.header_table_count >= existing_quality.header_table_count
        and normalized_quality.inline_family_heading_count == 0
    )
    split_inline_families_into_tables = (
        existing_quality.inline_family_heading_count > 0
        and normalized_quality.inline_family_heading_count == 0
        and normalized_quality.table_count > existing_quality.table_count
        and normalized_quality.header_table_count > existing_quality.header_table_count
    )
    return collapse_to_single_table or split_inline_families_into_tables


def _build_prompt(rescue_hints: Optional[str]) -> str:
    prompt = build_system_prompt(PROMPT_HINTS)
    if rescue_hints:
        prompt += "\n\nRecipe hints:\n" + rescue_hints.strip() + "\n"
    return prompt


def _build_user_text(current_html: str, max_context_chars: int) -> str:
    prompt = "Return only HTML."
    current_html = (current_html or "").strip()
    if not current_html or max_context_chars <= 0:
        return prompt
    if len(current_html) > max_context_chars:
        current_html = current_html[:max_context_chars].rstrip() + "\n<!-- truncated -->"
    return (
        "Return only HTML.\n"
        "Current extracted HTML/text is provided below as a clue for exact wording and row content. "
        "It may be structurally wrong. Trust the image for final structure, but use this context "
        "to recover missing family headings, child rows, and summary lines when visible.\n"
        "<current-html>\n"
        f"{current_html}\n"
        "</current-html>"
    )


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
    parser.add_argument("--rescue-hints", dest="rescue_hints")
    parser.add_argument("--rescue_hints", dest="rescue_hints")
    parser.add_argument("--max-context-chars", dest="max_context_chars", type=int, default=6000)
    parser.add_argument("--max_context_chars", dest="max_context_chars", type=int, default=6000)
    parser.add_argument("--min-score-gain", dest="min_score_gain", type=int, default=15)
    parser.add_argument("--min_score_gain", dest="min_score_gain", type=int, default=15)
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

    prompt = _build_prompt(args.rescue_hints)

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

        normalized_existing = _normalize_rescue_html(html)
        normalized_existing_accepted, normalized_reason, input_quality, normalized_quality = _should_accept_rescue(
            html,
            normalized_existing,
            args.header_threshold,
            args.min_score_gain,
        )
        normalized_existing_applied = normalized_existing_accepted and _should_apply_normalized_existing(
            input_quality,
            normalized_quality,
        )
        baseline_html = normalized_existing if normalized_existing_applied else html
        if normalized_existing_applied:
            row["html"] = normalized_existing

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

        if normalized_existing_applied:
            final_html = row.get("html") or row.get("raw_html") or ""
            if not _table_has_headers(final_html, args.header_threshold):
                unresolved.append(pn)
            report_rows.append({
                "page_number": pn,
                "rescued": True,
                "accepted": None,
                "decision_reason": "normalized_existing_applied_without_ocr",
                "model": None,
                "request_id": None,
                "usage": None,
                "normalized_existing_accepted": normalized_existing_accepted,
                "normalized_existing_applied": normalized_existing_applied,
                "normalized_existing_reason": normalized_reason,
                "input_quality": asdict(input_quality),
                "normalized_existing_quality": asdict(normalized_quality),
                "existing_quality": asdict(normalized_quality),
                "candidate_quality": None,
            })
            continue

        image_data = _encode_image(image_path)
        user_text = _build_user_text(baseline_html, args.max_context_chars)
        try:
            raw, usage, request_id = _call_ocr(
                args.model,
                prompt,
                image_data,
                args.temperature,
                args.max_output_tokens,
                args.timeout_seconds,
                user_text=user_text,
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
        cleaned = _normalize_rescue_html(cleaned_raw)

        accepted, decision_reason, existing_quality, candidate_quality = _should_accept_rescue(
            baseline_html,
            cleaned,
            args.header_threshold,
            args.min_score_gain,
        )
        if accepted:
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
        final_html = row.get("html") or row.get("raw_html") or ""
        if not _table_has_headers(final_html, args.header_threshold):
            unresolved.append(pn)

        report_rows.append({
            "page_number": pn,
            "rescued": True,
            "accepted": accepted,
            "decision_reason": decision_reason,
            "model": args.model,
            "request_id": request_id,
            "usage": _model_to_dict(usage),
            "normalized_existing_accepted": normalized_existing_accepted,
            "normalized_existing_applied": normalized_existing_applied,
            "normalized_existing_reason": normalized_reason,
            "input_quality": asdict(input_quality),
            "normalized_existing_quality": asdict(normalized_quality),
            "existing_quality": asdict(existing_quality),
            "candidate_quality": asdict(candidate_quality),
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
