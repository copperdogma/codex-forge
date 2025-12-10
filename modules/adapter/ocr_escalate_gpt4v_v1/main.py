import argparse
import base64
import json
import os
from pathlib import Path
from typing import Dict, Any, List

from modules.common.utils import ensure_dir, save_json


def load_index(index_path: str) -> Dict[str, str]:
    """
    Load pagelines index. Keys may be integers (non-spread) or strings like "001L", "001R" (spread).
    Returns dict with string keys (preserves original key types as strings).
    """
    data = json.load(open(index_path, "r", encoding="utf-8"))
    return {str(k): v for k, v in data.items()}


def find_page_paths(index: Dict[str, str], page_num: int) -> List[str]:
    """
    Find page file paths for a given numeric page number.
    Handles both non-spread (single entry) and spread (L/R entries) cases.
    Returns list of paths (usually 1 for non-spread, 2 for spread).
    """
    paths = []
    # Try direct numeric key first
    key = str(page_num)
    if key in index:
        paths.append(index[key])
    # Try L/R variants (for spread pages)
    key_l = f"{page_num:03d}L"
    key_r = f"{page_num:03d}R"
    if key_l in index:
        paths.append(index[key_l])
    if key_r in index:
        paths.append(index[key_r])
    return paths


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
    parser.add_argument("--budget-pages", dest="budget_pages", type=int, default=None,
                        help="Optional hard cap from intake; if set, overrides max_pages")
    parser.add_argument("--budget_pages", dest="budget_pages", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--max_pages", dest="max_pages", type=int, default=10, help=argparse.SUPPRESS)
    parser.add_argument("--model", default="gpt-4.1", help="Vision-capable model id")
    parser.add_argument("--prompt-file", dest="prompt_file", default="prompts/ocr_page_gpt4v.md")
    parser.add_argument("--prompt_file", dest="prompt_file", default="prompts/ocr_page_gpt4v.md", help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", help="List candidates without calling GPT-4V")
    parser.add_argument("--dry_run", dest="dry_run", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # Derive paths when called via driver with only --inputs
    if args.inputs and (not args.index or not args.quality or not args.images_dir or not args.outdir):
        # If input is a json, use its parent; if it's a directory, use it directly
        first = Path(args.inputs[0]).resolve()
        run_dir = first.parent if first.is_file() else first
        if run_dir.name in {"ocr_ensemble", "ocr_ensemble_gpt4v"}:
            run_dir = run_dir.parent
        args.index = args.index or os.path.join(run_dir, "ocr_ensemble", "pagelines_index.json")
        args.quality = args.quality or os.path.join(run_dir, "ocr_ensemble", "ocr_quality_report.json")
        args.images_dir = args.images_dir or os.path.join(run_dir, "images")
        # Write escalated pages into main run directory (ocr_ensemble_gpt4v subdirectory)
        args.outdir = args.outdir or os.path.join(run_dir, "ocr_ensemble_gpt4v")

    if not (args.index and args.quality and args.images_dir and args.outdir):
        raise SystemExit("index, quality, images-dir, and outdir are required (or infer via --inputs)")

    ensure_dir(args.outdir)
    prompt = read_prompt(args.prompt_file)

    index = load_index(args.index)
    quality = load_quality(args.quality)

    # Select pages needing escalation
    # Use enhanced quality metrics: quality_score, corruption_score, or traditional disagreement_score
    candidates = []
    for q in quality:
        # Extract nested quality metrics if present
        quality_metrics = q.get("quality_metrics", {})
        if isinstance(quality_metrics, dict):
            corruption_score = quality_metrics.get("corruption_score", 0)
            missing_content_score = quality_metrics.get("missing_content_score", 0)
        else:
            corruption_score = q.get("corruption_score", 0)
            missing_content_score = q.get("missing_content_score", 0)
        
        # Check multiple quality indicators
        needs_escalation = (
            q.get("needs_escalation", False) or
            q.get("disagreement_score", 0) >= args.threshold or
            q.get("disagree_rate", 0) > 0.25 or  # High line-level disagreement rate
            q.get("quality_score", 0) >= args.threshold or  # Enhanced quality score
            corruption_score >= 0.5 or  # High corruption
            missing_content_score >= 0.6  # Missing content
        )
        if needs_escalation:
            candidates.append(q)
    
    # Sort by quality_score (if available) or disagreement_score, prioritizing worst pages
    # Extract nested quality metrics for sorting
    def get_sort_key(r):
        quality_metrics = r.get("quality_metrics", {})
        if isinstance(quality_metrics, dict):
            corruption = quality_metrics.get("corruption_score", 0)
            missing = quality_metrics.get("missing_content_score", 0)
        else:
            corruption = r.get("corruption_score", 0)
            missing = r.get("missing_content_score", 0)
        
        # Primary sort: use quality_score if meaningful (>0.01), otherwise use disagree_rate
        # This ensures pages with high disagree_rate but low quality_score still get prioritized
        quality_score = r.get("quality_score", 0)
        if quality_score < 0.01:
            # Quality score is too low, use disagree_rate as primary sort
            primary = r.get("disagree_rate", r.get("disagreement_score", 0))
        else:
            primary = quality_score
        
        return (
            primary,
            corruption,
            missing,
            r.get("disagree_rate", 0)  # Tie-breaker: prefer higher disagree_rate
        )
    candidates.sort(key=get_sort_key, reverse=True)
    cap = args.budget_pages if args.budget_pages is not None else args.max_pages
    candidates = candidates[: cap]

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
        # Quality report uses page_key (string like "001L"/"001R") not numeric page
        page_key = str(q["page"])
        src_path = index.get(page_key)
        if not src_path:
            continue
        
        with open(src_path, "r", encoding="utf-8") as f:
            page_data = json.load(f)

        # Output path preserves L/R if present in page_key
        if page_key.endswith("L") or page_key.endswith("R"):
            out_page_path = os.path.join(args.outdir, f"page-{page_key}.json")
        else:
            # Fallback for non-spread pages (shouldn't happen with current setup, but safe)
            page_num = int(page_key) if page_key.isdigit() else 1
            out_page_path = os.path.join(args.outdir, f"page-{page_num:03d}.json")

        # Check if this page needs escalation (compare by page_key)
        needs_escalation = any(str(c["page"]) == page_key for c in candidates)
        
        if needs_escalation:
            image_path = os.path.join(args.images_dir, os.path.basename(page_data.get("image", "")))
            if args.dry_run:
                print(f"[DRY] would escalate page {page_key} using {image_path}")
                new_page = dict(page_data)
            else:
                text = vision_transcribe(image_path, prompt, args.model, client=client)
                # Format lines with canonical text only (raw/fused/post remain in engines_raw for provenance)
                # For GPT-4V escalation, we output only the final canonical text
                lines = []
                for line_text in to_lines(text):
                    lines.append({
                        "text": line_text,
                        "source": "gpt4v",
                    })
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
                new_page["module_id"] = "ocr_escalate_gpt4v_v1"
        else:
            new_page = page_data

        save_json(out_page_path, new_page)
        new_index[page_key] = out_page_path

        # update quality row
        if needs_escalation:
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
            "module_id": "ocr_escalate_gpt4v_v1",
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
