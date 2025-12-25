import argparse
import json
import base64
from pathlib import Path
from typing import List

from modules.common.utils import ensure_dir, read_jsonl, save_jsonl
from openai import OpenAI


def choose_recipe(plan):
    book_type = plan.get("book_type") or "other"
    signals = set(plan.get("signals", []))
    gaps = plan.get("capability_gaps", [])

    # Simple heuristic mapping
    if book_type == "genealogy" or "tables" in signals:
        return "configs/recipes/legacy/recipe-ocr.yaml"  # placeholder until genealogy recipe exists
    if book_type == "cyoa" or "cyoa" in signals:
        return "configs/recipes/legacy/recipe-ocr.yaml"  # placeholder for CYOA pipeline
    if book_type == "novel":
        return "configs/recipes/legacy/recipe-ocr.yaml"
    if gaps:
        # keep None to force user decision
        return None
    return "configs/recipes/legacy/recipe-ocr.yaml"


def build_display_to_image(manifest_path: Path) -> dict:
    mapping = {}
    for line in manifest_path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        mapping[int(row.get("display_number"))] = row.get("source_image")
    return mapping


def encode_image_file(path: Path, detail: str):
    mime = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": detail}}


def verify_tables(plan, source_dir: Path, manifest_path: Path, model: str, vision_detail: str, max_verify: int = 8):
    pages = []
    for ev in plan.get("signal_evidence", []):
        if ev.get("signal") == "tables":
            pages.extend(ev.get("pages", []))
    pages = list(dict.fromkeys(pages))[:max_verify]
    if not pages:
        return plan

    display_to_img = build_display_to_image(manifest_path)
    client = OpenAI()
    keep_pages = []
    for pg in pages:
        fname = display_to_img.get(int(pg))
        if not fname:
            continue
        img_path = source_dir / fname
        if not img_path.exists():
            continue
        img_part = encode_image_file(img_path, vision_detail)
        prompt = "Does this page contain a tabular layout (rows/columns of names/dates/relationships)? Reply JSON {\"table\":true/false, \"reason\":string}."
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": [img_part]}],
            temperature=0.0,
            max_tokens=60,
        )
        content = resp.choices[0].message.content
        try:
            data = json.loads(content)
            if data.get("table") is True:
                keep_pages.append(pg)
        except Exception:
            continue

    if keep_pages:
        new_evidence = []
        for ev in plan.get("signal_evidence", []):
            if ev.get("signal") == "tables":
                ev = dict(ev)
                ev["pages"] = keep_pages
            new_evidence.append(ev)
        plan["signal_evidence"] = new_evidence
    return plan


def main():
    parser = argparse.ArgumentParser(description="Zoom refinement for intake plan")
    parser.add_argument("--plan-in", "--plan_in", dest="plan_in", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max_zoom_pages", type=int, default=5)
    parser.add_argument("--model", default="gpt-4.1")
    parser.add_argument("--vision_detail", default="low", choices=["low", "high"])
    parser.add_argument("--source_images_dir", default=None)
    parser.add_argument("--mock_output", default=None, help="Path to JSON to use instead of LLM")
    parser.add_argument("--boost_model", default=None)
    args, _unknown = parser.parse_known_args()

    plan_rows = list(read_jsonl(args.plan_in))
    plan = plan_rows[0] if plan_rows else {}

    zooms = plan.get("zoom_requests", [])
    if len(zooms) > args.max_zoom_pages:
        plan["zoom_requests"] = zooms[: args.max_zoom_pages]
        plan.setdefault("warnings", []).append(
            f"zoom_requests truncated to {args.max_zoom_pages}"
        )

    if plan.get("zoom_requests"):
        client = OpenAI()
        prompt = (
            "You are refining an intake plan for a book."
            " Inspect the provided page images and requested filenames."
            " Output JSON: book_type, type_confidence (0-1), signals (list: tables, formulas, images, cyoa, maps, sheet_music, forms, comics),"
            " signal_evidence (array of {signal, pages, reason}), recommended_recipe (path string), zoom_requests (may reorder/trim), warnings."
            " Use filenames to order pages; prefer earliest display numbers first if ambiguous."
        )
        contents: List = []
        if args.source_images_dir:
            src_dir = Path(args.source_images_dir)
            for fname in plan.get("zoom_requests", [])[: args.max_zoom_pages]:
                fp = src_dir / fname
                if fp.exists():
                    mime = "image/jpeg" if fp.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
                    b64 = base64.b64encode(fp.read_bytes()).decode("utf-8")
                    contents.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": args.vision_detail}})
        # If no images found, fall back to text-only context
        user_content = contents if contents else json.dumps({"zoom_requests": plan.get("zoom_requests", []), "signals": plan.get("signals", [])})
        if args.mock_output:
            data = json.load(open(args.mock_output, "r", encoding="utf-8"))
        else:
            resp = client.chat.completions.create(
                model=args.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.1,
                max_tokens=400,
            )
            content = resp.choices[0].message.content
            try:
                data = json.loads(content)
            except Exception:
                plan.setdefault("warnings", []).append("zoom_refine LLM parse failure")
                data = {}

        plan["book_type"] = data.get("book_type", plan.get("book_type"))
        plan["type_confidence"] = data.get("type_confidence", plan.get("type_confidence"))
        plan["signals"] = list(dict.fromkeys(plan.get("signals", []) + data.get("signals", [])))
        if data.get("signal_evidence"):
            plan["signal_evidence"] = data.get("signal_evidence")
        if data.get("recommended_recipe"):
            plan["recommended_recipe"] = data["recommended_recipe"]
        if data.get("zoom_requests"):
            plan["zoom_requests"] = data["zoom_requests"]
        plan.setdefault("warnings", []).extend(data.get("warnings", []))

    rec = plan.get("recommended_recipe") or choose_recipe(plan)
    plan["recommended_recipe"] = rec
    ensure_dir(Path(args.out).parent)
    save_jsonl(args.out, [plan])
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
