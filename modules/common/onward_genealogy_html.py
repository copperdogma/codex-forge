"""
Shared HTML stitching helpers for the Onward scanned-genealogy seam.

This keeps the late chapter-build repair focused on chapter-local table
continuity while giving rerun/build one explicit owner for the shared HTML
normalization behavior.
"""

from copy import deepcopy
import re
from typing import Any, List, Optional

from bs4 import BeautifulSoup

try:
    from modules.adapter.table_rescue_onward_tables_v1.main import (
        _normalize_rescue_html as _normalize_genealogy_rescue_html,
    )
except Exception:  # pragma: no cover - optional adapter reuse
    _normalize_genealogy_rescue_html = None


_GENEALOGY_EXPECTED_HEADERS = ["name", "born", "married", "spouse", "boy", "girl", "died"]
_GENEALOGY_HEADER_TOKEN_SETS = {
    tuple(_GENEALOGY_EXPECTED_HEADERS),
    ("name", "born", "married", "spouse", "boygirl", "died"),
}
_GENEALOGY_FAMILY_HEADING_RE = re.compile(r"\b[A-Z][A-Z'’\-]+(?:\s+[A-Z][A-Z'’\-]+)*\s+FAMILY\b")
_GENEALOGY_GENERATION_CONTEXT_RE = re.compile(
    r"\b(?:great\s+grandchildren|grandchildren|children)\b",
    re.IGNORECASE,
)
_GENEALOGY_CONTEXT_LINE_RE = re.compile(
    r"(?:[A-Z][\w.\-]*\s+)*[A-Z][\w.\-]*['’](?:s)?\s+"
    r"(?:Great\s+Great\s+Grandchildren|Great\s+Grandchildren|Grandchildren|Children)\b"
)
_GENEALOGY_SUMMARY_LABELS = ("TOTAL DESCENDANTS", "LIVING", "DECEASED")


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _normalize_genealogy_token(text: str) -> str:
    return re.sub(r"[^a-z]", "", (text or "").lower())


def _genealogy_heading_lines(tag: Any) -> List[str]:
    if tag is None:
        return []
    return _genealogy_heading_lines_from_text(tag.get_text("\n", strip=True))


def _genealogy_heading_lines_from_text(text: str) -> List[str]:
    raw_lines = [
        line.strip()
        for line in (text or "").split("\n")
        if line.strip()
    ]
    lines: List[str] = []
    for line in raw_lines:
        lines.extend(_split_flattened_genealogy_heading_line(line))
    return lines


def _split_flattened_genealogy_heading_line(line: str) -> List[str]:
    normalized = _normalize_ws(line)
    if not normalized:
        return []

    family_line = None
    prefix = normalized
    family_matches = list(_GENEALOGY_FAMILY_HEADING_RE.finditer(normalized))
    if family_matches and family_matches[-1].end() == len(normalized):
        family_line = family_matches[-1].group(0).strip()
        prefix = normalized[:family_matches[-1].start()].strip()

    parts: List[str] = []
    if prefix:
        pos = 0
        for match in _GENEALOGY_CONTEXT_LINE_RE.finditer(prefix):
            if prefix[pos:match.start()].strip():
                parts = []
                break
            parts.append(match.group(0).strip())
            pos = match.end()
        if parts and prefix[pos:].strip():
            parts = []
    if family_line:
        parts.append(family_line)

    if parts and all(
        _extract_genealogy_family_labels(part) or _is_genealogy_generation_context(part)
        for part in parts
    ):
        return parts
    return [normalized]


def _extract_genealogy_family_labels(text: str) -> List[str]:
    normalized = _normalize_ws(text).replace("’", "'").upper()
    return list(dict.fromkeys(_GENEALOGY_FAMILY_HEADING_RE.findall(normalized)))


def _is_genealogy_generation_context(text: str) -> bool:
    normalized = _normalize_ws(text).replace("’", "'")
    if not normalized or len(normalized) > 120:
        return False
    if _extract_genealogy_family_labels(normalized):
        return False
    return bool(_GENEALOGY_GENERATION_CONTEXT_RE.search(normalized))


def _is_genealogy_heading_tag(tag: Any) -> bool:
    if getattr(tag, "name", None) not in {"h1", "h2", "h3", "p"}:
        return False
    lines = _genealogy_heading_lines(tag)
    if not lines:
        return False
    return all(
        _extract_genealogy_family_labels(line) or _is_genealogy_generation_context(line)
        for line in lines
    )


def _genealogy_table_header_tokens(table: Any) -> List[str]:
    thead = table.find("thead", recursive=False)
    header_row = thead.find("tr", recursive=False) if thead is not None else None
    if header_row is None:
        header_row = table.find("tr", recursive=False)
    if header_row is None:
        return []
    return [
        _normalize_genealogy_token(cell.get_text(" ", strip=True))
        for cell in header_row.find_all(["th", "td"], recursive=False)
    ]


def _is_genealogy_table_header(table: Any) -> bool:
    return tuple(_genealogy_table_header_tokens(table)) in _GENEALOGY_HEADER_TOKEN_SETS


def _genealogy_table_column_count(table: Any) -> int:
    counts = [len(_genealogy_table_header_tokens(table))]
    tbody = table.find("tbody", recursive=False)
    rows = tbody.find_all("tr", recursive=False) if tbody is not None else table.find_all("tr", recursive=False)
    for row in rows:
        cells = row.find_all(["th", "td"], recursive=False)
        if cells:
            counts.append(len(cells))
    return max(counts) if counts else len(_GENEALOGY_EXPECTED_HEADERS)


def _is_compatible_genealogy_table(table: Any, expected_cols: int) -> bool:
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


def _looks_like_genealogy_continuation_table(table: Any) -> bool:
    if _is_genealogy_table_header(table):
        return True

    tbody = table.find("tbody", recursive=False)
    rows = tbody.find_all("tr", recursive=False) if tbody is not None else table.find_all("tr", recursive=False)
    for row in rows:
        cells = row.find_all(["th", "td"], recursive=False)
        if not cells:
            continue
        texts = [_normalize_ws(cell.get_text(" ", strip=True)) for cell in cells]
        non_empty = [text for text in texts if text]
        if not non_empty:
            continue
        if len(cells) == 1:
            text = non_empty[0]
            if _extract_genealogy_family_labels(text) or _is_genealogy_generation_context(text):
                return True
            continue
        if any(label in non_empty[0].upper() for label in _GENEALOGY_SUMMARY_LABELS):
            continue
        return True
    return False


def _next_significant_sibling(node: Any) -> Any:
    sibling = node.next_sibling
    while sibling is not None:
        if getattr(sibling, "name", None) is not None:
            return sibling
        if str(sibling).strip():
            return sibling
        sibling = sibling.next_sibling
    return None


def _is_genealogy_name_list_paragraph(tag: Any) -> bool:
    if getattr(tag, "name", None) != "p" or tag.find_parent("table") is not None:
        return False
    if tag.find(["table", "img", "figure"]) is not None:
        return False

    lines = [
        line.strip()
        for line in tag.get_text("\n", strip=True).split("\n")
        if line.strip()
    ]
    if not lines or len(lines) > 8:
        return False

    for line in lines:
        normalized = _normalize_ws(line)
        if not normalized or any(ch.isdigit() for ch in normalized):
            return False
        if _extract_genealogy_family_labels(normalized) or _is_genealogy_generation_context(normalized):
            return False
        tokens = normalized.replace("’", "'").split()
        if len(tokens) > 3:
            return False
        if not all(re.fullmatch(r"[A-Za-z][A-Za-z'’.\-]*", token) for token in tokens):
            return False
    return True


def _convert_genealogy_name_list_paragraphs_to_tables(soup: BeautifulSoup) -> None:
    for heading in list(soup.find_all(["h1", "h2", "h3"])):
        heading_lines = _genealogy_heading_lines(heading)
        if not heading_lines or not _extract_genealogy_family_labels(heading_lines[-1]):
            continue

        paragraph = _next_significant_sibling(heading)
        if not _is_genealogy_name_list_paragraph(paragraph):
            continue

        follow = _next_significant_sibling(paragraph)
        if getattr(follow, "name", None) not in {"h1", "h2", "h3", "table"}:
            continue

        table = soup.new_tag("table")
        tbody = soup.new_tag("tbody")
        table.append(tbody)
        for line in [
            line.strip()
            for line in paragraph.get_text("\n", strip=True).split("\n")
            if line.strip()
        ]:
            row = soup.new_tag("tr")
            cell = soup.new_tag("td")
            cell.string = line
            row.append(cell)
            tbody.append(row)

        paragraph.replace_with(table)


def _row_genealogy_heading_lines(row: Any) -> List[str]:
    cells = row.find_all(["th", "td"], recursive=False)
    if not cells:
        return []

    non_empty_indices = [
        idx
        for idx, cell in enumerate(cells)
        if _normalize_ws(cell.get_text(" ", strip=True))
    ]
    if non_empty_indices != [0]:
        return []

    lines = _genealogy_heading_lines_from_text(cells[0].get_text("\n", strip=True))
    if not lines:
        return []
    if not all(
        _extract_genealogy_family_labels(line) or _is_genealogy_generation_context(line)
        for line in lines
    ):
        return []
    return lines


def _looks_like_death_value(text: str) -> bool:
    normalized = _normalize_ws(text)
    if not normalized:
        return False
    upper = normalized.upper()
    if upper == "DECEASED" or "MONTH" in upper or "YEAR" in upper:
        return True
    if re.search(r"\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)[A-Z.]*\b", upper):
        return True
    if re.fullmatch(r",?\s*\d{4}", normalized):
        return True
    return bool(re.search(r"\d{4}", normalized) and not re.fullmatch(r"\d+", normalized))


def _normalize_genealogy_body_rows(table: Any, soup: BeautifulSoup) -> None:
    tbody = table.find("tbody", recursive=False)
    rows = list(tbody.find_all("tr", recursive=False)) if tbody is not None else list(table.find_all("tr", recursive=False))
    if not rows:
        return

    col_count = _genealogy_table_column_count(table)
    header_tokens = _genealogy_table_header_tokens(table)
    canonical_seven_col = header_tokens[:7] == ["name", "born", "married", "spouse", "boy", "girl", "died"]

    for row in rows:
        if row.parent is None:
            continue

        heading_lines = _row_genealogy_heading_lines(row)
        if heading_lines:
            new_rows = [
                _build_genealogy_subgroup_row(line, col_count, soup)
                for line in heading_lines
            ]
            for new_row in new_rows[::-1]:
                row.insert_after(new_row)
            row.decompose()
            continue

        if "genealogy-subgroup-heading" in (row.get("class") or []):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) == 1:
                cells[0]["colspan"] = str(col_count)
            continue

        if not canonical_seven_col:
            continue

        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 7:
            continue

        boy_cell = cells[4]
        girl_cell = cells[5]
        died_cell = cells[6]
        boy_text = _normalize_ws(boy_cell.get_text(" ", strip=True))
        girl_text = _normalize_ws(girl_cell.get_text(" ", strip=True))
        died_text = _normalize_ws(died_cell.get_text(" ", strip=True))

        if boy_text and not girl_text and not died_text:
            nums = re.findall(r"\d+", boy_text)
            if len(nums) >= 2:
                boy_cell.clear()
                boy_cell.append(nums[0])
                girl_cell.clear()
                girl_cell.append(nums[1])
                girl_text = nums[1]
                died_text = ""

        if girl_text and not died_text and _looks_like_death_value(girl_text):
            girl_cell.clear()
            died_cell.clear()
            died_cell.append(girl_text)


def _build_genealogy_subgroup_row(line: str, colspan: int, soup: BeautifulSoup) -> Any:
    row = soup.new_tag("tr")
    row["class"] = "genealogy-subgroup-heading"
    cell = soup.new_tag("th", colspan=str(colspan))
    cell.string = line
    row.append(cell)
    return row


def _clone_genealogy_row(row: Any, col_count: int, soup: BeautifulSoup) -> Any:
    cloned = deepcopy(row)
    cells = cloned.find_all(["td", "th"], recursive=False)
    if "genealogy-subgroup-heading" in (cloned.get("class") or []):
        if len(cells) == 1:
            cells[0]["colspan"] = str(col_count)
        return cloned

    while len(cells) < col_count:
        cell = soup.new_tag("td")
        cloned.append(cell)
        cells.append(cell)
    return cloned


def _append_genealogy_heading_and_rows(base_table: Any, heading_tags: List[Any], source_table: Any,
                                       soup: BeautifulSoup) -> None:
    base_tbody = base_table.find("tbody", recursive=False)
    if base_tbody is None:
        base_tbody = soup.new_tag("tbody")
        base_table.append(base_tbody)

    col_count = _genealogy_table_column_count(base_table)
    for tag in heading_tags:
        for line in _genealogy_heading_lines(tag):
            base_tbody.append(_build_genealogy_subgroup_row(line, col_count, soup))

    source_tbody = source_table.find("tbody", recursive=False)
    rows = source_tbody.find_all("tr", recursive=False) if source_tbody is not None else source_table.find_all("tr", recursive=False)
    if source_table.find("thead", recursive=False) is None and _is_genealogy_table_header(source_table) and rows:
        rows = rows[1:]
    for row in rows:
        base_tbody.append(_clone_genealogy_row(row, col_count, soup))


def _preserve_figure_and_image_attrs(original_html: str, merged_html: str) -> str:
    original_soup = BeautifulSoup(original_html or "", "html.parser")
    merged_soup = BeautifulSoup(merged_html or "", "html.parser")

    original_imgs = original_soup.find_all("img")
    merged_imgs = merged_soup.find_all("img")
    if len(original_imgs) != len(merged_imgs):
        return merged_html

    for original_img, merged_img in zip(original_imgs, merged_imgs):
        merged_img.attrs = dict(original_img.attrs)

        original_parent = original_img.parent
        merged_parent = merged_img.parent
        if getattr(original_parent, "name", None) == "figure" and getattr(merged_parent, "name", None) == "figure":
            merged_parent.attrs = dict(original_parent.attrs)

    return merged_soup.decode_contents()


def merge_contiguous_genealogy_tables(html: str, *, rescue_normalizer: Optional[Any] = None) -> str:
    if "<table" not in (html or "").lower():
        return html or ""

    normalizer = rescue_normalizer
    if normalizer is None:
        normalizer = _normalize_genealogy_rescue_html

    normalized = html or ""
    if normalizer is not None:
        normalized = normalizer(normalized)

    soup = BeautifulSoup(normalized, "html.parser")
    _convert_genealogy_name_list_paragraphs_to_tables(soup)
    for base_table in list(soup.find_all("table")):
        if base_table.parent is None or not _is_genealogy_table_header(base_table):
            continue

        expected_cols = _genealogy_table_column_count(base_table)
        cursor = base_table
        pending_headings: List[Any] = []

        while True:
            next_node = _next_significant_sibling(cursor)
            if next_node is None:
                break
            if _is_genealogy_heading_tag(next_node):
                pending_headings.append(next_node)
                cursor = next_node
                continue
            if (
                getattr(next_node, "name", None) == "table"
                and not pending_headings
                and _is_compatible_genealogy_table(next_node, expected_cols)
                and _looks_like_genealogy_continuation_table(next_node)
            ):
                _append_genealogy_heading_and_rows(base_table, [], next_node, soup)
                next_node.decompose()
                cursor = base_table
                continue
            if getattr(next_node, "name", None) == "table" and pending_headings and _is_compatible_genealogy_table(next_node, expected_cols):
                _append_genealogy_heading_and_rows(base_table, pending_headings, next_node, soup)
                for heading in pending_headings:
                    heading.decompose()
                pending_headings = []
                next_node.decompose()
                cursor = base_table
                continue
            break

    for table in soup.find_all("table"):
        if _is_genealogy_table_header(table):
            _normalize_genealogy_body_rows(table, soup)

    return _preserve_figure_and_image_attrs(html, soup.decode_contents())

