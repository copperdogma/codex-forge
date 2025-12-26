#!/usr/bin/env python3
"""
elements_content_type_v1

Text-first content type tagging for element_core_v1 JSONL.

Outputs element_core_v1 with:
- content_type (DocLayNet label by default)
- content_type_confidence
- content_subtype (small optional dict)
"""

import argparse
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from modules.common.openai_client import OpenAI
from modules.common.utils import read_jsonl, append_jsonl, ensure_dir
from schemas import ElementCore


DOCLAYNET_LABELS = [
    "Title",
    "Section-header",
    "Text",
    "List-item",
    "Table",
    "Picture",
    "Caption",
    "Formula",
    "Footnote",
    "Page-header",
    "Page-footer",
]

PUBLAYNET_LABELS = ["Title", "Text", "List", "Table", "Figure"]

DEFAULT_KV_KEY_WHITELIST = {"SKILL", "STAMINA", "LUCK"}

ROLE_TO_DOCLAYNET = {
    # Generic/common
    "TITLE": "Title",
    "HEADING": "Section-header",
    "SECTION_HEADER": "Section-header",
    "SECTION-HEADER": "Section-header",
    "HEADER": "Page-header",
    "FOOTER": "Page-footer",
    "PAGE_HEADER": "Page-header",
    "PAGE_FOOTER": "Page-footer",
    "LIST": "List-item",
    "LIST_ITEM": "List-item",
    "LIST-ITEM": "List-item",
    "TABLE": "Table",
    "FIGURE": "Picture",
    "PICTURE": "Picture",
    "CAPTION": "Caption",
    "FOOTNOTE": "Footnote",
    "FORMULA": "Formula",
    # AWS Textract-style (when provided)
    "LAYOUT_TITLE": "Title",
    "LAYOUT_SECTION_HEADER": "Section-header",
    "LAYOUT_HEADER": "Page-header",
    "LAYOUT_FOOTER": "Page-footer",
    "LAYOUT_LIST": "List-item",
    "LAYOUT_TABLE": "Table",
    "LAYOUT_FIGURE": "Picture",
    "LAYOUT_TEXT": "Text",
}


def role_to_doclaynet(role: str) -> Optional[str]:
    if not isinstance(role, str):
        return None
    key = role.strip().upper().replace(" ", "_")
    return ROLE_TO_DOCLAYNET.get(key)


def is_numeric_only(text: str) -> Optional[int]:
    m = re.match(r"^\s*(\d{1,3})\s*$", text or "")
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def is_all_caps_heading(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    # Avoid misclassifying form-field labels like "STAMINA =" as headings.
    if "=" in t:
        return False
    if len(t) > 60:
        return False
    letters = [c for c in t if c.isalpha()]
    if len(letters) < 4:
        return False
    upper = sum(1 for c in letters if c.isupper())
    return upper / len(letters) >= 0.9


def looks_like_page_range(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return bool(re.match(r"^\d{1,3}\s*[-–]\s*\d{1,3}\s*$", t))


def looks_like_toc_entry(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 120:
        return False
    if re.search(r"\.{3,}\s*\d+\s*$", t):
        return True
    if re.search(r"\s{2,}\d+\s*$", t) and re.search(r"[A-Za-z]", t):
        return True
    return False


def looks_like_list_item(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if re.match(r"^[-\*\u2022\u00b7]\s+\S", t):
        return True
    if re.match(r"^\(?[0-9]{1,3}[\)\.]\s+\S", t):
        return True
    if re.match(r"^\(?[a-zA-Z][\)\.]\s+\S", t):
        return True
    return False


def looks_like_stats_table_line(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    u = t.upper()
    if re.match(r"^SKILL\s+STAMINA\s*$", u):
        return True
    m = re.match(r"^(.+?)\s+(\d+)\s+(\d+)\s*$", t)
    if m:
        prefix = (m.group(1) or "").strip()
        if 5 <= len(prefix) <= 50 and re.search(r"[A-Za-z]", prefix):
            return True
    return False


def looks_like_combat_stat_block(text: str) -> bool:
    """
    Detect FF-style combat stat blocks like:
      "MANTICORE      SKILL 11      STAMINA 11"
    These often appear inline with narrative text and should not be treated as a Table.
    """
    t = (text or "").strip()
    if not t:
        return False
    u = t.upper()
    if "SKILL" not in u or "STAMINA" not in u:
        return False
    # Require numeric stats near the keywords.
    if re.search(r"\bSKILL\s*\d{1,2}\b", u) and re.search(r"\bSTAMINA\s*\d{1,2}\b", u):
        return True
    return False


def extract_key_value_subtype(
    text: str,
    *,
    allow_unknown_keys: bool = False,
    key_whitelist: Optional[set] = None,
) -> Optional[Dict[str, Any]]:
    """
    Best-effort, high-precision extraction of key/value signals from a line.

    Intended uses:
    - FF combat stat blocks: "MANTICORE  SKILL 11  STAMINA 11"
    - Simple field assignments: "STAMINA = 12" or "SKILL: 7"

    Returns a small dict suitable for `content_subtype["key_value"]`, or None.
    """
    t = (text or "").strip()
    if not t:
        return None

    # Combat stat blocks: capture entity + common stat keys.
    u = t.upper()
    if "SKILL" in u and "STAMINA" in u:
        entity = None
        # Try to capture a creature/entity name immediately before "SKILL <n>".
        # Keep it strict to avoid swallowing the stats themselves.
        m_ent = re.search(r"\b([A-Z][A-Z' -]{2,30})\s+SKILL\s+\d{1,3}\b", u)
        if m_ent:
            entity = " ".join(m_ent.group(1).strip().split())

        pairs = []
        for key in ("SKILL", "STAMINA", "LUCK"):
            m = re.search(rf"\b{key}\s+(\d{{1,3}})\b", u)
            if m:
                pairs.append({"key": key, "value": int(m.group(1))})
        if pairs:
            out: Dict[str, Any] = {"pairs": pairs}
            if entity:
                out["entity"] = entity
            return out

    # Generic KEY = VALUE or KEY: VALUE patterns (keep narrow to avoid false positives).
    m = re.match(r"^([A-Za-z][A-Za-z ]{1,24})\s*[:=]\s*([0-9]{1,4})\s*$", t)
    if m:
        key = " ".join(m.group(1).strip().split()).upper()
        if not allow_unknown_keys and key_whitelist and key not in key_whitelist:
            return None
        try:
            val = int(m.group(2))
        except Exception:
            return None
        return {"pairs": [{"key": key, "value": val}]}

    # Field label with missing value (e.g., "STAMINA =" or "SKILL:").
    m = re.match(r"^([A-Za-z][A-Za-z ]{1,24})\s*[:=]\s*$", t)
    if m:
        key = " ".join(m.group(1).strip().split()).upper()
        if not allow_unknown_keys and key_whitelist and key not in key_whitelist:
            return None
        return {"pairs": [{"key": key, "value": None}]}

    return None


def looks_like_table(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    # Avoid treating combat stat blocks as tables.
    if looks_like_combat_stat_block(t):
        return False
    if looks_like_stats_table_line(t):
        return True
    if "|" in t and sum(1 for c in t if c == "|") >= 2:
        return True
    if re.search(r"\S\s{2,}\S", t):
        tokens = re.split(r"\s{2,}", t)
        if len(tokens) >= 3 and sum(1 for tok in tokens if tok.strip()) >= 3:
            return True
    digits = sum(1 for c in t if c.isdigit())
    letters = sum(1 for c in t if c.isalpha())
    if digits >= 6 and letters >= 3 and re.search(r"\s{2,}", t):
        return True
    return False


def looks_like_caption(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 120:
        return False
    if re.match(r"^(FIG\.?|FIGURE|TABLE)\s+\d+", t.strip(), flags=re.IGNORECASE):
        return True
    if re.match(r"^Illustration\s+\d+", t.strip(), flags=re.IGNORECASE):
        return True
    return False


def looks_like_formula(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 80:
        return False
    # High-precision numeric arithmetic.
    if re.search(r"\b\d+\s*[+\*/]\s*\d+\b", t):
        return True
    # Treat minus as arithmetic only when spaced; avoid interpreting numeric ranges like "16-17".
    if re.search(r"\b\d+\s+-\s+\d+\b", t):
        return True
    # Equations: require either digits or explicit math operators beyond "=".
    if "=" in t:
        has_digit = bool(re.search(r"\d", t))
        has_strong_op = bool(re.search(r"[+\*/\^]", t)) or bool(re.search(r"\b\d+\s+-\s+\d+\b", t))
        if not (has_digit or has_strong_op):
            return False
        if re.search(r"\b\w+\s*=\s*[\w\d]+", t):
            return True
    # Approx/inequality: require digits to avoid OCR-garble false positives.
    if any(sym in t for sym in ("≈", "≠", "≤", "≥")) and re.search(r"\d", t):
        return True
    return False


def pub_map(doclaynet_label: str) -> str:
    if doclaynet_label in {"List-item"}:
        return "List"
    if doclaynet_label in {"Picture", "Caption"}:
        return "Figure"
    if doclaynet_label in {"Table"}:
        return "Table"
    if doclaynet_label in {"Title"}:
        return "Title"
    return "Text"


def doc_label_ok(label: str, allow_extensions: bool) -> bool:
    if allow_extensions:
        return True
    return label in DOCLAYNET_LABELS


def classify_element_heuristic(elem: Dict[str, Any]) -> Tuple[str, float, Optional[Dict[str, Any]]]:
    kind = (elem.get("kind") or "").strip()
    text = elem.get("text") or ""
    layout = elem.get("layout") or {}
    layout_role = elem.get("layout_role")
    y = None
    h_align = None
    if isinstance(layout, dict):
        y = layout.get("y")
        h_align = layout.get("h_align")

    mapped = role_to_doclaynet(layout_role) if layout_role else None
    if mapped:
        return (mapped, 0.95, {"source_role": str(layout_role)})

    if kind == "image":
        return ("Picture", 0.9, None)
    if kind == "table":
        return ("Table", 0.9, None)
    if kind != "text":
        return ("Text", 0.4, None)

    t = text.strip()
    if not t:
        return ("Text", 0.0, None)

    # Form-ish field labels frequently appear as "SKILL =" / "STAMINA =" in FF sheets.
    # DocLayNet doesn't have a dedicated "Form" label, so keep these as Text and
    # tag a subtype for downstream routing.
    if "=" in t and not re.search(r"\d", t) and len(t) <= 80 and re.search(r"[A-Za-z]", t):
        # High precision: clean label like "STAMINA ="
        if re.match(r"^[A-Za-z][A-Za-z\s]{1,30}\s*=\s*$", t):
            subtype: Dict[str, Any] = {"form_field": True}
            kv = extract_key_value_subtype(t, allow_unknown_keys=True, key_whitelist=DEFAULT_KV_KEY_WHITELIST)
            if kv is not None:
                subtype["key_value"] = kv
            return ("Text", 0.75, subtype)
        # Lower precision: noisy OCR labels still tend to contain '=' with no digits.
        # Prefer routing these as form fields instead of misclassifying as Title.
        subtype = {"form_field": True}
        kv = extract_key_value_subtype(t, allow_unknown_keys=True, key_whitelist=DEFAULT_KV_KEY_WHITELIST)
        if kv is not None:
            subtype["key_value"] = kv
        return ("Text", 0.7, subtype)

    if looks_like_combat_stat_block(t):
        subtype = {"combat_stats": True}
        kv = extract_key_value_subtype(t, allow_unknown_keys=True, key_whitelist=DEFAULT_KV_KEY_WHITELIST)
        if kv is not None:
            subtype["key_value"] = kv
        return ("Text", 0.8, subtype)

    n = is_numeric_only(t)
    if n is not None and 1 <= n <= 600:
        return ("Section-header", 0.9, {"number": n})

    if looks_like_table(t):
        return ("Table", 0.85, None)

    if looks_like_toc_entry(t) or looks_like_list_item(t):
        return ("List-item", 0.85, None)

    if looks_like_caption(t):
        return ("Caption", 0.8, None)

    if looks_like_formula(t):
        return ("Formula", 0.75, None)

    if (h_align == "center" and len(t) <= 50) or is_all_caps_heading(t):
        if len(t) <= 30:
            return ("Title", 0.75, None)
        return ("Section-header", 0.75, None)

    return ("Text", 0.6, None)


def _sig(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def get_abstract_position(layout: Dict[str, Any], bbox: Optional[List[float]] = None) -> Optional[Tuple[str, str]]:
    """
    Determine abstract position as (vertical_align, horizontal_align) tuple.
    
    Returns None if layout data insufficient.
    
    NOTE: Coordinate system handling:
    - Tesseract/EasyOCR: y=0 = top, y=1 = bottom (standard image coordinates)
    - Apple Vision: y=0 = bottom, y=1 = top (inverted, bottom-left origin)
    - If bbox is provided and y0 is high (>0.8), coordinate system may be inverted
    - We detect inversion by checking if y is high AND element is at corner (likely running header)
    
    Examples:
        (top, left), (top, center), (top, right)
        (middle, left), (middle, center), (middle, right)
        (bottom, left), (bottom, center), (bottom, right)
    """
    if not isinstance(layout, dict):
        return None
    
    y = layout.get("y")
    h_align = layout.get("h_align")
    
    if not isinstance(y, (int, float)):
        return None
    
    # Detect inverted coordinate system: if y is high (>0.8) and element is at corner,
    # it's likely a running header at top (inverted coords) rather than footer at bottom
    # Heuristic: If y > 0.85 and h_align is left/right (corner), likely inverted
    y_normalized = y
    if bbox and len(bbox) >= 4:
        y0, y1 = bbox[1], bbox[3]
        # If y0 is very high (>0.9) and h_align suggests corner, likely inverted
        # For running headers at top corners, they'll have high y in inverted system
        if y0 > 0.85 and isinstance(h_align, str) and h_align.lower() in ["left", "right"]:
            # Likely inverted: use (1 - y) to convert to standard
            y_normalized = 1.0 - y
        # Otherwise, assume standard coordinates
    elif y > 0.85 and isinstance(h_align, str) and h_align.lower() in ["left", "right"]:
        # No bbox but high y at corner - likely inverted
        y_normalized = 1.0 - y
    
    # Vertical alignment (using normalized y)
    if y_normalized <= 0.10:
        vertical = "top"
    elif y_normalized >= 0.90:
        vertical = "bottom"
    else:
        vertical = "middle"
    
    # Horizontal alignment
    if not isinstance(h_align, str):
        # Default based on position if h_align not available
        horizontal = "center"  # Conservative default
    else:
        h_align_lower = h_align.lower()
        if "left" in h_align_lower:
            horizontal = "left"
        elif "right" in h_align_lower:
            horizontal = "right"
        elif "center" in h_align_lower:
            horizontal = "center"
        else:
            horizontal = "center"  # Default
    
    return (vertical, horizontal)


@dataclass
class NumericElementInfo:
    """Information about a numeric element or page range for pattern analysis."""
    idx: int
    element_id: str
    page: int
    number: Optional[int]  # None for page ranges (e.g., "6-8")
    is_page_range: bool  # True if text is a page range like "6-8"
    abstract_pos: Optional[Tuple[str, str]]
    text: str
    segment: Optional[str] = None  # frontmatter, gameplay, endmatter (optional, for debugging only)


def detect_sequential_page_numbers(
    numeric_elements: List[NumericElementInfo],
    min_sequence_length: int = 3,
    segment_filter: Optional[str] = None,
) -> Dict[int, Dict[str, Any]]:
    """
    Detect sequential page number patterns (highest priority pattern).
    
    Looks for sequences of increasing integers (N, N+1, N+2...) at the same
    abstract position on consecutive pages. Only processes numeric-only (not ranges).
    
    If segment_filter is provided, only processes elements from that segment (frontmatter/gameplay/endmatter).
    Patterns should be detected separately per macro segment to avoid mixing patterns.
    
    Returns dict mapping element idx -> pattern info with high confidence.
    """
    # Filter by segment if provided (patterns should be detected per macro segment)
    filtered_elements = numeric_elements
    if segment_filter:
        filtered_elements = [e for e in numeric_elements if e.segment == segment_filter]
    
    # Only process numeric-only elements (not page ranges) for sequential detection
    numeric_only = [e for e in filtered_elements if not e.is_page_range and e.number is not None]
    
    if len(numeric_only) < min_sequence_length:
        return {}
    
    # Group by abstract position (generic, no segment-specific logic)
    by_pos: Dict[Optional[Tuple[str, str]], List[NumericElementInfo]] = defaultdict(list)
    for elem in numeric_only:
        by_pos[elem.abstract_pos].append(elem)
    
    matched_elements: Dict[int, Dict[str, Any]] = {}
    
    for pos, elems in by_pos.items():
        if pos is None or len(elems) < min_sequence_length:
            continue
        
        # Sort by page number
        elems_sorted = sorted(elems, key=lambda e: e.page)
        
        # Look for sequences where number increases with page number
        sequences: List[List[NumericElementInfo]] = []
        current_seq: List[NumericElementInfo] = [elems_sorted[0]]
        
        for i in range(1, len(elems_sorted)):
            prev = elems_sorted[i - 1]
            curr = elems_sorted[i]
            
            # Check if this continues a sequence
            # Page numbers typically increase by 1, but allow some gaps
            if curr.page == prev.page + 1 or (curr.page > prev.page and curr.number is not None and prev.number is not None and curr.number == prev.number + 1):
                current_seq.append(curr)
            else:
                if len(current_seq) >= min_sequence_length:
                    sequences.append(current_seq)
                current_seq = [curr]
        
        if len(current_seq) >= min_sequence_length:
            sequences.append(current_seq)
        
        # Mark elements in valid sequences as page numbers
        for seq in sequences:
            for elem in seq:
                if elem.number is not None:
                    matched_elements[elem.idx] = {
                        "pattern_type": "sequential_page_number",
                        "content_type": "Page-footer",
                        "confidence": 0.99,
                        "pattern_info": {
                            "sequence_length": len(seq),
                            "abstract_position": pos,
                            "page_range": (seq[0].page, seq[-1].page),
                            "number_range": (seq[0].number, seq[-1].number) if seq[0].number is not None and seq[-1].number is not None else None,
                        }
                    }
    
    return matched_elements


def detect_other_header_footer_patterns(
    numeric_elements: List[NumericElementInfo],
    matched_indices: set,
    min_repeats: int = 3,
    segment_filter: Optional[str] = None,
) -> Dict[int, Dict[str, Any]]:
    """
    Detect other header/footer patterns for remaining numeric elements and page ranges.
    
    - Running Headers: Repeating page ranges or numbers at same position (typically top)
    - Other Page Footers: Consistently placed non-sequential numbers at bottom
    
    If segment_filter is provided, only processes elements from that segment (frontmatter/gameplay/endmatter).
    Patterns should be detected separately per macro segment to avoid mixing patterns.
    """
    matched_elements: Dict[int, Dict[str, Any]] = {}
    
    # Filter by segment if provided (patterns should be detected per macro segment)
    filtered_elements = numeric_elements
    if segment_filter:
        filtered_elements = [e for e in numeric_elements if e.segment == segment_filter]
    
    # Filter out already matched elements
    remaining = [e for e in filtered_elements if e.idx not in matched_indices]
    
    if not remaining:
        return matched_elements
    
    # Group by abstract position (generic, no segment-specific logic)
    by_pos: Dict[Optional[Tuple[str, str]], List[NumericElementInfo]] = defaultdict(list)
    for elem in remaining:
        by_pos[elem.abstract_pos].append(elem)
    
    for pos, elems in by_pos.items():
        if pos is None or len(elems) < min_repeats:
            continue
        
        vertical, horizontal = pos
        
        # Running Headers: Top position, repeating page ranges or numbers
        if vertical == "top":
            # Running headers can be detected in two ways:
            # 1. Same text repeating (traditional running header with identical text)
            # 2. Position pattern: Multiple DIFFERENT page ranges/numbers at same position
            #    (e.g., "9-10", "14-15", "18-21" all at top-left - section ranges per page)
            
            # Group by text signature for exact matches
            by_text_sig: Dict[str, List[NumericElementInfo]] = defaultdict(list)
            for elem in elems:
                sig = elem.text.strip()
                by_text_sig[sig].append(elem)
            
            # Pattern 1: Same text repeating (traditional running header)
            for text_sig, sig_elems in by_text_sig.items():
                if len(sig_elems) >= min_repeats:
                    for elem in sig_elems:
                        pattern_info = {
                            "abstract_position": pos,
                            "repeat_count": len(sig_elems),
                            "text": text_sig,
                            "pattern_variant": "exact_text_repeat",
                        }
                        if elem.is_page_range:
                            pattern_info["is_page_range"] = True
                        else:
                            pattern_info["number"] = elem.number
                        
                        matched_elements[elem.idx] = {
                            "pattern_type": "running_header",
                            "content_type": "Page-header",
                            "confidence": 0.90,
                            "pattern_info": pattern_info,
                        }
            
            # Pattern 2: Position-based pattern (different text, same position)
            # If we have enough elements at this position (even with different text),
            # and they're page ranges or numbers, classify as running headers
            # Lower threshold for position pattern (different text is still a pattern)
            position_pattern_min = max(5, min_repeats)  # Need at least 5 occurrences for position pattern
            
            # Filter out already matched elements (from exact text matches)
            unmatched_at_pos = [e for e in elems if e.idx not in matched_elements]
            
            # Check if enough unmatched elements remain to form a position pattern
            # Look for page ranges specifically (section ranges are most common)
            page_ranges_at_pos = [e for e in unmatched_at_pos if e.is_page_range]
            numeric_at_pos = [e for e in unmatched_at_pos if not e.is_page_range and e.number is not None]
            
            # If we have enough page ranges at this position, classify all as running headers
            if len(page_ranges_at_pos) >= position_pattern_min:
                for elem in page_ranges_at_pos:
                    matched_elements[elem.idx] = {
                        "pattern_type": "running_header",
                        "content_type": "Page-header",
                        "confidence": 0.90,
                        "pattern_info": {
                            "abstract_position": pos,
                            "occurrence_count": len(page_ranges_at_pos),
                            "text": elem.text,
                            "pattern_variant": "position_pattern",
                            "is_page_range": True,
                        }
                    }
            # If we have enough numeric elements at this position (but not ranges), also classify
            elif len(numeric_at_pos) >= position_pattern_min:
                for elem in numeric_at_pos:
                    matched_elements[elem.idx] = {
                        "pattern_type": "running_header",
                        "content_type": "Page-header",
                        "confidence": 0.85,  # Slightly lower confidence for numeric-only
                        "pattern_info": {
                            "abstract_position": pos,
                            "occurrence_count": len(numeric_at_pos),
                            "text": elem.text,
                            "pattern_variant": "position_pattern",
                            "number": elem.number,
                        }
                    }
        
        # Other Page Footers: Bottom position, non-sequential but consistent
        elif vertical == "bottom":
            # Only process numeric-only (not ranges) at bottom - ranges at bottom are unusual
            numeric_at_bottom = [e for e in elems if not e.is_page_range]
            if len(numeric_at_bottom) >= min_repeats:
                for elem in numeric_at_bottom:
                    # Only if not already matched and not sequential (sequential handled earlier)
                    matched_elements[elem.idx] = {
                        "pattern_type": "consistent_bottom_footer",
                        "content_type": "Page-footer",
                        "confidence": 0.85,
                        "pattern_info": {
                            "abstract_position": pos,
                            "occurrence_count": len(numeric_at_bottom),
                        }
                    }
    
    return matched_elements


def batch_items(items: List[Any], batch_size: int) -> List[List[Any]]:
    out: List[List[Any]] = []
    for i in range(0, len(items), batch_size):
        out.append(items[i : i + batch_size])
    return out


def build_llm_prompt(items: List[Dict[str, Any]]) -> str:
    instructions = {
        "labels": DOCLAYNET_LABELS,
        "task": "Assign exactly one DocLayNet label to each element.",
        "output_format": {
            "elements": [
                {
                    "seq": 0,
                    "content_type": "Text",
                    "content_type_confidence": 0.5,
                    "content_subtype": {},
                }
            ]
        },
        "notes": [
            "Use Section-header for headings, including standalone section numbers.",
            "Use List-item for TOC rows and bullet/numbered list items.",
            "Use Table only when text is clearly tabular.",
            "Prefer Text when uncertain; keep confidence low when uncertain.",
        ],
    }
    return json.dumps({"instructions": instructions, "items": items}, ensure_ascii=True, indent=2)


def llm_classify(
    client: OpenAI,
    model: str,
    items: List[Dict[str, Any]],
    max_tokens: int = 2500,
) -> Dict[int, Dict[str, Any]]:
    try:
        prompt = build_llm_prompt(items)
        kwargs: Dict[str, Any] = dict(
            model=model,
            messages=[
                {"role": "system", "content": "You are a precise document layout labeler."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        if model.startswith("gpt-5"):
            kwargs["max_completion_tokens"] = max_tokens
            kwargs["temperature"] = 1
        else:
            kwargs["max_tokens"] = max_tokens
            kwargs["temperature"] = 0.0

        completion = client.chat.completions.create(**kwargs)
        payload = json.loads(completion.choices[0].message.content)
        results: Dict[int, Dict[str, Any]] = {}
        for row in (payload or {}).get("elements", []):
            try:
                seq = int(row.get("seq"))
            except Exception:
                continue
            results[seq] = row
        return results
    except Exception as e:
        print(f"[elements_content_type_v1] LLM classify failed: {e}")
        return {}


@dataclass
class Prediction:
    content_type: str
    confidence: float
    subtype: Optional[Dict[str, Any]]


def main():
    parser = argparse.ArgumentParser(description="Tag element_core_v1 with DocLayNet content types.")
    parser.add_argument("--inputs", nargs="+", required=True, help="Input element_core_v1 JSONL(s); first is used.")
    parser.add_argument("--out", required=True, help="Output element_core_v1 JSONL path")
    parser.add_argument("--debug-out", dest="debug_out", help="Optional JSONL debug output path")
    parser.add_argument("--debug_out", dest="debug_out", help=argparse.SUPPRESS)  # alias for driver params
    parser.add_argument("--disabled", action="store_true", help="Pass-through without tagging")
    parser.add_argument("--use-llm", dest="use_llm", action="store_true", help="Enable LLM classification for ambiguous items")
    parser.add_argument("--use_llm", dest="use_llm", action="store_true", help=argparse.SUPPRESS)  # alias for driver params
    parser.add_argument("--model", default="gpt-4.1-mini", help="LLM model (when --use-llm)")
    parser.add_argument("--batch-size", dest="batch_size", type=int, default=200)
    parser.add_argument("--batch_size", dest="batch_size", type=int, help=argparse.SUPPRESS)  # alias for driver params
    parser.add_argument("--context-window", dest="context_window", type=int, default=1)
    parser.add_argument("--context_window", dest="context_window", type=int, help=argparse.SUPPRESS)  # alias for driver params
    parser.add_argument("--llm-threshold", dest="llm_threshold", type=float, default=0.65)
    parser.add_argument("--llm_threshold", dest="llm_threshold", type=float, help=argparse.SUPPRESS)  # alias for driver params
    parser.add_argument("--coarse-only", dest="coarse_only", action="store_true", help="Map to PubLayNet-style coarse labels")
    parser.add_argument("--coarse_only", dest="coarse_only", action="store_true", help=argparse.SUPPRESS)  # alias for driver params
    parser.add_argument("--allow-extensions", dest="allow_extensions", action="store_true", help="Allow non-DocLayNet labels")
    parser.add_argument("--allow_extensions", dest="allow_extensions", action="store_true", help=argparse.SUPPRESS)  # alias for driver params
    parser.add_argument(
        "--allow-unknown-kv-keys",
        dest="allow_unknown_kv_keys",
        action="store_true",
        help="Allow key_value extraction for non-whitelisted keys (default: only common FF keys)",
    )
    parser.add_argument(
        "--allow_unknown_kv_keys",
        dest="allow_unknown_kv_keys",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--coarse-segments",
        dest="coarse_segments",
        help="Optional path to coarse_segments.json for segment-aware pattern analysis",
    )
    parser.add_argument(
        "--coarse_segments",
        dest="coarse_segments",
        help=argparse.SUPPRESS,  # alias for driver params
    )
    parser.add_argument(
        "--patterns-out",
        dest="patterns_out",
        help="Optional path for element_patterns.jsonl debug artifact",
    )
    parser.add_argument(
        "--patterns_out",
        dest="patterns_out",
        help=argparse.SUPPRESS,  # alias for driver params
    )
    args = parser.parse_args()

    inp = args.inputs[0]
    ensure_dir(os.path.dirname(args.out) or ".")
    # This module uses append-only writers for simplicity; ensure we start fresh.
    open(args.out, "w", encoding="utf-8").close()
    if args.debug_out:
        # If debug_out is relative, place it next to the primary output artifact
        # so driver recipes can specify simple filenames.
        if not os.path.isabs(args.debug_out):
            args.debug_out = os.path.join(os.path.dirname(os.path.abspath(args.out)), args.debug_out)
        ensure_dir(os.path.dirname(args.debug_out) or ".")
        open(args.debug_out, "w", encoding="utf-8").close()
    
    if args.patterns_out:
        # If patterns_out is relative, place it next to the primary output artifact
        if not os.path.isabs(args.patterns_out):
            args.patterns_out = os.path.join(os.path.dirname(os.path.abspath(args.out)), args.patterns_out)
        ensure_dir(os.path.dirname(args.patterns_out) or ".")
        open(args.patterns_out, "w", encoding="utf-8").close()
    
    # Load coarse segments if available
    segment_map: Dict[int, str] = {}  # page -> segment name
    if args.coarse_segments and os.path.exists(args.coarse_segments):
        try:
            with open(args.coarse_segments, "r", encoding="utf-8") as f:
                coarse = json.load(f)
            if "frontmatter_pages" in coarse:
                start, end = coarse["frontmatter_pages"]
                for page in range(start, end + 1):
                    segment_map[page] = "frontmatter"
            if "gameplay_pages" in coarse:
                start, end = coarse["gameplay_pages"]
                for page in range(start, end + 1):
                    segment_map[page] = "gameplay"
            if "endmatter_pages" in coarse and coarse["endmatter_pages"]:
                start, end = coarse["endmatter_pages"]
                for page in range(start, end + 1):
                    segment_map[page] = "endmatter"
        except Exception as e:
            print(f"[elements_content_type_v1] Warning: Failed to load coarse_segments: {e}")

    elements: List[Dict[str, Any]] = []
    for row in read_jsonl(inp):
        ElementCore(**row)
        elements.append(row)

    pages_all = sorted({r.get("page") for r in elements if isinstance(r.get("page"), int)})
    page_count = len(pages_all)
    min_repeats = max(3, int(page_count * 0.2)) if page_count else 3

    header_pages_by_sig: Dict[str, set] = defaultdict(set)
    footer_pages_by_sig: Dict[str, set] = defaultdict(set)
    top_text_idx_by_page: Dict[int, int] = {}

    for idx, elem in enumerate(elements):
        if (elem.get("kind") or "").strip() != "text":
            continue
        page = elem.get("page")
        if not isinstance(page, int):
            continue
        layout = elem.get("layout") or {}
        if not isinstance(layout, dict):
            continue
        y = layout.get("y")
        if not isinstance(y, (int, float)):
            continue
        text = (elem.get("text") or "").strip()
        if not text:
            continue

        # Track top-most text element per page (by y), used for "Title" nudging.
        top_idx = top_text_idx_by_page.get(page)
        if top_idx is None:
            top_text_idx_by_page[page] = idx
        else:
            prev_y = (elements[top_idx].get("layout") or {}).get("y")
            if isinstance(prev_y, (int, float)) and y < prev_y:
                top_text_idx_by_page[page] = idx

        # Candidate header/footer signatures are repetition-based; avoid naive y-only tagging.
        # NOTE: We now include numeric-only text in repetition analysis for pattern detection
        if len(text) > 90:
            continue
        # REMOVED: if is_numeric_only(text) is not None: continue
        # Now numeric-only text is included for pattern-based detection
        if looks_like_list_item(text) or looks_like_toc_entry(text):
            continue
        if not re.search(r"[A-Za-z]", text) and is_numeric_only(text) is None:
            # Skip non-numeric, non-alphabetic text (but allow numeric-only for pattern analysis)
            continue

        sig = _sig(text)
        if not sig:
            continue
        if y <= 0.08:
            header_pages_by_sig[sig].add(page)
        if y >= 0.92:
            footer_pages_by_sig[sig].add(page)

    header_sigs = {s for s, pages in header_pages_by_sig.items() if len(pages) >= min_repeats}
    footer_sigs = {s for s, pages in footer_pages_by_sig.items() if len(pages) >= min_repeats}

    if args.disabled:
        for row in elements:
            append_jsonl(args.out, row)
        if args.debug_out:
            append_jsonl(
                args.debug_out,
                {
                    "disabled": True,
                    "input": inp,
                    "out": args.out,
                    "count": len(elements),
                },
            )
        return

    key_whitelist = DEFAULT_KV_KEY_WHITELIST

    predictions: List[Prediction] = []
    ambiguous: List[int] = []
    seq_to_index: Dict[int, int] = {}
    for i, elem in enumerate(elements):
        seq = elem.get("seq")
        if isinstance(seq, int):
            seq_to_index[seq] = i
    for idx, elem in enumerate(elements):
        label, conf, subtype = classify_element_heuristic(elem)

        # Tighten key/value signals by default: reject OCR-garbled "keys" unless explicitly enabled.
        if isinstance(subtype, dict) and "key_value" in subtype and isinstance(subtype.get("key_value"), dict):
            kv = subtype.get("key_value") or {}
            pairs = kv.get("pairs") if isinstance(kv, dict) else None
            if isinstance(pairs, list) and pairs:
                key0 = pairs[0].get("key") if isinstance(pairs[0], dict) else None
                if (
                    isinstance(key0, str)
                    and not args.allow_unknown_kv_keys
                    and key0.upper() not in key_whitelist
                ):
                    subtype = dict(subtype)
                    subtype.pop("key_value", None)
        if args.coarse_only:
            label = pub_map(label)
        predictions.append(Prediction(content_type=label, confidence=conf, subtype=subtype))
        if args.use_llm and conf < args.llm_threshold and (elem.get("kind") == "text"):
            ambiguous.append(idx)
    
    # NEW: Collect numeric elements and page ranges with abstract positions BEFORE post-processing
    # (so pattern detection can work on all numeric elements and ranges regardless of current classification)
    numeric_elements: List[NumericElementInfo] = []
    for idx, elem in enumerate(elements):
        if (elem.get("kind") or "").strip() != "text":
            continue
        text = (elem.get("text") or "").strip()
        
        # Check for numeric-only OR page ranges (e.g., "6-8", "12-17")
        n = is_numeric_only(text)
        is_range = looks_like_page_range(text)
        
        if n is None and not is_range:
            continue
        
        page = elem.get("page")
        if not isinstance(page, int):
            continue
        
        layout = elem.get("layout") or {}
        bbox = elem.get("bbox")  # Get bbox to help detect coordinate system
        abstract_pos = get_abstract_position(layout, bbox=bbox) if isinstance(layout, dict) else None
        
        # Skip if no position info (will use fallback heuristics)
        if abstract_pos is None:
            continue
        
        segment = segment_map.get(page)  # Optional, for debugging only
        element_id = elem.get("id") or elem.get("element_id") or f"elem_{idx}"
        
        numeric_elements.append(NumericElementInfo(
            idx=idx,
            element_id=element_id,
            page=page,
            number=n,
            is_page_range=is_range,
            abstract_pos=abstract_pos,
            text=text,
            segment=segment,
        ))

    # Post-process: bbox/layout-aware tagging where we can do it safely (repetition + page-number).
    for idx, elem in enumerate(elements):
        pred = predictions[idx]
        subtype = pred.subtype or {}
        if isinstance(subtype, dict) and "source_role" in subtype:
            continue  # role-first is authoritative

        if (elem.get("kind") or "").strip() != "text":
            continue
        layout = elem.get("layout") or {}
        if not isinstance(layout, dict):
            continue
        y = layout.get("y")
        if not isinstance(y, (int, float)):
            continue

        text = (elem.get("text") or "").strip()
        sig = _sig(text)

        # Page numbers: numeric-only at the bottom is almost always a footer, not a section header.
        n = is_numeric_only(text)
        if n is not None and y >= 0.92 and 1 <= n <= 9999:
            st = dict(subtype) if isinstance(subtype, dict) else {}
            st["page_number"] = n
            predictions[idx] = Prediction(content_type="Page-footer", confidence=max(pred.confidence, 0.9), subtype=st)
            continue

        # Page range indicators at the top (e.g., "6-8" / "6–8") are headers, not Titles.
        # NOTE: These will also be processed by pattern detection, which may override with higher confidence
        if y <= 0.08 and looks_like_page_range(text):
            predictions[idx] = Prediction(content_type="Page-header", confidence=max(pred.confidence, 0.85), subtype=pred.subtype)
            continue

        if sig in header_sigs:
            predictions[idx] = Prediction(content_type="Page-header", confidence=max(pred.confidence, 0.9), subtype=pred.subtype)
            continue
        if sig in footer_sigs:
            predictions[idx] = Prediction(content_type="Page-footer", confidence=max(pred.confidence, 0.9), subtype=pred.subtype)
    
    # NEW: Pattern-based classification for numeric elements at margins
    # (runs after initial post-processing, can override with higher confidence)
    # Patterns should be detected separately per macro segment (frontmatter/gameplay/endmatter)
    # to avoid mixing patterns from different segments
    
    # Get unique segments from numeric elements (if segment_map was loaded)
    segments = sorted(set(e.segment for e in numeric_elements if e.segment))
    if not segments:
        # No segment information available - process all together (backward compatibility)
        segments = [None]
    
    all_sequential_patterns: Dict[int, Dict[str, Any]] = {}
    all_other_patterns: Dict[int, Dict[str, Any]] = {}
    all_matched_indices: set = set()
    
    # Process each segment separately
    for segment in segments:
        # Step 2: Detect sequential page numbers (highest priority) for this segment
        sequential_patterns = detect_sequential_page_numbers(
            numeric_elements, 
            min_sequence_length=3,
            segment_filter=segment
        )
        all_sequential_patterns.update(sequential_patterns)
        all_matched_indices.update(sequential_patterns.keys())
        
        # Step 3: Detect other header/footer patterns (lower priority) for this segment
        other_patterns = detect_other_header_footer_patterns(
            numeric_elements, 
            all_matched_indices, 
            min_repeats=min_repeats,
            segment_filter=segment
        )
        all_other_patterns.update(other_patterns)
        all_matched_indices.update(other_patterns.keys())
    
    # Combine results from all segments
    sequential_patterns = all_sequential_patterns
    matched_indices = all_matched_indices
    other_patterns = all_other_patterns
    
    # Step 4: Apply pattern-based overrides
    pattern_debug_log: List[Dict[str, Any]] = []
    all_patterns = {**sequential_patterns, **other_patterns}
    
    for idx, pattern_info in all_patterns.items():
        if idx >= len(predictions):
            continue
        
        pred = predictions[idx]
        elem = elements[idx]
        
        # Override only if pattern confidence is higher than current
        pattern_conf = pattern_info["confidence"]
        if pattern_conf > pred.confidence:
            new_content_type = pattern_info["content_type"]
            
            # Update subtype if needed
            subtype = dict(pred.subtype) if isinstance(pred.subtype, dict) else {}
            if pattern_info["content_type"] == "Page-footer" and "page_number" not in subtype:
                subtype["page_number"] = numeric_elements[next(i for i, e in enumerate(numeric_elements) if e.idx == idx)].number
            
            predictions[idx] = Prediction(
                content_type=new_content_type,
                confidence=pattern_conf,
                subtype=subtype if subtype else None
            )
            
            # Log for debug artifact
            pattern_debug_log.append({
                "element_id": elem.get("id") or elem.get("element_id"),
                "page": elem.get("page"),
                "text": elem.get("text", "")[:50],
                "original_type": pred.content_type,
                "original_confidence": pred.confidence,
                "pattern_type": pattern_info["pattern_type"],
                "new_type": new_content_type,
                "new_confidence": pattern_conf,
                "pattern_info": pattern_info.get("pattern_info", {}),
            })
    
    # Write pattern debug artifact
    if args.patterns_out and pattern_debug_log:
        for entry in pattern_debug_log:
            append_jsonl(args.patterns_out, entry)

    # Top-of-page title nudge: if the top-most element is near the top and not a repeating header,
    # treat it as a Title when heuristics were otherwise uncertain.
    for page, idx in top_text_idx_by_page.items():
        elem = elements[idx]
        pred = predictions[idx]
        if pred.content_type not in {"Text", "Section-header"} or pred.confidence >= 0.8:
            continue
        layout = elem.get("layout") or {}
        if not isinstance(layout, dict):
            continue
        y = layout.get("y")
        if not isinstance(y, (int, float)) or y > 0.08:
            continue
        text = (elem.get("text") or "").strip()
        if not text:
            continue
        if _sig(text) in header_sigs:
            continue
        if is_numeric_only(text) is not None:
            continue
        if looks_like_list_item(text) or looks_like_toc_entry(text) or looks_like_table(text):
            continue
        predictions[idx] = Prediction(content_type="Title", confidence=max(pred.confidence, 0.75), subtype=pred.subtype)

    if args.use_llm and ambiguous:
        client = OpenAI(timeout=60.0)
        items: List[Dict[str, Any]] = []
        for idx in ambiguous:
            elem = elements[idx]
            seq = elem.get("seq")
            page = elem.get("page")
            text = elem.get("text") or ""
            ctx_before: List[str] = []
            ctx_after: List[str] = []
            for k in range(1, args.context_window + 1):
                if idx - k >= 0:
                    ctx_before.append((elements[idx - k].get("text") or "").strip())
                if idx + k < len(elements):
                    ctx_after.append((elements[idx + k].get("text") or "").strip())
            items.append(
                {
                    "seq": seq,
                    "page": page,
                    "text": text,
                    "prev": list(reversed(ctx_before)),
                    "next": ctx_after,
                }
            )

        for batch in batch_items(items, args.batch_size):
            results = llm_classify(client, args.model, batch)
            for row in batch:
                seq = row.get("seq")
                if not isinstance(seq, int):
                    continue
                out_row = results.get(seq)
                if not out_row:
                    continue
                label = out_row.get("content_type")
                conf = out_row.get("content_type_confidence")
                subtype = out_row.get("content_subtype")
                if not isinstance(label, str):
                    continue
                if args.coarse_only:
                    label = pub_map(label)
                if not doc_label_ok(label, args.allow_extensions) and not args.coarse_only:
                    continue
                if not isinstance(conf, (int, float)):
                    conf = 0.5
                idx0 = seq_to_index.get(seq)
                if idx0 is None:
                    continue
                predictions[idx0] = Prediction(content_type=label, confidence=float(conf), subtype=subtype if isinstance(subtype, dict) else None)

    per_page_counts: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    per_page_low: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for elem, pred in zip(elements, predictions):
        page = elem.get("page")
        if isinstance(page, int):
            per_page_counts[page][pred.content_type] += 1
            if pred.confidence < 0.7 and len(per_page_low[page]) < 8:
                per_page_low[page].append(
                    {
                        "seq": elem.get("seq"),
                        "text": (elem.get("text") or "")[:160],
                        "content_type": pred.content_type,
                        "confidence": pred.confidence,
                    }
                )

        out_row = dict(elem)
        out_row["content_type"] = pred.content_type
        out_row["content_type_confidence"] = pred.confidence
        if pred.subtype is not None:
            out_row["content_subtype"] = pred.subtype
        append_jsonl(args.out, out_row)

    if args.debug_out:
        pages = sorted(per_page_counts.keys())
        for page in pages:
            append_jsonl(
                args.debug_out,
                {
                    "page": page,
                    "label_counts": dict(per_page_counts[page]),
                    "low_conf_samples": per_page_low.get(page, []),
                },
            )


if __name__ == "__main__":
    main()
