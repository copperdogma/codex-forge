"""MobileSAM ONNXRuntime inference to get masks -> boxes.

Strategy: single positive point at image center to capture main illustration; take largest mask per image and convert to box.
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any

import cv2
import numpy as np
import onnxruntime as ort


IMAGE_SIZE = 1024


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


def preprocess(img: np.ndarray):
    h, w = img.shape[:2]
    scale = IMAGE_SIZE / max(h, w)
    nh, nw = int(round(h * scale)), int(round(w * scale))
    img_resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    pad_h = IMAGE_SIZE - nh
    pad_w = IMAGE_SIZE - nw
    top = pad_h // 2
    left = pad_w // 2
    img_padded = cv2.copyMakeBorder(img_resized, top, pad_h - top, left, pad_w - left, cv2.BORDER_CONSTANT, value=(0, 0, 0))
    img_rgb = cv2.cvtColor(img_padded, cv2.COLOR_BGR2RGB)
    img_norm = img_rgb.astype(np.float32) / 255.0
    img_norm = (img_norm - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array([0.229, 0.224, 0.225], dtype=np.float32)
    return img_norm, (top, left), scale, (h, w)


def mask_to_box(mask: np.ndarray):
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def propose_points(mask_fg: np.ndarray, k: int = 5):
    ys, xs = np.where(mask_fg)
    if len(xs) == 0:
        return np.array([[mask_fg.shape[1]/2, mask_fg.shape[0]/2]], dtype=np.float32)
    pts = np.column_stack([xs, ys])
    # simple k-means++ init via quantiles
    quantiles = np.linspace(0, len(pts)-1, k, dtype=int)
    return pts[quantiles].astype(np.float32)


def infer(image_path: Path, enc_sess, dec_sess, conf_thresh: float, max_masks: int = 3):
    img0 = cv2.imread(str(image_path))
    if img0 is None:
        return []
    inp, pad, scale, orig_hw = preprocess(img0)
    # Encoder
    enc_out = enc_sess.run(None, {enc_sess.get_inputs()[0].name: inp})[0]
    # quick foreground mask for point proposals
    gray = cv2.cvtColor(img0, cv2.COLOR_BGR2GRAY)
    _, fg = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
    points = propose_points(fg.astype(bool), k=5)
    mask_input = np.zeros((1, 1, 256, 256), dtype=np.float32)
    has_mask_input = np.zeros(1, dtype=np.float32)
    orig_im_size = np.array(orig_hw, dtype=np.float32)

    proposals = []
    for p in points:
        point_label = np.array([[1.0]], dtype=np.float32)
        dec_inputs = {
            dec_sess.get_inputs()[0].name: enc_out,
            dec_sess.get_inputs()[1].name: p[None, None, ...],
            dec_sess.get_inputs()[2].name: point_label,
            dec_sess.get_inputs()[3].name: mask_input,
            dec_sess.get_inputs()[4].name: has_mask_input,
            dec_sess.get_inputs()[5].name: orig_im_size,
        }
        masks, iou_preds, _ = dec_sess.run(None, dec_inputs)
        mask = masks[0, 0]
        mask_bin = (mask > conf_thresh).astype(np.uint8)
        box = mask_to_box(mask_bin)
        if box:
            x0, y0, x1, y1 = box
            proposals.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "score": float(iou_preds[0,0])})

    # keep top by score*area
    def area(b):
        return (b['x1']-b['x0'])*(b['y1']-b['y0'])
    proposals = sorted(proposals, key=lambda b: b['score']*area(b), reverse=True)
    return proposals[:max_masks]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--image-root", type=Path, default=Path("input/images"))
    ap.add_argument("--images-json", type=Path, default=None)
    ap.add_argument("--glob", default=None)
    ap.add_argument("--encoder", type=Path, default=Path("models/mobilesam.encoder.onnx"))
    ap.add_argument("--decoder", type=Path, default=Path("models/mobilesam.decoder.onnx"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--mask-thresh", type=float, default=0.5)
    args = ap.parse_args()

    enc_sess = ort.InferenceSession(str(args.encoder), providers=["CPUExecutionProvider"])
    dec_sess = ort.InferenceSession(str(args.decoder), providers=["CPUExecutionProvider"])

    items = load_image_list(args.image_root, args.images_json, args.glob)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as f:
        for item in items:
            boxes = infer(args.image_root / item["image"], enc_sess, dec_sess, args.mask_thresh)
            f.write(json.dumps({"page": item.get("page"), "image": item["image"], "boxes": boxes}) + "\n")


if __name__ == "__main__":
    main()
