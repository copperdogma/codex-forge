"""
Table structure scorer for promptfoo OCR eval.

Compares model HTML output against golden reference HTML,
measuring how well the model preserves table structure,
column separation, text accuracy, and image placeholder detection.

Metrics (weights — adapt dynamically based on page content):
  table_detection  : Fraction of golden tables found as <table> in output
  column_accuracy  : Per-matched-table column count correctness
  cell_text        : Cell content similarity (fuzzy)
  row_accuracy     : Per-matched-table row count correctness
  header_accuracy  : <thead> usage matches golden
  img_detection    : Fraction of golden <img> placeholders found in output

Pages with both tables and images use all metrics.
Pages with only images (no tables) weight img_detection at 100%.
Pages with only tables (no images) use the original 5-metric weights.

Usage (in promptfoo YAML):
  assert:
    - type: python
      value: file://benchmarks/scorers/table_structure_scorer.py
"""

import os
import re
from difflib import SequenceMatcher
from html.parser import HTMLParser


# ── HTML parsing helpers ─────────────────────────────────────────────

class TableExtractor(HTMLParser):
    """Extract tables from HTML as structured data."""

    def __init__(self):
        super().__init__()
        self.tables = []
        self._table = None
        self._row = None
        self._cell = None
        self._in_thead = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table = {"has_thead": False, "rows": []}
        elif tag == "thead":
            self._in_thead = True
            if self._table is not None:
                self._table["has_thead"] = True
        elif tag == "tr":
            self._row = {"cells": [], "is_header": self._in_thead}
        elif tag in ("td", "th"):
            self._cell = ""
        elif tag == "br" and self._cell is not None:
            self._cell += "\n"

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None:
            self._row["cells"].append(self._cell or "")
            self._cell = None
        elif tag == "tr" and self._table is not None and self._row is not None:
            if self._row["cells"]:
                self._table["rows"].append(self._row)
            self._row = None
        elif tag == "thead":
            self._in_thead = False
        elif tag == "table" and self._table is not None:
            if self._table["rows"]:
                self.tables.append(self._table)
            self._table = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell += data


class ImgExtractor(HTMLParser):
    """Extract <img> tags and their alt text."""

    def __init__(self):
        super().__init__()
        self.imgs = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            alt = dict(attrs).get("alt", "")
            self.imgs.append(alt)


class ParagraphTextExtractor(HTMLParser):
    """Extract text from <p> tags (not inside tables) for TABLE-AS-TEXT detection."""

    def __init__(self):
        super().__init__()
        self.p_texts = []
        self._current_p = None
        self._table_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table_depth += 1
        elif tag == "p" and self._table_depth == 0:
            self._current_p = ""
        elif tag == "br" and self._current_p is not None:
            self._current_p += " "

    def handle_endtag(self, tag):
        if tag == "table":
            self._table_depth = max(0, self._table_depth - 1)
        elif tag == "p" and self._current_p is not None:
            text = self._current_p.strip()
            if text:
                self.p_texts.append(text)
            self._current_p = None

    def handle_data(self, data):
        if self._current_p is not None:
            self._current_p += data


def parse_tables(html: str) -> list:
    parser = TableExtractor()
    parser.feed(html)
    return parser.tables


def parse_imgs(html: str) -> list:
    parser = ImgExtractor()
    parser.feed(html)
    return parser.imgs


def parse_p_texts(html: str) -> list:
    parser = ParagraphTextExtractor()
    parser.feed(html)
    return parser.p_texts


def strip_markdown_fences(text: str) -> str:
    """Remove ```html ... ``` fences from model output."""
    text = text.strip()
    m = re.match(r"^```(?:html)?\s*\n(.*?)```\s*$", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text


# ── Matching & scoring helpers ───────────────────────────────────────

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def text_similarity(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _table_signature(table: dict) -> str:
    """Concatenate non-header cell text for matching."""
    parts = []
    for row in table["rows"]:
        if not row.get("is_header"):
            for cell in row["cells"]:
                t = cell.strip()
                if t:
                    parts.append(_norm(t))
    return " ".join(parts)


def match_tables(golden_tables: list, output_tables: list) -> list[tuple]:
    """Match golden tables to output tables by content similarity.
    Returns [(golden_idx, output_idx, similarity), ...]."""
    if not golden_tables or not output_tables:
        return []

    g_sigs = [_table_signature(t) for t in golden_tables]
    o_sigs = [_table_signature(t) for t in output_tables]

    matches = []
    used = set()

    for gi, gsig in enumerate(g_sigs):
        if not gsig:
            continue
        best_oi, best_sim = -1, 0.25  # min threshold
        for oi, osig in enumerate(o_sigs):
            if oi in used or not osig:
                continue
            sim = SequenceMatcher(None, gsig, osig).ratio()
            if sim > best_sim:
                best_sim = sim
                best_oi = oi
        if best_oi >= 0:
            matches.append((gi, best_oi, best_sim))
            used.add(best_oi)

    return matches


def check_table_as_text(golden_table: dict, p_texts: list) -> float:
    """Check if a golden table's data appears in <p> tags.
    Returns fraction of golden data cells found in <p> text."""
    cells = []
    for row in golden_table["rows"]:
        if not row.get("is_header"):
            for cell in row["cells"]:
                t = cell.strip()
                if len(t) > 2:
                    cells.append(_norm(t))
    if not cells:
        return 0.0

    blob = " ".join(_norm(p) for p in p_texts)
    found = sum(1 for c in cells if c in blob)
    return found / len(cells)


# ── Per-table scoring functions ──────────────────────────────────────

def score_columns(g_table: dict, o_table: dict) -> float:
    """Column count accuracy for matched tables."""
    g_counts = [len(r["cells"]) for r in g_table["rows"] if not r.get("is_header")]
    o_counts = [len(r["cells"]) for r in o_table["rows"] if not r.get("is_header")]
    if not g_counts:
        return 1.0

    def mode(lst):
        from collections import Counter
        return Counter(lst).most_common(1)[0][0] if lst else 0

    g_mode = mode(g_counts)
    o_mode = mode(o_counts) if o_counts else 0

    if g_mode == o_mode:
        return 1.0
    elif abs(g_mode - o_mode) == 1:
        return 0.5
    return 0.0


def score_rows(g_table: dict, o_table: dict) -> float:
    """Row count accuracy for matched tables."""
    g_n = sum(1 for r in g_table["rows"] if not r.get("is_header"))
    o_n = sum(1 for r in o_table["rows"] if not r.get("is_header"))
    if g_n == 0:
        return 1.0 if o_n == 0 else 0.0
    if g_n == o_n:
        return 1.0
    return max(0.0, 1.0 - abs(g_n - o_n) / g_n)


def score_cell_text(g_table: dict, o_table: dict) -> float:
    """Cell-level text similarity for matched tables."""
    g_rows = [r for r in g_table["rows"] if not r.get("is_header")]
    o_rows = [r for r in o_table["rows"] if not r.get("is_header")]
    if not g_rows:
        return 1.0

    scores = []
    for i, g_row in enumerate(g_rows):
        if i >= len(o_rows):
            scores.append(0.0)
            continue
        o_row = o_rows[i]
        max_cells = max(len(g_row["cells"]), len(o_row["cells"]))
        if max_cells == 0:
            scores.append(1.0)
            continue
        cell_sims = []
        for j in range(max_cells):
            g_text = g_row["cells"][j] if j < len(g_row["cells"]) else ""
            o_text = o_row["cells"][j] if j < len(o_row["cells"]) else ""
            cell_sims.append(text_similarity(g_text, o_text))
        scores.append(sum(cell_sims) / len(cell_sims))

    return sum(scores) / len(scores)


def score_header(g_table: dict, o_table: dict) -> float:
    return 1.0 if g_table["has_thead"] == o_table["has_thead"] else 0.0


# ── Image scoring ──────────────────────────────────────────────────

def score_img_detection(golden_imgs: list, output_imgs: list) -> float:
    """Score how many golden <img> placeholders appear in output.

    Matching is generous: an output img matches a golden img if their
    alt texts share significant word overlap (≥40% Jaccard on words).
    Falls back to count-based: min(output_count, golden_count) / golden_count.
    """
    if not golden_imgs:
        return 1.0  # no images expected

    n_golden = len(golden_imgs)
    n_output = len(output_imgs)

    if n_output == 0:
        return 0.0

    # Try word-overlap matching first
    def _words(s):
        return set(re.sub(r"[^\w\s]", "", s.lower()).split())

    matched = 0
    used = set()
    for g_alt in golden_imgs:
        g_words = _words(g_alt)
        for oi, o_alt in enumerate(output_imgs):
            if oi in used:
                continue
            o_words = _words(o_alt)
            if g_words and o_words:
                jaccard = len(g_words & o_words) / len(g_words | o_words)
                if jaccard >= 0.25:
                    matched += 1
                    used.add(oi)
                    break
            elif not g_words and not o_words:
                # Both have empty/minimal alt text — count as match
                matched += 1
                used.add(oi)
                break

    # If word matching found some, use that; otherwise use count-based
    if matched > 0:
        return matched / n_golden

    # Fallback: count-based (model emitted img tags but alt text differs)
    return min(n_output, n_golden) / n_golden


# ── Main scorer entry point ─────────────────────────────────────────

# Base weights for table-only pages
TABLE_WEIGHTS = {
    "table_detection": 0.25,
    "column_accuracy": 0.25,
    "cell_text": 0.25,
    "row_accuracy": 0.15,
    "header_accuracy": 0.10,
}


def get_assert(output: str, context: dict) -> dict:
    """promptfoo scorer entry point.

    context.vars should include:
      golden_file: path to golden HTML (relative to benchmarks/)
    """
    vars_ = context.get("vars", {})
    golden_file = vars_.get("golden_file", "")

    # Resolve path relative to benchmarks/
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    golden_path = os.path.join(base, golden_file)

    if not os.path.exists(golden_path):
        return {"pass": False, "score": 0.0,
                "reason": f"Golden file not found: {golden_path}"}

    with open(golden_path, "r") as f:
        golden_html = f.read()

    output_html = strip_markdown_fences(output)

    golden_tables = parse_tables(golden_html)
    golden_imgs = parse_imgs(golden_html)
    output_tables = parse_tables(output_html)
    output_imgs = parse_imgs(output_html)
    output_p_texts = parse_p_texts(output_html)

    has_tables = len(golden_tables) > 0
    has_imgs = len(golden_imgs) > 0

    if not has_tables and not has_imgs:
        return {"pass": True, "score": 1.0,
                "reason": "No tables or images in golden reference"}

    # ── img_detection ────────────────────────────────────────────
    img_score = score_img_detection(golden_imgs, output_imgs)

    # ── Image-only pages (no tables) ─────────────────────────────
    if not has_tables:
        passed = img_score >= 0.60
        lines = [
            f"img_detection: {img_score:.2f} ({len(output_imgs)}/{len(golden_imgs)} images detected)",
            f"TOTAL: {img_score:.3f} ({'PASS' if passed else 'FAIL'})",
        ]
        return {"pass": passed, "score": img_score,
                "reason": "\n".join(lines)}

    # ── Table scoring (same as before) ───────────────────────────
    total_golden = len(golden_tables)
    matches = match_tables(golden_tables, output_tables)
    matched_gi = {gi for gi, _, _ in matches}

    tat_count = 0
    for gi in range(total_golden):
        if gi not in matched_gi:
            if check_table_as_text(golden_tables[gi], output_p_texts) > 0.3:
                tat_count += 1

    table_detection = len(matches) / total_golden

    col_scores = [0.0] * total_golden
    row_scores = [0.0] * total_golden
    text_scores = [0.0] * total_golden
    hdr_scores = [0.0] * total_golden

    for gi, oi, _ in matches:
        col_scores[gi] = score_columns(golden_tables[gi], output_tables[oi])
        row_scores[gi] = score_rows(golden_tables[gi], output_tables[oi])
        text_scores[gi] = score_cell_text(golden_tables[gi], output_tables[oi])
        hdr_scores[gi] = score_header(golden_tables[gi], output_tables[oi])

    column_accuracy = sum(col_scores) / total_golden
    row_accuracy = sum(row_scores) / total_golden
    cell_text = sum(text_scores) / total_golden
    header_accuracy = sum(hdr_scores) / total_golden

    # ── Compute weighted total ───────────────────────────────────
    if has_imgs:
        # Mixed page: tables + images — allocate 15% to img_detection
        total = (
            0.20 * table_detection
            + 0.20 * column_accuracy
            + 0.20 * cell_text
            + 0.15 * row_accuracy
            + 0.10 * header_accuracy
            + 0.15 * img_score
        )
    else:
        # Table-only page: original weights
        total = (
            TABLE_WEIGHTS["table_detection"] * table_detection
            + TABLE_WEIGHTS["column_accuracy"] * column_accuracy
            + TABLE_WEIGHTS["cell_text"] * cell_text
            + TABLE_WEIGHTS["row_accuracy"] * row_accuracy
            + TABLE_WEIGHTS["header_accuracy"] * header_accuracy
        )

    passed = total >= 0.60

    lines = [
        f"table_detection: {table_detection:.2f} ({len(matches)}/{total_golden} tables matched)",
    ]
    if tat_count:
        lines.append(
            f"  TABLE-AS-TEXT: {tat_count} golden tables rendered as <p> tags"
        )
    lines += [
        f"column_accuracy: {column_accuracy:.2f}",
        f"row_accuracy:    {row_accuracy:.2f}",
        f"cell_text:       {cell_text:.2f}",
        f"header_accuracy: {header_accuracy:.2f}",
    ]
    if has_imgs:
        lines.append(
            f"img_detection:   {img_score:.2f} ({len(output_imgs)}/{len(golden_imgs)} images)"
        )
    lines.append(f"TOTAL: {total:.3f} ({'PASS' if passed else 'FAIL'})")

    return {"pass": passed, "score": total, "reason": "\n".join(lines)}
