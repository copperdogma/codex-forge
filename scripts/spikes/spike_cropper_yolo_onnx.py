"""ONNXRuntime YOLOv8-seg inference (boxes only).

Uses a pre-exported yolov8n-seg.onnx (default path models/yolov8n-seg.onnx).
Outputs JSONL with boxes per image.

Example:
. .venv/bin/activate
python scripts/spikes/spike_cropper_yolo_onnx.py \
  --image-root input/images \
  --images-json configs/groundtruth/image_boxes_eval.jsonl \
  --model models/yolov8n-seg.onnx \
  --out /tmp/detections_yolo_onnx.jsonl
"""

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

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


def nms(boxes, scores, iou_thresh=0.5):
    idxs = scores.argsort()[::-1]
    keep = []
    while idxs.size > 0:
        i = idxs[0]
        keep.append(i)
        if idxs.size == 1:
            break
        rest = idxs[1:]
        ious = box_iou(boxes[i], boxes[rest])
        idxs = rest[ious <= iou_thresh]
    return keep


def box_iou(box, boxes):
    x0 = np.maximum(box[0], boxes[:, 0])
    y0 = np.maximum(box[1], boxes[:, 1])
    x1 = np.minimum(box[2], boxes[:, 2])
    y1 = np.minimum(box[3], boxes[:, 3])
    inter = np.maximum(0, x1 - x0) * np.maximum(0, y1 - y0)
    area1 = (box[2] - box[0]) * (box[3] - box[1])
    area2 = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    union = area1 + area2 - inter
    return inter / (union + 1e-9)


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def postprocess(pred, proto, img_shape, pad, scale, conf_thresh=0.25, iou_thresh=0.45, topk=50):
    # pred: (116, 8400) typical
    pred = pred.transpose(1, 0)  # (8400, 116)
    # infer class count and mask dims
    num_mask = 32
    num_classes = pred.shape[1] - 4 - num_mask - 1
    boxes = pred[:, :4]
    obj = sigmoid(pred[:, 4:5])
    cls = sigmoid(pred[:, 5 : 5 + num_classes])
    scores = obj * cls.max(axis=1, keepdims=True)
    scores = scores.squeeze()
    keep = scores > conf_thresh
    boxes, scores = boxes[keep], scores[keep]
    if boxes.shape[0] == 0:
        return []

    # xywh -> xyxy
    boxes[:, 0] -= boxes[:, 2] / 2
    boxes[:, 1] -= boxes[:, 3] / 2
    boxes[:, 2] += boxes[:, 0]
    boxes[:, 3] += boxes[:, 1]

    # de-pad / de-scale to original image
    boxes[:, [0, 2]] -= pad[0]
    boxes[:, [1, 3]] -= pad[1]
    boxes /= scale

    # clip
    h, w = img_shape
    boxes[:, 0::2] = boxes[:, 0::2].clip(0, w)
    boxes[:, 1::2] = boxes[:, 1::2].clip(0, h)

    # NMS
    keep_idx = nms(boxes, scores, iou_thresh)
    boxes = boxes[keep_idx]
    scores = scores[keep_idx]

    # keep top-k by score to avoid thousands of low-value boxes
    if topk and len(scores) > topk:
        top_idx = scores.argsort()[::-1][:topk]
        boxes = boxes[top_idx]
        scores = scores[top_idx]

    return [
        {"x0": int(b[0]), "y0": int(b[1]), "x1": int(b[2]), "y1": int(b[3]), "score": float(s)}
        for b, s in zip(boxes, scores)
    ]


def run_model(session, img_path: Path, input_name: str, conf: float, iou: float, topk: int):
    img0 = cv2.imread(str(img_path))
    if img0 is None:
        return []
    img, scale, pad = letterbox(img0, new_shape=(640, 640))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.astype(np.float32) / 255.0
    img = np.transpose(img, (2, 0, 1))[None, ...]

    outputs = session.run(None, {input_name: img})
    pred = outputs[0]  # (1, 116, 8400)
    proto = outputs[1] if len(outputs) > 1 else None
    return postprocess(pred[0], proto, img0.shape[:2], pad, scale, conf, iou, topk)


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
    ap.add_argument("--image-root", type=Path, default=Path("input/images"))
    ap.add_argument("--images-json", type=Path, default=None)
    ap.add_argument("--glob", default=None)
    ap.add_argument("--model", type=Path, default=Path("models/yolov8n-seg.onnx"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--conf", type=float, default=0.4)
    ap.add_argument("--iou", type=float, default=0.45)
    ap.add_argument("--topk", type=int, default=50)
    args = ap.parse_args()

    sess = ort.InferenceSession(str(args.model), providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name

    items = load_image_list(args.image_root, args.images_json, args.glob)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as f:
        for item in items:
            path = args.image_root / item["image"]
            boxes = run_model(sess, path, input_name, args.conf, args.iou, args.topk)
            f.write(json.dumps({"page": item.get("page"), "image": item["image"], "boxes": boxes}) + "\n")

if __name__ == "__main__":
    main()
