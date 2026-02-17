"""
Surya layout detection provider for promptfoo.

Detects figure regions on scanned book pages using Surya's layout model.
Outputs JSON in the same format as VLM providers for scorer compatibility.

Usage in promptfoo config:
  - id: "python:providers/surya_provider.py"
    label: "Surya Layout"
"""

import base64
import io
import json
import os
import warnings

os.environ["TRANSFORMERS_NO_TF"] = "1"
warnings.filterwarnings("ignore")

# Lazy-load models (singleton pattern for reuse across calls)
_det_model = None
_det_processor = None
_layout_model = None
_layout_processor = None


def _ensure_models():
    global _det_model, _det_processor, _layout_model, _layout_processor
    if _det_model is not None:
        return

    from surya.model.detection.segformer import load_model, load_processor

    _det_model = load_model()
    _det_processor = load_processor()
    _layout_model = load_model(checkpoint="vikp/surya_layout2")
    _layout_processor = load_processor(checkpoint="vikp/surya_layout2")


def _decode_image(data_uri: str):
    """Decode base64 data URI to PIL Image."""
    from PIL import Image

    b64_data = data_uri.split(",", 1)[1] if "," in data_uri else data_uri
    img_bytes = base64.b64decode(b64_data)
    return Image.open(io.BytesIO(img_bytes))


def call_api(prompt, options, context):
    """Run Surya layout detection and return figure bounding boxes."""
    from surya.detection import batch_text_detection
    from surya.layout import batch_layout_detection

    try:
        _ensure_models()

        # Get image from context vars
        image_data = context.get("vars", {}).get("image", "")
        if not image_data:
            return {"error": "No image data in context vars"}

        image = _decode_image(image_data)
        w, h = image.size

        # Run detection pipeline
        text_det = batch_text_detection([image], _det_model, _det_processor)
        layout = batch_layout_detection(
            [image], _layout_model, _layout_processor, text_det
        )

        # Extract figure regions and normalize coordinates
        result = layout[0]
        images = []
        for bbox in result.bboxes:
            if bbox.label in ("Figure", "Picture", "Image"):
                x0, y0, x1, y1 = bbox.bbox
                images.append(
                    {
                        "description": f"Figure (confidence={bbox.confidence:.3f})",
                        "bbox": [
                            round(x0 / w, 4),
                            round(y0 / h, 4),
                            round(x1 / w, 4),
                            round(y1 / h, 4),
                        ],
                    }
                )

        output = json.dumps({"images": images})
        return {"output": output}

    except Exception as e:
        return {"error": str(e)}
