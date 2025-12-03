import argparse
import json
from typing import List, Dict

from openai import OpenAI

from modules.common.utils import read_jsonl, save_json
from modules.common.utils import log_llm_usage


PROMPT_HEADER = """You are a book-structure analyzer.
Your job is to identify the three macro-sections of a book using OCR’d page text:
- frontmatter
- main_content
- endmatter

Follow the rules below.

⸻

1. GLOBAL RULES (apply to all books unless overridden)

1.1 Input

You will receive:

pages — an array of objects:

{
  "page": <integer>,
  "raw_text": "<OCR text for this page>"
}

- The JSON page numbers are the only valid page numbers you may output.
- Printed page numbers inside the text must be ignored.
- Table-of-contents numbers must be ignored.

secondary_hint — optional string containing supporting information.
Use it only to refine an inference; never override textual evidence.

⸻

1.2 Determine the book type

Conceptually scan:
- the first 10–20 pages, and
- the last 10–20 pages.

Infer the book type using headings, structure, typography, and content patterns.

⸻

1.3 Define macro-sections

frontmatter
- Always begins at page 1.
- Includes items such as: title page, copyright, dedication, acknowledgements, TOC, preface, how-to-use, rules, equipment lists, tips, adventure sheets, etc.

main_content
- Begins at the earliest JSON page that clearly marks the start of the book’s primary body of material according to the book type.
- Confirm via raw_text.

endmatter
- Begins at the earliest JSON page after the main content has clearly ended.
- Includes: ads, previews, author bios, unrelated catalogs, or appendices not part of the main text.
- If no endmatter is clearly present, return null.

⸻

1.4 Constraints
- Only use JSON page numbers.
- Never invent or infer page numbers outside the input.
- If uncertain, be conservative:
  - Prefer starting main_content later rather than earlier.
  - Prefer starting endmatter at the first clearly non-main page.
- Use secondary_hint only as a minor tie-breaker.

⸻

1.5 Table of contents handling
- Use TOC only as a structural hint.
- Ignore all page references printed in it.
- Locate real headings in the raw_text.

⸻

1.6 Output

Return exactly this JSON object:

{
  "sections": [
    {
      "section_name": "frontmatter",
      "page": <integer>,
      "confidence": <float 0.0–1.0>
    },
    {
      "section_name": "main_content",
      "page": <integer>,
      "confidence": <float 0.0–1.0>
    },
    {
      "section_name": "endmatter",
      "page": <integer or null>,
      "confidence": <float 0.0–1.0>
    }
  ]
}

- frontmatter.page must always be 1.
- Confidence reflects clarity of classification.

⸻

2. OVERRIDE SECTION — these rules take precedence over all global rules

This book IS a CYOA / Fighting Fantasy–style gamebook.
Therefore, the following override rules must be applied and override any generic rules or genre expectations you may have.

2.1 CYOA / Fighting Fantasy Override Rules
- Main content always begins on the first page containing the heading “BACKGROUND”, “INTRODUCTION”, or any equivalent in-world narrative opening.
- These BACKGROUND/INTRODUCTION pages are part of main content, not frontmatter.
- The numbered choice/paragraph sections (e.g., “1”, “3”, “12”…):
  - Do not determine the start of main content.
  - They occur after the main content start defined above.
- Rules, instructions, how-to-play sections, equipment lists, potions, adventure sheets, and hints remain frontmatter.

⸻

JSONL pages:"""


def load_pages(path: str, max_chars: int) -> List[Dict]:
    pages = []
    for row in read_jsonl(path):
        pages.append({"page": row["page"], "raw_text": (row.get("raw_text") or "")[:max_chars]})
    return pages


def main():
    parser = argparse.ArgumentParser(description="Macro section detector for FF books using prompt-based LLM.")
    parser.add_argument("--pages", required=True, help="pages_clean.jsonl (expects page and raw_text)")
    parser.add_argument("--out", required=True, help="Output JSON with sections array.")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--max-chars", type=int, default=150)
    parser.add_argument("--secondary-hint", default=None)
    args = parser.parse_args()

    pages = load_pages(args.pages, args.max_chars)

    client = OpenAI()
    user_content = PROMPT_HEADER + "\n" + "\n".join(json.dumps(p) for p in pages)
    if args.secondary_hint:
        user_content += f"\n\nsecondary_hint: {args.secondary_hint}"

    completion = client.chat.completions.create(
        model=args.model,
        messages=[
            {"role": "user", "content": user_content}
        ],
        response_format={"type": "json_object"},
    )
    usage = getattr(completion, "usage", None)
    if usage:
        log_llm_usage(
            model=args.model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )
    data = json.loads(completion.choices[0].message.content)
    save_json(args.out, data)
    print(f"Saved macro sections → {args.out}")


if __name__ == "__main__":
    main()
