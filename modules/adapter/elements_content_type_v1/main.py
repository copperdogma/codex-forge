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

from openai import OpenAI

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
        if len(text) > 90:
            continue
        if is_numeric_only(text) is not None:
            continue
        if looks_like_list_item(text) or looks_like_toc_entry(text):
            continue
        if not re.search(r"[A-Za-z]", text):
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
        if y <= 0.08 and looks_like_page_range(text):
            predictions[idx] = Prediction(content_type="Page-header", confidence=max(pred.confidence, 0.85), subtype=pred.subtype)
            continue

        if sig in header_sigs:
            predictions[idx] = Prediction(content_type="Page-header", confidence=max(pred.confidence, 0.9), subtype=pred.subtype)
            continue
        if sig in footer_sigs:
            predictions[idx] = Prediction(content_type="Page-footer", confidence=max(pred.confidence, 0.9), subtype=pred.subtype)

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
