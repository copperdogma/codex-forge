import argparse
import base64
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

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


def _extract_quality_subscores(q: Dict[str, Any]) -> Dict[str, float]:
    """
    Normalize quality report fields across versions (nested vs flat).
    Values are 0..1 where higher generally indicates worse quality.
    """
    quality_metrics = q.get("quality_metrics", {})
    if not isinstance(quality_metrics, dict):
        quality_metrics = {}
    return {
        "quality_score": float(q.get("quality_score", 0) or 0),
        "disagreement_score": float(q.get("disagreement_score", 0) or 0),
        "disagree_rate": float(q.get("disagree_rate", 0) or 0),
        "corruption_score": float(quality_metrics.get("corruption_score", q.get("corruption_score", 0)) or 0),
        "missing_content_score": float(quality_metrics.get("missing_content_score", q.get("missing_content_score", 0)) or 0),
        "dictionary_score": float(quality_metrics.get("dictionary_score", q.get("dictionary_score", 0)) or 0),
        "char_confusion_score": float(quality_metrics.get("char_confusion_score", q.get("char_confusion_score", 0)) or 0),
    }


def page_escalation_reasons(q: Dict[str, Any], *, threshold: float) -> List[str]:
    """
    Derive explicit reasons for escalation from the quality report record.

    Prefer upstream-computed `escalation_reasons` when present; otherwise fall back
    to conservative legacy signals.
    """
    reasons = q.get("escalation_reasons")
    if isinstance(reasons, list) and all(isinstance(x, str) for x in reasons):
        return list(reasons)

    subs = _extract_quality_subscores(q)
    out: List[str] = []
    if q.get("needs_escalation", False):
        out.append("needs_escalation_flag")
    if subs["disagreement_score"] >= threshold:
        out.append("high_disagreement")
    if subs["disagree_rate"] > 0.25:
        out.append("high_disagree_rate")
    if subs["quality_score"] >= threshold:
        out.append("high_quality_score")
    if subs["corruption_score"] >= 0.5:
        out.append("high_corruption")
    if subs["missing_content_score"] >= 0.6:
        out.append("missing_content")
    if subs["dictionary_score"] >= 0.5:
        out.append("dictionary_oov")
    if subs["char_confusion_score"] >= 0.25:
        out.append("char_confusion")
    return out


def page_needs_escalation(q: Dict[str, Any], *, threshold: float) -> bool:
    if q.get("needs_escalation", False):
        return True
    return bool(page_escalation_reasons(q, threshold=threshold))


def candidate_sort_key(q: Dict[str, Any]) -> Tuple[float, float, float, float, float, float]:
    subs = _extract_quality_subscores(q)
    # Primary: prioritize disagreement_score (this is what thresholding historically used),
    # but allow quality_score to bubble up severe non-disagreement failures when present.
    quality_score = subs["quality_score"]
    disagreement_score = subs["disagreement_score"]
    if quality_score < 0.01 and disagreement_score < 0.01:
        primary = subs["disagree_rate"]
    else:
        # Add small boosts for content-centric failure signals so they are less likely
        # to be starved by purely structural disagreement pages under small budgets.
        primary = max(disagreement_score, quality_score)
        primary += subs["dictionary_score"] * 0.12
        primary += subs["char_confusion_score"] * 0.10
        primary += subs["missing_content_score"] * 0.06
        primary += subs["corruption_score"] * 0.04
    return (
        float(primary),
        subs["corruption_score"],
        subs["missing_content_score"],
        subs["dictionary_score"],
        subs["char_confusion_score"],
        subs["disagree_rate"],
    )


def _page_text_stats(page_data: Dict[str, Any]) -> Dict[str, Any]:
    lines = page_data.get("lines") or []
    texts: List[str] = []
    for ln in lines:
        if isinstance(ln, dict):
            t = ln.get("text")
            if isinstance(t, str) and t:
                texts.append(t)
    joined = "\n".join(texts)
    return {
        "line_count": len(texts),
        "char_count": len(joined),
        "has_text": bool(joined.strip()),
    }


def _load_page_data(page_key: str,
                    index: Dict[str, str],
                    pages_cache: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    page_path = index.get(page_key)
    if not page_path:
        return None
    if page_key in pages_cache:
        return pages_cache[page_key]
    try:
        page_data = json.load(open(page_path, "r", encoding="utf-8"))
        pages_cache[page_key] = page_data
        return page_data
    except Exception:
        return None


def _resolve_other_side_key(page_key: str,
                            page_data: Optional[Dict[str, Any]],
                            index: Dict[str, str],
                            pages_cache: Dict[str, Dict[str, Any]]) -> Optional[str]:
    # Legacy fast path: L/R suffix in key
    if page_key.endswith("L") or page_key.endswith("R"):
        return page_key[:-1] + ("R" if page_key.endswith("L") else "L")
    if not page_data:
        return None
    orig = page_data.get("original_page_number")
    side = page_data.get("spread_side")
    if side not in ("L", "R") or not isinstance(orig, int):
        return None
    target = "R" if side == "L" else "L"
    key_lr = f"{orig:03d}{target}"
    if key_lr in index:
        return key_lr
    key_plain = f"{orig}{target}"
    if key_plain in index:
        return key_plain
    for k in index.keys():
        if k == page_key:
            continue
        other = _load_page_data(k, index, pages_cache)
        if not other:
            continue
        if other.get("original_page_number") == orig and other.get("spread_side") == target:
            return k
    return None


def should_escalate_page_key(page_key: str,
                            reasons: List[str],
                            *,
                            index: Dict[str, str],
                            pages_cache: Dict[str, Dict[str, Any]],
                            min_other_side_chars: int,
                            min_chars_to_escalate_short_missing: int) -> Tuple[bool, Optional[str]]:
    """
    Apply conservative policy to avoid expensive rereads on likely-legit short/blank pages.

    Returns (should_escalate, skip_reason).
    """
    if not reasons:
        return False, "no_reasons"

    # Load current page data for text stats when needed.
    page_data = _load_page_data(page_key, index, pages_cache)

    stats = _page_text_stats(page_data or {})

    # Heuristic 1: For "missing_content" only, avoid escalating very short legit pages
    # like "NOW TURN OVER" unless they're actually empty.
    if reasons == ["missing_content"] and stats["has_text"] and stats["char_count"] < min_chars_to_escalate_short_missing:
        return False, "skip_short_missing_content"

    # Heuristic 2: For half-spreads, empty-side pages are often truly blank.
    # If this side is empty and the other side has substantial text, skip reread.
    if reasons == ["missing_content"] and (not stats["has_text"]):
        other_key = _resolve_other_side_key(page_key, page_data, index, pages_cache)
        if other_key:
            other = _load_page_data(other_key, index, pages_cache)
            other_stats = _page_text_stats(other or {})
            if other_stats["has_text"] and (other_stats["char_count"] >= min_other_side_chars or other_stats["char_count"] > 0):
                return False, "skip_blank_half_spread"

    return True, None


def update_quality_row(q: Dict[str, Any], *, would_escalate: bool, reasons: List[str], dry_run: bool) -> Dict[str, Any]:
    """
    Return a new quality row reflecting escalation.
    In dry-run mode, never clears flags; instead annotates with `would_escalate`.
    """
    out = dict(q)
    if not would_escalate:
        return out

    if dry_run:
        out["would_escalate"] = True
        out["would_escalate_reasons"] = list(reasons)
        return out

    out["disagreement_score"] = 0.0
    out["needs_escalation"] = False
    out["source"] = "gpt4v"
    out["engines"] = ["gpt4v"]
    if reasons:
        out["escalated_from_reasons"] = list(reasons)
    out["escalation_reasons"] = []
    return out


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
    parser.add_argument("--min-other-side-chars", dest="min_other_side_chars", type=int, default=200,
                        help="When skipping blank half-spreads, require the other side to have at least this many chars.")
    parser.add_argument("--min_other_side_chars", dest="min_other_side_chars", type=int, default=200, help=argparse.SUPPRESS)
    parser.add_argument("--min-chars-to-escalate-short-missing", dest="min_chars_to_escalate_short_missing", type=int, default=120,
                        help="Skip escalating missing_content-only pages if they have some text but fewer than this many chars.")
    parser.add_argument("--min_chars_to_escalate_short_missing", dest="min_chars_to_escalate_short_missing", type=int, default=120, help=argparse.SUPPRESS)
    args = parser.parse_args()

    # Derive paths when called via driver with only --inputs
    if args.inputs and (not args.index or not args.quality or not args.images_dir or not args.outdir):
        # If input is a file, use its parent; if it's a directory, use it directly.
        # Infer the correct layout by checking for expected artifacts rather than relying on folder names.
        first = Path(args.inputs[0]).resolve()
        base = first.parent if first.is_file() else first

        # Layout A (driver-style):
        #   <base>/images/
        #   <base>/ocr_ensemble/pagelines_index.json
        ocr_dir_a = base / "ocr_ensemble"

        # Layout B (module outdir-style):
        #   <base>/images/
        #   <base>/ocr_ensemble/ocr_ensemble/pagelines_index.json
        ocr_dir_b = base / "ocr_ensemble" / "ocr_ensemble"

        # Layout C (already pointing at ocr_ensemble directory):
        #   <base>/pagelines_index.json
        ocr_dir_c = base
        base_c = base.parent

        if (ocr_dir_a / "pagelines_index.json").exists():
            base_dir = base
            ocr_dir = ocr_dir_a
            images_dir = base_dir / "images"
        elif (ocr_dir_b / "pagelines_index.json").exists():
            base_dir = base / "ocr_ensemble"
            ocr_dir = ocr_dir_b
            images_dir = base_dir / "images"
        elif (ocr_dir_c / "pagelines_index.json").exists():
            base_dir = base_c
            ocr_dir = ocr_dir_c
            images_dir = base_dir / "images"
        else:
            base_dir = base
            ocr_dir = ocr_dir_a
            images_dir = base_dir / "images"

        args.index = args.index or str(ocr_dir / "pagelines_index.json")
        args.quality = args.quality or str(ocr_dir / "ocr_quality_report.json")
        args.images_dir = args.images_dir or str(images_dir)
        args.outdir = args.outdir or str(base_dir / "ocr_ensemble_gpt4v")

    if not (args.index and args.quality and args.images_dir and args.outdir):
        raise SystemExit("index, quality, images-dir, and outdir are required (or infer via --inputs)")

    ensure_dir(args.outdir)
    prompt = read_prompt(args.prompt_file)

    index = load_index(args.index)
    quality = load_quality(args.quality)
    pages_cache: Dict[str, Dict[str, Any]] = {}

    # Select pages needing escalation
    # Use enhanced quality metrics: quality_score, corruption_score, or traditional disagreement_score
    candidates = []
    for q in quality:
        if not page_needs_escalation(q, threshold=args.threshold):
            continue
        q_page = q.get("page")
        if isinstance(q_page, int):
            page_key = str(q_page)
        else:
            page_key = str(q_page or "")
        reasons = page_escalation_reasons(q, threshold=args.threshold)
        ok, _skip_reason = should_escalate_page_key(
            page_key,
            reasons,
            index=index,
            pages_cache=pages_cache,
            min_other_side_chars=args.min_other_side_chars,
            min_chars_to_escalate_short_missing=args.min_chars_to_escalate_short_missing,
        )
        if ok:
            candidates.append(q)
    
    # Sort by quality_score (if available) or disagreement_score, prioritizing worst pages
    # Extract nested quality metrics for sorting
    candidates.sort(key=candidate_sort_key, reverse=True)
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
        # Quality report uses page_key (string like "001L"/"001R") or numeric page_number
        q_page = q.get("page")
        if isinstance(q_page, int):
            page_key = str(q_page)
        else:
            page_key = str(q_page or "")
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

        escalation_reasons = page_escalation_reasons(q, threshold=args.threshold)
        # Check if this page needs escalation (compare by page_key)
        would_escalate = any(str(c["page"]) == page_key for c in candidates)
        
        if would_escalate:
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
                    "prev_escalation_reasons": escalation_reasons,
                    "prev_quality": _extract_quality_subscores(q),
                }
                new_page["meta"] = meta_prev
                new_page["module_id"] = "ocr_escalate_gpt4v_v1"
                new_page["escalation_reasons"] = []
        else:
            new_page = page_data

        save_json(out_page_path, new_page)
        new_index[page_key] = out_page_path

        new_quality.append(update_quality_row(q, would_escalate=would_escalate, reasons=escalation_reasons, dry_run=args.dry_run))

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
            "escalated_pages_with_reasons": [
                {"page": c.get("page"), "reasons": page_escalation_reasons(c, threshold=args.threshold)}
                for c in candidates
            ],
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
