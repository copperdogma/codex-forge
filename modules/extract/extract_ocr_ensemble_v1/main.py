import argparse
import os
import difflib
import sys
from pathlib import Path


# Add local vendor packages (pip --target .pip-packages) to sys.path for BetterOCR/EasyOCR
ROOT = Path(__file__).resolve().parents[3]
VENDOR = ROOT / ".pip-packages"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

from modules.common import render_pdf, run_ocr, ensure_dir, save_json, save_jsonl, ProgressLogger


def split_lines(text: str):
    if not text:
        return []
    # Preserve blank lines to keep paragraph breaks visible downstream
    return text.splitlines()


def compute_disagreement(by_engine):
    texts = list(by_engine.values())
    if len(texts) < 2:
        return 0.0
    scores = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a, b = texts[i], texts[j]
            ratio = difflib.SequenceMatcher(None, a, b).ratio()
            scores.append(1 - ratio)
    return round(sum(scores) / len(scores), 4) if scores else 0.0


def call_betterocr(image_path: str, engines, lang: str, *, use_llm: bool, llm_model: str,
                   allow_fallback: bool, psm: int, oem: int):
    try:
        from betterocr.wrappers import job_tesseract, job_easy_ocr
    except ImportError as e:
        if not allow_fallback:
            raise RuntimeError("betterocr not installed; pip install betterocr easyocr") from e
        text = run_ocr(image_path, lang="eng" if lang == "en" else lang, psm=psm, oem=oem)
        return text, {"tesseract": text}, "tesseract-fallback"

    by_engine = {}
    tess_text = ""
    try:
        tess_text = job_tesseract({"path": image_path, "lang": [lang], "tesseract": {"config": f"--psm {psm} --oem {oem}"}})
        tess_text = tess_text.replace("\\n", "\n")
        by_engine["tesseract"] = tess_text
    except Exception:
        pass

    easy_text = ""
    if "easyocr" in engines:
        try:
            easy_text = job_easy_ocr({"path": image_path, "lang": [lang]})
            by_engine["easyocr"] = easy_text
        except Exception:
            pass

    primary = tess_text if len(tess_text) >= len(easy_text) else easy_text
    secondary = easy_text if primary is tess_text else tess_text
    if secondary and secondary.strip() != primary.strip():
        merged = primary.strip() + "\n" + secondary.strip()
    else:
        merged = primary or secondary

    if not merged and allow_fallback:
        merged = run_ocr(image_path, lang="eng" if lang == "en" else lang, psm=psm, oem=oem)
        by_engine.setdefault("tesseract-fallback", merged)
        return merged, by_engine, "tesseract-fallback"

    return merged, by_engine, "betterocr"


def main():
    parser = argparse.ArgumentParser(description="Multi-engine OCR ensemble (BetterOCR) → PageLines IR")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--outdir", required=True, help="Base output directory")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--lang", default="en")
    parser.add_argument("--engines", nargs="+", default=["tesseract", "easyocr"],
                        help="Engines to enable within BetterOCR")
    parser.add_argument("--use-llm", action="store_true", help="Enable BetterOCR LLM reconciliation")
    parser.add_argument("--llm-model", dest="llm_model", default="gpt-4.1-mini")
    parser.add_argument("--llm_model", dest="llm_model", default="gpt-4.1-mini")
    parser.add_argument("--escalation-threshold", dest="escalation_threshold", type=float, default=0.15)
    parser.add_argument("--escalation_threshold", dest="escalation_threshold", type=float, default=0.15)
    parser.add_argument("--write-engine-dumps", action="store_true",
                        help="Persist per-engine raw text under ocr_engines/ for debugging")
    parser.add_argument("--disable-fallback", action="store_true",
                        help="Fail hard if BetterOCR is unavailable instead of running tesseract only")
    parser.add_argument("--psm", type=int, default=4, help="Tesseract PSM (fallback only)")
    parser.add_argument("--oem", type=int, default=3, help="Tesseract OEM (fallback only)")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    allow_fallback = not args.disable_fallback

    images_dir = os.path.join(args.outdir, "images")
    ocr_dir = os.path.join(args.outdir, "ocr_ensemble")
    pages_dir = os.path.join(ocr_dir, "pages")
    engines_dir = os.path.join(ocr_dir, "ocr_engines")
    ensure_dir(images_dir)
    ensure_dir(pages_dir)
    if args.write_engine_dumps:
        ensure_dir(engines_dir)

    image_paths = render_pdf(args.pdf, images_dir, dpi=args.dpi,
                             start_page=args.start, end_page=args.end)

    total = len(image_paths)
    quality_report = []
    index = {}
    page_rows = []

    logger.log("extract", "running", current=0, total=total,
               message="Running BetterOCR ensemble", artifact=os.path.join(ocr_dir, "pagelines_index.json"),
               module_id="extract_ocr_ensemble_v1", schema_version="pagelines_v1")

    for idx, img_path in enumerate(image_paths, start=args.start):
        text, by_engine, source = call_betterocr(
            img_path,
            args.engines,
            args.lang,
            use_llm=args.use_llm,
            llm_model=args.llm_model,
            allow_fallback=allow_fallback,
            psm=args.psm,
            oem=args.oem,
        )

        lines = split_lines(text)
        disagreement = compute_disagreement(by_engine)
        needs_escalation = disagreement > args.escalation_threshold

        line_rows = [{"text": line, "source": source} for line in lines]
        page_payload = {
            "schema_version": "pagelines_v1",
            "module_id": "extract_ocr_ensemble_v1",
            "run_id": args.run_id,
            "page": idx,
            "image": os.path.abspath(img_path),
            "lines": line_rows,
            "disagreement_score": disagreement,
            "needs_escalation": needs_escalation,
            "engines_raw": by_engine,
        }

        page_path = os.path.join(pages_dir, f"page-{idx:03d}.json")
        save_json(page_path, page_payload)
        index[idx] = page_path
        page_rows.append(page_payload)

        if args.write_engine_dumps:
            page_engine_dir = os.path.join(engines_dir, f"page-{idx:03d}")
            ensure_dir(page_engine_dir)
            for name, engine_text in by_engine.items():
                dump_path = os.path.join(page_engine_dir, f"{name}.txt")
                with open(dump_path, "w", encoding="utf-8") as f:
                    f.write(engine_text or "")

        quality_report.append({
            "page": idx,
            "disagreement_score": disagreement,
            "needs_escalation": needs_escalation,
            "engines": list(by_engine.keys()),
            "source": source,
            "fallback": source != "betterocr",
        })

        logger.log("extract", "running", current=len(quality_report), total=total,
                   message=f"OCR ensemble page {idx}", artifact=page_path,
                   module_id="extract_ocr_ensemble_v1", schema_version="pagelines_v1",
                   extra={"disagreement_score": disagreement, "needs_escalation": needs_escalation})

    index_path = os.path.join(ocr_dir, "pagelines_index.json")
    report_path = os.path.join(ocr_dir, "ocr_quality_report.json")
    jsonl_path = os.path.join(ocr_dir, "pages_raw.jsonl")
    jsonl_root_path = os.path.join(args.outdir, "pages_raw.jsonl")
    save_json(index_path, index)
    save_json(report_path, quality_report)
    save_jsonl(jsonl_path, page_rows)
    save_jsonl(jsonl_root_path, page_rows)

    logger.log("extract", "done", current=total, total=total,
               message="OCR ensemble complete", artifact=index_path,
               module_id="extract_ocr_ensemble_v1", schema_version="pagelines_v1")

    print(f"Saved {total} pagelines to {pages_dir}\nIndex: {index_path}\nQuality: {report_path}\nJSONL: {jsonl_path}")


if __name__ == "__main__":
    main()
