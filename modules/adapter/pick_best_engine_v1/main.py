import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from modules.common.text_quality import spell_garble_metrics
from modules.common.utils import ensure_dir, save_json, append_jsonl, ProgressLogger


def load_index(index_path: str) -> Dict[str, str]:
    data = json.load(open(index_path, "r", encoding="utf-8"))
    return {str(k): v for k, v in data.items()}


def split_lines(text: str) -> List[str]:
    if not isinstance(text, str) or not text:
        return []
    return text.splitlines()


def _line_dup_ratio(lines: List[str]) -> float:
    non_empty = [ln.strip() for ln in (lines or []) if ln and ln.strip()]
    if not non_empty:
        return 0.0
    uniq = len(set(non_empty))
    return 1.0 - (uniq / len(non_empty))


def _engine_text_from_page(page_data: Dict[str, Any], engine: str) -> str:
    engines = page_data.get("engines_raw") or {}
    if not isinstance(engines, dict):
        return ""
    txt = engines.get(engine)
    return txt if isinstance(txt, str) else ""


def score_engine_lines(lines: List[str]) -> Dict[str, Any]:
    joined = "\n".join(lines or [])
    dup_ratio = _line_dup_ratio(lines)
    spell = spell_garble_metrics(lines)

    # Score is "higher is worse".
    # Weight duplication because repeated blocks are very harmful for downstream segmentation.
    score = (
        float(spell.get("dictionary_score", 0.0)) * 0.55 +
        float(spell.get("char_confusion_score", 0.0)) * 0.25 +
        float(dup_ratio) * 0.35
    )
    # Penalize extremely short outputs (often headers-only / partial reads).
    if len(joined.strip()) < 40:
        score += 0.25
    return {
        "score": round(min(1.5, score), 4),
        "dup_ratio": round(dup_ratio, 4),
        "char_count": len(joined.strip()),
        "spell": spell,
    }


def pick_best_engine(page_data: Dict[str, Any], preferred: List[str], *, min_chars: int) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Returns (engine_name or None, details).
    """
    details: Dict[str, Any] = {"candidates": {}}
    best_engine = None
    best_score = None

    for engine in preferred:
        txt = _engine_text_from_page(page_data, engine)
        lines = split_lines(txt)
        if len("".join(lines).strip()) < max(1, min_chars):
            continue
        metrics = score_engine_lines(lines)
        details["candidates"][engine] = metrics
        score = metrics["score"]
        if best_score is None or score < best_score:
            best_score = score
            best_engine = engine

    details["picked_engine"] = best_engine
    details["picked_score"] = best_score
    return best_engine, details


def main():
    parser = argparse.ArgumentParser(description="Pick best OCR engine per page (no LLM).")
    parser.add_argument("--inputs", nargs="*", help="Driver-provided inputs; expects pages_raw*.jsonl for run_dir inference.")
    parser.add_argument("--index", help="Input pagelines_index.json (defaults to run_dir/ocr_ensemble/pagelines_index.json)")
    parser.add_argument("--outdir", help="Output directory to write picked pages/index (defaults to run_dir/ocr_ensemble_picked)")
    parser.add_argument("--out", required=True, help="Output pagelines_v1 JSONL (pass-through with picked canonical lines).")
    parser.add_argument("--preferred-engines", dest="preferred_engines", nargs="+",
                        default=["easyocr", "tesseract", "apple"],
                        help="Engine preference order to consider.")
    parser.add_argument("--preferred_engines", dest="preferred_engines", nargs="+", help=argparse.SUPPRESS)
    parser.add_argument("--min-chars", dest="min_chars", type=int, default=40,
                        help="Ignore engine outputs shorter than this many characters.")
    parser.add_argument("--min_chars", dest="min_chars", type=int, default=40, help=argparse.SUPPRESS)
    parser.add_argument("--max-pages", dest="max_pages", type=int, default=None,
                        help="Optional cap on pages processed (debug).")
    parser.add_argument("--max_pages", dest="max_pages", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    # Normalize preferred_engines if driver passed a single string like "['easyocr','tesseract','apple']".
    if len(args.preferred_engines) == 1 and isinstance(args.preferred_engines[0], str) and "[" in args.preferred_engines[0]:
        import ast
        try:
            parsed = ast.literal_eval(args.preferred_engines[0])
            if isinstance(parsed, (list, tuple)):
                args.preferred_engines = list(parsed)
        except Exception:
            pass

    # Infer run directory from inputs.
    run_dir = None
    if args.inputs:
        first = Path(args.inputs[0]).resolve()
        run_dir = first.parent if first.is_file() else first
        if run_dir.name in {"ocr_ensemble", "ocr_ensemble_gpt4v", "pagelines_final"}:
            run_dir = run_dir.parent
    if not run_dir:
        raise SystemExit("Unable to infer run directory; pass --inputs or --index/--outdir explicitly.")

    index_path = args.index or str(run_dir / "ocr_ensemble" / "pagelines_index.json")
    outdir = Path(args.outdir or (run_dir / "ocr_ensemble_picked")).resolve()
    pages_out = outdir / "pages"
    ensure_dir(str(pages_out))
    ensure_dir(os.path.dirname(args.out) or ".")

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    index = load_index(index_path)
    keys = sorted(index.keys())
    if args.max_pages is not None:
        keys = keys[: args.max_pages]

    new_index: Dict[str, str] = {}
    picked = 0
    unchanged = 0
    per_engine_counts: Dict[str, int] = {}

    for idx, page_key in enumerate(keys, start=1):
        src_path = index.get(page_key)
        if not src_path or not os.path.exists(src_path):
            continue
        page_data = json.load(open(src_path, "r", encoding="utf-8"))

        engine, details = pick_best_engine(page_data, args.preferred_engines, min_chars=args.min_chars)
        if engine is None:
            # Nothing usable to pick; keep original.
            engine = page_data.get("source") or "unknown"
            details["picked_engine"] = None
            details["skip_reason"] = "no_engine_meets_min_chars"
            chosen_lines = page_data.get("lines") or []
            unchanged += 1
        else:
            txt = _engine_text_from_page(page_data, engine)
            lines = split_lines(txt)
            chosen_lines = [{"text": ln, "source": engine} for ln in lines]

            # If chosen engine equals the existing canonical source and line count matches, call it unchanged.
            existing_src = None
            try:
                if page_data.get("lines") and isinstance(page_data["lines"][0], dict):
                    existing_src = page_data["lines"][0].get("source")
            except Exception:
                existing_src = None
            if existing_src == engine:
                unchanged += 1
            else:
                picked += 1

        per_engine_counts[engine] = per_engine_counts.get(engine, 0) + 1

        out_page = dict(page_data)
        out_page["module_id"] = "pick_best_engine_v1"
        out_page["lines"] = chosen_lines
        out_page.setdefault("meta", {})
        if isinstance(out_page["meta"], dict):
            out_page["meta"]["picked_engine"] = details.get("picked_engine")
            out_page["meta"]["picked_details"] = details.get("candidates")
            out_page["meta"]["picked_score"] = details.get("picked_score")
            out_page["meta"]["picked_from_module_id"] = page_data.get("module_id")

        filename = os.path.basename(src_path)
        dst_path = pages_out / filename
        save_json(str(dst_path), out_page)
        new_index[page_key] = str(dst_path)
        append_jsonl(args.out, out_page)

        if idx % 25 == 0:
            logger.log("adapter", "running", current=idx, total=len(keys),
                       message=f"Picked engines for {idx}/{len(keys)} pages",
                       artifact=str(outdir), module_id="pick_best_engine_v1")

    index_out = outdir / "pagelines_index.json"
    save_json(str(index_out), {k: v for k, v in sorted(new_index.items())})

    logger.log("adapter", "done", current=len(new_index), total=len(new_index),
               message=f"Picked best engine for {len(new_index)} pages (changed={picked}, unchanged={unchanged})",
               artifact=str(index_out), module_id="pick_best_engine_v1", schema_version="pagelines_v1")

    print(f"Picked index: {index_out} (changed={picked}, unchanged={unchanged}); JSONL: {args.out}")


if __name__ == "__main__":
    main()
