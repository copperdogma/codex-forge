# Story: Image cropper follow-up

**Status**: To Do

---

## Summary of prior work (from story-008-image-cropper)
- Baseline CV contour cropper (`image_crop_cv_v1`) added; schema `image_crop_v1` created; recipe drafts exist.
- GT set of 12 pages (1,3,11,14,17,18,63,88,91,98,105,110) with bounding boxes; overlays in `output/overlays-ft/`.
- Heuristic CV F1≈0.50 on the eval set; best working baseline.
- YOLOv8/YOLO-ORT attempts: SHM/OpenMP issues and low precision; ONNX NMS path blocked by export/runtime constraints.
- MobileSAM ONNX: low precision/recall.
- GPT-4o vision fine-tunes (models `ft:gpt-4o-2024-08-06:personal::CfTYEBmb` and `ft:gpt-4o-2024-08-06:personal::CfU8W6mr`) performed poorly (F1 down to 0), even after expanding GT.
- GroundingDINO tiny ONNX downloaded but cannot run here due to OpenMP SHM crash (needs different ORT build/environment).

## Goals
- Replace/augment contour baseline with a higher-accuracy detector backend.
- Keep `image_crop_v1` schema and driver integration consistent.

## Tasks
- [ ] Acquire/run an open-vocab detector without SHM issues (e.g., GroundingDINO tiny with non-OpenMP ORT or different host) and benchmark vs GT.
- [ ] Get an OpenCV-friendly YOLO ONNX (opset 12/13, simplified, NMS built-in) and benchmark vs GT.
- [ ] If detector remains weak, consider SAM refinement with better seeds (text masks or detector-proposed boxes) and re-evaluate.
- [ ] Decide default backend (contour vs detector) and update recipes/README accordingly.
- [ ] Optionally expand GT set for broader coverage and easier FT/detector tuning.
- [ ] Remove or gate underperforming FT/LLM backends in driver/recipes; document outcomes.

## Notes
- Current overlays for GT in `output/overlays-ft/` should be reused for quick visual checks.
- FT models available but off by default: `ft:gpt-4o-2024-08-06:personal::CfTYEBmb`, `ft:gpt-4o-2024-08-06:personal::CfU8W6mr`.
- GroundingDINO tiny files fetched under `models/groundingdino-tiny/onnx/` (multiple quantized variants).

## Work Log
- Pending
