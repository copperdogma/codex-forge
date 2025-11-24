"""YOLOv8-seg ONNXRuntime using exported NMS head (Hyuto repo).

Expects fused yolov8n-seg.onnx (detect head) and nms-yolov8.onnx (performs NMS).
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any

import cv2
import numpy as np
import onnxruntime as ort


def letterbox(img, new_shape=(640, 640), color=(114, 114, 114)):
    h, w = img.shape[:2]
    r = min(new_shape[0] / h, new_shape[1] / w)
    nh, nw = int(round(h * r)), int(round(w * r))
    pad_h = new_shape[0] - nh
    pad_w = new_shape[1] - nw
    top = pad_h // 2
    bottom = pad_h - top
    left = pad_w // 2
    right = pad_w - left
    img = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return img, r, (left, top)


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


def run_model(sess_feat, sess_nms, img_path: Path, conf: float, iou: float):
    img0 = cv2.imread(str(img_path))
    if img0 is None:
        return []
    img, scale, pad = letterbox(img0, new_shape=(640, 640))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    img = np.transpose(img, (2, 0, 1))[None, ...]

    det_in = sess_feat.run(None, {sess_feat.get_inputs()[0].name: img})[0]
    # config: [score_thresh, iou_thresh, top_k, max_detections]
    config = np.array([conf, iou, 1000, 300], dtype=np.float32)
    det = sess_nms.run(None, {sess_nms.get_inputs()[0].name: det_in, sess_nms.get_inputs()[1].name: config})[0]
    boxes = []
    h, w = img0.shape[:2]
    for x1, y1, x2, y2, score, cls_id, batch in det:
        boxes.append({"x0": int(x1), "y0": int(y1), "x1": int(x2), "y1": int(y2), "score": float(score)})
    return boxes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--image-root", type=Path, default=Path("input/images"))
    ap.add_argument("--images-json", type=Path, default=None)
    ap.add_argument("--glob", default=None)
    ap.add_argument("--model", type=Path, default=Path("models/yolov8n-seg.onnx"))
    ap.add_argument("--nms", type=Path, default=Path("models/nms-yolov8.onnx"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--iou", type=float, default=0.45)
    args = ap.parse_args()

    sess_feat = ort.InferenceSession(str(args.model), providers=["CPUExecutionProvider"])
    sess_nms = ort.InferenceSession(str(args.nms), providers=["CPUExecutionProvider"])

    items = load_image_list(args.image_root, args.images_json, args.glob)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as f:
        for item in items:
            boxes = run_model(sess_feat, sess_nms, args.image_root / item["image"], args.conf, args.iou)
            f.write(json.dumps({"page": item.get("page"), "image": item["image"], "boxes": boxes}) + "\n")


if __name__ == "__main__":
    main()
