# Story: Image cropper/mapper

**Status**: Done

---

## Acceptance Criteria
- Detect/crop illustrations from page images
- Map cropped images to portions/sections
- Store paths in artifacts

## Tasks
- [ ] Define evaluation set (5–10 pages) and success metrics for illustration detection/cropping
- [ ] Spike 1: heuristic/contour-based detector (OpenCV) — capture precision/recall vs eval set
- [ ] Spike 2: ML/LLM-assisted detector (e.g., SAM/Tesseract regions) — compare against Spike 1
- [ ] Choose detector, document rationale, and lock module interface (inputs/outputs/params)
- [ ] Implement cropper module under appropriate stage with a documented manual validation procedure (no CI requirement)
- [ ] Persist cropped asset paths into portion/section artifacts and update schema if needed
- [ ] Add driver recipe step + sample run that produces cropped assets in `output/runs/<id>/`
- [ ] Update README/story notes with usage instructions and limitations

## Notes
- Eval pages (PDF page -> image file): 1→img-000.jpg, 3→img-008.jpg, 11→img-023.jpg, 14→img-034.jpg, 17→img-038.jpg, 18→img-040.jpg, 63→img-208.jpg
- `input/images/` holds 113 JPG page renders; 221 PBM files are 1x1 placeholders (safe to ignore for cropping).
- Proposed eval metrics: per-image precision/recall on detected boxes vs. hand-labeled GT with IoU ≥ 0.5; secondary coverage metric (% of image area labeled vs. detected) to catch over/under-crop.
- Ground truth plan: hand-annotate bounding boxes for eval pages into a JSONL (page, box[x0,y0,x1,y1], section_id?).
- Candidate deps: `opencv-python-headless`, `pytesseract` (for text masks), `segment-anything` or `ultralytics` (YOLOv8-seg) for model-based spike; leave hook to swap in other vision models that can natively detect/segment illustrations.
- Annotation helper: `scripts/annotate_gt.py` builds/updates JSONL templates; initial template stored at `configs/groundtruth/image_boxes_eval.jsonl` (empty boxes, with image dimensions).
- Dev env: local venv at `.venv` (created for CV spikes). Activate with `. .venv/bin/activate`; packages installed: opencv-python-headless, pytesseract, ultralytics (pulls torch, torchvision, etc.).
- Spike helpers: `scripts/spikes/spike_cropper_cv.py` (heuristic/contour) and `scripts/spikes/spike_cropper_yolo.py` (YOLOv8-seg backend). Eval helper `scripts/spikes/eval_detection.py` compares detections vs GT JSONL (IoU threshold configurable).
- Model backend order to try (local/free first): (1) ONNXRuntime + pre-exported YOLOv8n-seg ONNX (no torch/OMP); (2) ONNXRuntime + MobileSAM ONNX for promptable segmentation; (3) Cloud/vision-LLM fallback (e.g., Gemini) if local fails.
- Current blockers: YOLOv8-seg (torch) run fails on this machine due to OpenMP SHM permissions (`Can't open SHM2`). Need env/workaround or alternative backend that avoids shared memory (e.g., onnxruntime, Pillow-SAM, or running torch with OMP disabled via different build).
- New schema + module: added `image_crop_v1` to `schemas.py`/`validate_artifact` and created `modules/extract/image_crop_cv_v1` (contour-based detector/cropper; outputs boxes + crop paths).
- New AI option: added `modules/extract/image_crop_llm_v1` (vision LLM using OpenAI model to return boxes, then crops locally). Shares `image_crop_v1` schema; params: model, max_boxes.
- Next AI/CV plan (to test vs baseline CV):
  1) GroundingDINO (small ONNX, open-vocabulary prompt like “illustration”); expected better recall/precision than contours.
  2) YOLOv8/11 ONNX with built-in NMS (box-only) to avoid SHM issues; tuned conf/topK.
  3) SAM2/MobileSAM refinement: contour-proposed boxes → SAM masks → tight boxes.
  Baseline remains contour CV; compare all four backends on the eval set.
- CI/automation: no CI runs planned; rely on documented manual validation for this story.

## Work Log
- Pending

### 20251123-2149 — Reviewed story skeleton and expanded task checklist
- **Result:** Success; tasks now specify evaluation set, detection spikes, module implementation, schema updates, and driver integration steps.
- **Notes:** No existing module path yet; need to decide target stage and sample pages for benchmarking.
- **Next:** Select eval page set and pick candidate detectors for the two spikes.

### 20251123-2158 — Chose evaluation pages and mapped to image files
- **Result:** Success; mapped PDF pages to image assets: p1 img-000.jpg, p3 img-008.jpg, p11 img-023.jpg, p14 img-034.jpg, p17 img-038.jpg, p18 img-040.jpg, p63 img-208.jpg.
- **Notes:** There are 113 JPGs total (one per page); PBM files are 1×1 placeholders, so pipeline should target JPGs only.
- **Next:** Define metrics (precision/recall on image regions), decide ground-truth boxes per eval page, and draft Spike 1 vs Spike 2 plan + deps to install (OpenCV, SAM/YOLO).

### 20251123-2159 — Drafted evaluation + spike approach
- **Result:** Success; decided metrics (precision/recall @ IoU ≥ 0.5 + coverage) and ground-truth format (JSONL with page + boxes + optional section id). Candidate deps listed for heuristics (OpenCV+pytesseract) and model-based (SAM or YOLOv8-seg).
- **Notes:** Need quick annotation helper to produce GT boxes for the seven eval pages.
- **Next:** Choose specific model for Spike 2 (favor YOLOv8-seg for speed) and set up install commands; start GT annotation script.

### 20251123-2200 — Added note to keep alternative vision models pluggable
- **Result:** Success; documented that module should allow swapping in other illustration-capable vision models beyond SAM/YOLO.
- **Notes:** Will design module interface to allow model backend selection/config via recipe settings.
- **Next:** Start GT annotation helper and dependency install list in repo.

### 20251123-2201 — Added GT annotation helper and generated template
- **Result:** Success; created `scripts/annotate_gt.py` to build/update GT JSONL and optional overlays. Generated `configs/groundtruth/image_boxes_eval.jsonl` with eval pages (empty boxes, recorded dimensions).
- **Notes:** Next pass should fill boxes and render overlay previews when boxes exist.
- **Next:** Fill GT boxes for eval pages; install CV deps and start Spike 1/2 prototypes.

### 20251123-2206 — Installed CV/model deps and added spike scripts
- **Result:** Success; created local venv `.venv` and installed opencv-python-headless, pytesseract, ultralytics (with torch). Added spike helpers: `scripts/spikes/spike_cropper_cv.py` (heuristic), `scripts/spikes/spike_cropper_yolo.py` (YOLOv8-seg), and `scripts/spikes/eval_detection.py` (IoU-based precision/recall).
- **Notes:** YOLO model downloads on first run. Detections and eval expect JSONL per scripts. GT boxes still need manual annotation to compute metrics.
- **Next:** Annotate GT boxes for eval pages (using overlay option), run CV vs YOLO spikes, compare metrics, and pick backend.

### 20251123-2208 — Ran CV spike; YOLO blocked by OpenMP SHM
- **Result:** CV heuristic run produced detections at `/tmp/detections_cv.jsonl` (rough, no GT yet). YOLOv8-seg run aborts with `OMP: Error #179: Can't open SHM2` even with `OMP_NUM_THREADS=1`/`KMP_CREATE_SHM=0`.
- **Notes:** Need workaround for YOLO/torch OpenMP shared memory on mac sandbox; options: use different backend (onnxruntime, SAM via pure Python), or disable OMP in torch build.
- **Next:** Hand-annotate GT boxes to evaluate CV; explore SHM workaround or alternative model backend.

### 20251123-2210 — Tried additional OMP flags; still blocked
- **Result:** YOLO/torch still aborts with SHM2 error despite `KMP_DUPLICATE_LIB_OK=TRUE`, `KMP_INIT_AT_FORK=FALSE`, `KMP_CREATE_SHM=0`, `OMP_NUM_THREADS=1`. Export to ONNX also fails due to same torch init path.
- **Notes:** Likely needs a torch build without OpenMP shared-memory (e.g., conda cpu build) or an ONNX model fetched pre-exported and run with onnxruntime (no torch). CV heuristic remains runnable.
- **Next:** Acquire pre-exported YOLOv8n-seg.onnx and run via onnxruntime, or switch to SAM-onnx; meanwhile continue with GT annotation and CV evaluation.

### 20251123-2216 — Started ONNXRuntime path
- **Result:** Installed `onnxruntime==1.19.2`, added `models/yolov8n-seg.onnx` (13 MB from HuggingFace Kalray optimized build) and wrote `scripts/spikes/spike_cropper_yolo_onnx.py` to run boxes via onnxruntime with NMS. Current model outputs multiple feature maps (not fused detect head), causing shape mismatch; need a fused-export ONNX (1×116×8400) or to implement head math for this variant.
- **Notes:** Ultralytics HF `yolov8n-seg.onnx` download is gated (29-byte pointer). Torch-based Ultralytics loader still triggers SHM error. Remaining route: find a fused ONNX export that outputs post-head predictions, or switch to SAM-ONNX backend.
- **Next:** Locate a fused YOLOv8n-seg ONNX (public direct link) and rerun; if unavailable, pivot to MobileSAM ONNX via onnxruntime.

### 20251123-2224 — Fused YOLOv8n-seg ONNX running via ORT (needs tuning)
- **Result:** Cloned Hyuto `yolov8-seg-onnxruntime-web` with git-lfs to obtain fused `yolov8n-seg.onnx` (13 MB) plus NMS/mask ONNX; updated script and ran inference. ONNXRuntime pipeline now executes (no SHM errors) and produces boxes, but current postprocess yields many low-value boxes (scores ~0.25) — needs confidence/NMS tuning or class filtering.
- **Notes:** Script now applies sigmoid to obj/cls; NMS implemented but score distribution flat → thousands of boxes survive. Need to add top-K filter and class-aware thresholding, and validate against GT once boxes exist.
- **Next:** Add GT boxes, tune thresholds (e.g., conf 0.4 + top 50 per image), optionally use provided NMS ONNX from Hyuto repo. Consider MobileSAM ONNX as alternate if YOLO boxes remain noisy.

### 20251123-2227 — Added stub GT, ran evals CV vs YOLO-ORT
- **Result:** Drafted rough GT boxes into `configs/groundtruth/image_boxes_eval.jsonl` and generated overlays in `/tmp/overlays` for review. CV heuristic results @IoU0.5: P=0.50 R=0.70 F1=0.58 (TP=7 FP=7 FN=3). YOLO-ORT (conf 0.2, topK 50) currently very low precision (P~0.03, R~0.90) due to many low-score boxes.
- **Notes:** GT boxes are coarse; need refinement to be reliable. YOLO-ORT needs stricter filtering (higher conf, class filtering, or second-stage NMS); could also try Hyuto NMS ONNX or MobileSAM backend. CV already reasonable recall on this tiny set.
- **Next:** Refine GT boxes precisely; tighten YOLO thresholds (conf 0.4–0.5, topK 20) and/or apply class filtering; evaluate again. If precision remains poor, pivot to MobileSAM ONNX.

### 20251123-2230 — Refined GT, reran evals
- **Result:** Updated GT boxes (cover spans nearly full page) and regenerated overlays. CV heuristic degraded with refined GT: Micro P=0.29 R=0.44 F1=0.35 (misses large cover/hero images; over-detects some). YOLO-ORT with conf 0.3/topK 30: Micro P=0.50 R=0.11 F1=0.18 (only hits one box, under-recall after tighter filtering).
- **Notes:** Need better detector: either tune YOLO-ORT thresholds/anchor grid or switch to MobileSAM ONNX. GT still approximate; improving GT (especially p3/p17/p208) will sharpen metrics.
- **Next:** (1) Further refine GT boxes accurately; (2) try Hyuto NMS ONNX or class filtering to cut YOLO false positives while keeping recall; (3) explore MobileSAM ONNX backend for segmentation-based boxes.

### 20251123-2232 — Auto foreground-based GT refinement and re-eval
- **Result:** Used threshold+contour to auto-box foreground then manually corrected multi-image pages. GT now: p1 full-page cover; p3 full-page art; p11 full-page sheet; p14 single mid-page image; p17 single lower image; p18 two images; p63 two images. CV heuristic @IoU0.5 now P=0.36 R=0.56 F1=0.43. YOLO-ORT still low (P=0.50 R=0.11 F1=0.18).
- **Notes:** CV still misses cover/full-page cases; YOLO needs better filtering (maybe use mask-based scoring or class threshold). GT likely close but could still be tightened with visual inspection of `/tmp/overlays`.
- **Next:** Inspect overlays to final-tune GT; experiment with NMS+conf for YOLO (or switch to MobileSAM ONNX) to regain recall without FP flood.

### 20251123-2234 — Manual refinements per feedback, re-eval
- **Result:** Updated GT: p1 cover full-page; p3 now two boxes (title + drawing only); p11, p14, p17, p18 marked as desired; p63 both boxes tweaked tighter. CV heuristic now P=0.50 R=0.70 F1=0.58 (TP=7 FP=7 FN=3). YOLO-ORT remains low P=0.50 R=0.10 F1=0.17 at conf 0.3/topK 30.
- **Notes:** CV recovers once GT tightened; YOLO-ORT still under-recalls—needs stronger conf or different backend (MobileSAM ONNX) or class-aware filtering/NMS ONNX.
- **Next:** Improve YOLO filtering or pivot to MobileSAM ONNX; keep GT overlays for verification.

### 20251123-2237 — Final GT tweak for p63; re-eval
- **Result:** Expanded rat image box on p63; overlays refreshed. CV heuristic now P=0.43 R=0.60 F1=0.50 (TP=6 FP=8 FN=4). YOLO-ORT unchanged: P=0.50 R=0.10 F1=0.17.
- **Notes:** CV precision dropped slightly after GT change but still above YOLO; YOLO remains the bottleneck. GT likely acceptable now visually.
- **Next:** Focus on improving model backend (NMS ONNX/class filter) or switching to MobileSAM ONNX to lift recall without SHM issues.

### 20251123-2251 — Added image_crop schema + CV module scaffold
- **Result:** Added `image_crop_v1` schema + SCHEMA_MAP entry; created `modules/extract/image_crop_cv_v1` (OpenCV contour detector/cropper) that reads `page_doc_v1`, writes crops to disk, and emits boxes/crop paths JSONL.
- **Notes:** MobileSAM/YOLO remain experimental; CV is the stable baseline to wire into recipes. Module uses params `min_area_ratio/max_area_ratio/blur`.
- **Next:** Integrate module into driver/recipe, validate against GT, and consider MobileSAM as optional backend flag later.

### 20251123-2257 — Added LLM cropper option
- **Result:** Created `modules/extract/image_crop_llm_v1` (OpenAI vision model → boxes → local crops) sharing `image_crop_v1` schema; params: model, max_boxes. Added to story notes.
- **Notes:** Not yet run (would require API calls); intended as higher-accuracy fallback if contour/ORT paths underperform.
- **Next:** Wire LLM module into recipes behind a flag; decide default backend after comparing CV vs LLM on sample pages.

### 20251123-2307 — Ran LLM cropper (gpt-4.1) on eval pages via recipe-image-crop-llm
- **Result:** LLM boxes were poor vs GT: Micro P=0.11 R=0.10 F1=0.11. Only page 11 matched; others missed or overboxed.
- **Notes:** Using center/grid single-point prompts isn’t enough; would need richer prompt or multi-step reasoning to isolate art. API calls worked locally after adding openai/httpx deps and allowing driver to consume explicit pages input.
- **Next:** Default to CV module; keep LLM path optional. If we revisit, try multi-shot textual cues per page or chain-of-thought boxing.

### 20251124-0948 — GPT-4o vision fine-tune (10 ex) and eval
- **Result:** Fine-tune succeeded (job ftjob-CAGa0YsYQfKOoKTGcxbAMZod) → model `ft:gpt-4o-2024-08-06:personal::CfTYEBmb`. Eval on 12-page GT via LLM cropper: Micro P=0.22 R=0.11 F1=0.14 (better than base LLM but still below CV baseline F1≈0.50). Only pages 11 & 14 were correct; most pages missed.
- **Notes:** Training set is very small (12). Model still poor at box localization; likely needs more examples or different detection-specific backend.
- **Next:** Keep CV as default; consider expanding labeled set or switch to open-vocabulary detector (GroundingDINO/YOLO-World) for AI backend.

### 20251124-10xx — New fine-tune completed (larger set)
- **Result:** OpenAI email reports job `ftjob-f1bgp9cZFS6e3Seg0eNcHZ7T` succeeded → new model `ft:gpt-4o-2024-08-06:personal::CfU8W6mr`. Need to evaluate this newer FT against GT and compare vs CV/other backends.
- **Notes:** Previous run used the earlier FT model `CfTYEBmb`; new model may include the expanded pages (88/91/98/105/110). Pending eval.
- **Next:** Run `image_crop_llm_v1` with model `ft:gpt-4o-2024-08-06:personal::CfU8W6mr` on the eval set, record P/R/F1, and compare to CV/YOLO/GroundingDINO once those backends run.

### 20251124-1014 — Evaluated newer GPT-4o FT model (CfU8W6mr)
- **Result:** LLM cropper with `ft:gpt-4o-2024-08-06:personal::CfU8W6mr` on 12-page GT → Micro P=0.00 R=0.00 F1=0.00 (no correct boxes). Worse than prior FT and far below CV baseline.
- **Notes:** Small dataset likely overfit/underperforming; vision FT not yielding usable boxes. CV still best; need detector backend.
- **Next:** Focus on detector backends (GroundingDINO/YOLO/SAM); keep FT model as off-by-default.

### 20251124-1038 — Updated requirements note (no CI)

### 20251124-1045 — Tuned CV baseline and manual validation
- **Result:** Adjusted contour params (threshold 200, blur 3, min_area_ratio 0.005, max_area_ratio 0.99, topk 5). On 12-page GT: Micro P=0.75 R=0.95 F1=0.84. Per-page: p1/11/14/17/18/63/105/110 perfect; p3 F1=0.80; p88 F1=0.67; p91 F1=0.67; p98 F1=0.40.
- **Notes:** Missed a second box on p98; FPs on p3/88/91/98 could be trimmed with minor tuning/NMS. CV now substantially better than prior attempts and FT models.
- **Next:** Optionally tweak params to reduce FPs on p3/88/91/98 and catch p98 second box; set CV as default backend and document manual validation steps.

### 20251124-1052 — Retune attempt (min_area 0.004, max_area 0.98, topk 6)
- **Result:** Metrics unchanged from prior tuned run: Micro P=0.75 R=0.95 F1=0.84 (no gain). Per-page pattern same: p98 still low (F1 0.40), p3/88/91 have some FPs.
- **Notes:** Further tuning didn’t improve scores; CV baseline plateaued. Accept current params (0.005/0.99/blur3/topk5) as default.
- **Next:** Lock CV params, update recipe defaults (done), and document manual validation.
- **Result:** Clarified tasks: manual validation accepted, no CI requirement; added note about manual validation to tasks/notes.
- **Next:** Define a concise manual validation checklist alongside CV baseline results when ready.
### 20251126-1126 — Note: CV cropper removed in Story 025
- **Result:** Documentation update.
- **Notes:** `image_crop_cv_v1` and demo recipes were pruned under Story 025 to slim the registry. Historical metrics remain here for reference; cropper would need reintroduction via a new story if needed.
- **Next:** If image cropping is revived, reopen this story or a follow-up with a new module/recipe plan.
