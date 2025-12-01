import argparse
import base64
import json
import os
from typing import Dict, Any, List

from modules.common.utils import ensure_dir, save_json


def load_index(index_path: str) -> Dict[int, str]:
    data = json.load(open(index_path, "r", encoding="utf-8"))
    return {int(k): v for k, v in data.items()}


def load_quality(path: str) -> List[Dict[str, Any]]:
    return json.load(open(path, "r", encoding="utf-8"))


def read_prompt(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "jpeg"
    return f"data:image/{ext};base64,{b64}"


def vision_transcribe(image_path: str, prompt: str, model: str, client=None) -> str:
    if client is None:
        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover - defensive
            raise RuntimeError("openai package not installed; pip install openai") from e
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
    content = response.choices[0].message.content
    return content or ""


def to_lines(text: str):
    return text.splitlines()


def main():
    parser = argparse.ArgumentParser(description="Escalate low-quality pages with GPT-4V transcription.")
    parser.add_argument("--index", help="pagelines_index.json from BetterOCR run")
    parser.add_argument("--quality", help="ocr_quality_report.json")
    parser.add_argument("--images-dir", dest="images_dir", help="Directory containing rendered page images")
    parser.add_argument("--images_dir", dest="images_dir", help=argparse.SUPPRESS)
    parser.add_argument("--outdir", help="Output base directory for escalated PageLines")
    parser.add_argument("--inputs", nargs="*", help="Optional driver-provided inputs (use first to infer paths)")
    parser.add_argument("--out", help="Optional adapter_out.jsonl path for driver stamping")
    parser.add_argument("--threshold", type=float, default=0.8, help="Disagreement threshold to escalate")
    parser.add_argument("--max-pages", dest="max_pages", type=int, default=10, help="Maximum pages to escalate")
    parser.add_argument("--max_pages", dest="max_pages", type=int, default=10, help=argparse.SUPPRESS)
    parser.add_argument("--model", default="gpt-4.1", help="Vision-capable model id")
    parser.add_argument("--prompt-file", dest="prompt_file", default="prompts/ocr_page_gpt4v.md")
    parser.add_argument("--prompt_file", dest="prompt_file", default="prompts/ocr_page_gpt4v.md", help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", help="List candidates without calling GPT-4V")
    parser.add_argument("--dry_run", dest="dry_run", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # Derive paths when called via driver with only --inputs
    if args.inputs and (not args.index or not args.quality or not args.images_dir or not args.outdir):
        run_dir = os.path.abspath(os.path.join(os.path.dirname(args.inputs[0]), ".."))
        args.index = args.index or os.path.join(run_dir, "ocr_ensemble", "pagelines_index.json")
        args.quality = args.quality or os.path.join(run_dir, "ocr_ensemble", "ocr_quality_report.json")
        args.images_dir = args.images_dir or os.path.join(run_dir, "images")
        args.outdir = args.outdir or run_dir + "-gpt4v"

    if not (args.index and args.quality and args.images_dir and args.outdir):
        raise SystemExit("index, quality, images-dir, and outdir are required (or infer via --inputs)")

    ensure_dir(args.outdir)
    prompt = read_prompt(args.prompt_file)

    index = load_index(args.index)
    quality = load_quality(args.quality)

    # Select pages needing escalation
    candidates = [q for q in quality if q.get("disagreement_score", 0) >= args.threshold]
    candidates.sort(key=lambda r: r.get("disagreement_score", 0), reverse=True)
    candidates = candidates[: args.max_pages]

    if not candidates:
        print("No pages exceed threshold; nothing to do.")
        return

    try:
        from openai import OpenAI
        client = OpenAI()
    except Exception as e:  # pragma: no cover - defensive
        client = None
        if not args.dry_run:
            raise

    new_index = {}
    new_quality = []

    for q in quality:
        page = int(q["page"])
        src_path = index.get(page)
        if not src_path:
            continue
        with open(src_path, "r", encoding="utf-8") as f:
            page_data = json.load(f)

        # default: copy unchanged
        out_page_path = os.path.join(args.outdir, f"page-{page:03d}.json")

        if any(c["page"] == page for c in candidates):
            image_path = os.path.join(args.images_dir, os.path.basename(page_data.get("image", "")))
            if args.dry_run:
                print(f"[DRY] would escalate page {page} using {image_path}")
                new_page = dict(page_data)
            else:
                text = vision_transcribe(image_path, prompt, args.model, client=client)
                lines = [{"text": line, "source": "gpt4v"} for line in to_lines(text)]
                new_page = dict(page_data)
                new_page["lines"] = lines
                new_page["disagreement_score"] = 0.0
                new_page["needs_escalation"] = False
                meta_prev = {
                    "prev_source": page_data.get("module_id"),
                    "prev_disagreement": page_data.get("disagreement_score"),
                    "engines_raw": page_data.get("engines_raw"),
                }
                new_page["meta"] = meta_prev
                new_page["module_id"] = "escalate_gpt4v_v1"
        else:
            new_page = page_data

        save_json(out_page_path, new_page)
        new_index[page] = out_page_path

        # update quality row
        if any(c["page"] == page for c in candidates):
            q = dict(q)
            q["disagreement_score"] = 0.0
            q["needs_escalation"] = False
            q["source"] = "gpt4v"
            q["engines"] = ["gpt4v"]
        new_quality.append(q)

    # Save index and quality
    index_path = os.path.join(args.outdir, "pagelines_index.json")
    quality_path = os.path.join(args.outdir, "ocr_quality_report.json")
    save_json(index_path, {k: v for k, v in sorted(new_index.items())})
    save_json(quality_path, new_quality)

    if args.out:
        summary = {
            "schema_version": "adapter_out",
            "module_id": "escalate_gpt4v_v1",
            "run_id": None,
            "created_at": None,
            "escalated_pages": [c["page"] for c in candidates],
            "threshold": args.threshold,
            "max_pages": args.max_pages,
            "index": index_path,
            "quality": quality_path,
            "outdir": args.outdir,
        }
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(json.dumps(summary) + "\n")
        print(f"Adapter summary → {args.out}")

    print(f"Escalated {len(candidates)} pages → {args.outdir}")
    print(f"Index: {index_path}\nQuality: {quality_path}")


if __name__ == "__main__":
    main()
