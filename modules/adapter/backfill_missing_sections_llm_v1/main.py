import argparse
import json
from typing import Dict, List, Optional, Tuple

from openai import OpenAI

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger, log_llm_usage

SYSTEM_PROMPT = """You are analyzing text extracted from a Fighting Fantasy gamebook. Sections are numbered consecutively.
You receive:
- prev_section: last known section number before this text
- next_section: next known section number after this text
- missing_sections: list of section numbers that are missing between prev and next
- elements: ordered list of text snippets with their element_id values

Goal: find where any missing section header appears inside the elements. A section header is typically a standalone number or a number preceding the section body.

Return JSON with a list of objects: [{"section_id": "<num>", "start_element_id": "<id>"}] for each missing section you can clearly locate. If you cannot find a section, omit it.
Be conservative; only return when confident the element marks the start of that section."""


def load_boundaries(path: str) -> List[Dict]:
    return list(read_jsonl(path))


def load_elements(path: str) -> Tuple[List[Dict], Dict[str, int]]:
    elements = list(read_jsonl(path))
    index = {e["id"]: idx for idx, e in enumerate(elements)}
    return elements, index


def span_between(elements: List[Dict], start_id: str, end_id: Optional[str], max_elements: int) -> List[Dict]:
    # inclusive of start, exclusive of end
    idx_map = {e["id"]: i for i, e in enumerate(elements)}
    start_idx = idx_map.get(start_id, 0)
    end_idx = idx_map.get(end_id, len(elements)) if end_id else len(elements)
    span = elements[start_idx:end_idx]
    return span[:max_elements]


def build_messages(prev_sec: str, next_sec: Optional[str], missing: List[str], span: List[Dict]) -> List[Dict]:
    lines = []
    for el in span:
        txt = str(el.get("text", ""))
        lines.append(f"{el.get('id')}: {txt}")
    user = {
        "role": "user",
        "content": json.dumps({
            "prev_section": prev_sec,
            "next_section": next_sec,
            "missing_sections": missing,
            "elements": lines,
        }, ensure_ascii=False)
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        user,
    ]


def call_llm(client: OpenAI, model: str, messages: List[Dict], max_tokens: int) -> List[Dict]:
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        max_tokens=max_tokens,
    )
    usage = getattr(completion, "usage", None)
    pt = getattr(usage, "prompt_tokens", 0) if usage else 0
    ct = getattr(usage, "completion_tokens", 0) if usage else 0
    log_llm_usage(model=model, prompt_tokens=pt, completion_tokens=ct, request_ms=None)
    content = completion.choices[0].message.content
    data = json.loads(content)
    return data.get("sections") or data.get("results") or data.get("found") or []


def main():
    parser = argparse.ArgumentParser(description="LLM backfill of missing section boundaries using gap spans.")
    parser.add_argument("--boundaries", required=True, help="section_boundaries.jsonl")
    parser.add_argument("--elements", required=True, help="elements_core.jsonl")
    parser.add_argument("--out", required=True, help="output boundaries JSONL")
    parser.add_argument("--expected-range-start", type=int, default=1)
    parser.add_argument("--expected-range-end", type=int, default=400)
    parser.add_argument("--target-ids", help="Optional comma-separated list or file with specific missing ids to consider")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--max-tokens", type=int, default=800)
    parser.add_argument("--max-elements", type=int, default=120)
    parser.add_argument("--progress-file", help="pipeline_events.jsonl")
    parser.add_argument("--state-file", help="pipeline_state.json")
    parser.add_argument("--run-id", help="run identifier")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    client = OpenAI()

    boundaries = load_boundaries(args.boundaries)
    elements, _ = load_elements(args.elements)

    existing_ids = {b.get("section_id") for b in boundaries if b.get("section_id")}
    if args.target_ids:
        if "," in args.target_ids or args.target_ids.strip().isdigit():
            targets = [t.strip() for t in args.target_ids.split(",") if t.strip()]
        else:
            with open(args.target_ids, "r", encoding="utf-8") as f:
                targets = [ln.strip() for ln in f if ln.strip()]
        expected = set(targets)
    else:
        expected = {str(i) for i in range(args.expected_range_start, args.expected_range_end + 1)}
    missing_all = sorted(list(expected - existing_ids), key=lambda x: int(x))

    numeric_sorted = sorted([b for b in boundaries if str(b.get("section_id", "")).isdigit()], key=lambda b: int(b["section_id"]))
    added = []

    for idx, b in enumerate(numeric_sorted[:-1]):
        cur_sec = b["section_id"]
        next_b = numeric_sorted[idx + 1]
        next_sec = next_b["section_id"]
        gap = list(range(int(cur_sec) + 1, int(next_sec)))
        gap_missing = [str(g) for g in gap if str(g) in missing_all]
        if not gap_missing:
            continue

        span = span_between(elements, b["start_element_id"], next_b["start_element_id"], args.max_elements)
        if not span:
            continue

        messages = build_messages(cur_sec, next_sec, gap_missing, span)
        try:
            results = call_llm(client, args.model, messages, args.max_tokens)
        except Exception as e:
            logger.log("adapter", "running", current=idx, total=len(numeric_sorted),
                       message=f"LLM error on gap {cur_sec}-{next_sec}: {e}", artifact=args.out,
                       module_id="backfill_missing_sections_llm_v1")
            continue

        if not isinstance(results, list):
            continue

        for res in results:
            sid = str(res.get("section_id")) if isinstance(res, dict) else None
            start_id = res.get("start_element_id") if isinstance(res, dict) else None
            if not sid or not start_id:
                continue
            added.append({
                "schema_version": "section_boundary_v1",
                "module_id": "backfill_missing_sections_llm_v1",
                "section_id": sid,
                "start_element_id": start_id,
                "end_element_id": next_b["start_element_id"],
                "confidence": 0.35,
                "evidence": f"LLM gap backfill between {cur_sec} and {next_sec}",
            })

    all_boundaries = boundaries + added
    all_sorted = sorted(all_boundaries, key=lambda b: int(b.get("section_id", 999999)))
    save_jsonl(args.out, all_sorted)

    still_missing = len(missing_all) - len({a["section_id"] for a in added})
    logger.log("adapter", "done", current=len(all_sorted), total=len(all_sorted),
               message=f"Added {len(added)} boundaries; {still_missing} still missing", artifact=args.out,
               module_id="backfill_missing_sections_llm_v1", schema_version="section_boundary_v1")
    print(f"Added {len(added)} boundaries; {still_missing} still missing → {args.out}")


if __name__ == "__main__":
    main()
