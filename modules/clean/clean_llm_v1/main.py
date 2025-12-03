import argparse
import json
import os
from base64 import b64encode
from typing import List, Dict
from openai import OpenAI
from tqdm import tqdm

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger, log_llm_usage


CLEAN_PROMPT = """You are cleaning OCR text for a scanned book page.
Input: the page image and the raw OCR text. Output: a corrected text that matches the image faithfully.
Rules:
- Do NOT invent or omit content.
- Preserve page-internal markers like headings and numbers.
- Fix obvious OCR errors (letters, spacing, punctuation).
- Keep the original line breaks roughly; paragraphs can be joined if needed, but keep order.
- If unsure about a word, choose the most visually probable reading, not a guess from context.
Return JSON: { "clean_text": "<string>", "confidence": <0-1 float> }"""


def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return b64encode(f.read()).decode("utf-8")


def clean_page(client: OpenAI, model: str, page: Dict) -> Dict:
    content = [
        {"type": "text", "text": "Raw OCR:\n" + page.get("text", "")},
    ]
    if page.get("image"):
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{page['image_b64']}"}})

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": CLEAN_PROMPT},
            {"role": "user", "content": content}
        ],
        response_format={"type": "json_object"}
    )
    usage = getattr(completion, "usage", None)
    pt = getattr(usage, "prompt_tokens", None)
    ct = getattr(usage, "completion_tokens", None)
    if pt is None or ct is None:
        pt = pt or 0
        ct = ct or 0
    log_llm_usage(
        model=model,
        prompt_tokens=pt,
        completion_tokens=ct,
        request_ms=None,
    )
    data = json.loads(completion.choices[0].message.content)
    return {
        "page": page["page"],
        "image": page.get("image"),
        "raw_text": page.get("text", ""),
        "clean_text": data.get("clean_text", page.get("text", "")),
        "confidence": data.get("confidence", 0.0)
    }


def main():
    parser = argparse.ArgumentParser(description="Clean OCR text per page using multimodal LLM.")
    parser.add_argument("--pages", required=True, help="pages_raw.jsonl")
    parser.add_argument("--out", required=True, help="pages_clean.jsonl")
    parser.add_argument("--model", default="gpt-5-mini")
    parser.add_argument("--boost_model", default=None, help="Optional higher-tier model if confidence too low.")
    parser.add_argument("--min_conf", type=float, default=0.75, help="Boost if below this confidence.")
    parser.add_argument("--skip-ai", action="store_true", help="Bypass LLM calls and load clean pages from stub.")
    parser.add_argument("--stub", help="Stub clean_page jsonl to use when --skip-ai")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    # Smoke/skip path
    if args.skip_ai:
        if not args.stub:
            raise SystemExit("--skip-ai set but no --stub provided for clean_llm_v1")
        stub_rows = list(read_jsonl(args.stub))
        save_jsonl(args.out, stub_rows)
        logger.log("clean", "done", current=len(stub_rows), total=len(stub_rows),
                   message="Loaded clean stubs", artifact=args.out)
        print(f"[skip-ai] clean_llm_v1 copied stubs → {args.out}")
        return

    client = OpenAI()
    pages = list(read_jsonl(args.pages))

    # attach base64 images
    for p in pages:
        if "image" in p and p["image"] and os.path.exists(p["image"]):
            p["image_b64"] = encode_image(p["image"])

    out_rows = []
    total = len(pages)
    for idx, p in enumerate(tqdm(pages, desc="Clean pages"), start=1):
        result = clean_page(client, args.model, p)
        if result["confidence"] < args.min_conf and args.boost_model:
            result = clean_page(client, args.boost_model, p)
        out_rows.append(result)
        logger.log("clean", "running", current=idx, total=total,
                   message=f"Cleaned page {p.get('page')}", artifact=args.out)

    save_jsonl(args.out, out_rows)
    logger.log("clean", "done", current=total, total=total,
               message="Clean complete", artifact=args.out)
    print(f"Saved cleaned pages → {args.out}")


if __name__ == "__main__":
    main()
