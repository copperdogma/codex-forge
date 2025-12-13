import argparse
import json
from typing import Any, Dict, List

from openai import OpenAI

from modules.common.utils import ProgressLogger, log_llm_usage, read_jsonl, save_jsonl

SYSTEM_PROMPT = """You are a context-aware proofreading assistant for Fighting Fantasy sections.
Correct the supplied section text so it reads coherently: fix missing words, fragmented sentences, and obvious grammar/spacing glitches while preserving punctuation, stats, choices, and original meaning. Use the supplied reasons/quality signals to guide the repair, but do NOT invent new plot elements.
Return JSON: {"context_corrected": "<string>", "confidence": <0-1 float>}.
"""


def load_portions(path: str) -> List[Dict[str, Any]]:
    return list(read_jsonl(path))


def call_context_model(client: OpenAI, text: str, section_id: str, reasons: List[str], model: str) -> (str, float):
    content = [
        {
            "type": "text",
            "text": (
                f"Section ID: {section_id}\n"
                f"Reasons: {', '.join(reasons) or 'none'}\n"
                f"Current text:\n{text.strip()}\n"
            ),
        }
    ]
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
    )
    usage = getattr(completion, "usage", None)
    if usage:
        log_llm_usage(
            model=model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            request_ms=None,
        )
    data = json.loads(completion.choices[0].message.content)
    corrected = (data.get("context_corrected") or "").strip()
    confidence = float(data.get("confidence", 0.0))
    return corrected, confidence


def should_repair_portion(text: str, metrics: Dict[str, Any], args: Any) -> (bool, List[str]):
    if not text:
        return False, []
    stripped = text.strip()
    if len(stripped) < args.min_chars:
        return False, []
    reasons: List[str] = []
    dict_score = float(metrics.get("dictionary_score") or 0.0)
    char_score = float(metrics.get("char_confusion_score") or 0.0)
    if dict_score >= args.dictionary_threshold:
        reasons.append(f"dictionary_score({dict_score:.2f})")
    if char_score >= args.char_confusion_threshold:
        reasons.append(f"char_confusion({char_score:.2f})")
    return bool(reasons), reasons


def save_portions(rows: List[Dict[str, Any]], path: str):
    save_jsonl(path, rows)


def main():
    parser = argparse.ArgumentParser(description="Context-aware post-processing for repaired sections.")
    parser.add_argument("--portions", required=True, help="Input portions jsonl.")
    parser.add_argument("--out", required=True, help="Output portions jsonl.")
    parser.add_argument("--model", default="gpt-5", help="Multimodal model for context repair.")
    parser.add_argument("--dictionary-threshold", type=float, default=0.15)
    parser.add_argument("--char-confusion-threshold", type=float, default=0.25)
    parser.add_argument("--min-chars", type=int, default=80)
    parser.add_argument("--max-corrections", type=int, default=32)
    parser.add_argument("--dry-run", action="store_true", help="Flag triggers without calling the model.")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    rows = load_portions(args.portions)
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("context_post", "running", current=0, total=len(rows),
               message="Scanning for context-aware repairs",
               artifact=args.out, module_id="context_aware_post_process_v1", schema_version="enriched_portion_v1")

    client = OpenAI()
    applied = 0
    for idx, row in enumerate(rows, start=1):
        text = row.get("raw_text") or row.get("text") or ""
        metrics = row.get("quality_metrics") or {}
        should_repair, reasons = should_repair_portion(text, metrics, args)
        correction: Dict[str, Any] = {
            "attempted": False,
            "reasons": reasons,
            "trigger_scores": {
                "dictionary_score": float(metrics.get("dictionary_score") or 0.0),
                "char_confusion_score": float(metrics.get("char_confusion_score") or 0.0),
            },
        }
        if should_repair and applied < args.max_corrections and not args.dry_run:
            correction["attempted"] = True
            try:
                cleaned, confidence = call_context_model(client, text, str(row.get("portion_id") or row.get("section_id") or idx), reasons, args.model)
                correction.update({"applied": bool(cleaned and cleaned != text), "confidence": confidence, "model": args.model})
                if cleaned and cleaned != text:
                    row["raw_text_original"] = text
                    row["raw_text"] = cleaned
                    applied += 1
                else:
                    correction["applied"] = False
            except Exception as exc:  # noqa: BLE001
                correction.update({"error": str(exc), "applied": False})
        elif should_repair and args.dry_run:
            correction.update({"would_repair": True})
        row["context_correction"] = correction
        if idx % 25 == 0:
            logger.log("context_post", "running", current=idx, total=len(rows),
                       message=f"Processed {idx}/{len(rows)} portions (corrections attempted: {applied})",
                       artifact=args.out, module_id="context_aware_post_process_v1")
    save_portions(rows, args.out)
    logger.log("context_post", "done", current=len(rows), total=len(rows),
               message=f"Context repairs scanned: {len(rows)} (applied: {applied})",
               artifact=args.out, module_id="context_aware_post_process_v1", schema_version="enriched_portion_v1")

if __name__ == "__main__":
    main()
