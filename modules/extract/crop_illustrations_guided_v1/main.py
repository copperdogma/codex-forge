"""Guided illustration cropping using OCR metadata + CV contour detection.

Two-pass approach:
1. OCR identifies pages with images (alt text + count)
2. This module runs CV detection ONLY on those pages, extracting N largest contours

This works because:
- We KNOW which pages have images (high confidence from GPT-5.1)
- CV just needs to find N largest non-text regions (not distinguish text from art)
- Falls back to vision model for edge cases
"""

import argparse
import base64
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

import re

from modules.common import ensure_dir, save_jsonl, read_jsonl

try:
    from modules.common.openai_client import OpenAI
except Exception as exc:  # pragma: no cover - environment dependency
    OpenAI = None
    _OPENAI_IMPORT_ERROR = exc
else:
    _OPENAI_IMPORT_ERROR = None

try:
    from modules.common.google_client import GeminiVisionClient
except Exception as exc:  # pragma: no cover - environment dependency
    GeminiVisionClient = None
    _GEMINI_IMPORT_ERROR = exc
else:
    _GEMINI_IMPORT_ERROR = None


def _is_gemini_model(model: str) -> bool:
    return model.startswith("gemini-")

Image.MAX_IMAGE_PIXELS = None

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}


def _normalize_output_format(output_format: Optional[str]) -> Tuple[str, str]:
    fmt = (output_format or "png").strip().lower().lstrip(".")
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in {"png", "jpeg"}:
        raise ValueError(f"Unsupported output_format: {output_format}")
    ext = "png" if fmt == "png" else "jpg"
    return fmt, ext


_BBOX_PROMPT = """
You are given a scanned book page. Identify each distinct illustration or photo region.
Return a JSON array of objects with keys:
  - image_box: {x0, y0, x1, y1}
  - caption_box: {x0, y0, x1, y1} or null
- Coordinates must be normalized floats in [0,1], relative to the full image.
- Origin is top-left; x increases right, y increases down.
- image_box must be a tight box around the image content ONLY (exclude captions, page numbers, and any text).
- If the image has a clear border, crop to that border.
- If there is any caption or nearby text directly below or above the image, caption_box MUST be that text region (non-null), even if it is a header line.
- Prefer to under-crop rather than include any text; if in doubt, shrink image_box to exclude text.
- If multiple illustrations, return distinct, non-overlapping boxes in top-to-bottom, left-to-right order.
Return JSON only.
""".strip()

_CAPTION_PROMPT = """
You are given a scanned book page. Identify ONLY the caption or nearby text regions that belong to each illustration.
Return a JSON array of objects with keys: x0, y0, x1, y1.
- Each box must tightly bound the caption text (no image content).
- Captions can be above or below the image.
- Return boxes in the same order as the images appear top-to-bottom, left-to-right.
- If a caption is absent for an image, return a zero-area box by repeating x0,y0,x1,y1=0, or omit it.
Return JSON only.
""".strip()


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "jpeg"
    return f"data:image/{ext};base64,{b64}"


def _call_vlm_boxes(
    model: str,
    image_data: str,
    expected_count: int,
    alt_hints: Optional[List[str]],
    temperature: float,
    max_tokens: int,
    timeout_seconds: Optional[float],
    extra_instructions: Optional[str] = None,
) -> Tuple[List[Dict[str, float]], Optional[Any], Optional[str], str]:
    raw = ""
    usage = None
    request_id = None
    user_text = (
        f"Return up to {expected_count} boxes. "
        "If fewer illustrations are visible, return only the boxes you can see. "
        "Do NOT guess or invent extra boxes. "
        "Boxes must be distinct and should not significantly overlap."
    )
    if alt_hints:
        hints = "\n".join(f"{idx+1}. {text}" for idx, text in enumerate(alt_hints))
        user_text += (
            "\nImage descriptions (one per image, keep the same order):\n"
            f"{hints}"
        )
    if extra_instructions:
        user_text += f"\n{extra_instructions.strip()}"
    if _is_gemini_model(model):
        if GeminiVisionClient is None:  # pragma: no cover
            raise RuntimeError("google-genai package required") from _GEMINI_IMPORT_ERROR
        gclient = GeminiVisionClient()
        raw, usage, request_id = gclient.generate_vision(
            model=model,
            system_prompt=_BBOX_PROMPT,
            user_text=user_text,
            image_data=image_data,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:
        if OpenAI is None:  # pragma: no cover
            raise RuntimeError("openai package required") from _OPENAI_IMPORT_ERROR
        client = OpenAI(timeout=timeout_seconds) if timeout_seconds else OpenAI()
        if hasattr(client, "responses"):
            resp = client.responses.create(
                model=model,
                temperature=temperature,
                max_output_tokens=max_tokens,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": _BBOX_PROMPT}]},
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": user_text},
                            {"type": "input_image", "image_url": image_data},
                        ],
                    },
                ],
            )
            raw = resp.output_text or ""
            usage = getattr(resp, "usage", None)
            request_id = getattr(resp, "id", None)
        else:
            resp = client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_completion_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": _BBOX_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {"type": "image_url", "image_url": {"url": image_data}},
                        ],
                    },
                ],
            )
            raw = resp.choices[0].message.content or ""

    boxes = []
    try:
        raw_json = raw.strip()
        if not raw_json.startswith("["):
            start = raw_json.find("[")
            end = raw_json.rfind("]")
            if start != -1 and end != -1:
                raw_json = raw_json[start:end + 1]
        data = json.loads(raw_json)
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                if "image_box" in item:
                    img_box = item.get("image_box") or {}
                    cap_box = item.get("caption_box")
                    schema_mode = True
                else:
                    img_box = item
                    cap_box = None
                    schema_mode = False
                # Handle array format [x0, y0, x1, y1] from some models
                if isinstance(img_box, (list, tuple)) and len(img_box) == 4:
                    img_box = {"x0": img_box[0], "y0": img_box[1], "x1": img_box[2], "y1": img_box[3]}
                if isinstance(cap_box, (list, tuple)) and len(cap_box) == 4:
                    cap_box = {"x0": cap_box[0], "y0": cap_box[1], "x1": cap_box[2], "y1": cap_box[3]}
                try:
                    x0 = float(img_box.get("x0"))
                    y0 = float(img_box.get("y0"))
                    x1 = float(img_box.get("x1"))
                    y1 = float(img_box.get("y1"))
                except Exception:
                    continue
                box = {"x0": x0, "y0": y0, "x1": x1, "y1": y1}
                if schema_mode:
                    box["_caption_schema"] = True
                if isinstance(cap_box, dict):
                    try:
                        cx0 = float(cap_box.get("x0"))
                        cy0 = float(cap_box.get("y0"))
                        cx1 = float(cap_box.get("x1"))
                        cy1 = float(cap_box.get("y1"))
                    except Exception:
                        cap_box = None
                    else:
                        box["caption_box"] = {
                            "x0": cx0,
                            "y0": cy0,
                            "x1": cx1,
                            "y1": cy1,
                        }
                boxes.append(box)
    except Exception:
        boxes = []
    return boxes, usage, request_id, raw


def _call_vlm_caption_boxes(
    model: str,
    image_data: str,
    expected_count: int,
    alt_hints: Optional[List[str]],
    temperature: float,
    max_tokens: int,
    timeout_seconds: Optional[float],
    extra_instructions: Optional[str] = None,
) -> Tuple[List[Dict[str, float]], Optional[Any], Optional[str], str]:
    raw = ""
    usage = None
    request_id = None
    user_text = f"Return up to {expected_count} caption boxes."
    if alt_hints:
        hints = "\n".join(f"{idx+1}. {text}" for idx, text in enumerate(alt_hints))
        user_text += (
            "\nImage descriptions (one per image, keep the same order):\n"
            f"{hints}"
        )
    if extra_instructions:
        user_text += f"\n{extra_instructions.strip()}"
    if _is_gemini_model(model):
        if GeminiVisionClient is None:  # pragma: no cover
            raise RuntimeError("google-genai package required") from _GEMINI_IMPORT_ERROR
        gclient = GeminiVisionClient()
        raw, usage, request_id = gclient.generate_vision(
            model=model,
            system_prompt=_CAPTION_PROMPT,
            user_text=user_text,
            image_data=image_data,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:
        if OpenAI is None:  # pragma: no cover
            raise RuntimeError("openai package required") from _OPENAI_IMPORT_ERROR
        client = OpenAI(timeout=timeout_seconds) if timeout_seconds else OpenAI()
        if hasattr(client, "responses"):
            resp = client.responses.create(
                model=model,
                temperature=temperature,
                max_output_tokens=max_tokens,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": _CAPTION_PROMPT}]},
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": user_text},
                            {"type": "input_image", "image_url": image_data},
                        ],
                    },
                ],
            )
            raw = resp.output_text or ""
            usage = getattr(resp, "usage", None)
            request_id = getattr(resp, "id", None)
        else:
            resp = client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_completion_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": _CAPTION_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {"type": "image_url", "image_url": {"url": image_data}},
                        ],
                    },
                ],
            )
            raw = resp.choices[0].message.content or ""

    boxes: List[Dict[str, float]] = []
    try:
        raw_json = raw.strip()
        if not raw_json.startswith("["):
            start = raw_json.find("[")
            end = raw_json.rfind("]")
            if start != -1 and end != -1:
                raw_json = raw_json[start:end + 1]
        data = json.loads(raw_json)
        if isinstance(data, list):
            for item in data:
                # Handle array format [x0, y0, x1, y1] from some models
                if isinstance(item, (list, tuple)) and len(item) == 4:
                    item = {"x0": item[0], "y0": item[1], "x1": item[2], "y1": item[3]}
                if not isinstance(item, dict):
                    continue
                try:
                    x0 = float(item.get("x0"))
                    y0 = float(item.get("y0"))
                    x1 = float(item.get("x1"))
                    y1 = float(item.get("y1"))
                except Exception:
                    continue
                if x0 == x1 or y0 == y1:
                    continue
                boxes.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1})
    except Exception:
        boxes = []
    return boxes, usage, request_id, raw


def _refine_boxes_with_vlm(
    page_img: Image.Image,
    boxes: List[Dict[str, int]],
    model: str,
    temperature: float,
    max_tokens: int,
    timeout_seconds: Optional[float],
    min_area_ratio: float,
) -> List[Dict[str, int]]:
    refined = []
    for box in boxes:
        x0, y0, x1, y1 = box["x0"], box["y0"], box["x1"], box["y1"]
        if x1 <= x0 or y1 <= y0:
            refined.append(box)
            continue
        crop = page_img.crop((x0, y0, x1, y1))
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir) / "crop.jpg"
                crop.save(tmp_path, format="JPEG", quality=92)
                image_data = _encode_image(str(tmp_path))
        except Exception:
            refined.append(box)
            continue
        try:
            vlm_boxes, _, _, _ = _call_vlm_boxes(
                model,
                image_data,
                expected_count=1,
                alt_hints=None,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_seconds=timeout_seconds,
                extra_instructions=(
                    "This is a cropped image. Return ONE tight box around the image content only. "
                    "Exclude any caption or text. If no image content remains, return []."
                ),
            )
        except Exception:
            refined.append(box)
            continue
        if not vlm_boxes:
            refined.append(box)
            continue
        w, h = crop.size
        px = _normalize_box(vlm_boxes[0], w, h)
        if not px:
            refined.append(box)
            continue
        new_w = px["x1"] - px["x0"]
        new_h = px["y1"] - px["y0"]
        old_area = max(1, (x1 - x0) * (y1 - y0))
        new_area = new_w * new_h
        if new_area / float(old_area) < min_area_ratio:
            refined.append(box)
            continue
        refined.append({
            "x0": x0 + px["x0"],
            "y0": y0 + px["y0"],
            "x1": x0 + px["x1"],
            "y1": y0 + px["y1"],
            "width": new_w,
            "height": new_h,
        })
    return refined


def _normalize_box(box: Dict[str, float], w: int, h: int) -> Optional[Dict[str, int]]:
    try:
        x0 = max(0.0, min(1.0, float(box["x0"])))
        y0 = max(0.0, min(1.0, float(box["y0"])))
        x1 = max(0.0, min(1.0, float(box["x1"])))
        y1 = max(0.0, min(1.0, float(box["y1"])))
    except Exception:
        return None
    if x1 <= x0 or y1 <= y0:
        return None
    ix0 = int(round(x0 * w))
    iy0 = int(round(y0 * h))
    ix1 = int(round(x1 * w))
    iy1 = int(round(y1 * h))
    ix0 = max(0, min(w - 1, ix0))
    iy0 = max(0, min(h - 1, iy0))
    ix1 = max(0, min(w, ix1))
    iy1 = max(0, min(h, iy1))
    if ix1 <= ix0 or iy1 <= iy0:
        return None
    return {
        "x0": ix0,
        "y0": iy0,
        "x1": ix1,
        "y1": iy1,
        "width": int(ix1 - ix0),
        "height": int(iy1 - iy0),
    }


def _apply_caption_box(box: Dict[str, int], margin_px: int, max_gap_ratio: float) -> Dict[str, int]:
    caption = box.get("caption_box")
    if not isinstance(caption, dict):
        return box
    try:
        cx0 = int(caption.get("x0", 0))
        cy0 = int(caption.get("y0", 0))
        cx1 = int(caption.get("x1", 0))
        cy1 = int(caption.get("y1", 0))
    except Exception:
        return box
    if cx1 <= cx0 or cy1 <= cy0:
        return box
    box = dict(box)
    applied = False
    max_gap = int(max_gap_ratio * max(1, box["height"]))
    # If caption is below the image box (or overlaps), trim to caption start.
    if cy0 >= box["y0"] and cy0 <= box["y1"] + max_gap:
        new_y1 = cy0 - margin_px
        if new_y1 > box["y0"]:
            box["y1"] = new_y1
            box["height"] = new_y1 - box["y0"]
            applied = True
    # If caption is above the image box (or overlaps), trim to caption end.
    if cy1 >= box["y0"] - max_gap and cy1 <= box["y1"]:
        new_y0 = cy1 + margin_px
        if new_y0 < box["y1"]:
            box["y0"] = new_y0
            box["height"] = box["y1"] - new_y0
            applied = True
    if applied:
        box["_caption_applied"] = True
    return box


def _refine_boxes_remove_text_lines(
    img_gray: np.ndarray,
    boxes: List[Dict[str, int]],
    white_threshold: int,
    text_line_kernel_w: int,
    text_line_kernel_h: int,
    text_line_iterations: int,
    min_component_area_ratio: float = 0.05,
) -> List[Dict[str, int]]:
    if img_gray is None or not boxes:
        return boxes
    refined = []
    for box in boxes:
        x0, y0, x1, y1 = box["x0"], box["y0"], box["x1"], box["y1"]
        roi = img_gray[y0:y1, x0:x1]
        if roi.size == 0:
            refined.append(box)
            continue
        h, w = roi.shape[:2]
        roi_area = float(max(1, h * w))

        # Nonwhite mask for candidate image pixels.
        nonwhite = (roi < white_threshold).astype("uint8") * 255

        # Text-line mask: horizontal morphological open on thresholded ink.
        _, ink = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        kw = max(text_line_kernel_w, w // 8)
        kh = max(1, text_line_kernel_h)
        kw = kw if kw % 2 == 1 else kw + 1
        kh = kh if kh % 2 == 1 else kh + 1
        line_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, kh))
        text_lines = cv2.morphologyEx(ink, cv2.MORPH_OPEN, line_kernel, iterations=text_line_iterations)
        # Slightly expand text lines to be safe.
        text_lines = cv2.dilate(text_lines, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)

        nontext = cv2.bitwise_and(nonwhite, cv2.bitwise_not(text_lines))
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(nontext, connectivity=8)
        best = None
        best_area = 0
        for lbl in range(1, num_labels):
            x, y, cw, ch, area = stats[lbl]
            if area <= 0:
                continue
            if area > best_area:
                best_area = area
                best = (x, y, cw, ch)
        if best is None:
            refined.append(box)
            continue
        if best_area / roi_area < min_component_area_ratio:
            refined.append(box)
            continue
        bx, by, bw, bh = best
        rx0 = x0 + bx
        ry0 = y0 + by
        rx1 = x0 + bx + bw
        ry1 = y0 + by + bh
        if rx1 <= rx0 or ry1 <= ry0:
            refined.append(box)
        else:
            refined.append({
                "x0": int(rx0),
                "y0": int(ry0),
                "x1": int(rx1),
                "y1": int(ry1),
                "width": int(rx1 - rx0),
                "height": int(ry1 - ry0),
            })
    return refined


def _trim_text_edges(
    img_gray: np.ndarray,
    box: Dict[str, int],
    white_threshold: int,
    text_line_kernel_w: int,
    text_line_kernel_h: int,
    text_line_iterations: int,
    max_trim_ratio: float,
    margin_px: int,
) -> Dict[str, int]:
    x0, y0, x1, y1 = box["x0"], box["y0"], box["x1"], box["y1"]
    if y1 <= y0 or x1 <= x0:
        return box
    roi = img_gray[y0:y1, x0:x1]
    if roi.size == 0:
        return box
    h, w = roi.shape[:2]
    max_trim = int(h * max_trim_ratio)
    if max_trim <= 0:
        return box

    # Avoid trimming on mostly-ink regions unless the top/bottom band looks text-like.
    nonwhite_ratio = float(np.count_nonzero(roi < white_threshold)) / float(max(1, roi.size))
    effective_max_trim = max_trim
    if nonwhite_ratio < 0.25:
        effective_max_trim = max(effective_max_trim, int(h * 0.5))

    _, ink = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kw = max(text_line_kernel_w, w // 8)
    kh = max(1, text_line_kernel_h)
    kw = kw if kw % 2 == 1 else kw + 1
    kh = kh if kh % 2 == 1 else kh + 1
    line_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, kh))
    text_lines = cv2.morphologyEx(ink, cv2.MORPH_OPEN, line_kernel, iterations=text_line_iterations)
    row_ratio = (text_lines > 0).sum(axis=1) / float(max(1, w))
    if row_ratio.size == 0:
        return box
    thr = max(0.01, float(np.quantile(row_ratio, 0.9) * 0.5))

    # Allow trimming even on ink-heavy crops if text lines are concentrated near the edge.
    band_h = max(1, min(h, effective_max_trim))
    top_band = roi[:band_h, :]
    bottom_band = roi[h - band_h :, :]
    top_nonwhite = float(np.count_nonzero(top_band < white_threshold)) / float(max(1, top_band.size))
    bottom_nonwhite = float(np.count_nonzero(bottom_band < white_threshold)) / float(max(1, bottom_band.size))

    # Find first text band within the top window (even if there is whitespace above).
    top_trim = 0
    top_idx = None
    for i in range(0, min(h, effective_max_trim)):
        if row_ratio[i] >= thr:
            top_idx = i
            break
    if top_idx is not None:
        j = top_idx
        while j < h and row_ratio[j] >= thr:
            j += 1
        if (j - top_idx) > 0 and j <= effective_max_trim and (nonwhite_ratio <= 0.35 or top_nonwhite <= 0.2):
            top_trim = max(0, j + margin_px)

    # Find last text band within the bottom window.
    bottom_trim = 0
    bottom_idx = None
    for i in range(h - 1, max(-1, h - effective_max_trim) - 1, -1):
        if row_ratio[i] >= thr:
            bottom_idx = i
            break
    if bottom_idx is not None:
        j = bottom_idx
        while j >= 0 and row_ratio[j] >= thr:
            j -= 1
        band_start = j + 1
        if (bottom_idx - band_start + 1) > 0 and (h - band_start) <= effective_max_trim and (nonwhite_ratio <= 0.35 or bottom_nonwhite <= 0.2):
            bottom_trim = max(0, (h - band_start) + margin_px)

    if top_trim == 0 and bottom_trim == 0:
        # Fallback: detect a text band at the top followed by a clear white gap.
        row_nonwhite = (roi < white_threshold).sum(axis=1) / float(max(1, w))
        text_min = 0.05
        text_max = 0.35
        gap_max = 0.01
        band_min = 4
        gap_min = 6
        band_start = None
        band_end = None
        for i in range(0, min(h, effective_max_trim)):
            if text_min <= row_nonwhite[i] <= text_max:
                if band_start is None:
                    band_start = i
                band_end = i
            elif band_start is not None:
                if band_end is not None and (band_end - band_start + 1) >= band_min:
                    break
                band_start = None
                band_end = None
        if band_start is not None and band_end is not None and (band_end - band_start + 1) >= band_min:
            gap_len = 0
            gap_start = None
            for i in range(band_end + 1, min(h, effective_max_trim)):
                if row_nonwhite[i] <= gap_max:
                    if gap_start is None:
                        gap_start = i
                    gap_len += 1
                else:
                    if gap_len >= gap_min:
                        break
                    gap_start = None
                    gap_len = 0
            if gap_start is not None and gap_len >= gap_min and (nonwhite_ratio <= 0.45):
                new_y0 = y0 + max(0, gap_start + margin_px)
                new_y1 = y1
                if new_y1 > new_y0:
                    return {
                        "x0": x0,
                        "y0": new_y0,
                        "x1": x1,
                        "y1": new_y1,
                        "width": x1 - x0,
                        "height": new_y1 - new_y0,
                    }
        return box

    new_y0 = y0 + top_trim
    new_y1 = y1 - bottom_trim
    if new_y1 <= new_y0:
        return box
    return {
        "x0": x0,
        "y0": new_y0,
        "x1": x1,
        "y1": new_y1,
        "width": x1 - x0,
        "height": new_y1 - new_y0,
    }


def _box_has_text_band(
    img_gray: np.ndarray,
    box: Dict[str, int],
    white_threshold: int,
    edge_ratio: float,
) -> bool:
    x0, y0, x1, y1 = box["x0"], box["y0"], box["x1"], box["y1"]
    if x1 <= x0 or y1 <= y0:
        return False
    roi = img_gray[y0:y1, x0:x1]
    if roi.size == 0:
        return False
    h, w = roi.shape[:2]
    window = int(h * edge_ratio)
    if window <= 0:
        return False
    row_nonwhite = (roi < white_threshold).sum(axis=1) / float(max(1, w))
    text_min = 0.05
    text_max = 0.45
    band_min = 4
    gap_min = 6
    gap_max = 0.01

    def _has_band_with_gap(start: int, end: int) -> bool:
        run = 0
        band_start = None
        band_end = None
        for i in range(start, end):
            if text_min <= row_nonwhite[i] <= text_max:
                if band_start is None:
                    band_start = i
                run += 1
                band_end = i
            else:
                if run >= band_min:
                    break
                run = 0
                band_start = None
                band_end = None
        if band_start is None or band_end is None or run < band_min:
            return False
        gap_len = 0
        for i in range(band_end + 1, end):
            if row_nonwhite[i] <= gap_max:
                gap_len += 1
                if gap_len >= gap_min:
                    return True
            else:
                gap_len = 0
        return False

    top_end = min(h, window)
    if _has_band_with_gap(0, top_end):
        return True
    bottom_start = max(0, h - window)
    if _has_band_with_gap(bottom_start, h):
        return True
    return False


def _trim_box_by_ocr_text(
    img_gray: np.ndarray,
    box: Dict[str, int],
    tesseract_cmd: Optional[str],
    edge_ratio: float,
    min_conf: int,
    min_word_len: int,
    white_threshold: int,
    min_line_words: int,
    min_line_chars: int,
    max_trim_ratio: float,
    margin_px: int,
) -> Dict[str, int]:
    if tesseract_cmd is None:
        return box
    x0, y0, x1, y1 = box["x0"], box["y0"], box["x1"], box["y1"]
    if x1 <= x0 or y1 <= y0:
        return box
    roi = img_gray[y0:y1, x0:x1]
    if roi.size == 0:
        return box
    h, w = roi.shape[:2]
    window = int(h * edge_ratio)
    if window <= 0:
        return box
    max_trim = int(h * max_trim_ratio)
    if max_trim <= 0:
        return box
    try:
        import tempfile
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "crop.png"
            cv2.imwrite(str(tmp_path), roi)
            cmd = [
                tesseract_cmd,
                str(tmp_path),
                "stdout",
                "--psm",
                "6",
                "tsv",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                return box
            lines = proc.stdout.splitlines()
    except Exception:
        return box

    top_text_max = None
    bottom_text_min = None
    lines_by_id: Dict[Tuple[int, int, int], Dict[str, int]] = {}
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 12:
            continue
        try:
            conf = int(float(parts[10]))
        except Exception:
            continue
        text = parts[11].strip()
        if conf < min_conf or len(text) < min_word_len:
            continue
        try:
            block_num = int(parts[2])
            par_num = int(parts[4])
            line_num = int(parts[5])
            y = int(parts[7])
            h_box = int(parts[9])
        except Exception:
            continue
        if h_box <= 0:
            continue
        key = (block_num, par_num, line_num)
        entry = lines_by_id.get(key)
        if entry is None:
            entry = {"words": 0, "chars": 0, "y0": y, "y1": y + h_box}
            lines_by_id[key] = entry
        entry["words"] += 1
        entry["chars"] += len(text)
        if y < entry["y0"]:
            entry["y0"] = y
        if y + h_box > entry["y1"]:
            entry["y1"] = y + h_box

    for entry in lines_by_id.values():
        if entry["words"] < min_line_words or entry["chars"] < min_line_chars:
            continue
        y0_box = entry["y0"]
        y1_box = entry["y1"]
        if y1_box <= window:
            if top_text_max is None or y1_box > top_text_max:
                top_text_max = y1_box
        if y0_box >= h - window:
            if bottom_text_min is None or y0_box < bottom_text_min:
                bottom_text_min = y0_box

    new_y0 = y0
    new_y1 = y1
    if top_text_max is not None:
        trim = min(max_trim, top_text_max + margin_px)
        if trim > 0:
            new_y0 = y0 + trim
    if bottom_text_min is not None:
        trim = min(max_trim, (h - bottom_text_min) + margin_px)
        if trim > 0:
            new_y1 = y1 - trim
    if new_y1 <= new_y0:
        return box
    if new_y0 == y0 and new_y1 == y1:
        return box
    return {
        "x0": x0,
        "y0": new_y0,
        "x1": x1,
        "y1": new_y1,
        "width": x1 - x0,
        "height": new_y1 - new_y0,
    }


def _trim_box_by_layout_text(
    box: Dict[str, int],
    text_boxes: List[Any],
    max_gap_ratio: float,
    bottom_band_ratio: float,
    top_band_ratio: float,
    margin_px: int,
    min_width_ratio: float,
    max_height_ratio: float,
) -> Dict[str, int]:
    x0, y0, x1, y1 = box["x0"], box["y0"], box["x1"], box["y1"]
    if x1 <= x0 or y1 <= y0:
        return box
    h = y1 - y0
    max_gap = max(0, int(h * max_gap_ratio))
    bottom_band = y0 + int(h * (1.0 - bottom_band_ratio))
    top_band = y0 + int(h * top_band_ratio)
    bottom_trim = None
    top_trim = None
    for tb in text_boxes:
        label = None
        if isinstance(tb, dict):
            try:
                tx0, ty0, tx1, ty1 = tb["x0"], tb["y0"], tb["x1"], tb["y1"]
            except Exception:
                continue
            label = tb.get("label")
        else:
            if len(tb) != 4:
                continue
            tx0, ty0, tx1, ty1 = tb
        if ty1 < y0 - max_gap or ty0 > y1 + max_gap:
            continue
        tw = tx1 - tx0
        th = ty1 - ty0
        if tw <= 0 or th <= 0:
            continue
        if (tw / float(max(1, x1 - x0))) < min_width_ratio:
            continue
        if (th / float(max(1, y1 - y0))) > max_height_ratio:
            continue
        if ty0 >= bottom_band and ty0 <= y1 + max_gap:
            if bottom_trim is None or ty0 < bottom_trim:
                bottom_trim = ty0
        if ty1 <= top_band and ty1 >= y0 - max_gap:
            if top_trim is None or ty1 > top_trim:
                top_trim = ty1
    new_y0 = y0
    new_y1 = y1
    if top_trim is not None:
        new_y0 = max(new_y0, top_trim + margin_px)
    if bottom_trim is not None:
        new_y1 = min(new_y1, bottom_trim - margin_px)
    if new_y1 <= new_y0:
        return box
    if new_y0 == y0 and new_y1 == y1:
        return box
    return {
        "x0": x0,
        "y0": new_y0,
        "x1": x1,
        "y1": new_y1,
        "width": x1 - x0,
        "height": new_y1 - new_y0,
    }


def _split_box_by_layout_text_band(
    box: Dict[str, int],
    text_boxes: List[Any],
    min_width_ratio: float,
    max_height_ratio: float,
    min_gap_ratio: float,
    margin_px: int,
) -> List[Dict[str, int]]:
    x0, y0, x1, y1 = box["x0"], box["y0"], box["x1"], box["y1"]
    if x1 <= x0 or y1 <= y0:
        return [box]
    bw = x1 - x0
    bh = y1 - y0
    min_gap = max(1, int(bh * min_gap_ratio))
    bands = []
    for tb in text_boxes:
        if isinstance(tb, dict):
            try:
                tx0, ty0, tx1, ty1 = tb["x0"], tb["y0"], tb["x1"], tb["y1"]
            except Exception:
                continue
        else:
            if len(tb) != 4:
                continue
            tx0, ty0, tx1, ty1 = tb
        if ty1 <= y0 or ty0 >= y1:
            continue
        tw = tx1 - tx0
        th = ty1 - ty0
        if tw <= 0 or th <= 0:
            continue
        if (tw / float(max(1, bw))) < min_width_ratio:
            continue
        if (th / float(max(1, bh))) > max_height_ratio:
            continue
        bands.append((ty0, ty1))
    if not bands:
        return [box]
    band_y0 = min(b[0] for b in bands)
    band_y1 = max(b[1] for b in bands)
    if band_y0 - y0 < min_gap or y1 - band_y1 < min_gap:
        return [box]
    top_y1 = band_y0 - margin_px
    bottom_y0 = band_y1 + margin_px
    out = []
    if top_y1 > y0:
        out.append(
            {
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": top_y1,
                "width": bw,
                "height": top_y1 - y0,
            }
        )
    if bottom_y0 < y1:
        out.append(
            {
                "x0": x0,
                "y0": bottom_y0,
                "x1": x1,
                "y1": y1,
                "width": bw,
                "height": y1 - bottom_y0,
            }
        )
    return out if out else [box]


def _layout_text_boxes_for_page(
    layout_engine: Any,
    image_path: str,
    score_thresh: float,
) -> List[Dict[str, int]]:
    try:
        results = layout_engine.predict(image_path)
    except Exception:
        return []
    if not results:
        return []
    record = results[0]
    boxes = []
    for item in record.get("boxes", []):
        label = item.get("label")
        score = float(item.get("score", 1.0))
        if label not in ("text", "figure_title", "doc_title", "number"):
            continue
        if score < score_thresh:
            continue
        coords = item.get("coordinate") or []
        if len(coords) != 4:
            continue
        x0, y0, x1, y1 = [int(round(float(v))) for v in coords]
        if x1 <= x0 or y1 <= y0:
            continue
        boxes.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "label": label})
    return boxes


def _layout_image_boxes_for_page(
    layout_engine: Any,
    image_path: str,
    score_thresh: float,
) -> List[Dict[str, int]]:
    try:
        results = layout_engine.predict(image_path)
    except Exception:
        return []
    if not results:
        return []
    record = results[0]
    boxes = []
    for item in record.get("boxes", []):
        label = item.get("label")
        score = float(item.get("score", 1.0))
        if label != "image" or score < score_thresh:
            continue
        coords = item.get("coordinate") or []
        if len(coords) != 4:
            continue
        x0, y0, x1, y1 = [int(round(float(v))) for v in coords]
        if x1 <= x0 or y1 <= y0:
            continue
        boxes.append(
            {
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "width": x1 - x0,
                "height": y1 - y0,
            }
        )
    return boxes


def _refine_boxes_with_nonwhite(
    image_path: str,
    boxes: List[Dict[str, int]],
    white_threshold: int,
    close_kernel: int,
    close_iterations: int,
) -> List[Dict[str, int]]:
    if not boxes:
        return boxes
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return boxes
    h, w = img.shape[:2]
    mask = (img < white_threshold).astype("uint8") * 255
    k = close_kernel if close_kernel % 2 == 1 else close_kernel + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=close_iterations)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    refined = []
    for box in boxes:
        x0, y0, x1, y1 = box["x0"], box["y0"], box["x1"], box["y1"]
        region = labels[y0:y1, x0:x1]
        if region.size == 0:
            refined.append(box)
            continue
        overlap_labels = set(int(v) for v in np.unique(region) if v > 0)
        if not overlap_labels:
            refined.append(box)
            continue
        xs = []
        ys = []
        xes = []
        yes = []
        for lbl in overlap_labels:
            x, y, cw, ch, _area = stats[lbl]
            xs.append(x)
            ys.append(y)
            xes.append(x + cw)
            yes.append(y + ch)
        rx0 = max(0, min(xs))
        ry0 = max(0, min(ys))
        rx1 = min(w, max(xes))
        ry1 = min(h, max(yes))
        if rx1 <= rx0 or ry1 <= ry0:
            refined.append(box)
        else:
            refined.append({
                "x0": int(rx0),
                "y0": int(ry0),
                "x1": int(rx1),
                "y1": int(ry1),
                "width": int(rx1 - rx0),
                "height": int(ry1 - ry0),
            })
    return refined


def _refine_boxes_with_nontext(
    img_gray: np.ndarray,
    boxes: List[Dict[str, int]],
    white_threshold: int,
    close_kernel: int,
    close_iterations: int,
    text_block_kernel_w: int,
    text_block_kernel_h: int,
    text_block_iterations: int,
    min_component_area_ratio: float = 0.02,
) -> List[Dict[str, int]]:
    if img_gray is None or not boxes:
        return boxes
    refined = []
    for box in boxes:
        x0, y0, x1, y1 = box["x0"], box["y0"], box["x1"], box["y1"]
        roi = img_gray[y0:y1, x0:x1]
        if roi.size == 0:
            refined.append(box)
            continue
        h, w = roi.shape[:2]
        roi_area = float(max(1, h * w))

        nonwhite = (roi < white_threshold).astype("uint8") * 255
        k = close_kernel if close_kernel % 2 == 1 else close_kernel + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
        nonwhite = cv2.morphologyEx(nonwhite, cv2.MORPH_CLOSE, kernel, iterations=close_iterations)

        _, text_bin = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        kw = text_block_kernel_w if text_block_kernel_w % 2 == 1 else text_block_kernel_w + 1
        kh = text_block_kernel_h if text_block_kernel_h % 2 == 1 else text_block_kernel_h + 1
        text_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, kh))
        text_blocks = cv2.dilate(text_bin, text_kernel, iterations=text_block_iterations)

        nontext = cv2.bitwise_and(nonwhite, cv2.bitwise_not(text_blocks))
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(nontext, connectivity=8)
        best = None
        best_area = 0
        for lbl in range(1, num_labels):
            x, y, cw, ch, area = stats[lbl]
            if area <= 0:
                continue
            if area > best_area:
                best_area = area
                best = (x, y, cw, ch)
        if best is None:
            refined.append(box)
            continue
        if best_area / roi_area < min_component_area_ratio:
            refined.append(box)
            continue
        bx, by, bw, bh = best
        rx0 = x0 + bx
        ry0 = y0 + by
        rx1 = x0 + bx + bw
        ry1 = y0 + by + bh
        if rx1 <= rx0 or ry1 <= ry0:
            refined.append(box)
        else:
            refined.append({
                "x0": int(rx0),
                "y0": int(ry0),
                "x1": int(rx1),
                "y1": int(ry1),
                "width": int(rx1 - rx0),
                "height": int(ry1 - ry0),
            })
    return refined


def _trim_caption_from_box(
    img_gray: np.ndarray,
    box: Dict[str, int],
    max_caption_height_ratio: float,
    text_ratio_threshold: float,
    margin_px: int,
    caption_max_nonwhite_ratio: float,
    white_threshold: int,
) -> Dict[str, int]:
    x0, y0, x1, y1 = box["x0"], box["y0"], box["x1"], box["y1"]
    if y1 <= y0 or x1 <= x0:
        return box
    h_box = y1 - y0
    max_caption_h = int(h_box * max_caption_height_ratio)
    if max_caption_h <= 0:
        return box
    roi = img_gray[y0:y1, x0:x1]
    if roi.size == 0:
        return box
    caption_h = min(max_caption_h, roi.shape[0])
    caption_roi = roi[-caption_h:, :]
    caption_nonwhite = float(np.count_nonzero(caption_roi < white_threshold)) / float(caption_roi.size)
    start = max(0, h_box - max_caption_h)
    band = roi[start:h_box, :]
    if band.size == 0:
        return box

    # Text-line projection (caption detection).
    _, text_bin = cv2.threshold(band, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel_w = max(30, band.shape[1] // 10)
    text_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, 1))
    text_lines = cv2.morphologyEx(text_bin, cv2.MORPH_OPEN, text_kernel, iterations=1)
    row_counts = (text_lines > 0).sum(axis=1) / float(max(1, band.shape[1]))
    if row_counts.size:
        # Dynamic threshold for text-line density.
        thr = max(0.01, float(np.quantile(row_counts, 0.9) * 0.5))
        # Find bottom-most run of text-like rows.
        last_idx = None
        for idx in range(len(row_counts) - 1, -1, -1):
            if row_counts[idx] >= thr:
                last_idx = idx
                break
        if last_idx is not None:
            top_idx = last_idx
            while top_idx > 0 and row_counts[top_idx - 1] >= thr:
                top_idx -= 1
            # Only treat as caption if it's in the bottom half of the band.
            if top_idx >= int(0.5 * band.shape[0]):
                cut_row = top_idx
                new_y1 = y0 + start + cut_row - margin_px
                if new_y1 > y0:
                    return {
                        "x0": x0,
                        "y0": y0,
                        "x1": x1,
                        "y1": new_y1,
                        "width": x1 - x0,
                        "height": new_y1 - y0,
                    }

    nonwhite_ratios = []
    for yy in range(band.shape[0]):
        row = band[yy, :]
        nonwhite = float(np.count_nonzero(row < white_threshold)) / float(max(row.size, 1))
        nonwhite_ratios.append(nonwhite)
    smooth = []
    for i, val in enumerate(nonwhite_ratios):
        window = nonwhite_ratios[max(0, i - 1):min(len(nonwhite_ratios), i + 2)]
        smooth.append(sum(window) / float(len(window)))
    nonwhite_ratios = smooth

    gap_threshold = max(0.02, text_ratio_threshold)
    gap_run = 3
    gap_y = None
    # Find the first significant whitespace gap within the bottom band.
    for idx in range(0, len(nonwhite_ratios) - gap_run):
        if all(nonwhite_ratios[j] <= gap_threshold for j in range(idx, idx + gap_run)):
            if any(r >= gap_threshold for r in nonwhite_ratios[idx + gap_run:]):
                # Require some content above the gap to avoid trimming blank tails.
                if max(nonwhite_ratios[:idx + gap_run]) >= gap_threshold:
                    gap_y = idx
                    break
    if gap_y is not None:
        cut_row = gap_y
    else:
        # Blackhat to emphasize dark text on light background.
            k_w = max(25, band.shape[1] // 20)
            k_h = max(3, band.shape[0] // 60)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, k_h))
            blackhat = cv2.morphologyEx(band, cv2.MORPH_BLACKHAT, kernel)
            bh = cv2.normalize(blackhat, None, 0, 255, cv2.NORM_MINMAX)
            _, bw = cv2.threshold(bh, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            proj = np.sum(bw > 0, axis=1)
            width = max(1, band.shape[1])
            ratios = proj / float(width)
            ratios = np.convolve(ratios, np.ones(3) / 3, mode="same")
            thr = max(0.01, 0.5 * np.median(ratios) + 0.25 * np.max(ratios))
            min_run = 2
            run = 0
            caption_start = None
            for idx, ratio in enumerate(ratios):
                if ratio >= thr:
                    run += 1
                    if run >= min_run:
                        if idx - min_run >= 0 and ratios[idx - min_run] < thr:
                            caption_start = idx - min_run + 1
                            break
                else:
                    run = 0
            if caption_start is not None:
                cut_row = caption_start
            else:
                # Detect a caption text run near the bottom (transition from sparse to denser rows).
                min_run = 3
                caption_start = None
                run = 0
                for idx, ratio in enumerate(nonwhite_ratios):
                    if ratio >= text_ratio_threshold:
                        run += 1
                        if run >= min_run:
                            if idx - min_run >= 0 and nonwhite_ratios[idx - min_run] < text_ratio_threshold:
                                caption_start = idx - min_run + 1
                                break
                    else:
                        run = 0
                if caption_start is None:
                    edges = cv2.Canny(band, 50, 150)
                    edge_ratios = []
                    for yy in range(edges.shape[0]):
                        row = edges[yy, :]
                        edge_ratios.append(float(np.count_nonzero(row)) / float(max(row.size, 1)))
                    edge_thr = max(0.04, text_ratio_threshold * 3.0)
                    run = 0
                    for idx, ratio in enumerate(edge_ratios):
                        if ratio >= edge_thr:
                            run += 1
                            if run >= 2:
                                if idx - 2 >= 0 and edge_ratios[idx - 2] < edge_thr:
                                    caption_start = idx - 2 + 1
                                    break
                        else:
                            run = 0
                    if caption_start is None:
                        _, text_bin = cv2.threshold(band, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                        kernel_w = max(30, band.shape[1] // 12)
                        text_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, 1))
                        text_lines = cv2.morphologyEx(text_bin, cv2.MORPH_OPEN, text_kernel, iterations=1)
                        contours, _ = cv2.findContours(text_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        if contours:
                            min_y = None
                            for cnt in contours:
                                x, y, w, h = cv2.boundingRect(cnt)
                                if w < band.shape[1] * 0.08:
                                    continue
                                if h > band.shape[0] * 0.2:
                                    continue
                                if min_y is None or y < min_y:
                                    min_y = y
                            if min_y is not None:
                                cut_row = min_y
                            else:
                                if caption_nonwhite > caption_max_nonwhite_ratio:
                                    return box
                                return box
                        else:
                            if caption_nonwhite > caption_max_nonwhite_ratio:
                                return box
                            return box
                    else:
                        cut_row = caption_start
                else:
                    cut_row = caption_start

    new_y1 = y0 + start + cut_row - margin_px
    if new_y1 <= y0:
        return box
    return {
        "x0": x0,
        "y0": y0,
        "x1": x1,
        "y1": new_y1,
        "width": x1 - x0,
        "height": new_y1 - y0,
    }
def _extract_images_from_html(html: str) -> List[Dict[str, Any]]:
    """Extract image metadata from HTML img tags (fallback for older OCR output)."""
    images = []
    pattern_with_count = r'<img\s+alt="([^"]*)"\s+data-count="(\d+)">'
    pattern_simple = r'<img\s+alt="([^"]*)"(?:\s*/)?>'

    found_positions = set()
    for match in re.finditer(pattern_with_count, html):
        alt = match.group(1)
        count = int(match.group(2))
        images.append({"alt": alt, "count": count})
        found_positions.add(match.start())

    for match in re.finditer(pattern_simple, html):
        if match.start() not in found_positions:
            full_match = html[match.start():match.start()+150]
            if 'data-count=' not in full_match:
                alt = match.group(1)
                images.append({"alt": alt, "count": 1})

    return images


def _extract_numbers(name: str) -> List[int]:
    return [int(m) for m in re.findall(r"\d+", name)]


def _sort_key(path: Path) -> Tuple[int, List[int], str]:
    numbers = _extract_numbers(path.name)
    has_numbers = 0 if numbers else 1
    return (has_numbers, numbers, path.name.lower())


def _iter_images(input_dir: Path) -> List[Path]:
    images = [p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS]
    return sorted(images, key=_sort_key)


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _log(message: str):
    """Simple logging function."""
    print(message, flush=True)


def _is_bw_image(img: Image.Image) -> bool:
    """Check if image is black & white (grayscale or near-grayscale).
    
    Handles beige/cream paper backgrounds by checking both color variance
    and saturation levels. Desaturated images (low saturation) are treated
    as B&W even if they have slight color variance from aged paper.
    """
    if img.mode in ('L', '1'):
        return True

    if img.mode == 'RGB' or img.mode == 'RGBA':
        img_array = np.array(img)
        if img.mode == 'RGBA':
            rgb = img_array[:, :, :3]
        else:
            rgb = img_array

        # Method 1: Check color variance (strict)
        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        color_variance = np.std([np.mean(r), np.mean(g), np.mean(b)])
        if color_variance < 5:
            return True
        
        # Method 2: Check saturation (handles beige/cream backgrounds)
        # Convert to normalized RGB for saturation calculation
        rgb_norm = rgb.astype(np.float32) / 255.0
        max_val = np.max(rgb_norm, axis=2)
        min_val = np.min(rgb_norm, axis=2)
        delta = max_val - min_val
        
        # Calculate mean saturation (0.0 = grayscale, 1.0 = fully saturated)
        mean_saturation = np.mean(delta)
        
        # If saturation is very low (< 0.25), treat as B&W even with color variance
        # This handles beige/cream paper that has slight R/G/B differences but is effectively grayscale
        if mean_saturation < 0.25:
            return True
        
        # Fallback: if color variance is moderate (< 20) and saturation is low (< 0.30)
        if color_variance < 20 and mean_saturation < 0.30:
            return True

    return False


def _make_transparent(img: Image.Image, threshold: int = 230) -> Image.Image:
    """Convert white background to transparent for B&W artwork.
    
    First converts the image to proper grayscale to remove any beige/cream
    tint, then generates alpha channel from the grayscale values.
    """
    # Convert to proper grayscale first (removes beige/cream tint)
    # This ensures consistent black/white values regardless of paper color
    if img.mode != 'L':
        gray = img.convert('L')
    else:
        gray = img
    
    # Use the grayscale image for both RGB and alpha calculations
    # This ensures the final image is truly black & white (not beige-tinted)
    gray_array = np.array(gray)
    
    # Convert grayscale to RGB (single channel repeated for R, G, B)
    rgb_array = np.stack([gray_array, gray_array, gray_array], axis=2)

    # Invert grayscale to get alpha (dark = opaque, white/light = transparent)
    alpha_array = 255 - gray_array

    # Force near-white pixels fully transparent
    alpha_array[gray_array > threshold] = 0

    rgba_array = np.dstack((rgb_array, alpha_array))
    return Image.fromarray(rgba_array.astype('uint8'), 'RGBA')


def detect_contours_cv(
    image_path: Path,
    expected_count: int = 1,
    blur: int = 7,
    text_kernel: int = 3,
    text_iterations: int = 1,
    min_area_ratio: float = 0.01,
    max_area_ratio: float = 0.99,
    min_width: int = 50,
    min_height: int = 50,
    padding_percent: float = 0.05
) -> List[Dict[str, int]]:
    """Detect illustration bounding boxes using CV contour detection.

    Args:
        image_path: Path to page image
        expected_count: Number of illustrations expected on this page
        blur: Gaussian blur kernel size
        min_area_ratio: Minimum box area as fraction of page area
        max_area_ratio: Maximum box area as fraction of page area
        min_width: Minimum box width in pixels
        min_height: Minimum box height in pixels
        padding_percent: Percentage padding to add around detected boxes (default 0.15 = 15%)

    Returns:
        List of bounding boxes {x0, y0, x1, y1, width, height}
    """
    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img is None:
        return []

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur_k = blur if blur % 2 == 1 else blur + 1
    gray = cv2.GaussianBlur(gray, (blur_k, blur_k), 0)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Morph open to drop specks and suppress small text.
    kernel_size = text_kernel if text_kernel % 2 == 1 else text_kernel + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=text_iterations)

    contours, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    h, w = gray.shape[:2]
    img_area = w * h
    candidates = []

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        ratio = area / img_area

        # Filter by area ratio
        if ratio < min_area_ratio or ratio > max_area_ratio:
            continue

        # Filter by minimum pixel dimensions
        if cw < min_width or ch < min_height:
            continue

        # Looser aspect ratio for guided detection (we know it's an image)
        aspect = cw / max(ch, 1)
        if aspect > 5.0 or aspect < 0.2:
            continue

        candidates.append({
            "x0": int(x),
            "y0": int(y),
            "x1": int(x + cw),
            "y1": int(y + ch),
            "width": int(cw),
            "height": int(ch),
            "area": area,
            "area_ratio": round(ratio, 4)
        })

    # Sort by area (largest first)
    candidates.sort(key=lambda b: b["area"], reverse=True)

    # Take top N non-overlapping candidates
    selected = []
    for candidate in candidates:
        if len(selected) >= expected_count:
            break

        # Check for overlap with already selected boxes
        overlaps = False
        for sel in selected:
            if _boxes_overlap(candidate, sel):
                overlaps = True
                break

        if not overlaps:
            selected.append(candidate)

    # Add padding to selected boxes to capture lighter elements around main subject
    padded = []
    for box in selected:
        # Calculate padding in pixels
        pad_w = int(box["width"] * padding_percent)
        pad_h = int(box["height"] * padding_percent)

        # Expand box with padding, clamped to image boundaries
        x0 = max(0, box["x0"] - pad_w)
        y0 = max(0, box["y0"] - pad_h)
        x1 = min(w, box["x1"] + pad_w)
        y1 = min(h, box["y1"] + pad_h)

        padded.append({
            "x0": int(x0),
            "y0": int(y0),
            "x1": int(x1),
            "y1": int(y1),
            "width": int(x1 - x0),
            "height": int(y1 - y0),
            "area": int((x1 - x0) * (y1 - y0)),
            "area_ratio": round(((x1 - x0) * (y1 - y0)) / img_area, 4)
        })

    return padded


def _boxes_overlap(box1: Dict, box2: Dict) -> bool:
    """Check if two boxes overlap."""
    if (box1["x1"] <= box2["x0"] or box1["x0"] >= box2["x1"] or
        box1["y1"] <= box2["y0"] or box1["y0"] >= box2["y1"]):
        return False
    return True


def _box_iou(box1: Dict[str, int], box2: Dict[str, int]) -> float:
    x0 = max(box1["x0"], box2["x0"])
    y0 = max(box1["y0"], box2["y0"])
    x1 = min(box1["x1"], box2["x1"])
    y1 = min(box1["y1"], box2["y1"])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    area1 = (box1["x1"] - box1["x0"]) * (box1["y1"] - box1["y0"])
    area2 = (box2["x1"] - box2["x0"]) * (box2["y1"] - box2["y0"])
    union = area1 + area2 - inter
    if union <= 0:
        return 0.0
    return inter / union


def _dedupe_boxes(
    boxes: List[Dict[str, int]],
    iou_threshold: float = 0.95,
    center_threshold: int = 10,
    size_ratio_threshold: float = 0.02,
) -> List[Dict[str, int]]:
    if not boxes:
        return boxes
    kept: List[Dict[str, int]] = []
    for box in boxes:
        duplicate = False
        cx = (box["x0"] + box["x1"]) / 2.0
        cy = (box["y0"] + box["y1"]) / 2.0
        for prev in kept:
            if _box_iou(box, prev) >= iou_threshold:
                duplicate = True
                break
            pcx = (prev["x0"] + prev["x1"]) / 2.0
            pcy = (prev["y0"] + prev["y1"]) / 2.0
            if abs(cx - pcx) <= center_threshold and abs(cy - pcy) <= center_threshold:
                w = max(1, box["x1"] - box["x0"])
                h = max(1, box["y1"] - box["y0"])
                pw = max(1, prev["x1"] - prev["x0"])
                ph = max(1, prev["y1"] - prev["y0"])
                if abs(w - pw) / max(w, pw) <= size_ratio_threshold and abs(h - ph) / max(h, ph) <= size_ratio_threshold:
                    duplicate = True
                    break
        if not duplicate:
            kept.append(box)
    return kept


def _prune_contained_boxes(
    boxes: List[Dict[str, int]],
    contain_ratio: float = 0.9,
    min_area_ratio: float = 1.5,
) -> List[Dict[str, int]]:
    if len(boxes) < 2:
        return boxes
    areas = []
    for b in boxes:
        w = max(0, b["x1"] - b["x0"])
        h = max(0, b["y1"] - b["y0"])
        areas.append(float(w * h))
    keep = [True] * len(boxes)
    for i, a in enumerate(boxes):
        if not keep[i]:
            continue
        ax0, ay0, ax1, ay1 = a["x0"], a["y0"], a["x1"], a["y1"]
        for j, b in enumerate(boxes):
            if i == j or not keep[j]:
                continue
            bx0, by0, bx1, by1 = b["x0"], b["y0"], b["x1"], b["y1"]
            ix0 = max(ax0, bx0)
            iy0 = max(ay0, by0)
            ix1 = min(ax1, bx1)
            iy1 = min(ay1, by1)
            if ix1 <= ix0 or iy1 <= iy0:
                continue
            inter = float((ix1 - ix0) * (iy1 - iy0))
            if areas[j] <= 0:
                continue
            if inter / areas[j] >= contain_ratio:
                if areas[i] >= areas[j] * min_area_ratio:
                    keep[i] = False
                    break
    return [b for k, b in zip(keep, boxes) if k]


def _split_box_by_gaps(
    img_gray: np.ndarray,
    box: Dict[str, int],
    white_threshold: int,
    gap_ratio_threshold: float,
    min_gap_px: int,
    min_segment_height: int,
    min_segment_nonwhite_ratio: float,
) -> List[Dict[str, int]]:
    x0, y0, x1, y1 = box["x0"], box["y0"], box["x1"], box["y1"]
    if y1 <= y0 or x1 <= x0:
        return [box]
    roi = img_gray[y0:y1, x0:x1]
    if roi.size == 0:
        return [box]
    h, w = roi.shape[:2]
    if h < min_segment_height * 2:
        return [box]
    nonwhite = (roi < white_threshold).astype("uint8")
    row_ratios = nonwhite.sum(axis=1) / float(max(1, w))
    gaps = row_ratios <= gap_ratio_threshold
    gap_runs = []
    run_start = None
    for idx, is_gap in enumerate(gaps):
        if is_gap and run_start is None:
            run_start = idx
        elif not is_gap and run_start is not None:
            if idx - run_start >= min_gap_px:
                gap_runs.append((run_start, idx - 1))
            run_start = None
    if run_start is not None and h - run_start >= min_gap_px:
        gap_runs.append((run_start, h - 1))
    if not gap_runs:
        return [box]

    split_rows = []
    for g0, g1 in gap_runs:
        split_rows.append((g0 + g1) // 2)
    split_rows = sorted(set([r for r in split_rows if 0 < r < h - 1]))
    if not split_rows:
        return [box]

    segments = []
    prev = 0
    for cut in split_rows + [h]:
        seg_h = cut - prev
        if seg_h >= min_segment_height:
            seg = {
                "x0": x0,
                "y0": y0 + prev,
                "x1": x1,
                "y1": y0 + cut,
                "width": x1 - x0,
                "height": seg_h,
            }
            seg_roi = img_gray[seg["y0"]:seg["y1"], seg["x0"]:seg["x1"]]
            if seg_roi.size > 0:
                ratio = float(np.count_nonzero(seg_roi < white_threshold)) / float(seg_roi.size)
                if ratio >= min_segment_nonwhite_ratio:
                    segments.append(seg)
        prev = cut

    if not segments:
        return [box]
    return segments


def _split_boxes_to_count(
    img_gray: np.ndarray,
    boxes: List[Dict[str, int]],
    expected_count: int,
    white_threshold: int,
    gap_ratio_threshold: float,
    min_gap_px: int,
    min_segment_height: int,
    min_segment_nonwhite_ratio: float,
) -> List[Dict[str, int]]:
    if expected_count <= len(boxes) or not boxes:
        return boxes
    boxes_sorted = sorted(
        boxes,
        key=lambda b: (b.get("height", 0) * b.get("width", 0)),
        reverse=True,
    )
    out: List[Dict[str, int]] = []
    for box in boxes_sorted:
        if len(out) >= expected_count:
            out.append(box)
            continue
        splits = _split_box_by_gaps(
            img_gray,
            box,
            white_threshold=white_threshold,
            gap_ratio_threshold=gap_ratio_threshold,
            min_gap_px=min_gap_px,
            min_segment_height=min_segment_height,
            min_segment_nonwhite_ratio=min_segment_nonwhite_ratio,
        )
        if len(splits) > 1:
            out.extend(splits)
        else:
            out.append(box)
    if len(out) > expected_count:
        out.sort(key=lambda b: (b.get("height", 0) * b.get("width", 0)))
        out = out[-expected_count:]
    out.sort(key=lambda b: (b.get("y0", 0), b.get("x0", 0)))
    return out


def detect_nonwhite_boxes(
    image_path: Path,
    expected_count: int = 1,
    white_threshold: int = 245,
    close_kernel: int = 15,
    close_iterations: int = 2,
    min_nonwhite_ratio: float = 0.02,
    max_text_ratio: float = 0.02,
    text_line_kernel_w: int = 25,
    text_line_kernel_h: int = 3,
    text_line_iterations: int = 1,
    min_area_ratio: float = 0.01,
    max_area_ratio: float = 0.99,
    min_width: int = 50,
    min_height: int = 50,
    padding_percent: float = 0.05
) -> List[Dict[str, int]]:
    """Detect illustration boxes by thresholding non-white pixels and bounding large components."""
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []

    h, w = img.shape[:2]
    img_area = w * h

    # Non-white mask: keep pixels darker than threshold
    mask = (img < white_threshold).astype("uint8") * 255

    # Close to fill halftone dots and unify photo regions
    k = close_kernel if close_kernel % 2 == 1 else close_kernel + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=close_iterations)

    # Build a coarse text-line mask for filtering (favor long horizontal text)
    _, text_bin = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    tlw = text_line_kernel_w if text_line_kernel_w % 2 == 1 else text_line_kernel_w + 1
    tlh = text_line_kernel_h if text_line_kernel_h % 2 == 1 else text_line_kernel_h + 1
    text_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (tlw, tlh))
    text_lines = cv2.morphologyEx(text_bin, cv2.MORPH_OPEN, text_kernel, iterations=text_line_iterations)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        ratio = area / img_area
        if ratio < min_area_ratio or ratio > max_area_ratio:
            continue
        if cw < min_width or ch < min_height:
            continue
        # Filter low-density text blocks (few nonwhite pixels)
        box = closed[y:y + ch, x:x + cw]
        nonwhite_ratio = float(np.count_nonzero(box)) / float(area)
        if nonwhite_ratio < min_nonwhite_ratio:
            continue
        text_box = text_lines[y:y + ch, x:x + cw]
        text_ratio = float(np.count_nonzero(text_box)) / float(area)
        if text_ratio > max_text_ratio:
            continue
        candidates.append({
            "x0": int(x),
            "y0": int(y),
            "x1": int(x + cw),
            "y1": int(y + ch),
            "width": int(cw),
            "height": int(ch),
            "area": area,
            "area_ratio": round(ratio, 4),
        })

    candidates.sort(key=lambda b: b["area"], reverse=True)

    selected = []
    for candidate in candidates:
        if len(selected) >= expected_count:
            break
        overlaps = False
        for sel in selected:
            if _boxes_overlap(candidate, sel):
                overlaps = True
                break
        if not overlaps:
            selected.append(candidate)

    padded = []
    for box in selected:
        pad_w = int(box["width"] * padding_percent)
        pad_h = int(box["height"] * padding_percent)
        x0 = max(0, box["x0"] - pad_w)
        y0 = max(0, box["y0"] - pad_h)
        x1 = min(w, box["x1"] + pad_w)
        y1 = min(h, box["y1"] + pad_h)
        padded.append({
            "x0": int(x0),
            "y0": int(y0),
            "x1": int(x1),
            "y1": int(y1),
            "width": int(x1 - x0),
            "height": int(y1 - y0),
            "area": int((x1 - x0) * (y1 - y0)),
            "area_ratio": round(((x1 - x0) * (y1 - y0)) / img_area, 4),
        })

    return padded


def detect_nontext_boxes(
    image_path: Path,
    expected_count: int = 1,
    white_threshold: int = 245,
    close_kernel: int = 15,
    close_iterations: int = 2,
    text_block_kernel_w: int = 35,
    text_block_kernel_h: int = 7,
    text_block_iterations: int = 2,
    min_area_ratio: float = 0.01,
    max_area_ratio: float = 0.99,
    min_width: int = 50,
    min_height: int = 50,
    padding_percent: float = 0.05
) -> List[Dict[str, int]]:
    """Detect illustration boxes by removing text blocks from non-white mask."""
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []

    h, w = img.shape[:2]
    img_area = w * h

    # Non-white mask
    nonwhite = (img < white_threshold).astype("uint8") * 255

    # Close to fill halftone dots / unify photo regions
    k = close_kernel if close_kernel % 2 == 1 else close_kernel + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    nonwhite = cv2.morphologyEx(nonwhite, cv2.MORPH_CLOSE, kernel, iterations=close_iterations)

    # Text mask: threshold and dilate to join text into blocks
    _, text_bin = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kw = text_block_kernel_w if text_block_kernel_w % 2 == 1 else text_block_kernel_w + 1
    kh = text_block_kernel_h if text_block_kernel_h % 2 == 1 else text_block_kernel_h + 1
    text_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, kh))
    text_blocks = cv2.dilate(text_bin, text_kernel, iterations=text_block_iterations)

    # Remove text blocks from nonwhite mask
    nontext = cv2.bitwise_and(nonwhite, cv2.bitwise_not(text_blocks))

    contours, _ = cv2.findContours(nontext, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        ratio = area / img_area
        if ratio < min_area_ratio or ratio > max_area_ratio:
            continue
        if cw < min_width or ch < min_height:
            continue
        candidates.append({
            "x0": int(x),
            "y0": int(y),
            "x1": int(x + cw),
            "y1": int(y + ch),
            "width": int(cw),
            "height": int(ch),
            "area": area,
            "area_ratio": round(ratio, 4),
        })

    candidates.sort(key=lambda b: b["area"], reverse=True)

    selected = []
    for candidate in candidates:
        if len(selected) >= expected_count:
            break
        overlaps = False
        for sel in selected:
            if _boxes_overlap(candidate, sel):
                overlaps = True
                break
        if not overlaps:
            selected.append(candidate)

    padded = []
    for box in selected:
        pad_w = int(box["width"] * padding_percent)
        pad_h = int(box["height"] * padding_percent)
        x0 = max(0, box["x0"] - pad_w)
        y0 = max(0, box["y0"] - pad_h)
        x1 = min(w, box["x1"] + pad_w)
        y1 = min(h, box["y1"] + pad_h)
        padded.append({
            "x0": int(x0),
            "y0": int(y0),
            "x1": int(x1),
            "y1": int(y1),
            "width": int(x1 - x0),
            "height": int(y1 - y0),
            "area": int((x1 - x0) * (y1 - y0)),
            "area_ratio": round(((x1 - x0) * (y1 - y0)) / img_area, 4),
        })

    return padded


def _nonwhite_ratio(img_gray: np.ndarray, box: Dict[str, int], threshold: int) -> float:
    x0, y0, x1, y1 = box["x0"], box["y0"], box["x1"], box["y1"]
    crop = img_gray[y0:y1, x0:x1]
    if crop.size == 0:
        return 0.0
    mask = crop < threshold
    return float(mask.mean())


def select_boxes(
    image_path: Path,
    expected_count: int,
    candidates: List[Dict[str, int]],
    nonwhite_threshold: int,
    score_min_nonwhite: float
) -> List[Dict[str, int]]:
    """Select top non-overlapping boxes by area and nonwhite density."""
    if not candidates:
        return []

    img_gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img_gray is None:
        return candidates[:expected_count]

    scored = []
    for box in candidates:
        ratio = _nonwhite_ratio(img_gray, box, nonwhite_threshold)
        if ratio < score_min_nonwhite:
            continue
        score = (box.get("area_ratio", 0.0) or 0.0) * (0.5 + 0.5 * ratio)
        scored.append((score, box))
    if not scored:
        scored = [(box.get("area_ratio", 0.0) or 0.0, box) for box in candidates]

    scored.sort(key=lambda t: t[0], reverse=True)
    selected: List[Dict[str, int]] = []
    for _, candidate in scored:
        if len(selected) >= expected_count:
            break
        overlaps = False
        for sel in selected:
            if _boxes_overlap(candidate, sel):
                overlaps = True
                break
        if not overlaps:
            selected.append(candidate)
    return selected


def crop_illustrations_guided(
    ocr_manifest: str,
    output_dir: str,
    run_id: Optional[str] = None,
    transparency: bool = False,
    threshold: int = 230,
    output_format: Optional[str] = None,
    jpeg_quality: int = 92,
    blur: int = 7,
    text_kernel: int = 3,
    text_iterations: int = 1,
    detection_mode: str = "contour",
    white_threshold: int = 245,
    close_kernel: int = 15,
    close_iterations: int = 2,
    text_block_kernel_w: int = 35,
    text_block_kernel_h: int = 7,
    text_block_iterations: int = 2,
    score_min_nonwhite: float = 0.02,
    min_nonwhite_ratio: float = 0.02,
    max_text_ratio: float = 0.02,
    text_line_kernel_w: int = 25,
    text_line_kernel_h: int = 3,
    text_line_iterations: int = 1,
    min_area_ratio: float = 0.01,
    max_area_ratio: float = 0.99,
    min_width: int = 50,
    min_height: int = 50,
    highres_manifest: Optional[str] = None,
    highres_images_dir: Optional[str] = None,
    padding_percent: float = 0.05,
    rescue_model: Optional[str] = None,
    rescue_temperature: float = 0.0,
    rescue_max_tokens: int = 800,
    rescue_max_pages: int = 20,
    rescue_timeout_seconds: Optional[float] = None,
    rescue_include_alt: bool = False,
    rescue_always: bool = False,
    rescue_retry_on_overlap: bool = False,
    rescue_retry_on_missing: bool = False,
    rescue_retry_max: int = 1,
    rescue_require_caption_schema: bool = False,
    rescue_retry_on_text: bool = False,
    rescue_caption_second_pass: bool = False,
    rescue_caption_max_tokens: int = 400,
    rescue_refine_boxes: bool = False,
    rescue_refine_max_tokens: int = 400,
    rescue_refine_min_area_ratio: float = 0.05,
    refine_with_nonwhite: bool = False,
    refine_close_kernel: int = 5,
    refine_close_iterations: int = 1,
    refine_with_nontext: bool = False,
    refine_with_textlines: bool = False,
    refine_textlines_min_area_ratio: float = 0.05,
    trim_text_edges: bool = False,
    text_edge_max_ratio: float = 0.2,
    text_edge_margin_px: int = 4,
    trim_ocr_text_edges: bool = False,
    ocr_trim_edge_ratio: float = 0.2,
    ocr_trim_min_conf: int = 50,
    ocr_trim_min_word_len: int = 3,
    ocr_trim_min_line_words: int = 2,
    ocr_trim_min_line_chars: int = 6,
    ocr_trim_max_ratio: float = 0.45,
    ocr_trim_margin_px: int = 6,
    ocr_tesseract_cmd: Optional[str] = None,
    trim_layout_text: bool = False,
    layout_text_model: str = "PP-DocLayout_plus-L",
    layout_text_score_thresh: float = 0.6,
    layout_text_max_gap_ratio: float = 0.2,
    layout_text_bottom_band_ratio: float = 0.35,
    layout_text_top_band_ratio: float = 0.35,
    layout_text_margin_px: int = 6,
    layout_text_min_width_ratio: float = 0.3,
    layout_text_max_height_ratio: float = 0.25,
    layout_split_text: bool = False,
    layout_split_min_gap_ratio: float = 0.15,
    layout_split_margin_px: int = 6,
    split_when_missing: bool = True,
    split_gap_ratio_threshold: float = 0.01,
    split_min_gap_px: int = 12,
    split_min_segment_height_ratio: float = 0.12,
    split_min_segment_nonwhite_ratio: float = 0.01,
    trim_caption: bool = False,
    caption_max_height_ratio: float = 0.18,
    caption_text_ratio_threshold: float = 0.2,
    caption_margin_px: int = 4,
    caption_max_nonwhite_ratio: float = 0.2,
    caption_trim_passes: int = 1,
    caption_relax_max_gap_ratio: float = 0.15,
) -> List[Dict[str, Any]]:
    """Crop illustrations from pages identified by OCR.

    Args:
        ocr_manifest: Path to OCR JSONL (page_html_v1 schema with images field)
        output_dir: Output directory for cropped images
        run_id: Optional run identifier
        transparency: Generate alpha versions for B&W images
        threshold: White threshold for transparency
        output_format: Output image format (png or jpeg)
        jpeg_quality: JPEG quality when output_format=jpeg
        blur: Gaussian blur kernel size for CV
        min_area_ratio: Min box area ratio for CV
        max_area_ratio: Max box area ratio for CV
        min_width: Min box width in pixels
        min_height: Min box height in pixels
        highres_manifest: Optional path to high-res page images manifest (for better quality crops)
        padding_percent: Percentage padding around detected boxes (default 0.05 = 5%)

    Returns:
        List of manifest records for cropped illustrations
    """
    ensure_dir(output_dir)
    images_dir = os.path.join(output_dir, "images")
    ensure_dir(images_dir)

    fmt, ext = _normalize_output_format(output_format)
    if transparency and fmt == "jpeg":
        _log("  WARNING: transparency requested with JPEG output; disabling transparency.")
        transparency = False

    tesseract_cmd = ocr_tesseract_cmd or os.environ.get("TESSERACT_CMD") or shutil.which("tesseract")
    if trim_ocr_text_edges and not tesseract_cmd:
        _log("  WARNING: trim_ocr_text_edges enabled but no tesseract found; skipping OCR trims.")
    layout_engine = None
    layout_engine_failed = False
    layout_text_cache: Dict[int, List[List[int]]] = {}

    pages = list(read_jsonl(ocr_manifest))
    manifest = []

    # Build high-res page map from highres_manifest OR from image_native fields
    highres_page_map = {}

    # First, check if pages have image_native field (preferred)
    native_count = 0
    for page in pages:
        page_num = page.get("page_number")
        image_native = page.get("image_native")
        if page_num and image_native and os.path.exists(image_native):
            highres_page_map[page_num] = image_native
            native_count += 1

    if native_count > 0:
        _log(f"Using image_native from manifest for {native_count} pages")

    # If a high-res images directory is provided, map by sorted order (1-based page_number)
    if highres_images_dir:
        input_dir = Path(highres_images_dir)
        if input_dir.exists() and input_dir.is_dir():
            images = _iter_images(input_dir)
            if images:
                for idx, img_path in enumerate(images, start=1):
                    highres_page_map[idx] = str(img_path.resolve())
                _log(f"Loaded {len(images)} high-res images from directory {input_dir}")
        else:
            _log(f"High-res images dir not found: {input_dir}")

    # If highres_manifest provided, override/supplement with those
    if highres_manifest:
        _log(f"Loading additional high-res images from {highres_manifest}")
        highres_pages = list(read_jsonl(highres_manifest))
        external_count = 0
        for hr_page in highres_pages:
            page_num = hr_page.get("page_number")
            # Check both image and image_native from external manifest
            image_path = hr_page.get("image_native") or hr_page.get("image")
            if page_num and image_path and os.path.exists(image_path):
                highres_page_map[page_num] = image_path
                external_count += 1
        _log(f"Loaded {external_count} high-res images from external manifest")

    # Filter to pages with images (check images field or extract from HTML)
    pages_with_images = []
    for p in pages:
        if p.get("images"):
            pages_with_images.append(p)
        elif p.get("html") and "<img" in p.get("html", ""):
            # Fallback: extract from HTML for older OCR output
            extracted = _extract_images_from_html(p.get("html", ""))
            if extracted:
                p["images"] = extracted
                pages_with_images.append(p)

    _log(f"Found {len(pages_with_images)} pages with images out of {len(pages)} total")

    rescue_used = 0
    for page_rec in pages_with_images:
        page_num = page_rec.get("page_number")
        image_path = page_rec.get("image")
        ocr_images = page_rec.get("images", [])

        # Use high-res image if available, otherwise use OCR image
        source_image_path = highres_page_map.get(page_num, image_path)

        if not source_image_path or not os.path.exists(source_image_path):
            _log(f"  Page {page_num}: Image not found, skipping")
            continue

        # Calculate expected count.
        # If multiple <img> tags exist, prefer tag count (data-count is often noisy).
        # If only one tag exists, allow data-count to request multiple crops.
        if len(ocr_images) > 1:
            expected_count = len(ocr_images)
        else:
            expected_count = sum(img.get("count", 1) for img in ocr_images)

        # Flatten OCR image list for rescue hints and alt matching.
        # If multiple tags exist, treat each as a single image to avoid noisy data-count inflation.
        ocr_descriptions = []
        if len(ocr_images) > 1:
            for img in ocr_images:
                ocr_descriptions.append(img.get("alt", ""))
        else:
            for img in ocr_images:
                count = img.get("count", 1)
                for _ in range(count):
                    ocr_descriptions.append(img.get("alt", ""))

        using_highres = source_image_path != image_path
        resolution_label = "high-res" if using_highres else "OCR-res"
        _log(f"  Page {page_num}: Expecting {expected_count} illustration(s) [{resolution_label}]")

        # Run CV detection with expected count
        if detection_mode == "layout":
            if layout_engine is None and not layout_engine_failed:
                try:
                    os.environ.setdefault("DISABLE_MODEL_SOURCE_CHECK", "True")
                    from paddleocr import LayoutDetection
                    layout_engine = LayoutDetection(model_name=layout_text_model)
                except Exception as exc:
                    layout_engine_failed = True
                    _log(f"  WARNING: layout detection failed to init: {exc}")
            if layout_engine is None:
                boxes = []
            else:
                boxes = _layout_image_boxes_for_page(
                    layout_engine,
                    source_image_path,
                    score_thresh=layout_text_score_thresh,
                )
                if boxes:
                    boxes = _prune_contained_boxes(boxes, contain_ratio=0.9, min_area_ratio=1.5)
        elif detection_mode == "nonwhite":
            boxes = detect_nonwhite_boxes(
                Path(source_image_path),
                expected_count=expected_count,
                white_threshold=white_threshold,
                close_kernel=close_kernel,
                close_iterations=close_iterations,
                min_nonwhite_ratio=min_nonwhite_ratio,
                max_text_ratio=max_text_ratio,
                text_line_kernel_w=text_line_kernel_w,
                text_line_kernel_h=text_line_kernel_h,
                text_line_iterations=text_line_iterations,
                min_area_ratio=min_area_ratio,
                max_area_ratio=max_area_ratio,
                min_width=min_width,
                min_height=min_height,
                padding_percent=padding_percent,
            )
        elif detection_mode == "nontext":
            boxes = detect_nontext_boxes(
                Path(source_image_path),
                expected_count=expected_count,
                white_threshold=white_threshold,
                close_kernel=close_kernel,
                close_iterations=close_iterations,
                text_block_kernel_w=text_block_kernel_w,
                text_block_kernel_h=text_block_kernel_h,
                text_block_iterations=text_block_iterations,
                min_area_ratio=min_area_ratio,
                max_area_ratio=max_area_ratio,
                min_width=min_width,
                min_height=min_height,
                padding_percent=padding_percent,
            )
        elif detection_mode == "auto":
            contour_boxes = detect_contours_cv(
                Path(source_image_path),
                expected_count=expected_count,
                blur=blur,
                text_kernel=text_kernel,
                text_iterations=text_iterations,
                min_area_ratio=min_area_ratio,
                max_area_ratio=max_area_ratio,
                min_width=min_width,
                min_height=min_height,
                padding_percent=padding_percent,
            )
            nonwhite_boxes = detect_nonwhite_boxes(
                Path(source_image_path),
                expected_count=expected_count,
                white_threshold=white_threshold,
                close_kernel=close_kernel,
                close_iterations=close_iterations,
                min_nonwhite_ratio=min_nonwhite_ratio,
                max_text_ratio=max_text_ratio,
                text_line_kernel_w=text_line_kernel_w,
                text_line_kernel_h=text_line_kernel_h,
                text_line_iterations=text_line_iterations,
                min_area_ratio=min_area_ratio,
                max_area_ratio=max_area_ratio,
                min_width=min_width,
                min_height=min_height,
                padding_percent=padding_percent,
            )
            boxes = select_boxes(
                Path(source_image_path),
                expected_count,
                contour_boxes + nonwhite_boxes,
                nonwhite_threshold=white_threshold,
                score_min_nonwhite=score_min_nonwhite,
            )
        else:
            boxes = detect_contours_cv(
                Path(source_image_path),
                expected_count=expected_count,
                blur=blur,
                text_kernel=text_kernel,
                text_iterations=text_iterations,
                min_area_ratio=min_area_ratio,
                max_area_ratio=max_area_ratio,
                min_width=min_width,
                min_height=min_height,
                padding_percent=padding_percent,
            )

        image_data = None
        if rescue_model and rescue_used < rescue_max_pages and (rescue_always or len(boxes) < expected_count):
            try:
                img = cv2.imread(str(source_image_path), cv2.IMREAD_GRAYSCALE)
                if img is None:
                    raise RuntimeError("image load failed")
                h, w = img.shape[:2]
                image_data = _encode_image(source_image_path)
                _log(f"    VLM rescue: requesting {expected_count} box(es) via {rescue_model}")
                alt_hints = ocr_descriptions if rescue_include_alt else None
                vlm_boxes, usage, request_id, vlm_raw = _call_vlm_boxes(
                    rescue_model,
                    image_data,
                    expected_count,
                    alt_hints,
                    rescue_temperature,
                    rescue_max_tokens,
                    rescue_timeout_seconds,
                )
                has_caption_schema = any(b.get("_caption_schema") for b in vlm_boxes)
                _log(f"    VLM rescue: caption schema returned={has_caption_schema}")
                debug_dir = os.environ.get("CROP_VLM_DEBUG_DIR")
                if debug_dir:
                    ensure_dir(debug_dir)
                    debug_path = os.path.join(debug_dir, f"page-{page_num:03d}-vlm.json")
                    with open(debug_path, "w", encoding="utf-8") as f:
                        json.dump(
                            {
                                "page_number": page_num,
                                "expected_count": expected_count,
                                "alt_hints": alt_hints or [],
                                "raw": vlm_raw,
                            },
                            f,
                            ensure_ascii=True,
                            indent=2,
                        )
                normalized = []
                for box in vlm_boxes:
                    px = _normalize_box(box, w, h)
                    if not px:
                        continue
                    cap_box = box.get("caption_box")
                    if isinstance(cap_box, dict):
                        cap_px = _normalize_box(cap_box, w, h)
                        if cap_px:
                            px["caption_box"] = cap_px
                    px["_from_vlm"] = True
                    area_ratio = (px["width"] * px["height"]) / float(w * h)
                    px["area_ratio"] = round(area_ratio, 4)
                    normalized.append(px)
                if normalized:
                    retry = False
                    deduped = _dedupe_boxes(normalized, iou_threshold=0.9, center_threshold=8, size_ratio_threshold=0.03)
                    if rescue_retry_on_overlap and len(deduped) < len(normalized) and len(deduped) < expected_count:
                        retry = True
                    if rescue_retry_on_missing and len(normalized) < expected_count:
                        retry = True
                    if rescue_require_caption_schema and not has_caption_schema:
                        retry = True
                    if rescue_retry_on_text:
                        edge_ratio = text_edge_max_ratio if text_edge_max_ratio > 0 else 0.2
                        for box in normalized:
                            if _box_has_text_band(img, box, white_threshold, edge_ratio):
                                retry = True
                                break
                    if retry and rescue_retry_max > 0:
                        _log("    VLM rescue: retrying due to overlap/missing boxes")
                        retry_instructions = (
                            f"The page may contain multiple separate images. "
                            f"Return up to {expected_count} distinct boxes. "
                            "Do not return overlapping boxes. "
                            "If images are stacked vertically, return one box per image. "
                            "Exclude captions and all text."
                        )
                        vlm_boxes, usage, request_id, vlm_raw = _call_vlm_boxes(
                            rescue_model,
                            image_data,
                            expected_count,
                            alt_hints,
                            rescue_temperature,
                            rescue_max_tokens,
                            rescue_timeout_seconds,
                            extra_instructions=retry_instructions,
                        )
                        has_caption_schema = any(b.get("_caption_schema") for b in vlm_boxes)
                        debug_dir = os.environ.get("CROP_VLM_DEBUG_DIR")
                        if debug_dir:
                            ensure_dir(debug_dir)
                            debug_path = os.path.join(debug_dir, f"page-{page_num:03d}-vlm-retry.json")
                            with open(debug_path, "w", encoding="utf-8") as f:
                                json.dump(
                                    {
                                        "page_number": page_num,
                                        "expected_count": expected_count,
                                        "alt_hints": alt_hints or [],
                                        "raw": vlm_raw,
                                    },
                                    f,
                                    ensure_ascii=True,
                                    indent=2,
                                )
                        normalized = []
                        for box in vlm_boxes:
                            px = _normalize_box(box, w, h)
                            if not px:
                                continue
                            cap_box = box.get("caption_box")
                            if isinstance(cap_box, dict):
                                cap_px = _normalize_box(cap_box, w, h)
                                if cap_px:
                                    px["caption_box"] = cap_px
                            px["_from_vlm"] = True
                            area_ratio = (px["width"] * px["height"]) / float(w * h)
                            px["area_ratio"] = round(area_ratio, 4)
                            normalized.append(px)
                    if normalized:
                        boxes = normalized[:expected_count]
                        rescue_used += 1
                        _log(f"    VLM rescue: using {len(boxes)} box(es) (request {request_id})")
                    else:
                        _log("    VLM rescue: no valid boxes parsed")
                else:
                    _log("    VLM rescue: no valid boxes parsed")
            except Exception as exc:
                _log(f"    VLM rescue failed: {exc}")

        img_gray = None
        if boxes and (trim_caption or (split_when_missing and len(boxes) < expected_count)):
            img_gray = cv2.imread(str(source_image_path), cv2.IMREAD_GRAYSCALE)

        if rescue_caption_second_pass and rescue_model and boxes:
            try:
                if img_gray is None:
                    img_gray = cv2.imread(str(source_image_path), cv2.IMREAD_GRAYSCALE)
                if img_gray is not None:
                    if image_data is None:
                        image_data = _encode_image(source_image_path)
                    h, w = img_gray.shape[:2]
                    cap_boxes, _, _, _ = _call_vlm_caption_boxes(
                        rescue_model,
                        image_data,
                        expected_count=len(boxes),
                        alt_hints=ocr_descriptions if rescue_include_alt else None,
                        temperature=rescue_temperature,
                        max_tokens=rescue_caption_max_tokens,
                        timeout_seconds=rescue_timeout_seconds,
                    )
                    normalized_caps = []
                    for cap in cap_boxes:
                        cap_px = _normalize_box(cap, w, h)
                        if cap_px:
                            normalized_caps.append(cap_px)
                    if normalized_caps:
                        for idx, cap_px in enumerate(normalized_caps):
                            if idx >= len(boxes):
                                break
                            boxes[idx]["caption_box"] = {
                                "x0": cap_px["x0"],
                                "y0": cap_px["y0"],
                                "x1": cap_px["x1"],
                                "y1": cap_px["y1"],
                            }
            except Exception as exc:
                _log(f"    VLM caption pass failed: {exc}")

        if refine_with_nonwhite and boxes:
            boxes = _refine_boxes_with_nonwhite(
                source_image_path,
                boxes,
                white_threshold=white_threshold,
                close_kernel=refine_close_kernel,
                close_iterations=refine_close_iterations,
            )

        if refine_with_nontext and boxes:
            if img_gray is None:
                img_gray = cv2.imread(str(source_image_path), cv2.IMREAD_GRAYSCALE)
            boxes = _refine_boxes_with_nontext(
                img_gray,
                boxes,
                white_threshold=white_threshold,
                close_kernel=close_kernel,
                close_iterations=close_iterations,
                text_block_kernel_w=text_block_kernel_w,
                text_block_kernel_h=text_block_kernel_h,
                text_block_iterations=text_block_iterations,
            )

        if refine_with_textlines and boxes:
            if img_gray is None:
                img_gray = cv2.imread(str(source_image_path), cv2.IMREAD_GRAYSCALE)
            refined = []
            to_refine = []
            for box in boxes:
                if box.get("_from_vlm"):
                    refined.append(box)
                else:
                    to_refine.append(box)
            if to_refine:
                refined.extend(
                    _refine_boxes_remove_text_lines(
                        img_gray,
                        to_refine,
                        white_threshold=white_threshold,
                        text_line_kernel_w=text_line_kernel_w,
                        text_line_kernel_h=text_line_kernel_h,
                        text_line_iterations=text_line_iterations,
                        min_component_area_ratio=refine_textlines_min_area_ratio,
                    )
                )
            boxes = refined

        if trim_text_edges and boxes:
            if img_gray is None:
                img_gray = cv2.imread(str(source_image_path), cv2.IMREAD_GRAYSCALE)
            trimmed_edges = []
            for box in boxes:
                trimmed_edges.append(
                    _trim_text_edges(
                        img_gray,
                        box,
                        white_threshold=white_threshold,
                        text_line_kernel_w=text_line_kernel_w,
                        text_line_kernel_h=text_line_kernel_h,
                        text_line_iterations=text_line_iterations,
                        max_trim_ratio=text_edge_max_ratio,
                        margin_px=text_edge_margin_px,
                    )
                )
            boxes = trimmed_edges

        if not boxes:
            _log(f"    CV detection found 0 boxes (expected {expected_count})")
            continue

        if len(boxes) < expected_count:
            _log(f"    CV detection found {len(boxes)} boxes (expected {expected_count})")

        # Load page image for cropping
        page_img = Image.open(source_image_path)
        img_w, img_h = page_img.size
        for box in boxes:
            if "area_ratio" not in box:
                area = (box["width"] * box["height"]) if box.get("width") and box.get("height") else 0
                if area and img_w and img_h:
                    box["area_ratio"] = round(area / float(img_w * img_h), 4)
                else:
                    box["area_ratio"] = 0.0
        if detection_mode == "layout" and boxes:
            boxes = sorted(boxes, key=lambda b: b.get("area_ratio", 0.0), reverse=True)[:expected_count]

        # Match boxes with OCR image descriptions (by order/position)
        # Sort boxes by y-position to match reading order
        boxes_sorted = sorted(boxes, key=lambda b: (b["y0"], b["x0"]))
        boxes_deduped = _dedupe_boxes(boxes_sorted)
        if len(boxes_deduped) < len(boxes_sorted):
            boxes_sorted = boxes_deduped
            _log(f"    Deduped boxes: {len(boxes)} -> {len(boxes_sorted)}")

        if img_gray is not None and boxes_sorted and split_when_missing and len(boxes_sorted) < expected_count:
            min_segment_height = max(40, int(img_gray.shape[0] * split_min_segment_height_ratio))
            boxes_sorted = _split_boxes_to_count(
                img_gray,
                boxes_sorted,
                expected_count=expected_count,
                white_threshold=white_threshold,
                gap_ratio_threshold=split_gap_ratio_threshold,
                min_gap_px=split_min_gap_px,
                min_segment_height=min_segment_height,
                min_segment_nonwhite_ratio=split_min_segment_nonwhite_ratio,
            )

        if boxes_sorted:
            boxes_sorted = [_apply_caption_box(b, caption_margin_px, caption_relax_max_gap_ratio) for b in boxes_sorted]

        if trim_layout_text and boxes_sorted:
            if layout_engine is None and not layout_engine_failed:
                try:
                    os.environ.setdefault("DISABLE_MODEL_SOURCE_CHECK", "True")
                    from paddleocr import LayoutDetection
                    layout_engine = LayoutDetection(model_name=layout_text_model)
                except Exception as exc:
                    layout_engine_failed = True
                    _log(f"  WARNING: layout text trim disabled (LayoutDetection init failed): {exc}")
            if layout_engine is not None:
                layout_boxes = layout_text_cache.get(page_num)
                if layout_boxes is None:
                    layout_boxes = _layout_text_boxes_for_page(
                        layout_engine,
                        source_image_path,
                        score_thresh=layout_text_score_thresh,
                    )
                    layout_text_cache[page_num] = layout_boxes
                if layout_boxes:
                    processed = []
                    for box in boxes_sorted:
                        split_boxes = [box]
                        if layout_split_text:
                            split_boxes = _split_box_by_layout_text_band(
                                box,
                                layout_boxes,
                                min_width_ratio=layout_text_min_width_ratio,
                                max_height_ratio=layout_text_max_height_ratio,
                                min_gap_ratio=layout_split_min_gap_ratio,
                                margin_px=layout_split_margin_px,
                            )
                        for split_box in split_boxes:
                            processed.append(
                                _trim_box_by_layout_text(
                                    split_box,
                                    layout_boxes,
                                    max_gap_ratio=layout_text_max_gap_ratio,
                                    bottom_band_ratio=layout_text_bottom_band_ratio,
                                    top_band_ratio=layout_text_top_band_ratio,
                                    margin_px=layout_text_margin_px,
                                    min_width_ratio=layout_text_min_width_ratio,
                                    max_height_ratio=layout_text_max_height_ratio,
                                )
                            )
                    boxes_sorted = processed

        if trim_ocr_text_edges and boxes_sorted and tesseract_cmd:
            if img_gray is None:
                img_gray = cv2.imread(str(source_image_path), cv2.IMREAD_GRAYSCALE)
            if img_gray is not None:
                trimmed_ocr = []
                for box in boxes_sorted:
                    trimmed_ocr.append(
                        _trim_box_by_ocr_text(
                            img_gray,
                            box,
                            tesseract_cmd=tesseract_cmd,
                            edge_ratio=ocr_trim_edge_ratio,
                            min_conf=ocr_trim_min_conf,
                            min_word_len=ocr_trim_min_word_len,
                            white_threshold=white_threshold,
                            min_line_words=ocr_trim_min_line_words,
                            min_line_chars=ocr_trim_min_line_chars,
                            max_trim_ratio=ocr_trim_max_ratio,
                            margin_px=ocr_trim_margin_px,
                        )
                    )
                boxes_sorted = trimmed_ocr

        if trim_caption and boxes_sorted:
            if img_gray is None:
                img_gray = cv2.imread(str(source_image_path), cv2.IMREAD_GRAYSCALE)
            if img_gray is not None:
                trimmed = []
                for idx, box in enumerate(boxes_sorted):
                    if box.get("_caption_applied"):
                        trimmed.append(box)
                        continue
                    new_box = box
                    passes = max(1, int(caption_trim_passes))
                    for pass_idx in range(passes):
                        ratio = min(0.6, caption_max_height_ratio * (1.5 ** pass_idx))
                        next_box = _trim_caption_from_box(
                            img_gray,
                            new_box,
                            max_caption_height_ratio=ratio,
                            text_ratio_threshold=caption_text_ratio_threshold,
                            margin_px=caption_margin_px,
                            caption_max_nonwhite_ratio=caption_max_nonwhite_ratio,
                            white_threshold=white_threshold,
                        )
                        if next_box.get("y1") == new_box.get("y1"):
                            break
                        new_box = next_box
                    if new_box.get("y1") != box.get("y1"):
                        _log(f"    Trimmed caption: page {page_num} box {idx} y1 {box.get('y1')} -> {new_box.get('y1')}")
                    trimmed.append(new_box)
                boxes_sorted = trimmed

        if rescue_refine_boxes and rescue_model and boxes_sorted:
            try:
                if page_img is None:
                    page_img = Image.open(source_image_path)
                boxes_sorted = _refine_boxes_with_vlm(
                    page_img,
                    boxes_sorted,
                    model=rescue_model,
                    temperature=rescue_temperature,
                    max_tokens=rescue_refine_max_tokens,
                    timeout_seconds=rescue_timeout_seconds,
                    min_area_ratio=rescue_refine_min_area_ratio,
                )
            except Exception as exc:
                _log(f"    VLM refine failed: {exc}")

        for box in boxes_sorted:
            if "area_ratio" not in box:
                area = (box["x1"] - box["x0"]) * (box["y1"] - box["y0"])
                box["area_ratio"] = round(area / float(img_w * img_h), 4) if area and img_w and img_h else 0.0

        for box_idx, box in enumerate(boxes_sorted):
            # Get description from OCR if available
            alt = ""
            if box_idx < len(ocr_descriptions):
                alt = ocr_descriptions[box_idx]

            # Crop illustration
            cropped = page_img.crop((box["x0"], box["y0"], box["x1"], box["y1"]))

            # Generate filename
            filename = f"page-{page_num:03d}-{box_idx:03d}.{ext}"
            filepath = os.path.join(images_dir, filename)

            # Save original
            if fmt == "jpeg":
                if cropped.mode not in ("RGB", "L"):
                    cropped = cropped.convert("RGB")
                cropped.save(filepath, "JPEG", quality=jpeg_quality, optimize=True)
            else:
                cropped.save(filepath, "PNG")

            # Detect if image is color or B&W
            is_bw = _is_bw_image(cropped)
            is_color = not is_bw

            # Generate alpha version if B&W and transparency enabled
            filename_alpha = None
            has_transparency = False

            if transparency and is_bw:
                filename_alpha = f"page-{page_num:03d}-{box_idx:03d}-alpha.png"
                filepath_alpha = os.path.join(images_dir, filename_alpha)

                cropped_alpha = _make_transparent(cropped, threshold)
                cropped_alpha.save(filepath_alpha, "PNG")
                has_transparency = True

            # Build manifest record
            record = {
                "schema_version": "illustration_v1",
                "module_id": "crop_illustrations_guided_v1",
                "run_id": run_id,
                "created_at": _utc(),
                "source_image": image_path,
                "source_page": page_num,
                "filename": filename,
                "filename_alpha": filename_alpha,
                "has_transparency": has_transparency,
                "is_color": is_color,
                "alt": alt,
                "bbox": {
                    "x0": box["x0"],
                    "y0": box["y0"],
                    "x1": box["x1"],
                    "y1": box["y1"],
                    "width": box["width"],
                    "height": box["height"]
                },
                "area_ratio": box["area_ratio"],
                "detection_method": "cv_guided"
            }

            manifest.append(record)

    # Count color vs B&W illustrations
    color_count = sum(1 for m in manifest if m.get("is_color", False))
    bw_count = len(manifest) - color_count

    _log(f"\nCropped {len(manifest)} illustration(s) from {len(pages_with_images)} pages")
    _log(f"  Color: {color_count}, B&W: {bw_count}")
    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Crop illustrations using OCR metadata + CV detection"
    )
    parser.add_argument(
        "--ocr-manifest",
        required=True,
        help="OCR JSONL manifest (page_html_v1 with images field)"
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Output directory"
    )
    parser.add_argument(
        "--run-id",
        help="Run identifier"
    )
    parser.add_argument(
        "--transparency",
        action="store_true",
        help="Generate alpha versions for B&W images"
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=230,
        help="White threshold for transparency (default 230)"
    )
    parser.add_argument(
        "--output-format",
        default="png",
        choices=["png", "jpeg", "jpg"],
        help="Output image format: png (default) or jpeg"
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=92,
        help="JPEG quality when output-format=jpeg (default 92)"
    )
    parser.add_argument(
        "--blur",
        type=int,
        default=7,
        help="Gaussian blur kernel size for CV (default 7)"
    )
    parser.add_argument(
        "--text-kernel",
        type=int,
        default=3,
        help="Morphological open kernel size to suppress small text (default 3)"
    )
    parser.add_argument(
        "--text-iterations",
        type=int,
        default=1,
        help="Morphological open iterations for text suppression (default 1)"
    )
    parser.add_argument(
        "--detection-mode",
        default="contour",
        choices=["contour", "nonwhite", "nontext", "auto", "layout"],
        help="Detection mode: contour (default), nonwhite, nontext, auto, or layout"
    )
    parser.add_argument(
        "--white-threshold",
        type=int,
        default=245,
        help="Nonwhite detection threshold (default 245)"
    )
    parser.add_argument(
        "--close-kernel",
        type=int,
        default=15,
        help="Morphological close kernel size for nonwhite mode (default 15)"
    )
    parser.add_argument(
        "--close-iterations",
        type=int,
        default=2,
        help="Morphological close iterations for nonwhite mode (default 2)"
    )
    parser.add_argument(
        "--text-block-kernel-w",
        type=int,
        default=35,
        help="Text block kernel width for nontext mode (default 35)"
    )
    parser.add_argument(
        "--text-block-kernel-h",
        type=int,
        default=7,
        help="Text block kernel height for nontext mode (default 7)"
    )
    parser.add_argument(
        "--text-block-iterations",
        type=int,
        default=2,
        help="Text block dilation iterations for nontext mode (default 2)"
    )
    parser.add_argument(
        "--score-min-nonwhite",
        type=float,
        default=0.02,
        help="Minimum nonwhite ratio for scoring candidate boxes (auto mode)"
    )
    parser.add_argument(
        "--min-nonwhite-ratio",
        type=float,
        default=0.02,
        help="Minimum nonwhite ratio for nonwhite mode (default 0.02)"
    )
    parser.add_argument(
        "--max-text-ratio",
        type=float,
        default=0.02,
        help="Maximum text ratio for nonwhite mode (default 0.02)"
    )
    parser.add_argument(
        "--text-line-kernel-w",
        type=int,
        default=25,
        help="Text line kernel width for nonwhite mode (default 25)"
    )
    parser.add_argument(
        "--text-line-kernel-h",
        type=int,
        default=3,
        help="Text line kernel height for nonwhite mode (default 3)"
    )
    parser.add_argument(
        "--text-line-iterations",
        type=int,
        default=1,
        help="Text line morphology iterations for nonwhite mode (default 1)"
    )
    parser.add_argument(
        "--min-area-ratio",
        type=float,
        default=0.01,
        help="Min box area ratio (default 0.01)"
    )
    parser.add_argument(
        "--max-area-ratio",
        type=float,
        default=0.99,
        help="Max box area ratio (default 0.99)"
    )
    parser.add_argument(
        "--min-width",
        type=int,
        default=50,
        help="Min box width in pixels (default 50)"
    )
    parser.add_argument(
        "--min-height",
        type=int,
        default=50,
        help="Min box height in pixels (default 50)"
    )
    parser.add_argument(
        "--highres-manifest",
        help="Optional high-res page images manifest (for better quality crops)"
    )
    parser.add_argument(
        "--highres-images-dir",
        default=None,
        help="Optional high-res images directory (sorted to page order)"
    )
    parser.add_argument(
        "--padding-percent",
        type=float,
        default=0.05,
        help="Percentage padding around detected boxes (default 0.05 = 5%%)"
    )
    parser.add_argument(
        "--rescue-model",
        default=None,
        help="Optional vision model to rescue image boxes when CV misses (e.g., gpt-5.1)"
    )
    parser.add_argument(
        "--rescue-temperature",
        type=float,
        default=0.0,
        help="Rescue model temperature (default 0.0)"
    )
    parser.add_argument(
        "--rescue-max-tokens",
        type=int,
        default=800,
        help="Rescue model max output tokens (default 800)"
    )
    parser.add_argument(
        "--rescue-max-pages",
        type=int,
        default=20,
        help="Maximum pages to rescue with VLM (default 20)"
    )
    parser.add_argument(
        "--rescue-timeout-seconds",
        type=float,
        default=None,
        help="Timeout seconds for rescue model requests"
    )
    parser.add_argument(
        "--rescue-include-alt",
        action="store_true",
        help="Include OCR image descriptions in rescue prompt"
    )
    parser.add_argument(
        "--rescue-always",
        action="store_true",
        help="Always use rescue model on image pages (overrides CV boxes)"
    )
    parser.add_argument(
        "--rescue-retry-on-overlap",
        action="store_true",
        help="Retry VLM once if returned boxes overlap heavily"
    )
    parser.add_argument(
        "--rescue-retry-on-missing",
        action="store_true",
        help="Retry VLM once if returned box count is below expected"
    )
    parser.add_argument(
        "--rescue-retry-on-text",
        action="store_true",
        help="Retry VLM once if detected text bands remain inside crops"
    )
    parser.add_argument(
        "--rescue-retry-max",
        type=int,
        default=1,
        help="Maximum number of VLM retries (default 1)"
    )
    parser.add_argument(
        "--rescue-require-caption-schema",
        action="store_true",
        help="Require VLM to return image_box/caption_box schema (retry if not)"
    )
    parser.add_argument(
        "--rescue-caption-second-pass",
        action="store_true",
        help="Run a second VLM pass to locate caption boxes"
    )
    parser.add_argument(
        "--rescue-caption-max-tokens",
        type=int,
        default=400,
        help="Max tokens for VLM caption pass (default 400)"
    )
    parser.add_argument(
        "--rescue-refine-boxes",
        action="store_true",
        help="Refine each crop with a second VLM call on the crop"
    )
    parser.add_argument(
        "--rescue-refine-max-tokens",
        type=int,
        default=400,
        help="Max tokens for VLM refine pass (default 400)"
    )
    parser.add_argument(
        "--rescue-refine-min-area-ratio",
        type=float,
        default=0.05,
        help="Minimum area ratio vs original crop to accept VLM refine (default 0.05)"
    )
    parser.add_argument(
        "--refine-with-nonwhite",
        action="store_true",
        help="Refine boxes by expanding to nonwhite connected components"
    )
    parser.add_argument(
        "--refine-close-kernel",
        type=int,
        default=5,
        help="Close kernel size for refine nonwhite mask (default 5)"
    )
    parser.add_argument(
        "--refine-close-iterations",
        type=int,
        default=1,
        help="Close iterations for refine nonwhite mask (default 1)"
    )
    parser.add_argument(
        "--refine-with-nontext",
        action="store_true",
        help="Refine boxes by removing text blocks from nonwhite mask"
    )
    parser.add_argument(
        "--refine-with-textlines",
        action="store_true",
        help="Refine boxes by removing horizontal text lines (keep largest non-text component)"
    )
    parser.add_argument(
        "--refine-textlines-min-area-ratio",
        type=float,
        default=0.05,
        help="Minimum area ratio for text-line refinement (default 0.05)"
    )
    parser.add_argument(
        "--trim-text-edges",
        action="store_true",
        help="Trim text-line runs at top/bottom edges of a crop"
    )
    parser.add_argument(
        "--text-edge-max-ratio",
        type=float,
        default=0.2,
        help="Max fraction of box height allowed for text-edge trimming (default 0.2)"
    )
    parser.add_argument(
        "--text-edge-margin-px",
        type=int,
        default=4,
        help="Extra margin to remove past detected text-edge (default 4)"
    )
    parser.add_argument(
        "--trim-ocr-text-edges",
        action="store_true",
        help="Trim crops using OCR text detection in top/bottom bands"
    )
    parser.add_argument(
        "--ocr-trim-edge-ratio",
        type=float,
        default=0.2,
        help="Fraction of crop height to scan for OCR text (default 0.2)"
    )
    parser.add_argument(
        "--ocr-trim-min-conf",
        type=int,
        default=50,
        help="Minimum OCR confidence to consider text (default 50)"
    )
    parser.add_argument(
        "--ocr-trim-min-word-len",
        type=int,
        default=3,
        help="Minimum OCR word length to consider text (default 3)"
    )
    parser.add_argument(
        "--ocr-trim-min-line-words",
        type=int,
        default=2,
        help="Minimum number of words in a line to trim (default 2)"
    )
    parser.add_argument(
        "--ocr-trim-min-line-chars",
        type=int,
        default=6,
        help="Minimum number of characters in a line to trim (default 6)"
    )
    parser.add_argument(
        "--ocr-trim-max-ratio",
        type=float,
        default=0.45,
        help="Maximum fraction of crop height allowed for OCR trimming (default 0.45)"
    )
    parser.add_argument(
        "--ocr-trim-margin-px",
        type=int,
        default=6,
        help="Extra margin to remove past OCR text (default 6)"
    )
    parser.add_argument(
        "--ocr-tesseract-cmd",
        type=str,
        default=None,
        help="Optional tesseract command path for OCR trimming"
    )
    parser.add_argument(
        "--trim-layout-text",
        action="store_true",
        help="Trim crops using layout text boxes (PaddleOCR LayoutDetection)"
    )
    parser.add_argument(
        "--layout-text-model",
        type=str,
        default="PP-DocLayout_plus-L",
        help="Layout detection model name (default PP-DocLayout_plus-L)"
    )
    parser.add_argument(
        "--layout-text-score-thresh",
        type=float,
        default=0.6,
        help="Minimum score for layout text boxes (default 0.6)"
    )
    parser.add_argument(
        "--layout-text-max-gap-ratio",
        type=float,
        default=0.2,
        help="Max gap ratio beyond crop edge to consider text (default 0.2)"
    )
    parser.add_argument(
        "--layout-text-bottom-band-ratio",
        type=float,
        default=0.35,
        help="Bottom band ratio for caption trimming (default 0.35)"
    )
    parser.add_argument(
        "--layout-text-top-band-ratio",
        type=float,
        default=0.35,
        help="Top band ratio for header trimming (default 0.35)"
    )
    parser.add_argument(
        "--layout-text-margin-px",
        type=int,
        default=6,
        help="Extra margin to remove past layout text (default 6)"
    )
    parser.add_argument(
        "--layout-text-min-width-ratio",
        type=float,
        default=0.3,
        help="Minimum width ratio for layout text boxes (default 0.3)"
    )
    parser.add_argument(
        "--layout-text-max-height-ratio",
        type=float,
        default=0.25,
        help="Maximum height ratio for layout text boxes (default 0.25)"
    )
    parser.add_argument(
        "--layout-split-text",
        action="store_true",
        help="Split image boxes on mid-page layout text bands"
    )
    parser.add_argument(
        "--layout-split-min-gap-ratio",
        type=float,
        default=0.15,
        help="Minimum gap ratio around text band for splitting (default 0.15)"
    )
    parser.add_argument(
        "--layout-split-margin-px",
        type=int,
        default=6,
        help="Extra margin to remove past layout text band when splitting (default 6)"
    )
    parser.add_argument(
        "--split-when-missing",
        action="store_true",
        help="Split large boxes by whitespace gaps when expected_count is higher"
    )
    parser.add_argument(
        "--split-gap-ratio-threshold",
        type=float,
        default=0.01,
        help="Row nonwhite ratio threshold for gap splitting (default 0.01)"
    )
    parser.add_argument(
        "--split-min-gap-px",
        type=int,
        default=12,
        help="Minimum consecutive gap rows for splitting (default 12)"
    )
    parser.add_argument(
        "--split-min-segment-height-ratio",
        type=float,
        default=0.12,
        help="Minimum segment height as fraction of page height (default 0.12)"
    )
    parser.add_argument(
        "--split-min-segment-nonwhite-ratio",
        type=float,
        default=0.01,
        help="Minimum nonwhite ratio for segment retention (default 0.01)"
    )
    parser.add_argument(
        "--trim-caption",
        action="store_true",
        help="Trim caption text from bottom of detected image boxes"
    )
    parser.add_argument(
        "--caption-max-height-ratio",
        type=float,
        default=0.18,
        help="Max caption height as fraction of box height (default 0.18)"
    )
    parser.add_argument(
        "--caption-text-ratio-threshold",
        type=float,
        default=0.2,
        help="Row text ratio threshold for caption trimming (default 0.2)"
    )
    parser.add_argument(
        "--caption-margin-px",
        type=int,
        default=4,
        help="Extra margin to remove above detected caption line (default 4)"
    )
    parser.add_argument(
        "--caption-max-nonwhite-ratio",
        type=float,
        default=0.2,
        help="Skip caption trimming if bottom window has high nonwhite ratio (default 0.2)"
    )
    parser.add_argument(
        "--caption-trim-passes",
        type=int,
        default=1,
        help="Number of caption trim passes (default 1)"
    )
    parser.add_argument(
        "--caption-relax-max-gap-ratio",
        type=float,
        default=0.15,
        help="Max gap ratio to allow caption trim even if separated (default 0.15)"
    )

    args = parser.parse_args()

    manifest = crop_illustrations_guided(
        ocr_manifest=args.ocr_manifest,
        output_dir=args.output_dir,
        run_id=args.run_id,
        transparency=args.transparency,
        threshold=args.threshold,
        output_format=args.output_format,
        jpeg_quality=args.jpeg_quality,
        blur=args.blur,
        text_kernel=args.text_kernel,
        text_iterations=args.text_iterations,
        detection_mode=args.detection_mode,
        white_threshold=args.white_threshold,
        close_kernel=args.close_kernel,
        close_iterations=args.close_iterations,
        text_block_kernel_w=args.text_block_kernel_w,
        text_block_kernel_h=args.text_block_kernel_h,
        text_block_iterations=args.text_block_iterations,
        score_min_nonwhite=args.score_min_nonwhite,
        min_nonwhite_ratio=args.min_nonwhite_ratio,
        max_text_ratio=args.max_text_ratio,
        text_line_kernel_w=args.text_line_kernel_w,
        text_line_kernel_h=args.text_line_kernel_h,
        text_line_iterations=args.text_line_iterations,
        min_area_ratio=args.min_area_ratio,
        max_area_ratio=args.max_area_ratio,
        min_width=args.min_width,
        min_height=args.min_height,
        highres_manifest=args.highres_manifest,
        highres_images_dir=args.highres_images_dir,
        padding_percent=args.padding_percent,
        rescue_model=args.rescue_model,
        rescue_temperature=args.rescue_temperature,
        rescue_max_tokens=args.rescue_max_tokens,
        rescue_max_pages=args.rescue_max_pages,
        rescue_timeout_seconds=args.rescue_timeout_seconds,
        rescue_include_alt=args.rescue_include_alt,
        rescue_always=args.rescue_always,
        rescue_retry_on_overlap=args.rescue_retry_on_overlap,
        rescue_retry_on_missing=args.rescue_retry_on_missing,
        rescue_retry_max=args.rescue_retry_max,
        rescue_require_caption_schema=args.rescue_require_caption_schema,
        rescue_retry_on_text=args.rescue_retry_on_text,
        rescue_caption_second_pass=args.rescue_caption_second_pass,
        rescue_caption_max_tokens=args.rescue_caption_max_tokens,
        rescue_refine_boxes=args.rescue_refine_boxes,
        rescue_refine_max_tokens=args.rescue_refine_max_tokens,
        rescue_refine_min_area_ratio=args.rescue_refine_min_area_ratio,
        refine_with_nonwhite=args.refine_with_nonwhite,
        refine_close_kernel=args.refine_close_kernel,
        refine_close_iterations=args.refine_close_iterations,
        refine_with_nontext=args.refine_with_nontext,
        refine_with_textlines=args.refine_with_textlines,
        refine_textlines_min_area_ratio=args.refine_textlines_min_area_ratio,
        trim_text_edges=args.trim_text_edges,
        text_edge_max_ratio=args.text_edge_max_ratio,
        text_edge_margin_px=args.text_edge_margin_px,
        trim_ocr_text_edges=args.trim_ocr_text_edges,
        ocr_trim_edge_ratio=args.ocr_trim_edge_ratio,
        ocr_trim_min_conf=args.ocr_trim_min_conf,
        ocr_trim_min_word_len=args.ocr_trim_min_word_len,
        ocr_trim_min_line_words=args.ocr_trim_min_line_words,
        ocr_trim_min_line_chars=args.ocr_trim_min_line_chars,
        ocr_trim_max_ratio=args.ocr_trim_max_ratio,
        ocr_trim_margin_px=args.ocr_trim_margin_px,
        ocr_tesseract_cmd=args.ocr_tesseract_cmd,
        trim_layout_text=args.trim_layout_text,
        layout_text_model=args.layout_text_model,
        layout_text_score_thresh=args.layout_text_score_thresh,
        layout_text_max_gap_ratio=args.layout_text_max_gap_ratio,
        layout_text_bottom_band_ratio=args.layout_text_bottom_band_ratio,
        layout_text_top_band_ratio=args.layout_text_top_band_ratio,
        layout_text_margin_px=args.layout_text_margin_px,
        layout_text_min_width_ratio=args.layout_text_min_width_ratio,
        layout_text_max_height_ratio=args.layout_text_max_height_ratio,
        layout_split_text=args.layout_split_text,
        layout_split_min_gap_ratio=args.layout_split_min_gap_ratio,
        layout_split_margin_px=args.layout_split_margin_px,
        split_when_missing=args.split_when_missing,
        split_gap_ratio_threshold=args.split_gap_ratio_threshold,
        split_min_gap_px=args.split_min_gap_px,
        split_min_segment_height_ratio=args.split_min_segment_height_ratio,
        split_min_segment_nonwhite_ratio=args.split_min_segment_nonwhite_ratio,
        trim_caption=args.trim_caption,
        caption_max_height_ratio=args.caption_max_height_ratio,
        caption_text_ratio_threshold=args.caption_text_ratio_threshold,
        caption_margin_px=args.caption_margin_px,
        caption_max_nonwhite_ratio=args.caption_max_nonwhite_ratio,
        caption_trim_passes=args.caption_trim_passes,
        caption_relax_max_gap_ratio=args.caption_relax_max_gap_ratio,
    )

    # Save manifest
    manifest_path = os.path.join(args.output_dir, "illustration_manifest.jsonl")
    save_jsonl(manifest_path, manifest)

    _log(f"Manifest: {manifest_path}")
    _log(f"Images: {os.path.join(args.output_dir, 'images')}")


if __name__ == "__main__":
    main()
