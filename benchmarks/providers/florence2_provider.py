"""
Florence-2 provider for promptfoo.

Uses CAPTION_TO_PHRASE_GROUNDING to find photographs and illustrations,
then deduplicates overlapping boxes.

Usage in promptfoo config:
  - id: "python:providers/florence2_provider.py"
    label: "Florence-2-large"
"""

import base64
import io
import json
import os
import warnings

os.environ["TRANSFORMERS_NO_TF"] = "1"
warnings.filterwarnings("ignore")

# Lazy-load models
_model = None
_processor = None


def _ensure_model():
    global _model, _processor
    if _model is not None:
        return

    from transformers import AutoModelForCausalLM, AutoProcessor

    _model = AutoModelForCausalLM.from_pretrained(
        "microsoft/Florence-2-large", trust_remote_code=True
    )
    _processor = AutoProcessor.from_pretrained(
        "microsoft/Florence-2-large", trust_remote_code=True
    )


def _decode_image(data_uri: str):
    """Decode base64 data URI to PIL Image."""
    from PIL import Image

    b64_data = data_uri.split(",", 1)[1] if "," in data_uri else data_uri
    img_bytes = base64.b64decode(b64_data)
    return Image.open(io.BytesIO(img_bytes)).convert("RGB")


def _iou(a, b):
    """IoU between two [x0,y0,x1,y1] boxes."""
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0


def _deduplicate_boxes(bboxes, labels, iou_threshold=0.5):
    """Merge overlapping boxes by averaging coordinates."""
    if not bboxes:
        return [], []

    used = set()
    merged_boxes = []
    merged_labels = []

    for i in range(len(bboxes)):
        if i in used:
            continue
        cluster = [i]
        for j in range(i + 1, len(bboxes)):
            if j in used:
                continue
            if _iou(bboxes[i], bboxes[j]) > iou_threshold:
                cluster.append(j)
                used.add(j)
        used.add(i)

        # Average the cluster
        avg_box = [0, 0, 0, 0]
        for idx in cluster:
            for k in range(4):
                avg_box[k] += bboxes[idx][k]
        avg_box = [v / len(cluster) for v in avg_box]
        merged_boxes.append(avg_box)
        merged_labels.append(labels[cluster[0]])

    return merged_boxes, merged_labels


def call_api(prompt, options, context):
    """Run Florence-2 phrase grounding and return figure bounding boxes."""
    try:
        _ensure_model()

        image_data = context.get("vars", {}).get("image", "")
        if not image_data:
            return {"error": "No image data in context vars"}

        image = _decode_image(image_data)
        w, h = image.size

        # Use CAPTION_TO_PHRASE_GROUNDING to find visual elements
        task = "<CAPTION_TO_PHRASE_GROUNDING>"
        caption = "photographs, illustrations, drawings, logos, seals, and graphics on this page"
        inputs = _processor(text=task + caption, images=image, return_tensors="pt")
        gen = _model.generate(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            max_new_tokens=1024,
            num_beams=3,
        )
        result = _processor.batch_decode(gen, skip_special_tokens=False)[0]
        parsed = _processor.post_process_generation(result, task=task, image_size=(w, h))

        raw_bboxes = parsed.get(task, {}).get("bboxes", [])
        raw_labels = parsed.get(task, {}).get("labels", [])

        # Deduplicate overlapping boxes
        deduped_boxes, deduped_labels = _deduplicate_boxes(raw_bboxes, raw_labels)

        # Normalize to 0-1
        images = []
        for box, label in zip(deduped_boxes, deduped_labels):
            images.append(
                {
                    "description": label,
                    "bbox": [
                        round(box[0] / w, 4),
                        round(box[1] / h, 4),
                        round(box[2] / w, 4),
                        round(box[3] / h, 4),
                    ],
                }
            )

        output = json.dumps({"images": images})
        return {"output": output}

    except Exception as e:
        return {"error": str(e)}
