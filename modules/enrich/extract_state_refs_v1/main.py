#!/usr/bin/env python3
import argparse
import base64
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from modules.common.html_utils import html_to_text
from schemas import EnrichedPortion, StateValue, StateCheck

MAP_REFERENCE_VALUE_PAT = re.compile(
    r"\bmap reference is\s+([0-9]{1,3}X{0,2}|[0-9]{1,3})\b",
    re.IGNORECASE,
)
MAP_REFERENCE_TURN_PAT = re.compile(r"\bturn to (?:the )?map reference\b", re.IGNORECASE)
PLACEHOLDER_TURN_PAT = re.compile(r"\bturn\s+to\s+([0-9]*X+)\b", re.IGNORECASE)
MISSING_TARGET_PAT = re.compile(
    r"\b(?:if (?:you have not|you do not|you don't|not|you have no)|otherwise)\b[^.]{0,160}\bturn to\s+(\d{1,3})\b",
    re.IGNORECASE,
)
CANNOT_VISIT_PAT = re.compile(r"([^.]*\b(?:may not|cannot|can't|must not)\b[^.]*\.)", re.IGNORECASE)
LOCATION_PAT = re.compile(r"\b(City of (?:the )?[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\b")
QUOTED_WORD_PAT = re.compile(r"[\"'‘’]([^\"'’]+)[\"'’]")
COUNTERSIGN_PASSWORD_PAT = re.compile(
    r"[\"'‘’]([A-Za-z-]+)[\"'’].{0,40}\bpassword\b",
    re.IGNORECASE,
)
COUNTERSIGN_CHECK_PAT = re.compile(
    r"\bcountersign\b[^.]{0,160}\bturn to (?:that number|the number of the countersign)\b",
    re.IGNORECASE,
)
FLASK_POTION_PAT = re.compile(r"\bflask of (?:the )?([A-Za-z]+)\s+potion\b", re.IGNORECASE)
FLASK_LETTER_COUNT_PAT = re.compile(
    r"\bcount the letters in both words of its name\b[^.]{0,120}\bmultiply that number by 10\b",
    re.IGNORECASE,
)
REFERENCE_NUMBER_VALUE_PAT = re.compile(r"\breference number of the (?:book|volume) is\s+(\d{1,3})\b", re.IGNORECASE)
REFERENCE_NUMBER_CHECK_PAT = re.compile(r"\bturn to the reference number that came with that information\b", re.IGNORECASE)
MODEL_NUMBER_CHECK_PAT = re.compile(r"\b([A-Za-z]+(?:\s+[A-Za-z]+)*)'s model number\b.*turn to that reference number\b", re.IGNORECASE)
WASP_MODEL_PAT = re.compile(r"\bWasp\s+(\d{2,3})\b", re.IGNORECASE)
MODEL_NUMBER_VALUE_PAT = re.compile(r"\bModel\s+(\d{1,3})\b", re.IGNORECASE)
MODEL_NUMBER_ADD_OFFSET_PAT = re.compile(
    r"\badd\s+(\d{1,3})\s+to\s+(?:its|the)\s+model number\b[^.]{0,120}\bturn to\b",
    re.IGNORECASE,
)

WORD_NUM = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
}

STRICT_MAPREF_PROMPT = """You are reading a Fighting Fantasy gamebook page.
Return JSON: { "value": "<digits>", "confidence": <0-1 float> }.
Rules:
- Extract the numeric map reference value (1-3 digits).
- Use the image as ground truth; ignore OCR if it conflicts.
- If the map reference is unclear, return value \"\" and confidence 0.
"""

try:
    from modules.common.openai_client import OpenAI
except ImportError:
    OpenAI = None


def _normalize_key(base: str, location: Optional[str]) -> str:
    if not location:
        return base
    slug = re.sub(r"[^a-z0-9]+", "_", location.strip().lower())
    slug = slug.strip("_")
    if not slug:
        return base
    return f"{base}_{slug}"


def _extract_location(text: str) -> Optional[str]:
    if not text:
        return None
    match = LOCATION_PAT.search(text)
    if not match:
        return None
    return match.group(1).strip()


def _sentence_at(text: str, pos: int) -> str:
    if not text:
        return ""
    start = max(text.rfind(".", 0, pos), text.rfind("?", 0, pos), text.rfind("!", 0, pos), text.rfind("\n", 0, pos))
    end_candidates = [i for i in (text.find(".", pos), text.find("?", pos), text.find("!", pos), text.find("\n", pos)) if i != -1]
    end = min(end_candidates) if end_candidates else len(text)
    return text[start + 1:end].strip()


def _normalize_key_from_token(prefix: str, token: Optional[str]) -> str:
    if not token:
        return prefix
    slug = re.sub(r"[^a-z0-9]+", "_", token.strip().lower())
    slug = slug.strip("_")
    if not slug:
        return prefix
    return f"{prefix}_{slug}"


def _word_to_number(token: str) -> Optional[int]:
    if not token:
        return None
    lower = token.strip().lower()
    if lower.isdigit():
        return int(lower)
    return WORD_NUM.get(lower)


def _choice_text_before(text: str, pos: int) -> Optional[str]:
    if not text:
        return None
    line_start = text.rfind("\n", 0, pos)
    line = text[line_start + 1:pos].strip()
    if line:
        return line
    prev_line_end = line_start
    prev_line_start = text.rfind("\n", 0, prev_line_end)
    if prev_line_start != -1:
        prev_line = text[prev_line_start + 1:prev_line_end].strip()
        if prev_line:
            return prev_line
    return None


def _template_target(raw: str) -> Optional[str]:
    if not raw:
        return None
    upper = raw.strip().upper()
    if "X" not in upper:
        return None
    prefix_match = re.match(r"^(\d+)", upper)
    prefix = prefix_match.group(1) if prefix_match else ""
    return f"{prefix}{{state}}"


def _find_condition_text(text: str, location: Optional[str]) -> Optional[str]:
    if not text:
        return None
    for match in CANNOT_VISIT_PAT.finditer(text):
        sentence = match.group(1).strip()
        if not location or (location and location.lower() in sentence.lower()):
            return sentence
    return None


def _extract_state_refs(text: str, *, map_ref_override: Optional[str] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not text:
        return [], []

    state_values: List[Dict[str, Any]] = []
    state_checks: List[Dict[str, Any]] = []
    seen_values: set = set()
    seen_checks: set = set()

    for match in MAP_REFERENCE_VALUE_PAT.finditer(text):
        value = match.group(1).strip()
        if map_ref_override and "X" in value:
            value = map_ref_override
        sentence = _sentence_at(text, match.start())
        location = _extract_location(sentence) or _extract_location(text)
        key = _normalize_key("map_reference", location)
        ident = (key, value)
        if ident in seen_values:
            continue
        seen_values.add(ident)
        state_values.append({
            "key": key,
            "value": value,
            "confidence": 0.9,
            "source_text": sentence or match.group(0),
        })

    for match in MAP_REFERENCE_TURN_PAT.finditer(text):
        sentence = _sentence_at(text, match.start())
        location = _extract_location(sentence) or _extract_location(text)
        key = _normalize_key("map_reference", location)
        missing = None
        missing_match = MISSING_TARGET_PAT.search(text)
        if missing_match:
            missing = missing_match.group(1)
        ident = (key, "{state}", missing)
        if ident in seen_checks:
            continue
        seen_checks.add(ident)
        state_checks.append({
            "key": key,
            "condition_text": sentence or "map reference state check",
            "template_target": "{state}",
            "missing_target": missing,
            "confidence": 0.8,
        })

    for match in PLACEHOLDER_TURN_PAT.finditer(text):
        raw_target = match.group(1)
        template = _template_target(raw_target)
        if not template:
            continue
        choice_text = _choice_text_before(text, match.start())
        location = _extract_location(choice_text or "") or _extract_location(text)
        key = _normalize_key("map_reference", location)
        condition_text = _find_condition_text(text, location)
        ident = (key, template, choice_text)
        if ident in seen_checks:
            continue
        seen_checks.add(ident)
        state_checks.append({
            "key": key,
            "condition_text": condition_text,
            "template_target": template,
            "choice_text": choice_text,
            "confidence": 0.8,
        })

    _extract_countersign_state(text, state_values, state_checks, seen_values, seen_checks)
    _extract_flask_state(text, state_values, state_checks, seen_values, seen_checks)
    _extract_reference_number_state(text, state_values, state_checks, seen_values, seen_checks)
    _extract_model_number_state(text, state_values, state_checks, seen_values, seen_checks)

    return state_values, state_checks


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def _resolve_map_reference(
    portion: Dict[str, Any],
    text: str,
    *,
    client,
    model: str,
    max_images: int,
) -> Optional[str]:
    if not text or not MAP_REFERENCE_VALUE_PAT.search(text):
        return None
    match = MAP_REFERENCE_VALUE_PAT.search(text)
    if not match:
        return None
    value = match.group(1).strip()
    if "X" not in value:
        return None
    images = portion.get("source_images") or []
    if not images or client is None:
        return None
    content = [{"type": "text", "text": "Find the numeric map reference value on this page."}]
    for img in images[:max_images]:
        content.append({"type": "image_url", "image_url": {"url": _encode_image(img)}})
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": STRICT_MAPREF_PROMPT},
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
    )
    try:
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception:
        return None
    raw = str(data.get("value") or "").strip()
    if raw.isdigit():
        return raw
    return None


def _extract_countersign_state(
    text: str,
    state_values: List[Dict[str, Any]],
    state_checks: List[Dict[str, Any]],
    seen_values: set,
    seen_checks: set,
) -> None:
    if not text or "countersign" not in text.lower():
        return
    password = None
    password_match = COUNTERSIGN_PASSWORD_PAT.search(text)
    if password_match:
        password = password_match.group(1)
    quoted = QUOTED_WORD_PAT.findall(text)
    cleaned = []
    for token in quoted:
        cleaned_token = re.sub(r"[^A-Za-z-]", "", token)
        if cleaned_token:
            cleaned.append(cleaned_token)
    if cleaned and not password:
        password = cleaned[0]
    if len(cleaned) >= 2:
        reply = cleaned[1]
        value_num = _word_to_number(reply)
        value = str(value_num) if value_num is not None else reply
        key = _normalize_key_from_token("countersign", password)
        ident = (key, value)
        if ident not in seen_values:
            seen_values.add(ident)
            state_values.append({
                "key": key,
                "value": value,
                "confidence": 0.9,
                "source_text": _sentence_at(text, text.lower().find("countersign")),
            })
    if COUNTERSIGN_CHECK_PAT.search(text):
        key = _normalize_key_from_token("countersign", password)
        missing = None
        missing_match = MISSING_TARGET_PAT.search(text)
        if missing_match:
            missing = missing_match.group(1)
        ident = (key, "{state}", missing)
        if ident in seen_checks:
            return
        seen_checks.add(ident)
        state_checks.append({
            "key": key,
            "condition_text": _sentence_at(text, text.lower().find("countersign")),
            "template_target": "{state}",
            "missing_target": missing,
            "confidence": 0.8,
        })


def _extract_flask_state(
    text: str,
    state_values: List[Dict[str, Any]],
    state_checks: List[Dict[str, Any]],
    seen_values: set,
    seen_checks: set,
) -> None:
    if not text:
        return
    for match in FLASK_POTION_PAT.finditer(text):
        color = match.group(1)
        if not color:
            continue
        letter_count = len(color.strip()) + len("Potion")
        key = "flask_letter_count"
        value = str(letter_count)
        ident = (key, value)
        if ident in seen_values:
            continue
        seen_values.add(ident)
        state_values.append({
            "key": key,
            "value": value,
            "confidence": 0.8,
            "source_text": _sentence_at(text, match.start()),
        })

    if FLASK_LETTER_COUNT_PAT.search(text):
        key = "flask_letter_count"
        missing = None
        missing_match = MISSING_TARGET_PAT.search(text)
        if missing_match:
            missing = missing_match.group(1)
        ident = (key, "{state}0", missing)
        if ident in seen_checks:
            return
        seen_checks.add(ident)
        state_checks.append({
            "key": key,
            "condition_text": _sentence_at(text, text.lower().find("count the letters")),
            "template_target": "{state}0",
            "missing_target": missing,
            "confidence": 0.8,
        })


def _extract_reference_number_state(
    text: str,
    state_values: List[Dict[str, Any]],
    state_checks: List[Dict[str, Any]],
    seen_values: set,
    seen_checks: set,
) -> None:
    if not text:
        return
    for match in REFERENCE_NUMBER_VALUE_PAT.finditer(text):
        value = match.group(1).strip()
        key = "reference_number"
        ident = (key, value)
        if ident in seen_values:
            continue
        seen_values.add(ident)
        state_values.append({
            "key": key,
            "value": value,
            "confidence": 0.8,
            "source_text": _sentence_at(text, match.start()),
        })
    if REFERENCE_NUMBER_CHECK_PAT.search(text):
        key = "reference_number"
        missing = None
        missing_match = MISSING_TARGET_PAT.search(text)
        if missing_match:
            missing = missing_match.group(1)
        ident = (key, "{state}", missing)
        if ident in seen_checks:
            return
        seen_checks.add(ident)
        state_checks.append({
            "key": key,
            "condition_text": _sentence_at(text, text.lower().find("reference number")),
            "template_target": "{state}",
            "missing_target": missing,
            "confidence": 0.8,
        })


def _extract_model_number_state(
    text: str,
    state_values: List[Dict[str, Any]],
    state_checks: List[Dict[str, Any]],
    seen_values: set,
    seen_checks: set,
) -> None:
    if not text:
        return
    for match in MODEL_NUMBER_VALUE_PAT.finditer(text):
        value = match.group(1).strip()
        if not value:
            continue
        sentence = _sentence_at(text, match.start())
        span_start = max(0, match.start() - 80)
        span_end = min(len(text), match.end() + 80)
        nearby = text[span_start:span_end]
        quoted = QUOTED_WORD_PAT.findall(nearby)
        if quoted:
            name = quoted[-1]
            key = _normalize_key_from_token("model_number", name)
            ident = (key, value)
            if ident not in seen_values:
                seen_values.add(ident)
                state_values.append({
                    "key": key,
                    "value": value,
                    "confidence": 0.75,
                    "source_text": sentence or match.group(0),
                })
        key = "model_number"
        ident = (key, value)
        if ident not in seen_values:
            seen_values.add(ident)
            state_values.append({
                "key": key,
                "value": value,
                "confidence": 0.7,
                "source_text": sentence or match.group(0),
            })
    for match in WASP_MODEL_PAT.finditer(text):
        value = match.group(1).strip()
        key = "model_number_wasp_fighter"
        ident = (key, value)
        if ident in seen_values:
            continue
        seen_values.add(ident)
        state_values.append({
            "key": key,
            "value": value,
            "confidence": 0.8,
            "source_text": _sentence_at(text, match.start()),
        })
    model_check = MODEL_NUMBER_CHECK_PAT.search(text)
    if model_check:
        name = model_check.group(1)
        name = re.sub(r"^\s*if\s+you\s+know\s+", "", name, flags=re.IGNORECASE)
        name = re.sub(r"^\s*the\s+", "", name, flags=re.IGNORECASE)
        key = _normalize_key_from_token("model_number", name)
        missing = None
        missing_match = MISSING_TARGET_PAT.search(text)
        if missing_match:
            missing = missing_match.group(1)
        ident = (key, "{state}", missing)
        if ident in seen_checks:
            return
        seen_checks.add(ident)
        state_checks.append({
            "key": key,
            "condition_text": _sentence_at(text, model_check.start()),
            "template_target": "{state}",
            "missing_target": missing,
            "confidence": 0.8,
        })

    offset_match = MODEL_NUMBER_ADD_OFFSET_PAT.search(text)
    if offset_match:
        offset = offset_match.group(1)
        missing = None
        missing_match = MISSING_TARGET_PAT.search(text)
        if missing_match:
            missing = missing_match.group(1)
        key = "model_number"
        ident = (key, "{state}", "add", offset, missing)
        if ident not in seen_checks:
            seen_checks.add(ident)
            state_checks.append({
                "key": key,
                "condition_text": _sentence_at(text, offset_match.start()),
                "template_target": "{state}",
                "template_op": "add",
                "template_value": offset,
                "missing_target": missing,
                "confidence": 0.8,
            })


def _merge_state_items(existing: List[Dict[str, Any]], added: List[Dict[str, Any]], keys: Tuple[str, ...]) -> List[Dict[str, Any]]:
    merged = []
    seen = set()
    for item in existing + added:
        if not isinstance(item, dict):
            continue
        ident = tuple(item.get(k) for k in keys)
        if ident in seen:
            continue
        seen.add(ident)
        merged.append(item)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract state values and templated navigation references")
    parser.add_argument("--portions", required=True, help="Input portions JSONL")
    parser.add_argument("--pages", help="(optional) pages JSONL; unused")
    parser.add_argument("--out", required=True, help="Output JSONL")
    parser.add_argument("--state-file", dest="state_file")
    parser.add_argument("--progress-file", dest="progress_file")
    parser.add_argument("--run-id")
    parser.add_argument("--map-ref-escalate", "--map_ref_escalate", action="store_true",
                        help="Use vision escalation to resolve ambiguous map reference values (e.g., 2X).")
    parser.add_argument("--map-ref-escalation-model", "--map_ref_escalation_model", default="gpt-5.2",
                        help="Model to use for map reference escalation.")
    parser.add_argument("--map-ref-max-images", "--map_ref_max_images", type=int, default=2,
                        help="Max images to send for map reference escalation.")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    portions = list(read_jsonl(args.portions))
    out: List[Dict[str, Any]] = []

    client = OpenAI() if args.map_ref_escalate and OpenAI else None

    for idx, portion in enumerate(portions):
        if not isinstance(portion, dict):
            continue
        raw_html = portion.get("raw_html") or ""
        raw_text = portion.get("raw_text") or ""
        text = html_to_text(raw_html) if raw_html else raw_text

        map_ref_override = None
        if args.map_ref_escalate:
            map_ref_override = _resolve_map_reference(
                portion,
                text,
                client=client,
                model=args.map_ref_escalation_model,
                max_images=args.map_ref_max_images,
            )
        state_values, state_checks = _extract_state_refs(text, map_ref_override=map_ref_override)

        existing_values = portion.get("state_values") or []
        existing_checks = portion.get("state_checks") or []

        merged_values = _merge_state_items(existing_values, state_values, ("key", "value"))
        merged_checks = _merge_state_items(
            existing_checks,
            state_checks,
            ("key", "template_target", "template_op", "template_value", "choice_text", "missing_target"),
        )

        portion["state_values"] = merged_values
        portion["state_checks"] = merged_checks

        try:
            EnrichedPortion(**portion)
        except Exception:
            pass

        out.append(portion)

        if (idx + 1) % 100 == 0:
            logger.log(
                "extract_state_refs",
                "running",
                current=idx + 1,
                total=len(portions),
                message=f"Processed {idx + 1}/{len(portions)} portions",
                module_id="extract_state_refs_v1",
                artifact=args.out,
                schema_version="enriched_portion_v1",
            )

    save_jsonl(args.out, out)
    logger.log(
        "extract_state_refs",
        "done",
        current=len(out),
        total=len(out),
        message=f"Wrote {len(out)} portions",
        module_id="extract_state_refs_v1",
        artifact=args.out,
        schema_version="enriched_portion_v1",
    )


if __name__ == "__main__":
    main()
