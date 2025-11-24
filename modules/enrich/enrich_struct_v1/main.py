import argparse
import json
import os
from base64 import b64encode
from typing import Dict, List, Optional

from openai import OpenAI
from tqdm import tqdm

from modules.common.utils import read_jsonl, append_jsonl, ensure_dir, ProgressLogger, log_llm_usage
from schemas import EnrichedPortion

SYSTEM_PROMPT = """You extract structured adventure mechanics from a portion of text.
Return JSON with keys: choices (list of {target: string, text?: string}), combat (object with skill:int, stamina:int, name?: string or null if none), test_luck (boolean or null), item_effects (list of effects with fields description?, delta_gold?, delta_provisions?, add_item?, use_item?).
Rules:
- Only include choices that exist; omit or empty list if none. Targets should be numeric strings when present.
- If no combat, set combat: null.
- test_luck true only if the text asks the reader to Test your Luck; false if explicitly says not to test; null if absent.
- item_effects should stay minimal; when unsure use description.
- Do not invent content beyond the provided text.
Respond with JSON only."""


def load_pages(path: str) -> Dict[int, Dict]:
    return {p["page"]: p for p in read_jsonl(path)}


def extract_span_text(portion: Dict, pages: Dict[int, Dict], text_field: str, max_chars: int) -> (str, List[str], List[Dict]):
    pieces: List[str] = []
    images: List[str] = []
    page_blobs: List[Dict] = []
    for page_num in range(portion["page_start"], portion["page_end"] + 1):
        page = pages.get(page_num)
        if not page:
            continue
        text = page.get(text_field) or page.get("clean_text") or page.get("raw_text") or page.get("text") or ""
        pieces.append(f"[PAGE {page_num}]\n{text}")
        if page.get("image"):
            images.append(page["image"])
        page_blobs.append(page)
    text_joined = "\n\n".join(pieces)
    if len(text_joined) > max_chars:
        text_joined = text_joined[:max_chars] + "\n\n[TRUNCATED]"
    return text_joined, images, page_blobs


def call_llm(client: OpenAI, model: str, prompt_text: str, images: List[Dict]) -> Dict:
    content = [{"type": "text", "text": prompt_text}]
    for img in images:
        if img.get("image_b64"):
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img['image_b64']}"}})
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
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
    return json.loads(completion.choices[0].message.content)


def maybe_encode_images(pages: List[Dict], include_images: bool) -> List[Dict]:
    if not include_images:
        return pages
    encoded = []
    for p in pages:
        if p.get("image") and os.path.exists(p["image"]):
            if "image_b64" not in p:
                with open(p["image"], "rb") as f:
                    p = dict(p)
                    p["image_b64"] = b64encode(f.read()).decode("utf-8")
        encoded.append(p)
    return encoded


def normalize_enrichment(portion: Dict, enrichment: Dict, raw_text: str, source_images: List[str]) -> Dict:
    choices = enrichment.get("choices") or []
    item_effects = enrichment.get("item_effects") or []
    combat = enrichment.get("combat")
    test_luck = enrichment.get("test_luck")

    enriched = EnrichedPortion(
        portion_id=portion["portion_id"],
        page_start=portion["page_start"],
        page_end=portion["page_end"],
        title=portion.get("title"),
        type=portion.get("type"),
        confidence=portion.get("confidence", 0.0),
        source_images=source_images,
        raw_text=raw_text,
        choices=choices,
        combat=combat,
        test_luck=test_luck,
        item_effects=item_effects,
        module_id="enrich_struct_v1"
    )
    return enriched.dict()


def main():
    parser = argparse.ArgumentParser(description="Enrich resolved portions with adventure mechanics.")
    parser.add_argument("--portions", required=True, help="Resolved portions JSONL")
    parser.add_argument("--pages", required=True, help="Pages JSONL (clean/raw)")
    parser.add_argument("--out", required=True, help="Output enriched_portion JSONL")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--boost_model", default=None)
    parser.add_argument("--text_field", default="clean_text", choices=["clean_text", "raw_text", "text"])
    parser.add_argument("--max_chars", type=int, default=1600)
    parser.add_argument("--include_images", action="store_true", help="Attach images for multimodal extraction")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    portions = list(read_jsonl(args.portions))
    pages_map = load_pages(args.pages)
    client = OpenAI()
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    ensure_dir(os.path.dirname(args.out) or ".")

    total = len(portions)
    for idx, portion in enumerate(tqdm(portions, desc="Enrich"), start=1):
        raw_text, page_images, page_blobs = extract_span_text(portion, pages_map, args.text_field, args.max_chars)
        page_blobs = maybe_encode_images(page_blobs, args.include_images)
        try:
            enrichment = call_llm(
                client,
                args.model,
                f"Portion {portion.get('portion_id')} (pages {portion.get('page_start')}-{portion.get('page_end')}):\n{raw_text}",
                page_blobs
            )
            if not enrichment and args.boost_model:
                enrichment = call_llm(
                    client,
                    args.boost_model,
                    f"Portion {portion.get('portion_id')} (pages {portion.get('page_start')}-{portion.get('page_end')}):\n{raw_text}",
                    page_blobs
                )
            record = normalize_enrichment(portion, enrichment or {}, raw_text, page_images)
            append_jsonl(args.out, record)
            logger.log("enrich", "running", current=idx, total=total,
                       message=f"enriched {portion.get('portion_id')}", artifact=args.out)
        except Exception as e:
            append_jsonl(args.out, {**portion, "error": str(e), "raw_text": raw_text})
            logger.log("enrich", "running", current=idx, total=total,
                       message=f"error on {portion.get('portion_id')}: {e}", artifact=args.out)

    logger.log("enrich", "done", current=total, total=total,
               message=f"Enriched {total} portions", artifact=args.out)
    print(f"Enriched {total} portions → {args.out}")


if __name__ == "__main__":
    main()
