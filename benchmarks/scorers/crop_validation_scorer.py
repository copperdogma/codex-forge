"""
Crop quality validation scorer for promptfoo.

Binary classification scorer: compares VLM pass/fail verdict
against golden labels in crop-validation.json.

Metrics surfaced in reason string:
- classification: TP, FP, TN, FN
- VLM's reasoning (for debugging prompt quality)
- Score: 1.0 if correct, 0.0 if wrong
"""

import json
import os
import re
from typing import Any


def _parse_json(text: str) -> dict | None:
    """Extract JSON from model output, handling markdown fences and thinking."""
    text = text.strip()
    # Strip markdown code fences
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    else:
        # Try to find bare JSON object
        m2 = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if m2:
            text = m2.group(0)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_verdict(parsed: dict) -> str | None:
    """Extract verdict from parsed VLM output, handling various formats."""
    if not parsed:
        return None
    verdict = parsed.get("verdict", "").lower().strip()
    if verdict in ("pass", "fail"):
        return verdict
    return None


def get_assert(output: str, context: dict) -> dict:
    """Score crop validation output against golden labels.

    Expected context vars:
        - crop_key: key in crop-validation.json (e.g., "page-018-000")
    """
    # --- Load golden data ---
    crop_key = context["vars"].get("crop_key", "")
    scorer_dir = os.path.dirname(os.path.abspath(__file__))
    benchmarks_dir = os.path.dirname(scorer_dir)
    golden_path = os.path.join(benchmarks_dir, "golden", "crop-validation.json")

    try:
        with open(golden_path) as f:
            all_golden = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return {"pass": False, "score": 0.0, "reason": f"Cannot load golden data: {e}"}

    if crop_key not in all_golden:
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"Golden key '{crop_key}' not found in crop-validation.json",
        }

    golden = all_golden[crop_key]
    golden_verdict = golden["verdict"]  # "pass" or "fail"

    # --- Parse model output ---
    parsed = _parse_json(output)
    if parsed is None:
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"Failed to parse JSON from model output. Raw: {output[:200]}",
        }

    vlm_verdict = _extract_verdict(parsed)
    if vlm_verdict is None:
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"No valid verdict in model output. Parsed: {parsed}",
        }

    vlm_reason = parsed.get("reason", "no reason given")

    # --- Classification ---
    correct = vlm_verdict == golden_verdict

    if golden_verdict == "fail" and vlm_verdict == "fail":
        classification = "TP"  # True Positive: correctly caught bad crop
    elif golden_verdict == "pass" and vlm_verdict == "pass":
        classification = "TN"  # True Negative: correctly approved good crop
    elif golden_verdict == "pass" and vlm_verdict == "fail":
        classification = "FP"  # False Positive: wrongly rejected good crop
    else:  # golden_verdict == "fail" and vlm_verdict == "pass"
        classification = "FN"  # False Negative: missed bad crop

    score = 1.0 if correct else 0.0

    # --- Extra details from structured outputs ---
    extras = []
    if "has_external_text" in parsed:
        extras.append(f"has_external_text={parsed['has_external_text']}")
    if "blank_pct" in parsed:
        extras.append(f"blank_pct={parsed['blank_pct']}")
    if "image_pct" in parsed:
        extras.append(f"image_pct={parsed['image_pct']}")
    if "image_type" in parsed:
        extras.append(f"type={parsed['image_type']}")
    if "completeness" in parsed:
        extras.append(
            f"scores=[C={parsed.get('completeness')},T={parsed.get('text_free')},"
            f"Tight={parsed.get('tightness')},Cont={parsed.get('content')}]"
        )

    extra_str = f" | {', '.join(extras)}" if extras else ""

    reason = (
        f"{classification} | "
        f"golden={golden_verdict} vlm={vlm_verdict} | "
        f"vlm_reason=\"{vlm_reason}\""
        f"{extra_str}"
    )

    if golden.get("notes"):
        reason += f" | golden_notes=\"{golden['notes'][:80]}\""

    return {"pass": correct, "score": round(score, 4), "reason": reason}
