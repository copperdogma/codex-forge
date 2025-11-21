import base64
import json
import os
from typing import Any, Dict, List
from openai import OpenAI
from schemas import PageResult

SYSTEM_PROMPT = """You transcribe Fighting Fantasy gamebook pages.
Input: (1) the raw OCR text of a single printed page; (2) the page image. Output: strict JSON only.
Rules:
- Capture every paragraph on the page. Each paragraph begins with its numeric id (1-400).
- Preserve the paragraph id as a string in 'id'.
- 'text' must be the cleaned narrative for that paragraph, without the leading id.
- 'choices' is a list of objects: {{ "target": "<number as string>", "text": "<optional choice description>" }}. Infer choice text from the sentence that says 'turn to N'. If missing, allow empty list.
- 'images' list the image filenames for this page (pass through from the caller).
- 'combat' object only if present: {{ "skill": int, "stamina": int, "name": "<monster name (optional)>" }}.
- 'test_luck' boolean only if the paragraph includes 'Test your Luck' or similar.
- 'item_effects' capture obvious inventory effects; keep as short description and include deltas if clear.
- Do NOT invent ids or choices; do NOT leave placeholders like 'MISSING PARAGRAPH'.
- Output JSON as: {{ "paragraphs": [ ... ] }}
Validate internally before responding. If any field is uncertain, re-read the image and choose the most faithful text, not a guess."""


def encode_image_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def call_llm(client: OpenAI, model: str, ocr_text: str, image_path: str) -> Dict[str, Any]:
    image_b64 = encode_image_b64(image_path)
    completion = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": "Raw OCR text follows:\n" + ocr_text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
            ]}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(completion.choices[0].message.content)


def clean_page(client: OpenAI, model: str, ocr_text: str, image_path: str) -> PageResult:
    data = call_llm(client, model, ocr_text, image_path)
    return PageResult.parse_obj(data)
