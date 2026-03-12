"""
Image crop extraction scorer for promptfoo.

Scores model output against golden bounding boxes using:
- box_count: Did the model find the right number of images?
- iou_mean: Mean IoU across matched predicted <-> golden boxes
- iou_min: Worst-case IoU (catches one bad crop among good ones)
- bbox_coverage: Do predicted boxes cover the full golden region?

Weights are tunable. Pass threshold: weighted score >= 0.70.
"""

import json
import os
import re
import sys
from typing import Any


def _parse_json(text: str) -> dict | list | None:
    """Extract JSON from model output, handling markdown fences and arrays."""
    # Strip markdown code fences
    text = text.strip()
    # Try to find JSON in ```json ... ``` blocks (object or array)
    m = re.search(r"```(?:json)?\s*([\{\[].*?[\}\]])\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    else:
        # Try bare JSON object
        m2 = re.search(r"\{.*\}", text, re.DOTALL)
        # Try bare JSON array
        m3 = re.search(r"\[.*\]", text, re.DOTALL)
        if m2:
            text = m2.group(0)
        elif m3:
            text = m3.group(0)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _iou(box_a: list[float], box_b: list[float]) -> float:
    """Compute IoU between two [x0, y0, x1, y1] boxes (normalized coords)."""
    x0 = max(box_a[0], box_b[0])
    y0 = max(box_a[1], box_b[1])
    x1 = min(box_a[2], box_b[2])
    y1 = min(box_a[3], box_b[3])

    inter_w = max(0.0, x1 - x0)
    inter_h = max(0.0, y1 - y0)
    inter_area = inter_w * inter_h

    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])

    union_area = area_a + area_b - inter_area
    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def _match_boxes_greedy(
    predicted: list[list[float]], golden: list[list[float]]
) -> list[tuple[int, int, float]]:
    """Greedy match predicted boxes to golden boxes by highest IoU.

    Returns list of (pred_idx, gold_idx, iou) tuples.
    Unmatched boxes are not included.
    """
    if not predicted or not golden:
        return []

    # Compute all pairwise IoUs
    pairs = []
    for pi, pb in enumerate(predicted):
        for gi, gb in enumerate(golden):
            iou_val = _iou(pb, gb)
            if iou_val > 0:
                pairs.append((iou_val, pi, gi))

    # Sort by IoU descending and greedily assign
    pairs.sort(reverse=True)
    used_pred = set()
    used_gold = set()
    matches = []

    for iou_val, pi, gi in pairs:
        if pi not in used_pred and gi not in used_gold:
            matches.append((pi, gi, iou_val))
            used_pred.add(pi)
            used_gold.add(gi)

    return matches


def _normalize_scale(box: list[float]) -> list[float]:
    """If any coordinate > 1.0, assume 0-1000 scale and normalize to 0-1."""
    if any(v > 1.0 for v in box):
        return [v / 1000.0 for v in box]
    return list(box)


def _swap_axes(box: list[float]) -> list[float]:
    """Convert [y0, x0, y1, x1] -> [x0, y0, x1, y1]."""
    return [box[1], box[0], box[3], box[2]]


def _ensure_order(box: list[float]) -> list[float]:
    """Ensure x0 <= x1 and y0 <= y1."""
    x0, y0, x1, y1 = box
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def _auto_normalize_boxes(
    predicted: list[list[float]], golden: list[list[float]]
) -> list[list[float]]:
    """Try standard and axis-swapped interpretations, pick the one with better IoU."""
    if not predicted or not golden:
        return predicted

    # Candidate interpretations: (label, transform_fn)
    def as_standard(box):
        return _ensure_order(_normalize_scale(box))

    def as_swapped(box):
        return _ensure_order(_swap_axes(_normalize_scale(box)))

    # Score each interpretation against golden boxes
    best_interp = None
    best_total_iou = -1.0

    for transform in (as_standard, as_swapped):
        candidate = [transform(b) for b in predicted]
        matches = _match_boxes_greedy(candidate, golden)
        total_iou = sum(m[2] for m in matches)
        if total_iou > best_total_iou:
            best_total_iou = total_iou
            best_interp = candidate

    return best_interp


def get_assert(output: str, context: dict) -> dict:
    """Score image crop extraction output against golden bounding boxes.

    Expected context vars:
        - golden_key: key in image-crops.json (e.g., "Image021")
    """
    # --- Load golden data ---
    golden_key = context["vars"].get("golden_key", "")
    # Resolve golden JSON path relative to this scorer file
    scorer_dir = os.path.dirname(os.path.abspath(__file__))
    benchmarks_dir = os.path.dirname(scorer_dir)
    golden_path = os.path.join(benchmarks_dir, "golden", "image-crops.json")

    try:
        with open(golden_path) as f:
            all_golden = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return {"pass": False, "score": 0.0, "reason": f"Cannot load golden data: {e}"}

    if golden_key not in all_golden:
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"Golden key '{golden_key}' not found in image-crops.json",
        }

    golden_entry = all_golden[golden_key]
    golden_boxes = [c["bbox_normalized"] for c in golden_entry["crops"]]
    n_golden = len(golden_boxes)

    # --- Parse model output ---
    parsed = _parse_json(output)
    if parsed is None:
        return {
            "pass": False,
            "score": 0.0,
            "reason": "Failed to parse JSON from model output",
        }

    # Handle multiple response formats:
    # Standard: {"images": [{bbox: ...}, ...]}
    # Gemini native list: [{box_2d: ...}, ...]
    # Gemini native single: {box_2d: ...}
    if isinstance(parsed, list):
        images = parsed
    elif isinstance(parsed, dict):
        images = parsed.get("images", [])
        if not isinstance(images, list):
            if "box_2d" in parsed:
                images = [parsed]
            else:
                return {
                    "pass": False,
                    "score": 0.0,
                    "reason": f"'images' field is not a list: {type(images).__name__}",
                }
    else:
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"Unexpected parsed type: {type(parsed).__name__}",
        }

    # Extract predicted boxes, normalizing coordinate systems
    predicted_boxes = []
    for img in images:
        # Try standard "bbox", then Gemini's "box_2d", "box_3d", "box_4d", etc.
        bbox = img.get("bbox")
        if not bbox:
            for key in sorted(img.keys()):
                if key.startswith("box_") and isinstance(img[key], list):
                    bbox = img[key]
                    break
        if isinstance(bbox, list) and len(bbox) == 4:
            try:
                predicted_boxes.append([float(v) for v in bbox])
            except (TypeError, ValueError):
                continue

    # Auto-normalize: handle Gemini's native formats
    # 1) Scale: if coords > 1.0, assume 0-1000 scale and divide
    # 2) Axis order: Gemini natively returns [y_min, x_min, y_max, x_max],
    #    try both [x,y,x,y] and [y,x,y,x] interpretations, pick best IoU
    predicted_boxes = _auto_normalize_boxes(predicted_boxes, golden_boxes)

    n_predicted = len(predicted_boxes)

    # --- Score: box_count (0-1) ---
    if n_golden == 0:
        box_count_score = 1.0 if n_predicted == 0 else 0.0
    else:
        # Perfect = 1.0, off by 1 = 0.5, off by 2+ = 0.0
        diff = abs(n_predicted - n_golden)
        box_count_score = max(0.0, 1.0 - diff * 0.5)

    # --- Match and compute IoU ---
    matches = _match_boxes_greedy(predicted_boxes, golden_boxes)
    n_matched = len(matches)

    if n_golden == 0 and n_predicted == 0:
        iou_mean = 1.0
        iou_min = 1.0
    elif n_matched == 0:
        iou_mean = 0.0
        iou_min = 0.0
    else:
        ious = [m[2] for m in matches]
        # Penalize unmatched golden boxes as IoU=0
        while len(ious) < n_golden:
            ious.append(0.0)
        iou_mean = sum(ious) / len(ious)
        iou_min = min(ious)

    # --- Score: coverage (do predicted boxes fully contain golden regions?) ---
    # For each golden box, how much of it is covered by its matched prediction?
    coverage_scores = []
    matched_gold = {m[1]: m[0] for m in matches}
    for gi, gbox in enumerate(golden_boxes):
        if gi in matched_gold:
            pi = matched_gold[gi]
            pbox = predicted_boxes[pi]
            # Intersection area / golden area = recall of golden region
            x0 = max(gbox[0], pbox[0])
            y0 = max(gbox[1], pbox[1])
            x1 = min(gbox[2], pbox[2])
            y1 = min(gbox[3], pbox[3])
            inter = max(0, x1 - x0) * max(0, y1 - y0)
            gold_area = max(1e-9, (gbox[2] - gbox[0]) * (gbox[3] - gbox[1]))
            coverage_scores.append(inter / gold_area)
        else:
            coverage_scores.append(0.0)

    coverage = sum(coverage_scores) / max(1, len(coverage_scores))

    # --- Weighted total ---
    weights = {
        "box_count": 0.15,
        "iou_mean": 0.35,
        "iou_min": 0.15,
        "coverage": 0.35,
    }

    total = (
        weights["box_count"] * box_count_score
        + weights["iou_mean"] * iou_mean
        + weights["iou_min"] * iou_min
        + weights["coverage"] * coverage
    )

    passed = total >= 0.70

    # --- Build reason string ---
    match_details = []
    for pi, gi, iou_val in matches:
        match_details.append(f"pred[{pi}]<->gold[{gi}] IoU={iou_val:.3f}")
    if n_predicted > n_matched:
        match_details.append(f"+{n_predicted - n_matched} extra predicted")
    if n_golden > n_matched:
        match_details.append(f"+{n_golden - n_matched} missed golden")

    reason = (
        f"box_count={box_count_score:.2f} ({n_predicted}/{n_golden}) | "
        f"iou_mean={iou_mean:.3f} | iou_min={iou_min:.3f} | "
        f"coverage={coverage:.3f} | "
        f"total={total:.3f} | "
        f"matches=[{', '.join(match_details)}]"
    )

    return {"pass": passed, "score": round(total, 4), "reason": reason}
