#!/usr/bin/env python3
"""
Convert pagelines_v1 (BetterOCR/vision ensemble) into elements.jsonl + elements_core.jsonl.
Each line becomes a text element with basic metadata; preserves page numbers and order.
Column-aware sorting: lines are clustered by x-centers to keep multi-column pages in logical order.

Expects page keys in "001L"/"001R" format (spread pages with L/R suffixes).
Extracts numeric page number from these keys for metadata.
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict, Optional

from modules.common.utils import ensure_dir, save_jsonl, read_jsonl, ProgressLogger
from datetime import datetime, timezone
from schemas import UnstructuredElement, ElementCore, CodexMetadata, ElementLayout


def load_index(index_path: str) -> Dict[str, str]:
    """
    Load pagelines index. Keys are strings in "001L"/"001R" format (spread pages).
    Returns dict with string keys.
    """
    data = json.load(open(index_path, "r", encoding="utf-8"))
    return {str(k): v for k, v in data.items()}


def extract_page_number(page_key: str) -> int:
    """
    Extract numeric page number from page key in "001L"/"001R" format.
    Assumes format: zero-padded 3-digit number followed by "L" or "R".
    Example: "001L" -> 1, "042R" -> 42
    """
    # Remove trailing L/R suffix
    if page_key.endswith("L") or page_key.endswith("R"):
        page_key = page_key[:-1]
    # Remove leading zeros and convert to int
    return int(page_key.lstrip("0") or "0")


def cluster_columns(lines: List[Dict], gap: float = 0.12, min_per_col: int = 4) -> Dict[int, int]:
    """
    Heuristic column clustering:
    - if spread in x-centers > 0.2, run 2-means on x-centers and assign cols.
    - else fall back to largest-gap split.
    Returns mapping line_idx -> column_idx (0 or 1). Defaults to single column if confidence low.
    """
    centers = []
    for i, ln in enumerate(lines):
        bbox = ln.get("bbox")
        if not bbox or len(bbox) < 4:
            continue
        x_center = (bbox[0] + bbox[2]) / 2.0
        centers.append((i, x_center))
    if not centers:
        return {}
    centers.sort(key=lambda x: x[1])
    xs = [c for _, c in centers]
    spread = max(xs) - min(xs)
    # k-means with k=2 when spread is large
    if spread > 0.2 and len(xs) >= 2:
        c1, c2 = min(xs), max(xs)
        for _ in range(5):
            left = [c for c in xs if abs(c - c1) <= abs(c - c2)]
            right = [c for c in xs if abs(c - c2) < abs(c - c1)]
            if left:
                c1 = sum(left) / len(left)
            if right:
                c2 = sum(right) / len(right)
        left_ids = [idx for idx, c in centers if abs(c - c1) <= abs(c - c2)]
        right_ids = [idx for idx, c in centers if abs(c - c2) < abs(c - c1)]
        if len(left_ids) >= min_per_col and len(right_ids) >= min_per_col:
            col_assign = {idx: 0 for idx in left_ids}
            col_assign.update({idx: 1 for idx in right_ids})
            return col_assign
    # fallback: largest gap
    gaps = []
    for a, b in zip(centers, centers[1:]):
        gaps.append((b[1] - a[1], a, b))
    if gaps:
        max_gap, left, right = max(gaps, key=lambda g: g[0])
        if max_gap >= gap:
            split_at = right[1]
            left_ids = [idx for idx, c in centers if c < split_at]
            right_ids = [idx for idx, c in centers if c >= split_at]
            if len(left_ids) >= min_per_col and len(right_ids) >= min_per_col:
                col_assign = {idx: 0 for idx in left_ids}
                col_assign.update({idx: 1 for idx in right_ids})
                return col_assign
    return {idx: 0 for idx, _ in centers}


def sort_lines_preserving_columns(lines: List[Dict]) -> List[Dict]:
    """
    Sort lines by detected column (left→right) then top→bottom within each column.
    Falls back to original order if no bbox is present.
    """
    if not lines:
        return lines
    col_assign = cluster_columns(lines)
    if not col_assign:
        return lines

    def key_fn(item_tuple):
        idx, ln = item_tuple
        bbox = ln.get("bbox") or [0, 0, 0, 0]
        y_top = bbox[1]
        col = col_assign.get(idx, 0)
        return (col, y_top)

    sorted_items = sorted(list(enumerate(lines)), key=key_fn)
    return [ln for _, ln in sorted_items]


def main():
    parser = argparse.ArgumentParser(description="Pagelines → elements.jsonl + elements_core.jsonl")
    parser.add_argument("--index", help="pagelines_index.json (from extract_ocr_ensemble/ocr_escalate_gpt4v)")
    parser.add_argument("--out", required=False, help="elements_core.jsonl output path (primary artifact)")
    parser.add_argument("--out-core", dest="out_core", help=argparse.SUPPRESS)  # deprecated; still accepted
    parser.add_argument("--inputs", nargs="*", help="Optional driver-provided inputs (use first to infer paths)")
    parser.add_argument("--pages", help=argparse.SUPPRESS)
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    parser.add_argument("--columns-debug", dest="columns_debug", default=None,
                        help="Optional JSONL debug output with per-page column stats")
    parser.add_argument("--columns_debug", dest="columns_debug", default=None, help=argparse.SUPPRESS)
    # accept unused pass-through flags from driver
    parser.add_argument("--pdf", help=argparse.SUPPRESS)
    parser.add_argument("--outdir", help=argparse.SUPPRESS)
    args, _ = parser.parse_known_args()

    # If driver passed pages via hidden flag
    if args.pages and not args.inputs:
        args.inputs = [args.pages]

    if args.inputs and not args.index:
        first = Path(args.inputs[0]).resolve()
        # If adapter_out.jsonl provided, check for pagelines_final.jsonl first
        if first.is_file() and first.name == "adapter_out.jsonl":
            with first.open() as f:
                line = f.readline().strip()
                if line:
                    try:
                        obj = json.loads(line)
                        # Prefer pagelines_final.jsonl (unified artifact) over index
                        final_artifact = obj.get("pagelines_final")
                        if final_artifact:
                            # Resolve path (handle symlinks like /tmp -> /private/tmp)
                            if not os.path.exists(final_artifact):
                                # Try resolving through parent directory (handle symlinks)
                                base_dir = first.parent
                                candidate = base_dir / "pagelines_final.jsonl"
                                if candidate.exists():
                                    final_artifact = str(candidate)
                                else:
                                    # Try using realpath to resolve symlinks
                                    try:
                                        real_base = os.path.realpath(str(base_dir))
                                        real_candidate = os.path.join(real_base, "pagelines_final.jsonl")
                                        if os.path.exists(real_candidate):
                                            final_artifact = real_candidate
                                    except Exception:
                                        pass
                            if os.path.exists(final_artifact):
                                # Use the unified JSONL file directly
                                args.inputs = [final_artifact]
                                args.index = None  # Will be handled by JSONL reading below
                        else:
                            idx = obj.get("index")
                            if idx:
                                args.index = idx
                    except Exception:
                        pass
        if not args.index:
            base = first
            if base.is_file():
                base = base.parent
            # Check for pagelines_reconstructed.jsonl first (preferred), then pagelines_final.jsonl
            reconstructed_jsonl = base / "pagelines_reconstructed.jsonl"
            final_jsonl = base / "pagelines_final.jsonl"
            if reconstructed_jsonl.exists():
                args.inputs = [str(reconstructed_jsonl)]
                args.index = None
            elif final_jsonl.exists():
                args.inputs = [str(final_jsonl)]
                args.index = None
            # Also check in outdir if provided
            elif args.outdir:
                outdir_reconstructed = Path(args.outdir) / "pagelines_reconstructed.jsonl"
                outdir_jsonl = Path(args.outdir) / "pagelines_final.jsonl"
                if outdir_reconstructed.exists():
                    args.inputs = [str(outdir_reconstructed)]
                    args.index = None
                elif outdir_jsonl.exists():
                    args.inputs = [str(outdir_jsonl)]
                    args.index = None
            elif base.name in {"ocr_ensemble", "ocr_ensemble_gpt4v", "pagelines_final"}:
                candidate = base / "pagelines_index.json"
                if candidate.exists():
                    args.index = str(candidate)
            else:
                # Check final directory, then escalated, then original
                candidate = base / "pagelines_final" / "pagelines_index.json"
                if not candidate.exists():
                    candidate = base / "ocr_ensemble_gpt4v" / "pagelines_index.json"
                if not candidate.exists():
                    candidate = base / "ocr_ensemble" / "pagelines_index.json"
                if candidate.exists():
                    args.index = str(candidate)
        if not args.index and not (args.inputs and any(i.endswith('.jsonl') for i in args.inputs)):
            # Last resort: check outdir if provided
            if args.outdir:
                reconstructed_jsonl = Path(args.outdir) / "pagelines_reconstructed.jsonl"
                final_jsonl = Path(args.outdir) / "pagelines_final.jsonl"
                if reconstructed_jsonl.exists():
                    args.inputs = [str(reconstructed_jsonl)]
                    args.index = None
                elif final_jsonl.exists():
                    args.inputs = [str(final_jsonl)]
                    args.index = None
                else:
                    candidate = Path(args.outdir) / "ocr_ensemble" / "pagelines_index.json"
                    if candidate.exists():
                        args.index = str(candidate)
            if not args.index and not (args.inputs and any(i.endswith('.jsonl') for i in args.inputs)):
                raise SystemExit("pagelines_to_elements_v1: could not infer pagelines_index.json or pagelines_final.jsonl from inputs/outdir")
        if not args.out:
            if args.outdir:
                args.out = str(Path(args.outdir) / "elements_core.jsonl")
            else:
                # Default to current directory only if explicitly in a run directory
                # Otherwise, require explicit --out to avoid polluting repo root
                cwd = Path.cwd()
                if cwd.name.startswith("cf-") or "runs" in str(cwd):
                    args.out = str(cwd / "elements_core.jsonl")
                else:
                    raise SystemExit("pagelines_to_elements_v1: --out required when not in run directory and --outdir not provided")

    if not args.index and not (args.inputs and any(i.endswith('.jsonl') for i in args.inputs)):
        raise SystemExit("index or pagelines_final.jsonl input is required (or infer via --inputs)")
    if not args.out:
        raise SystemExit("out (elements_core) is required")

    # Resolve index relative to outdir if path not found
    if args.outdir and args.index and not Path(args.index).exists():
        candidate = Path(args.outdir) / args.index
        if candidate.exists():
            args.index = str(candidate)

    out_core = args.out  # elements_core primary
    if args.outdir and out_core and not Path(out_core).is_absolute():
        out_core = str(Path(args.outdir) / out_core)
    out_elements = args.out_core or str(Path(out_core).with_name("elements.jsonl"))
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    # Check if input is a JSONL file (unified artifact) or index file
    if args.inputs and any(i.endswith('.jsonl') for i in args.inputs):
        # Find the JSONL file
        jsonl_file = next(i for i in args.inputs if i.endswith('.jsonl'))
        # Read directly from JSONL file (unified artifact)
        page_rows = list(read_jsonl(jsonl_file))
        # Create a temporary index-like structure for compatibility
        index = {}
        for i, page_data in enumerate(page_rows):
            page_key = f"{page_data.get('page', i+1):03d}"
            if page_data.get('spread_side'):
                page_key += page_data['spread_side']
            # Use a placeholder path since we already have the data
            index[page_key] = f"__jsonl_row_{i}__"
        pages_data = {f"__jsonl_row_{i}__": page_data for i, page_data in enumerate(page_rows)}
    elif args.index:
        # Load from index file (traditional path)
        index = load_index(args.index)
        pages_data = {}
    else:
        raise SystemExit("Must provide either pagelines_final.jsonl input or index file")
    
    elements: List[Dict] = []
    elements_core: List[Dict] = []
    seq_global = 0
    debug_rows = []

    total_pages = len(index)
    logger.log("intake", "running", current=0, total=total_pages,
               message="Converting pagelines → elements", module_id="pagelines_to_elements_v1", artifact=out_core,
               schema_version="element_core_v1")

    # Sort by numeric page number (extract from "001L"/"001R" format)
    def sort_key(kv):
        page_key = kv[0]
        return extract_page_number(page_key)
    
    for page_key, path in sorted(index.items(), key=sort_key):
        # Check if we're reading from JSONL (unified artifact) or individual files
        if path.startswith("__jsonl_row_"):
            # Reading from unified JSONL artifact
            data = pages_data[path]
        else:
            # Reading from individual page files (traditional path)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        lines = data.get("lines", [])
        lines = sort_lines_preserving_columns(lines)
        
        # Extract numeric page number for metadata
        page_num = extract_page_number(page_key)
        
        # debug column stats
        if args.columns_debug:
            col_assign = cluster_columns(lines)
            num_cols = 1 if not col_assign else max(col_assign.values()) + 1
            debug_rows.append({
                "page": page_key,  # Keep original key for debug
                "num_columns": num_cols,
                "line_count": len(lines),
                "sample_first_lines": [ln.get("text", "") for ln in lines[:5]],
            })
        seq_page = 0
        # Note: bbox data is not currently preserved in line_rows from OCR ensemble
        # Layout extraction would require OCR module to preserve bbox in line data
        # For now, layout remains None - this can be enhanced later if needed
        
        for line in lines:
            text = (line.get("text") or "").rstrip()
            if text == "":
                continue
            
            # Extract layout information from bbox if available
            # Currently bbox is not in line data, so layout will be None
            # TODO: Enhance OCR module to preserve bbox in line_rows for layout extraction
            layout = None
            bbox = line.get("bbox")
            if bbox and len(bbox) >= 4:
                x0, y0, x1, y1 = bbox[0], bbox[1], bbox[2], bbox[3]
                # Normalized y position (top of line, 0=top, 1=bottom)
                y_pos = y0  # Assume already normalized 0-1
                
                # Determine horizontal alignment
                # For normalized bbox, center is at 0.5
                x_center = (x0 + x1) / 2.0
                if x_center < 0.35:
                    h_align = "left"
                elif x_center > 0.65:
                    h_align = "right"
                elif 0.4 <= x_center <= 0.6:
                    h_align = "center"
                else:
                    h_align = "unknown"
                
                layout = ElementLayout(h_align=h_align, y=y_pos)
            
            codex = CodexMetadata(
                run_id=args.run_id or os.environ.get("RUN_ID"),
                module_id="pagelines_to_elements_v1",
                sequence=seq_global,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            meta = {"page_number": page_num}  # Use extracted numeric page number
            if "source" in line:
                meta["source"] = line.get("source")
            # Element ID uses page_key (preserves L/R suffix for spread pages)
            elem_id = f"{page_key}-{seq_page:04d}"
            elem = UnstructuredElement(
                id=elem_id,
                type="NarrativeText",
                text=text,
                metadata=meta,
                codex=codex,
            )
            elements.append(elem.model_dump(by_alias=True))
            core = ElementCore(
                id=elem.id,
                seq=seq_global,
                page=page_num,  # Use extracted numeric page number
                kind="text",
                text=text,
                layout=layout.model_dump() if layout else None,
            )
            elements_core.append(core.model_dump())
            seq_page += 1
            seq_global += 1
        logger.log("intake", "running", current=page_num, total=total_pages,
                   message=f"page {page_key}", module_id="pagelines_to_elements_v1",
                   artifact=out_core, schema_version="element_core_v1")

    # Ensure output directories exist (create parent directories)
    ensure_dir(os.path.dirname(out_elements) or ".")
    ensure_dir(os.path.dirname(out_core) or ".")
    save_jsonl(out_elements, elements)
    save_jsonl(out_core, elements_core)
    if args.columns_debug:
        # Ensure columns_debug directory exists
        ensure_dir(os.path.dirname(args.columns_debug) or ".")
        save_jsonl(args.columns_debug, debug_rows)
    logger.log("intake", "done", current=total_pages, total=total_pages,
               message=f"Converted {len(elements)} elements", module_id="pagelines_to_elements_v1",
               artifact=out_core, schema_version="element_core_v1")
    print(f"Wrote {len(elements)} elements → {out_elements}\nCore: {out_core}")


if __name__ == "__main__":
    main()
