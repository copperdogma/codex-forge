#!/usr/bin/env python3
"""
Locate frontmatter/main_content/endmatter pages using the original minimal prompt.
Outputs a simple JSON report with section_name/page/confidence.
"""
import argparse
import json
import os
from collections import defaultdict

from openai import OpenAI

from modules.common.utils import read_jsonl, save_json, ProgressLogger, log_llm_usage

PROMPT = open(os.path.join(os.path.dirname(__file__), "prompt.md"), "r", encoding="utf-8").read()


def build_pages_summary(elements_path: str, max_chars: int = 200, max_pages: int = 120) -> list:
    by_page = defaultdict(list)
    for obj in read_jsonl(elements_path):
        # Handle both elements.jsonl (metadata.page_number) and elements_core.jsonl (page field)
        page = obj.get("page") or obj.get("metadata", {}).get("page_number")
        text = obj.get("text", "") or ""
        if page is None or not text.strip():
            continue
        by_page[page].append(text.strip()[:max_chars])
    pages = []
    for p in sorted(by_page.keys())[:max_pages]:
        pages.append({"page": p, "raw_text": "\n".join(by_page[p])})
    return pages


def call_llm(client: OpenAI, model: str, user_payload: str, max_tokens: int):
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": user_payload}],
        response_format={"type": "json_object"},
        max_tokens=max_tokens if not model.startswith("gpt-5") else None,
        **({"max_completion_tokens": max_tokens} if model.startswith("gpt-5") else {}),
    )
    usage = getattr(completion, "usage", None)
    log_llm_usage(
        model=model,
        prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        request_ms=None,
    )
    return completion.choices[0].message.content


def main():
    parser = argparse.ArgumentParser(description="Locate macro sections (frontmatter/main/end) using minimal OCR text.")
    parser.add_argument("--pages", required=True, help="elements.jsonl path")
    parser.add_argument("--out", required=True, help="Output JSON path for macro sections")
    parser.add_argument("--model", default="gpt-4.1", help="Model to use")
    parser.add_argument("--max_tokens", type=int, default=400, help="Max completion tokens")
    parser.add_argument("--max_pages", type=int, default=120, help="Max pages to include")
    parser.add_argument("--max_chars", type=int, default=200, help="Max chars per element line")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("portionize", "running", current=0, total=1, message="Building page summaries", module_id="macro_locate_ff_v1")

    pages = build_pages_summary(args.pages, max_chars=args.max_chars, max_pages=args.max_pages)
    if not pages:
        raise SystemExit("No pages found for macro location")

    buf = []
    for p in pages:
        buf.append(json.dumps(p))
    user_payload = PROMPT + "\n\nJSONL:\n\n" + "\n".join(buf)

    client = OpenAI(timeout=60.0)
    resp_text = call_llm(client, args.model, user_payload, args.max_tokens)
    try:
        payload = json.loads(resp_text)
    except Exception as e:
        raise SystemExit(f"LLM returned invalid JSON: {e}")

    save_json(args.out, payload)
    logger.log("portionize", "done", current=1, total=1,
               message=f"Macro sections detected", artifact=args.out, module_id="macro_locate_ff_v1")
    print(f"Wrote macro sections → {args.out}")


if __name__ == "__main__":
    main()
