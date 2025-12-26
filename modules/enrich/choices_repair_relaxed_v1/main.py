import argparse
import json
from typing import List, Dict, Optional

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from modules.common.html_utils import html_to_text

try:
    from modules.common.openai_client import OpenAI
except Exception as exc:  # pragma: no cover - environment dependency
    OpenAI = None
    _OPENAI_IMPORT_ERROR = exc


PROMPT = """You are validating navigation choices in a gamebook section.

Input fields:
- section_id
- html: full section HTML (with headings, tables, etc.)
- text: plain text for backup (may be noisy)
- suspected_targets: list of section numbers that may be referenced

Task:
- Only return targets that are explicitly referenced as navigation choices.
- Only include targets from suspected_targets.
- Accept common forms like:
  - "turn to 94", "turn to 94–", "turn to 94.", "turn to 94?"
  - "if you ... turn to 94", "if you are lucky, turn to 94"
  - "go to 94", "refer to 94", "continue to 94"
- Ignore section headers and running heads (e.g., "16–17").
- Ignore stat blocks, page numbers, or other non-choice numbers.
- If no targets from the list are referenced, return choices=[].
- Do not invent text. Use a short snippet from the HTML/text for each choice.

Return JSON:
{
  "section_id": "<id>",
  "choices": [{"text": "<choice snippet>", "target": "<number>"}]
}
"""


def load_portions(path: str) -> List[Dict]:
    return list(read_jsonl(path))


def _normalize_targets(suspected) -> List[str]:
    out = []
    for t in suspected or []:
        if t is None:
            continue
        s = str(t).strip()
        if s.isdigit():
            out.append(s)
    return sorted(set(out), key=lambda x: int(x))


def _find_orphans(rows: List[Dict], min_target: int, max_target: int) -> List[str]:
    all_sections = set()
    referenced = set()
    for r in rows:
        sid = str(r.get("section_id") or r.get("portion_id") or "")
        if sid.isdigit():
            n = int(sid)
            if min_target <= n <= max_target:
                all_sections.add(n)
        for c in r.get("choices") or []:
            tgt = str(c.get("target") or "")
            if tgt.isdigit():
                n = int(tgt)
                if min_target <= n <= max_target:
                    referenced.add(n)
    orphans = sorted(all_sections - referenced - {min_target})
    return [str(o) for o in orphans]


def _derive_stats_path(portions_path: str) -> str:
    if portions_path.endswith(".jsonl"):
        return portions_path.replace(".jsonl", "_stats.json")
    return portions_path + "_stats.json"


def _load_stats(path: str) -> Dict:
    try:
        return json.loads(open(path, "r", encoding="utf-8").read())
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser(description="Repair missing choices using relaxed references as targets.")
    ap.add_argument("--inputs", nargs="*", help="Driver-provided inputs")
    ap.add_argument("--pages", help="Ignored (driver enrich-stage compatibility)")
    ap.add_argument("--portions", help="Portions JSONL (default: first --inputs)")
    ap.add_argument("--stats", help="Stats JSON (default: derived from portions path)")
    ap.add_argument("--out", required=True, help="Output portions JSONL")
    ap.add_argument("--model", default="gpt-5.1")
    ap.add_argument("--max-sources", "--max_sources", dest="max_sources", type=int, default=50,
                    help="Max source sections to inspect")
    ap.add_argument("--max-calls", "--max_calls", dest="max_calls", type=int, default=50,
                    help="Max LLM calls")
    ap.add_argument("--min-target", "--min_target", dest="min_target", type=int, default=1)
    ap.add_argument("--max-target", "--max_target", dest="max_target", type=int, default=400)
    ap.add_argument("--progress-file")
    ap.add_argument("--state-file")
    ap.add_argument("--run-id")
    args = ap.parse_args()

    if args.portions:
        portions_path = args.portions
    elif args.inputs:
        portions_path = args.inputs[0]
    else:
        raise SystemExit("Missing --portions or --inputs")

    if OpenAI is None:  # pragma: no cover
        raise RuntimeError("openai package required") from _OPENAI_IMPORT_ERROR

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    rows = load_portions(portions_path)
    by_id = {str(r.get("section_id") or r.get("portion_id") or ""): r for r in rows}

    stats_path = args.stats or _derive_stats_path(portions_path)
    stats = _load_stats(stats_path)
    relaxed_index = stats.get("relaxed_reference_index") or {}

    orphans = _find_orphans(rows, args.min_target, args.max_target)
    source_sections: List[str] = []
    for orphan in orphans:
        sources = relaxed_index.get(orphan) or []
        for s in sources:
            ss = str(s)
            if ss not in source_sections:
                source_sections.append(ss)
            if len(source_sections) >= args.max_sources:
                break
        if len(source_sections) >= args.max_sources:
            break

    logger.log(
        "enrich",
        "running",
        current=0,
        total=len(source_sections),
        message=f"Repairing choices from {len(source_sections)} source sections",
        artifact=args.out,
        module_id="choices_repair_relaxed_v1",
        schema_version="enriched_portion_v1",
    )

    if not source_sections and orphans:
        logger.log(
            "enrich",
            "warning",
            current=0,
            total=0,
            message=f"No relaxed sources found for orphans: {', '.join(orphans)}",
            artifact=args.out,
            module_id="choices_repair_relaxed_v1",
            schema_version="enriched_portion_v1",
        )

    client = OpenAI()
    calls = 0
    added_choices = 0
    repair_errors = 0
    for idx, sid in enumerate(source_sections, start=1):
        if calls >= args.max_calls:
            break
        r = by_id.get(sid)
        if not r:
            continue
        html = r.get("raw_html") or ""
        text = html_to_text(html)
        suspected_targets = []
        for orphan in orphans:
            sources = relaxed_index.get(orphan) or []
            if sid in [str(x) for x in sources]:
                suspected_targets.append(orphan)
        suspected_targets = _normalize_targets(suspected_targets)
        if not suspected_targets:
            continue

        try:
            if hasattr(client, "responses"):
                resp = client.responses.create(
                    model=args.model,
                    temperature=0,
                    max_output_tokens=400,
                    input=[{
                        "role": "user",
                        "content": PROMPT
                        + "\n\nsection_id: " + sid
                        + "\nhtml:\n" + html
                        + "\ntext:\n" + text
                        + "\nsuspected_targets: " + json.dumps(suspected_targets)
                    }],
                )
                raw = resp.output_text or ""
                usage = getattr(resp, "usage", None)
                request_id = getattr(resp, "id", None)
            else:
                resp = client.chat.completions.create(
                    model=args.model,
                    temperature=0,
                    max_completion_tokens=400,
                    messages=[{"role": "user", "content": PROMPT
                               + "\n\nsection_id: " + sid
                               + "\nhtml:\n" + html
                               + "\ntext:\n" + text
                               + "\nsuspected_targets: " + json.dumps(suspected_targets)}],
                )
                raw = resp.choices[0].message.content
                usage = getattr(resp, "usage", None)
                request_id = getattr(resp, "id", None)
        except Exception as exc:
            repair_errors += 1
            logger.log(
                "enrich",
                "running",
                current=idx,
                total=len(source_sections),
                message=f"Repair call failed for section {sid}: {exc}",
                artifact=args.out,
                module_id="choices_repair_relaxed_v1",
                schema_version="enriched_portion_v1",
            )
            continue
        calls += 1
        try:
            parsed = json.loads(raw)
        except Exception:
            continue
        choices = parsed.get("choices") or []
        if not choices:
            continue
        existing_targets = {str(c.get("target")) for c in (r.get("choices") or []) if c.get("target")}
        for c in choices:
            tgt = str(c.get("target") or "")
            if not tgt or tgt in existing_targets:
                continue
            if tgt not in suspected_targets:
                continue
            r.setdefault("choices", []).append({
                "target": tgt,
                "text": c.get("text") or f"Turn to {tgt}",
                "confidence": 0.8,
                "extraction_method": "repair_relaxed_llm",
                "pattern": "llm_confirmed",
                "text_snippet": c.get("text") or "",
            })
            existing_targets.add(tgt)
            added_choices += 1

        logger.log(
            "enrich",
            "running",
            current=idx,
            total=len(source_sections),
            message=f"Repaired choices for section {sid}",
            artifact=args.out,
            module_id="choices_repair_relaxed_v1",
            schema_version="enriched_portion_v1",
        )

    # Recompute orphan stats after repair
    orphans_after = _find_orphans(rows, args.min_target, args.max_target)
    stats_out = {
        "orphaned_sections": orphans_after,
        "orphaned_count": len(orphans_after),
        "repair_calls": calls,
        "repair_added_choices": added_choices,
        "repair_sources_examined": len(source_sections),
        "repair_errors": repair_errors,
        "repair_no_sources": bool(orphans and not source_sections),
    }
    if isinstance(relaxed_index, dict) and relaxed_index:
        stats_out["relaxed_reference_index"] = relaxed_index

    save_jsonl(args.out, rows)
    stats_path_out = _derive_stats_path(args.out)
    with open(stats_path_out, "w", encoding="utf-8") as f:
        json.dump(stats_out, f, indent=2)

    logger.log(
        "repair_choices",
        "done",
        current=len(source_sections),
        total=len(source_sections),
        message=f"Repaired choices; added {added_choices} new choices",
        artifact=args.out,
        module_id="choices_repair_relaxed_v1",
        schema_version="enriched_portion_v1",
        extra={"summary_metrics": {
            "issues_detected_count": len(orphans),
            "issues_repaired_count": added_choices,
            "choices_added_count": added_choices,
            "repair_calls": calls,
            "orphaned_count_before": len(orphans),
            "orphaned_count_after": len(orphans_after),
        }},
    )


if __name__ == "__main__":
    main()