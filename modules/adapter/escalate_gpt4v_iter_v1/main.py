import argparse
import base64
import json
import os
from typing import Any, Dict, List

from modules.common.utils import ensure_dir, save_json


def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "jpeg"
    return f"data:image/{ext};base64,{b64}"


def load_prompt(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def vision_transcribe(image_path: str, prompt: str, model: str, client=None) -> str:
    if client is None:
        from modules.common.openai_client import OpenAI

        client = OpenAI()
    image_data = encode_image(image_path)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data}},
                ],
            }
        ],
        max_tokens=4096,
        temperature=0,
    )
    return response.choices[0].message.content or ""


def load_json(path: str):
    return json.load(open(path, "r", encoding="utf-8"))


def save_json_sorted(path: str, data: Dict[int, str]):
    save_json(path, {k: v for k, v in sorted(data.items())})


def split_lines(text: str):
    return text.splitlines()


def select_candidates(quality: List[Dict[str, Any]], threshold: float, limit: int) -> List[int]:
    rows = [r for r in quality if r.get("disagreement_score", 0) >= threshold]
    rows.sort(key=lambda r: r.get("disagreement_score", 0), reverse=True)
    return [int(r["page"]) for r in rows][:limit]


def main():
    parser = argparse.ArgumentParser(description="Iteratively escalate high-disagreement pages with GPT-4V until threshold met or budget used.")
    parser.add_argument("--index", required=True, help="pagelines_index.json (source run)")
    parser.add_argument("--quality", required=True, help="ocr_quality_report.json (source run)")
    parser.add_argument("--images-dir", required=True, help="images directory from source run")
    parser.add_argument("--outdir", required=True, help="output directory for escalated run")
    parser.add_argument("--threshold", type=float, default=0.4)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--max-pages", type=int, default=40, help="overall cap across batches")
    parser.add_argument("--model", default="gpt-4.1")
    parser.add_argument("--prompt-file", default="prompts/ocr_page_gpt4v.md")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pages", help="Comma-separated explicit page numbers to escalate (overrides threshold selection)")
    args = parser.parse_args()

    ensure_dir(args.outdir)
    prompt = load_prompt(args.prompt_file)

    index = {int(k): v for k, v in load_json(args.index).items()}
    quality = load_json(args.quality)

    explicit_pages: List[int] = []
    if args.pages:
        explicit_pages = [int(p.strip()) for p in args.pages.split(",") if p.strip()]

    escalated_pages: List[int] = []
    batches = 0

    def next_batch():
        remaining_budget = args.max_pages - len(escalated_pages)
        if remaining_budget <= 0:
            return []
        if explicit_pages:
            remaining = [p for p in explicit_pages if p not in escalated_pages]
            return remaining[: min(args.batch_size, remaining_budget)]
        return select_candidates(quality, args.threshold, min(args.batch_size, remaining_budget))

    while True:
        cand = next_batch()
        # skip already escalated
        cand = [c for c in cand if c not in escalated_pages]
        if not cand:
            break

        batches += 1
        print(f"Batch {batches}: escalating pages {cand}")

        from modules.common.openai_client import OpenAI

        client = OpenAI() if not args.dry_run else None

        for page in cand:
            src = index[page]
            page_data = load_json(src)
            image_path = os.path.join(args.images_dir, os.path.basename(page_data.get("image", "")))
            if args.dry_run:
                text = page_data.get("raw_text") or ""
            else:
                text = vision_transcribe(image_path, prompt, args.model, client)
            lines = [{"text": l, "source": "gpt4v"} for l in split_lines(text)]
            page_data["lines"] = lines
            page_data["disagreement_score"] = 0.0
            page_data["needs_escalation"] = False
            page_data["module_id"] = "escalate_gpt4v_iter_v1"
            out_page_path = os.path.join(args.outdir, f"page-{page:03d}.json")
            save_json(out_page_path, page_data)
            index[page] = out_page_path

            # update quality row
            for row in quality:
                if int(row["page"]) == page:
                    row["disagreement_score"] = 0.0
                    row["needs_escalation"] = False
                    row["source"] = "gpt4v"
                    row["engines"] = ["gpt4v"]
                    break
        escalated_pages.extend(cand)

    # dump untouched pages into outdir index too
    for page, path in index.items():
        if os.path.exists(path):
            continue  # already written into outdir
        # copy reference to existing file
        index[page] = path

    save_json_sorted(os.path.join(args.outdir, "pagelines_index.json"), index)
    save_json(os.path.join(args.outdir, "ocr_quality_report.json"), quality)

    summary = {
        "schema_version": "adapter_out",
        "module_id": "escalate_gpt4v_iter_v1",
        "run_id": None,
        "created_at": None,
        "escalated_pages": escalated_pages,
        "batches": batches,
        "threshold": args.threshold,
        "max_pages": args.max_pages,
        "batch_size": args.batch_size,
        "outdir": args.outdir,
    }
    with open(os.path.join(args.outdir, "adapter_out.jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps(summary) + "\n")

    print(f"Escalated {len(escalated_pages)} pages in {batches} batches → {args.outdir}")


if __name__ == "__main__":
    main()
