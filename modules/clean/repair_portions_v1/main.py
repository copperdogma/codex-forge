import argparse
import json
import re
from base64 import b64encode
from pathlib import Path
from typing import Dict, List, Tuple, Union

from modules.common.openai_client import OpenAI
from modules.common.utils import (
    ProgressLogger,
    read_jsonl,
    save_json,
    save_jsonl,
)


SYSTEM_PROMPT = """You are restoring the exact wording for one Fighting Fantasy section.
Section ID: {section_id}
Return JSON: {{ "clean_text": "<string>", "confidence": <0-1 float> }}.
Rules:
- Use the supplied page image(s) to transcribe; rely on the current OCR text as fallback.
- Output only section {section_id} (ignore other section numbers on the page).
- Preserve wording, punctuation, dice stats, and choice targets exactly; do NOT invent or summarize.
- If unreadable, return an empty string and confidence 0.
- Keep natural paragraph breaks; remove stray page numbers/headers."""


STRICT_ORPHAN_PROMPT = """You are restoring the exact wording for one Fighting Fantasy section.
Section ID: {section_id}
Return JSON: {{ "clean_text": "<string>", "confidence": <0-1 float> }}.
Rules:
- Use the supplied page image(s) as ground truth; do NOT trust OCR text if it conflicts.
- Output only section {section_id} (ignore other section numbers on the page).
- Pay special attention to any "turn to <number>" targets; the exact digits must match the image.
- If the digits are unclear, return an empty string and confidence 0 (do not guess).
- Preserve wording, punctuation, dice stats, and choice targets exactly; do NOT invent or summarize.
- Keep natural paragraph breaks; remove stray page numbers/headers."""


def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return b64encode(f.read()).decode("utf-8")


def load_portions(path: str) -> Tuple[List[Dict], str]:
    """
    Load portions from jsonl or json (dict or list). Returns (rows, fmt).
    fmt is 'jsonl' or 'json' so we can write back in the same shape.
    """
    if path.endswith(".jsonl"):
        return list(read_jsonl(path)), "jsonl"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        rows = []
        for pid, val in data.items():
            if "portion_id" not in val:
                val["portion_id"] = pid
            rows.append(val)
        return rows, "json"
    if isinstance(data, list):
        return data, "json"
    raise ValueError("Unsupported portions format; expected JSON object, list, or JSONL")


def alpha_ratio(text: str) -> float:
    if not text:
        return 0.0
    alpha = sum(1 for c in text if c.isalpha())
    return alpha / max(len(text), 1)


def digit_ratio(text: str) -> float:
    if not text:
        return 0.0
    digits = sum(1 for c in text if c.isdigit())
    return digits / max(len(text), 1)


def detect_garble(text: str, *, min_chars: int, alpha_thresh: float, max_digit_ratio: float) -> List[str]:
    reasons: List[str] = []
    stripped = text.strip()
    if len(stripped) < min_chars:
        reasons.append(f"short_text({len(stripped)})")
    a_ratio = alpha_ratio(stripped)
    if a_ratio < alpha_thresh:
        reasons.append(f"low_alpha({a_ratio:.2f})")
    d_ratio = digit_ratio(stripped)
    if d_ratio > max_digit_ratio:
        reasons.append(f"digit_heavy({d_ratio:.2f})")
    if "�" in stripped:
        reasons.append("replacement_chars")
    return reasons


def call_llm(
    client: OpenAI,
    portion: Dict,
    section_id: str,
    model: str,
    reasons: List[str],
    max_images: int,
    *,
    system_prompt: str = SYSTEM_PROMPT,
    extra_text: str = "",
) -> Tuple[str, float, Dict]:
    content: List[Dict[str, Union[str, Dict]]] = []
    raw_text = portion.get("raw_text") or portion.get("text") or ""
    reasons_str = ", ".join(reasons)
    prompt_text = f"Section ID: {section_id}\nReasons for repair: {reasons_str}\nCurrent OCR text:\n{raw_text}"
    if extra_text:
        prompt_text = f"{prompt_text}\n\n{extra_text.strip()}"
    content.append({
        "type": "text",
        "text": prompt_text,
    })

    images = portion.get("source_images") or []
    for img_path in images[:max_images]:
        if not img_path or not Path(img_path).exists():
            continue
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{encode_image(img_path)}"}
        })

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt.format(section_id=section_id)},
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
    )
    data = json.loads(completion.choices[0].message.content)
    clean_text = data.get("clean_text", "").strip()
    confidence = float(data.get("confidence", 0.0))
    meta = {"reason": reasons, "model": model, "llm_response": bool(clean_text)}
    return clean_text, confidence, meta


def _patch_html_target(html: str, old: str, new: str) -> str:
    if not html or not old or not new:
        return html
    out = html
    out = out.replace(f'href="#{old}"', f'href="#{new}"')
    out = out.replace(f"Turn to {old}", f"Turn to {new}")
    out = out.replace(f"turn to {old}", f"turn to {new}")
    # Patch anchor inner text if it still shows the old target
    pattern = re.compile(
        rf'(<a\s+[^>]*href=["\']#{re.escape(new)}["\'][^>]*>\s*){re.escape(old)}(\s*</a>)',
        flags=re.IGNORECASE,
    )
    out = pattern.sub(lambda m: f"{m.group(1)}{new}{m.group(2)}", out)
    return out


def _extract_turn_to_links(html: str) -> List[str]:
    if not html:
        return []
    return list({m.group(1) for m in re.finditer(r'href=["\']#\s*(\d+)\s*["\']', html)})


def save_portions(rows: List[Dict], fmt: str, path: str):
    if fmt == "jsonl":
        save_jsonl(path, rows)
    else:
        obj = {str(r.get("portion_id")): r for r in rows}
        save_json(path, obj)


def main():
    parser = argparse.ArgumentParser(description="Repair garbled sections by re-reading page images with an LLM.")
    parser.add_argument("--pages", help="Optional: unused; accepted for compatibility with driver pipelines.", default=None)
    parser.add_argument("--portions", required=True, help="Input portions (json/jsonl). Expects raw_text and source_images.")
    parser.add_argument("--out", required=True, help="Output path; same format as input.")
    parser.add_argument("--model", default="gpt-5", help="Primary multimodal model.")
    parser.add_argument("--boost-model", default=None, dest="boost_model", help="Optional secondary model if confidence is low.")
    parser.add_argument("--min-chars", type=int, default=320, help="Flag sections shorter than this many characters.")
    parser.add_argument("--alpha-threshold", type=float, default=0.72, help="Flag sections with alpha ratio below this.")
    parser.add_argument("--max-digit-ratio", type=float, default=0.38, help="Flag sections with digit ratio above this.")
    parser.add_argument("--min-confidence", "--min_confidence", type=float, default=0.65, help="Re-run with boost model if below this.")
    parser.add_argument("--max-repairs", "--max_repairs", type=int, default=40, help="Cap the number of sections to repair (to control cost).")
    parser.add_argument("--max-images", "--max_images", type=int, default=2, help="Max images to send per section.")
    parser.add_argument("--force-ids", type=str, default="", help="Comma-separated portion IDs to force repair.")
    parser.add_argument("--require-hints", "--require_hints", action="store_true",
                        help="Only repair when repair_hints/forced IDs provide reasons (skip heuristic garble scan).")
    parser.add_argument("--strict-orphan-targets", "--strict_orphan_targets", action="store_true",
                        help="For orphan-similar-target cases, re-run with a strict digit-focused prompt if needed.")
    parser.add_argument("--strict-orphan-model", "--strict_orphan_model", default=None,
                        help="Optional model override for strict orphan target reread.")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    forced = {s.strip() for s in args.force_ids.split(",") if s.strip()}

    rows, fmt = load_portions(args.portions)
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("repair", "running", current=0, total=len(rows),
               message="Scanning portions for garble", artifact=args.out,
               module_id="repair_portions_v1", schema_version="repair_portion_v1")

    client = OpenAI()
    repaired = 0
    repair_reasons: Dict[str, int] = {}
    for idx, row in enumerate(rows, start=1):
        section_id = str(row.get("section_id") or row.get("portion_id") or idx)
        text = row.get("raw_text") or row.get("text") or ""
        hints = row.get("repair_hints") or {}
        reasons = list(hints.get("escalation_reasons") or [])
        flagged_pages = hints.get("flagged_pages") or []
        if flagged_pages and not reasons:
            reasons = ["char_confusion"]
        if not reasons and not args.require_hints:
            reasons = detect_garble(text, min_chars=args.min_chars,
                                    alpha_thresh=args.alpha_threshold,
                                    max_digit_ratio=args.max_digit_ratio)
        if section_id in forced:
            reasons = reasons or ["forced"]

        if reasons and repaired < args.max_repairs:
            # Track reasons for summary
            for reason in reasons:
                repair_reasons[reason] = repair_reasons.get(reason, 0) + 1
            
            try:
                clean_text, conf, meta = call_llm(client, row, section_id, args.model, reasons, args.max_images)
                if conf < args.min_confidence and args.boost_model:
                    clean_text, conf, meta = call_llm(client, row, section_id, args.boost_model, reasons, args.max_images)
                    meta["boosted"] = True
                if args.strict_orphan_targets and "orphan_similar_target" in reasons:
                    hints = row.get("repair_hints") or {}
                    details = hints.get("orphan_similar_target") or []
                    suspect = details[0] if details else {}
                    orphan_id = str(suspect.get("orphan_id") or "")
                    suspect_target = str(suspect.get("suspect_target") or "")
                    if clean_text and suspect_target and suspect_target in clean_text and orphan_id not in clean_text:
                        extra = f"Suspected OCR confusion: orphan_id={orphan_id}, suspect_target={suspect_target}. Re-read from the image and verify the digits."
                        strict_model = args.strict_orphan_model or args.model
                        clean_text, conf, meta = call_llm(
                            client,
                            row,
                            section_id,
                            strict_model,
                            reasons,
                            args.max_images,
                            system_prompt=STRICT_ORPHAN_PROMPT,
                            extra_text=extra,
                        )
                        meta["strict_retry"] = True
                row["raw_text_original"] = text
                row["raw_text"] = clean_text or text
                row["clean_text"] = row["raw_text"]
                if "orphan_similar_target" in reasons:
                    hints = row.get("repair_hints") or {}
                    details = hints.get("orphan_similar_target") or []
                    suspect = details[0] if details else {}
                    orphan_id = str(suspect.get("orphan_id") or "")
                    suspect_target = str(suspect.get("suspect_target") or "")
                    if orphan_id and suspect_target and row.get("raw_html"):
                        # Only patch if the re-read text supports the orphan target
                        if clean_text and (orphan_id in clean_text) and (suspect_target not in clean_text):
                            row["raw_html"] = _patch_html_target(row["raw_html"], suspect_target, orphan_id)
                            row["turn_to_links"] = _extract_turn_to_links(row["raw_html"])
                row["repair"] = {
                    "attempted": True,
                    "applied": bool(clean_text),
                    "confidence": conf,
                    "reason": reasons,
                    "model": meta.get("model"),
                    "boosted": meta.get("boosted", False),
                }
                repaired += 1
            except Exception as exc:  # noqa: BLE001
                row["repair"] = {
                    "attempted": True,
                    "error": str(exc),
                    "reason": reasons,
                    "model": args.model,
                }
        else:
            row["repair"] = {
                "attempted": False,
                "reason": reasons,
            }

        if idx % 25 == 0 or idx == len(rows):
            logger.log("repair", "running", current=idx, total=len(rows),
                       message=f"Repaired {repaired}/{idx} portions",
                       artifact=args.out, module_id="repair_portions_v1")

    save_portions(rows, fmt, args.out)
    
    # Build reason summary for observability
    reason_summary = ", ".join(f"{r}({c})" for r, c in sorted(repair_reasons.items())) if repair_reasons else "none"
    
    logger.log("repair", "done", current=len(rows), total=len(rows),
               message=f"Repaired {repaired} portions: {reason_summary}", artifact=args.out,
               module_id="repair_portions_v1", schema_version="repair_portion_v1")
    print(f"Saved repaired portions → {args.out} (repairs attempted: {repaired})")
    if repair_reasons:
        print(f"  Reasons: {reason_summary}")


if __name__ == "__main__":
    main()
