import argparse
import json
import os
from base64 import b64encode
from typing import List, Dict
from openai import OpenAI
from tqdm import tqdm
from utils import read_jsonl, save_jsonl


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
    args = parser.parse_args()

    client = OpenAI()
    pages = list(read_jsonl(args.pages))

    # attach base64 images
    for p in pages:
        if "image" in p and p["image"] and os.path.exists(p["image"]):
            p["image_b64"] = encode_image(p["image"])

    out_rows = []
    for p in tqdm(pages, desc="Clean pages"):
        result = clean_page(client, args.model, p)
        if result["confidence"] < args.min_conf and args.boost_model:
            result = clean_page(client, args.boost_model, p)
        out_rows.append(result)

    save_jsonl(args.out, out_rows)
    print(f"Saved cleaned pages → {args.out}")


if __name__ == "__main__":
    main()
