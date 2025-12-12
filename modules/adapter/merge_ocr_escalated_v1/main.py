#!/usr/bin/env python3
"""
Merge original OCR output with escalated pages into a single unified index.

This adapter combines:
- Original OCR pages from intake stage
- Escalated pages from ocr_escalate_gpt4v_v1

Output: Final OCR artifact in `pagelines_final/` directory:
- `pagelines_final/pagelines_index.json` - unified index (final OCR output)
- `pagelines_final/pages/*.json` - all pages (escalated if available, otherwise original)

This is the final, authoritative OCR output that downstream stages consume.
"""
import argparse
import json
import os
from pathlib import Path
from typing import Dict, List

from modules.common.utils import ensure_dir, save_json, save_jsonl, ProgressLogger


def load_index(index_path: str) -> Dict[str, str]:
    """Load pagelines index (keys are strings like "001L"/"001R")."""
    if not index_path or not os.path.exists(index_path):
        return {}
    data = json.load(open(index_path, "r", encoding="utf-8"))
    return {str(k): v for k, v in data.items()}


def main():
    parser = argparse.ArgumentParser(description="Merge original OCR + escalated pages into unified index")
    parser.add_argument("--original-index", help="Original pagelines_index.json from intake")
    parser.add_argument("--escalated-index", help="Escalated pagelines_index.json from ocr_escalate_gpt4v_v1")
    parser.add_argument("--inputs", nargs="*", help="Driver-provided inputs: [intake, escalate_vision]")
    parser.add_argument("--outdir", help="Output directory (main run directory)")
    parser.add_argument("--out", help="Optional adapter_out.jsonl path for driver stamping")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    
    # Derive paths from driver inputs if not explicitly provided
    if args.inputs and len(args.inputs) >= 2:
        intake_input = Path(args.inputs[0]).resolve()  # pages_raw.jsonl from intake
        escalate_input = Path(args.inputs[1]).resolve()  # adapter_out.jsonl from escalate_vision
        
        # Determine run directory from intake input
        run_dir = intake_input.parent if intake_input.is_file() else intake_input
        if run_dir.name in {"ocr_ensemble"}:
            run_dir = run_dir.parent
        
        # Escalate input: should be adapter_out.jsonl with index path
        escalated_index_path = None
        if escalate_input.is_file() and escalate_input.name == "adapter_out.jsonl":
            try:
                with escalate_input.open() as f:
                    first_line = f.readline().strip()
                    if first_line:
                        escalate_summary = json.loads(first_line)
                        escalated_index_path = escalate_summary.get("index")
                        # If path is relative, make it absolute relative to run_dir
                        if escalated_index_path and not os.path.isabs(escalated_index_path):
                            escalated_index_path = os.path.join(run_dir, escalated_index_path)
            except (json.JSONDecodeError, ValueError):
                # If adapter_out.jsonl is empty or malformed, fall back to default path
                pass
        
        if not args.original_index:
            args.original_index = os.path.join(run_dir, "ocr_ensemble", "pagelines_index.json")
        if not args.escalated_index:
            if escalated_index_path:
                args.escalated_index = escalated_index_path
            else:
                args.escalated_index = os.path.join(run_dir, "ocr_ensemble_gpt4v", "pagelines_index.json")
        if not args.outdir:
            args.outdir = str(run_dir)
        # Ensure outdir is absolute and normalized
        args.outdir = os.path.abspath(args.outdir)
    
    if not args.original_index or not args.outdir:
        raise SystemExit("original-index and outdir are required (or infer via --inputs)")

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    
    # Load both indices
    original_index = load_index(args.original_index)
    escalated_index = load_index(args.escalated_index)
    
    # Merge: escalated pages override original, others kept from original
    # Strategy: Build final index with escalated pages taking precedence
    # Note: Escalation module writes ALL pages (both escalated and non-escalated),
    # so we need to check module_id to find which were actually escalated
    escalated_pages = []
    
    # Identify which pages were actually escalated (check module_id in escalated pages)
    for page_key, escalated_path in escalated_index.items():
        if page_key in original_index and os.path.exists(escalated_path):
            try:
                with open(escalated_path, "r", encoding="utf-8") as f:
                    page_data = json.load(f)
                if page_data.get("module_id") == "ocr_escalate_gpt4v_v1":
                    escalated_pages.append(page_key)
            except Exception:
                # If we can't read the file, assume it wasn't escalated
                pass
    
    # Write merged index to pagelines_final/ subdirectory (final OCR output)
    merged_dir = os.path.join(args.outdir, "pagelines_final")
    ensure_dir(merged_dir)
    pages_dir = os.path.join(merged_dir, "pages")
    ensure_dir(pages_dir)
    
    # Copy pages to merged directory, ensuring escalated pages take precedence
    # Track which files we've copied to avoid duplicates
    import shutil
    final_merged_index = {}
    copied_files = set()  # Track filenames we've already copied
    
    # First pass: Copy escalated pages (these take precedence over originals)
    # Only copy pages that were actually escalated (module_id == "ocr_escalate_gpt4v_v1")
    for page_key, escalated_path in escalated_index.items():
        if page_key in escalated_pages:  # Only copy if actually escalated
            filename = os.path.basename(escalated_path)
            dst_path = os.path.join(pages_dir, filename)
            if os.path.exists(escalated_path):
                # Only copy if source and destination are different
                if os.path.abspath(escalated_path) != os.path.abspath(dst_path):
                    # Always overwrite for escalated pages (they take precedence)
                    shutil.copy2(escalated_path, dst_path)
                    copied_files.add(filename)
                final_merged_index[page_key] = dst_path
    
    # Second pass: Copy original pages that weren't escalated
    for page_key, original_path in original_index.items():
        if page_key not in escalated_pages:  # Only copy if not escalated
            filename = os.path.basename(original_path)
            dst_path = os.path.join(pages_dir, filename)
            if os.path.exists(original_path):
                # Only copy if we haven't already copied a file with this name
                if filename not in copied_files:
                    shutil.copy2(original_path, dst_path)
                    copied_files.add(filename)
                final_merged_index[page_key] = dst_path
    
    # Save index for auditing (intermediate artifact)
    merged_index_path = os.path.join(merged_dir, "pagelines_index.json")
    save_json(merged_index_path, {k: v for k, v in sorted(final_merged_index.items())})
    
    # Load all pages and create unified JSONL file (final artifact)
    # Clean up line data to only include canonical text (remove raw/fused/post)
    page_rows = []
    for page_key in sorted(final_merged_index.keys()):
        page_path = final_merged_index[page_key]
        if os.path.exists(page_path):
            with open(page_path, "r", encoding="utf-8") as f:
                page_data = json.load(f)
            
            # Clean up lines: keep canonical text/source and preserve bbox/meta when present.
            # All alternatives remain in engines_raw for provenance.
            cleaned_lines = []
            for line in page_data.get("lines", []):
                cleaned_line = {
                    "text": line.get("text", ""),
                    "source": line.get("source", "unknown"),
                }
                bbox = line.get("bbox")
                if isinstance(bbox, list) and len(bbox) >= 4:
                    cleaned_line["bbox"] = bbox[:4]
                meta = line.get("meta")
                if isinstance(meta, dict) and meta:
                    cleaned_line["meta"] = meta
                cleaned_lines.append(cleaned_line)
            
            # Create cleaned page data
            cleaned_page = page_data.copy()
            cleaned_page["lines"] = cleaned_lines
            page_rows.append(cleaned_page)
    
    # Write final unified artifact to root run directory
    # Use the same path resolution as the driver (respect symlinks)
    final_artifact_path = os.path.join(args.outdir, "pagelines_final.jsonl")
    # Ensure parent directory exists
    ensure_dir(os.path.dirname(final_artifact_path) or ".")
    save_jsonl(final_artifact_path, page_rows)
    
    total_pages = len(final_merged_index)
    logger.log("adapter", "done", current=total_pages, total=total_pages,
               message=f"Merged {len(escalated_pages)} escalated pages into {total_pages} total",
               artifact=final_artifact_path, module_id="merge_ocr_escalated_v1")
    
    if args.out:
        summary = {
            "schema_version": "adapter_out",
            "module_id": "merge_ocr_escalated_v1",
            "run_id": args.run_id,
            "created_at": None,
            "pagelines_final": final_artifact_path,  # Final unified artifact
            "index": merged_index_path,  # Intermediate index (for auditing)
            "total_pages": total_pages,
            "escalated_pages": len(escalated_pages),
            "escalated_page_keys": escalated_pages,
        }
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(json.dumps(summary) + "\n")
        print(f"Adapter summary → {args.out}")
    
    print(f"Merged {len(escalated_pages)} escalated pages into {total_pages} total pages")
    print(f"Final artifact: {final_artifact_path}")
    print(f"Index (audit): {merged_index_path}")


if __name__ == "__main__":
    main()
