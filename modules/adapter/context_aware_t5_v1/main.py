import argparse
import json
import logging
from typing import Any, Dict, List, Optional

from modules.common.openai_client import OpenAI
try:
    from transformers import pipeline
    from transformers.pipelines import Pipeline
except ImportError:  # pragma: no cover
    pipeline = None
    Pipeline = None  # type: ignore

from modules.common.utils import ProgressLogger, log_llm_usage, read_jsonl, save_jsonl

MODEL_CACHE: Dict[str, Pipeline] = {}
logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT = """You are a T5-powered editor that rewrites a Fighting Fantasy section to fix fragmented or truncated sentences while preserving content, punctuation, choices, and stats. Return JSON with {"t5_corrected": "<string>", "confidence": <float>}."""


def _init_pipeline(model_name: str) -> Optional[Pipeline]:
    if pipeline is None:
        logging.warning("transformers pipeline unavailable; skipping T5 corrections")
        return None
    if model_name in MODEL_CACHE:
        return MODEL_CACHE[model_name]
    pipe = pipeline("text2text-generation", model=model_name, tokenizer=model_name, device=-1)
    MODEL_CACHE[model_name] = pipe
    return pipe


def load_portions(path: str) -> List[Dict[str, Any]]:
    return list(read_jsonl(path))


def call_t5(pipe: Pipeline, text: str, section_id: str) -> (str, float):
    prompt = f"Section ID: {section_id}\nContext-aware rewrite:\n{text.strip()}"
    completion = pipe(prompt, max_length=256, truncation=True)
    if not completion:
        return text, 0.0
    best = completion[0]
    return (best.get("generated_text") or text).strip(), float(best.get("score", 0.0))


def should_call_t5(metrics: Dict[str, Any], args: Any) -> (bool, List[str]):
    reasons = []
    if metrics.get("dictionary_score", 0.0) >= args.dictionary_threshold:
        reasons.append("dictionary_score")
    if metrics.get("char_confusion_score", 0.0) >= args.char_confusion_threshold:
        reasons.append("char_confusion")
    return bool(reasons), reasons


def main():
    parser = argparse.ArgumentParser(description="Context-aware T5 refinement for repaired sections.")
    parser.add_argument("--portions", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", default="google/t5-small-lm-adapt")
    parser.add_argument("--dictionary-threshold", type=float, default=0.2)
    parser.add_argument("--char-confusion-threshold", type=float, default=0.3)
    parser.add_argument("--max-corrections", type=int, default=24)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    rows = load_portions(args.portions)
    pipe = _init_pipeline(args.model)
    client = OpenAI()
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("context_t5", "running", current=0, total=len(rows), artifact=args.out,
               module_id="context_aware_t5_v1", message="Running T5 refinements", schema_version="enriched_portion_v1")

    applied = 0
    for idx, row in enumerate(rows, start=1):
        text = row.get("raw_text") or row.get("text") or ""
        metrics = row.get("quality_metrics") or {}
        should, reasons = should_call_t5(metrics, args)
        correction = {
            "attempted": False,
            "reasons": reasons,
            "trigger_scores": {
                "dictionary_score": float(metrics.get("dictionary_score") or 0.0),
                "char_confusion_score": float(metrics.get("char_confusion_score") or 0.0),
            },
        }
        if should and applied < args.max_corrections and not args.dry_run and pipe:
            correction["attempted"] = True
            try:
                cleaned, confidence = call_t5(pipe, text, str(row.get("portion_id") or row.get("section_id") or idx))
                correction.update({"confidence": confidence, "model": args.model, "applied": bool(cleaned and cleaned != text)})
                if cleaned and cleaned != text:
                    row["context_t5"] = {
                        "before": text,
                        "after": cleaned,
                        "confidence": confidence,
                        "trigger_scores": correction["trigger_scores"],
                    }
                    row["raw_text"] = cleaned
                    applied += 1
                else:
                    correction["applied"] = False
            except Exception as exc:  # noqa: BLE001
                correction.update({"error": str(exc), "applied": False})
        elif should and args.dry_run and not pipe:
            correction["would_repair"] = True
        row.setdefault("context_corrections", []).append(correction)
        if idx % 25 == 0:
            logger.log("context_t5", "running", current=idx, total=len(rows), artifact=args.out,
                       module_id="context_aware_t5_v1", message=f"Processed {idx}/{len(rows)} portions (applied: {applied})")
    save_jsonl(args.out, rows)
    logger.log("context_t5", "done", current=len(rows), total=len(rows), artifact=args.out,
               module_id="context_aware_t5_v1", message=f"T5 processed {len(rows)} portions (applied: {applied})", schema_version="enriched_portion_v1")

if __name__ == "__main__":
    main()
