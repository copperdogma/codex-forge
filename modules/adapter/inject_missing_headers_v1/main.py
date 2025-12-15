#!/usr/bin/env python3
"""
Missing Header Injection Module v1

Post-processes OCR ensemble picked output to inject missing numeric headers (section numbers)
from raw OCR engine outputs. Critical for 100% section coverage in game engine outputs.

Strategy:
1. Scan raw OCR engines (tesseract, easyocr, apple) for numeric-only lines (1-3 digits)
2. Check if those numbers exist in picked output
3. Inject missing numbers at appropriate positions
4. Preserve existing lines and metadata
"""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Optional
from collections import defaultdict

from modules.common.utils import ensure_dir, save_json, ProgressLogger


def is_numeric_header(text: str, min_val: int = 1, max_val: int = 400) -> Optional[int]:
    """Check if text is a numeric-only header (1-3 digits)."""
    if not text:
        return None
    stripped = text.strip()
    match = re.match(r'^(\d{1,3})$', stripped)
    if match:
        num = int(match.group(1))
        if min_val <= num <= max_val:
            return num
    return None


def scan_raw_engines_for_numbers(page_dir: Path, min_val: int, max_val: int) -> Set[int]:
    """Scan raw OCR engine outputs for numeric headers."""
    numbers = set()
    
    for engine in ['apple', 'easyocr', 'tesseract']:
        engine_file = page_dir / f"{engine}.txt"
        if not engine_file.exists():
            continue
        
        try:
            with open(engine_file, 'r', encoding='utf-8') as f:
                for line in f:
                    num = is_numeric_header(line, min_val, max_val)
                    if num is not None:
                        numbers.add(num)
        except Exception as e:
            print(f"Warning: Could not read {engine_file}: {e}")
    
    return numbers


def get_numbers_in_picked(lines: List[Dict]) -> Set[int]:
    """Get all numeric headers already in picked output."""
    numbers = set()
    for line in lines:
        text = line.get('text', '')
        num = is_numeric_header(text)
        if num is not None:
            numbers.add(num)
    return numbers


def inject_missing_numbers(page_data: Dict, missing_numbers: Set[int], page_num: int) -> Dict:
    """Inject missing numeric headers into page data."""
    if not missing_numbers:
        return page_data
    
    lines = page_data.get('lines', [])
    
    # Create new lines for missing numbers
    # Insert them at the end (they'll be sorted/positioned by downstream logic)
    for num in sorted(missing_numbers):
        new_line = {
            'text': str(num),
            'bbox': None,  # No bbox available
            'conf': 0.9,  # High confidence - we know it's in raw OCR
            'source': 'injected',  # Mark as injected for debugging
            'injected_reason': f'Found in raw OCR engines but missing from picked output'
        }
        lines.append(new_line)
    
    page_data['lines'] = lines
    return page_data


def main():
    parser = argparse.ArgumentParser(description='Inject missing numeric headers from raw OCR')
    parser.add_argument('--inputs', nargs='*', help='Driver-provided inputs (for run_dir inference)')
    parser.add_argument('--index', help='Input pagelines_index.json (defaults to run_dir/ocr_ensemble_picked/pagelines_index.json)')
    parser.add_argument('--outdir', help='Output directory (defaults to run_dir/ocr_ensemble_injected)')
    parser.add_argument('--out', required=True, help='Output pagelines_v1 JSONL (pass-through)')
    parser.add_argument('--min_value', '--min-value', type=int, default=1, dest='min_value', help='Minimum section number')
    parser.add_argument('--max_value', '--max-value', type=int, default=400, dest='max_value', help='Maximum section number')
    parser.add_argument('--run-id', '--run_id', dest='run_id', help='Run ID for logging')
    args = parser.parse_args()
    
    logger = ProgressLogger()
    
    # Infer run directory from inputs or output path
    import re
    run_dir = None
    if args.inputs:
        for inp in args.inputs:
            p = Path(inp).resolve()
            if p.exists():
                # If input is in a module folder (XX_module_name/), go up to run_dir
                # Otherwise, if it contains 'runs/', extract run_dir from that
                if 'runs/' in str(p):
                    parts = str(p).split('runs/')
                    if len(parts) >= 2:
                        run_id_part = parts[1].split('/')[0]
                        run_dir = Path(parts[0]) / 'runs' / run_id_part
                        break
                else:
                    # Try to find run_dir by going up from module folder
                    # Path like /tmp/cf-verify/03_module/file.jsonl -> /tmp/cf-verify
                    current = p.parent
                    # Go up until we find a directory that doesn't match module folder pattern
                    while current != current.parent:
                        if not re.match(r'^\d{2}_', current.name):
                            run_dir = current
                            break
                        current = current.parent
    
    if not run_dir or not run_dir.exists():
        raise ValueError(f"Could not infer run directory from inputs: {args.inputs}")
    
    # Determine paths
    if args.index:
        index_file = Path(args.index)
    else:
        index_file = run_dir / 'ocr_ensemble_picked' / 'pagelines_index.json'
    
    if not index_file.exists():
        raise FileNotFoundError(f"Index file not found: {index_file}")
    
    with open(index_file, 'r') as f:
        input_index = json.load(f)
    
    # Output directory
    if args.outdir:
        output_dir = Path(args.outdir)
    else:
        output_dir = run_dir / 'ocr_ensemble_injected' / 'pages'
    ensure_dir(output_dir)
    
    # OCR engines directory - look in intake module folder (01_extract_ocr_ensemble_v1/)
    # Note: This directory is optional (only exists if write_engine_dumps was enabled)
    ocr_engines_dir = None
    # Try to find intake module folder by looking for numbered module folders starting with 01_
    if run_dir and run_dir.exists():
        for item in run_dir.iterdir():
            if item.is_dir() and item.name.startswith('01_') and 'extract' in item.name.lower():
                candidate = item / 'ocr_ensemble' / 'ocr_engines'
                if candidate.exists():
                    ocr_engines_dir = candidate
                    break
    # Fallback to old location
    if not ocr_engines_dir:
        fallback_dir = run_dir / 'ocr_ensemble' / 'ocr_engines'
        if fallback_dir.exists():
            ocr_engines_dir = fallback_dir
    # If directory doesn't exist, that's OK - module will skip pages without engine subdirectories
    
    output_index = {}
    total_injected = 0
    injection_log = []
    
    total_pages = len(input_index)
    
    picked_pages_dir = index_file.parent / 'pages'
    
    for i, (page_key, page_path_str) in enumerate(sorted(input_index.items())):
        page_path = Path(page_path_str)
        
        # Load page data - handle both absolute and relative paths
        if not page_path.exists():
            # Try relative to picked pages directory
            page_path = picked_pages_dir / page_path.name
        
        if not page_path.exists():
            print(f"Warning: Page file not found: {page_path}")
            continue
        
        with open(page_path, 'r') as f:
            page_data = json.load(f)
        
        page_num = page_data.get('page', 0)
        
        # Scan raw engines for numeric headers (only if ocr_engines_dir exists)
        if ocr_engines_dir:
            page_dir = ocr_engines_dir / page_key
            if page_dir.exists():
                raw_numbers = scan_raw_engines_for_numbers(page_dir, args.min_value, args.max_value)
            else:
                # Page may not have engine subdirectory - skip header injection for this page
                raw_numbers = set()
        else:
            # ocr_engines_dir doesn't exist (write_engine_dumps was disabled) - skip header injection
            raw_numbers = set()
        
        if not raw_numbers:
            # No raw engine data available - pass through unchanged
            output_index[page_key] = str(page_path)
            continue
        picked_numbers = get_numbers_in_picked(page_data.get('lines', []))
        
        missing_numbers = raw_numbers - picked_numbers
        
        if missing_numbers:
            # Inject missing numbers
            page_data = inject_missing_numbers(page_data, missing_numbers, page_num)
            total_injected += len(missing_numbers)
            
            injection_log.append({
                'page': page_num,
                'page_key': page_key,
                'injected_numbers': sorted(list(missing_numbers)),
                'count': len(missing_numbers)
            })
            
            print(f"Page {page_key}: Injected {len(missing_numbers)} missing headers: {sorted(missing_numbers)}")
        
        # Write output page
        output_page_path = output_dir / f"{page_key}.json"
        save_json(output_page_path, page_data)
        output_index[page_key] = str(output_page_path)
        
        logger.log(
            "inject_missing_headers",
            "running",
            current=i + 1,
            total=total_pages,
            message=f"Page {page_key} ({len(missing_numbers)} injected)",
            artifact=args.out,
            module_id="inject_missing_headers_v1",
            schema_version="page_raw_v1"
        )
    
    # Write output index
    index_out_path = output_dir.parent / 'pagelines_index.json'
    save_json(index_out_path, output_index)
    
    # Write injection log
    log_path = output_dir.parent / 'header_injection_log.json'
    save_json(log_path, {
        'total_injected': total_injected,
        'pages_modified': len(injection_log),
        'injections': injection_log
    })
    
    # Write pass-through JSONL (empty for now, as pages are in separate files)
    # The driver expects this file to exist
    with open(args.out, 'w') as f:
        f.write('')
    
    logger.log(
        "inject_missing_headers",
        "done",
        current=total_pages,
        total=total_pages,
        message=f"Injected {total_injected} missing headers across {len(injection_log)} pages",
        artifact=args.out,
        module_id="inject_missing_headers_v1",
        schema_version="page_raw_v1"
    )
    
    print(f"\n=== Header Injection Summary ===")
    print(f"Total headers injected: {total_injected}")
    print(f"Pages modified: {len(injection_log)}")
    print(f"Output index: {index_out_path}")
    print(f"Injection log: {log_path}")
    
    if injection_log:
        print(f"\nInjected headers by page:")
        for entry in injection_log[:10]:  # Show first 10
            print(f"  Page {entry['page_key']}: {entry['injected_numbers']}")
        if len(injection_log) > 10:
            print(f"  ... and {len(injection_log) - 10} more pages")


if __name__ == '__main__':
    main()

