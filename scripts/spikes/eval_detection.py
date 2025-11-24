"""Evaluate detection JSONL against ground-truth boxes JSONL.

GT format: page,image,width,height,boxes:[{x0,y0,x1,y1,section_id?}]
Det format: page,image,boxes:[{x0,y0,x1,y1,score?}]

Outputs per-image precision/recall/F1 plus micro averages.
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple


def load_jsonl(path: Path) -> Dict[str, Any]:
    data = {}
    with path.open() as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            key = rec.get("page") if rec.get("page") is not None else rec.get("image")
            data[key] = rec
    return data


def iou(a: Dict[str, float], b: Dict[str, float]) -> float:
    x0 = max(a["x0"], b["x0"])
    y0 = max(a["y0"], b["y0"])
    x1 = min(a["x1"], b["x1"])
    y1 = min(a["y1"], b["y1"])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    if inter == 0:
        return 0.0
    area_a = (a["x1"] - a["x0"]) * (a["y1"] - a["y0"])
    area_b = (b["x1"] - b["x0"]) * (b["y1"] - b["y0"])
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def match_boxes(gt_boxes: List[Dict[str, float]], det_boxes: List[Dict[str, float]], iou_thresh: float) -> Tuple[int, int, int]:
    matched_det = set()
    tp = 0
    for gt in gt_boxes:
        best_iou = 0.0
        best_j = None
        for j, det in enumerate(det_boxes):
            if j in matched_det:
                continue
            score = iou(gt, det)
            if score > best_iou:
                best_iou = score
                best_j = j
        if best_iou >= iou_thresh and best_j is not None:
            matched_det.add(best_j)
            tp += 1
    fp = len(det_boxes) - tp
    fn = len(gt_boxes) - tp
    return tp, fp, fn


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gt", required=True, type=Path)
    ap.add_argument("--detections", required=True, type=Path)
    ap.add_argument("--iou", type=float, default=0.5)
    args = ap.parse_args()

    gt = load_jsonl(args.gt)
    det = load_jsonl(args.detections)

    total_tp = total_fp = total_fn = 0
    for key, gt_rec in gt.items():
        gt_boxes = gt_rec.get("boxes", [])
        det_boxes = det.get(key, {}).get("boxes", [])
        tp, fp, fn = match_boxes(gt_boxes, det_boxes, args.iou)
        total_tp += tp
        total_fp += fp
        total_fn += fn
        prec = tp / (tp + fp) if (tp + fp) else 0
        rec = tp / (tp + fn) if (tp + fn) else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
        print(f"{key}: TP={tp} FP={fp} FN={fn} P={prec:.2f} R={rec:.2f} F1={f1:.2f}")

    micro_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0
    micro_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0
    micro_f1 = 2 * micro_prec * micro_rec / (micro_prec + micro_rec) if (micro_prec + micro_rec) else 0
    print("---")
    print(f"Micro: TP={total_tp} FP={total_fp} FN={total_fn} P={micro_prec:.2f} R={micro_rec:.2f} F1={micro_f1:.2f}")

if __name__ == "__main__":
    main()
