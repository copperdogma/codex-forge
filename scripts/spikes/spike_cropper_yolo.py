"""Model-based illustration detector via YOLOv8-seg (Ultralytics).

Downloads model on first run. Outputs JSONL with boxes (seg masks collapsed to boxes).

Example:
. .venv/bin/activate
python scripts/spikes/spike_cropper_yolo.py \
  --image-root input/images \
  --images-json configs/groundtruth/image_boxes_eval.jsonl \
  --out /tmp/detections_yolo.jsonl \
  --model yolov8n-seg.pt
"""

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

from ultralytics import YOLO


def load_image_list(image_root: Path, images_json: Path = None, glob: str = None):
    items = []
    if images_json:
        with images_json.open() as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                items.append({"image": rec["image"], "page": rec.get("page")})
    elif glob:
        for path in image_root.glob(glob):
            items.append({"image": path.name, "page": None})
    else:
        raise SystemExit("Provide --images-json or --glob")
    return items


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--image-root", default="input/images", type=Path)
    ap.add_argument("--images-json", type=Path, default=None)
    ap.add_argument("--glob", default=None)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--model", default="yolov8n-seg.pt", help="Ultralytics model name or path")
    ap.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    args = ap.parse_args()

    items = load_image_list(args.image_root, args.images_json, args.glob)
    model = YOLO(args.model)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as f:
        for item in items:
            path = args.image_root / item["image"]
            results = model.predict(str(path), conf=args.conf, verbose=False)
            boxes = []
            for r in results:
                # Prefer masks if available; fall back to bbox.
                if r.masks is not None:
                    for seg, box in zip(r.masks.xy, r.boxes.xyxy):
                        x0, y0, x1, y1 = box.tolist()
                        boxes.append({
                            "x0": int(x0),
                            "y0": int(y0),
                            "x1": int(x1),
                            "y1": int(y1),
                            "score": float(r.boxes.conf[0]),
                        })
                else:
                    for box, score in zip(r.boxes.xyxy, r.boxes.conf):
                        x0, y0, x1, y1 = box.tolist()
                        boxes.append({
                            "x0": int(x0),
                            "y0": int(y0),
                            "x1": int(x1),
                            "y1": int(y1),
                            "score": float(score),
                        })
            rec = {
                "page": item.get("page"),
                "image": item["image"],
                "boxes": boxes,
            }
            f.write(json.dumps(rec) + "\n")

if __name__ == "__main__":
    main()
