#!/usr/bin/env python3
"""
IR Reduction Module v1

Reduces Unstructured's verbose IR to a minimal internal schema for all AI operations.
Maps element types to simple categories, extracts layout hints, and normalizes text.
"""

import argparse
import re
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from modules.common.utils import read_jsonl, save_jsonl, ensure_dir, ProgressLogger
from schemas import UnstructuredElement, ElementCore, ElementLayout


def map_element_type_to_kind(element_type: str) -> str:
    """
    Map Unstructured element types to simple kind categories.
    
    Returns: "text" | "image" | "table" | "other"
    """
    element_type_lower = element_type.lower() if element_type else ""
    
    # Image types
    if "image" in element_type_lower or element_type_lower == "figure":
        return "image"
    
    # Table types
    if "table" in element_type_lower:
        return "table"
    
    # Text types (most common)
    text_types = ["title", "narrativetext", "text", "listitem", "header", "footer", 
                  "figurecaption", "pagebreak", "unknown"]
    if any(text_type in element_type_lower for text_type in text_types):
        return "text"
    
    # Default to "other" for truly unknown types
    return "other"


def extract_layout_info(metadata: Dict[str, Any]) -> Optional[ElementLayout]:
    """
    Extract layout hints from Unstructured metadata.
    
    Returns ElementLayout with h_align and y position, or None if unavailable.
    """
    h_align = "unknown"
    y_pos = None
    
    # Try to extract horizontal alignment from coordinates
    coords = metadata.get("coordinates")
    if coords and isinstance(coords, dict):
        points = coords.get("points", [])
        if points and len(points) >= 2:
            # Calculate bounding box
            xs = [p[0] for p in points if len(p) >= 1]
            if xs:
                min_x = min(xs)
                max_x = max(xs)
                width = max_x - min_x
                
                # Estimate page width (assume ~600-800px typical)
                # If element is centered (within 20% margin), mark as center
                # This is heuristic - can be improved with actual page dimensions
                center_threshold = 0.2  # 20% margin
                if width > 0:
                    # Very rough heuristic: if element spans middle region, likely centered
                    # For now, default to "unknown" - can enhance with page width metadata
                    pass
    
    # Try to extract vertical position (normalized 0-1)
    # This requires page dimensions - for now, we'll skip y calculation
    # unless page height is available in metadata
    
    # Only return layout if we have meaningful data
    if h_align != "unknown" or y_pos is not None:
        return ElementLayout(h_align=h_align, y=y_pos)
    
    return None


def normalize_text(text: str) -> str:
    """
    Normalize text: trim whitespace, normalize line breaks.
    
    Per spec: Do not alter text beyond:
    - Normalizing line breaks (\n → \n or spaces)
    - Trimming leading/trailing whitespace
    """
    if not text:
        return ""
    
    # Normalize line breaks: convert \r\n to \n, preserve single \n
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    
    # Trim leading/trailing whitespace
    text = text.strip()
    
    return text


def reduce_element(unstructured_elem: Dict[str, Any], seq: int, 
                   run_id: Optional[str], module_id: str) -> ElementCore:
    """
    Reduce a single Unstructured element to minimal ElementCore schema.
    """
    # Parse UnstructuredElement schema (supports both 'codex' and '_codex')
    elem = UnstructuredElement(**unstructured_elem)
    
    # Extract page number from metadata
    page_num = elem.metadata.get("page_number")
    if page_num is None:
        # Fallback: try to extract from _codex or other sources
        # Default to 1 if not available
        page_num = 1
    
    # Map element type to kind
    kind = map_element_type_to_kind(elem.type)
    
    # Normalize text
    normalized_text = normalize_text(elem.text)
    
    # Extract layout info
    layout = extract_layout_info(elem.metadata)
    
    # Filter out empty elements (no text content)
    if not normalized_text.strip():
        return None  # Skip empty elements
    
    # Create ElementCore with minimal schema (no metadata fields)
    # Per spec: just {id, seq, page, kind, text, layout}
    # Metadata (schema_version, module_id, run_id, created_at) stripped to reduce AI workload
    core = ElementCore(
        id=elem.id,
        seq=seq,  # Preserve original seq number (may have gaps if empty elements filtered)
        page=int(page_num),
        kind=kind,
        text=normalized_text,
        layout=layout,
    )
    
    return core


def main():
    parser = argparse.ArgumentParser(
        description="Reduce Unstructured IR to minimal internal schema (elements_core.jsonl)"
    )
    parser.add_argument("--elements", required=False,
                       help="Input elements.jsonl (Unstructured format)")
    parser.add_argument("--pages", required=False,
                       help="Alias for --elements (driver compatibility)")
    parser.add_argument("--input", required=False,
                       help="Alias for --elements (driver compatibility)")
    parser.add_argument("--out", required=True,
                       help="Output elements_core.jsonl path")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()
    
    logger = ProgressLogger(
        state_path=args.state_file,
        progress_path=args.progress_file,
        run_id=args.run_id,
    )
    
    ensure_dir(os.path.dirname(args.out) or ".")
    
    # Log start
    logger.log(
        "normalize",
        "running",
        current=0,
        total=None,
        message="Starting IR reduction",
        module_id="reduce_ir_v1",
    )
    
    # Read input elements
    elements_path = args.elements or args.pages or args.input
    if not elements_path:
        parser.error("Missing --elements (or --pages) input")

    elements = list(read_jsonl(elements_path))
    total = len(elements)
    
    logger.log(
        "normalize",
        "running",
        current=0,
        total=total,
        message=f"Read {total} elements, reducing to minimal schema",
        module_id="reduce_ir_v1",
    )
    
    # Reduce each element (filtering empty ones)
    core_elements = []
    filtered_count = 0
    for idx, elem_dict in enumerate(elements):
        core = reduce_element(
            elem_dict,
            seq=idx,  # 0-based sequential index (preserved even if element filtered)
            run_id=args.run_id,
            module_id="reduce_ir_v1",
        )
        if core is None:
            filtered_count += 1  # Empty element filtered out
            continue
        core_elements.append(core.model_dump(exclude_none=True))
        
        if (idx + 1) % 100 == 0:
            logger.log(
                "normalize",
                "running",
                current=idx + 1,
                total=total,
                message=f"Reduced {idx + 1}/{total} elements ({filtered_count} empty filtered)",
                module_id="reduce_ir_v1",
            )
    
    # Write output
    save_jsonl(args.out, core_elements)
    
    logger.log(
        "normalize",
        "done",
        current=total,
        total=total,
        message=f"Reduced {total} elements to {len(core_elements)} (filtered {filtered_count} empty)",
        module_id="reduce_ir_v1",
        artifact=args.out,
    )
    
    print(f"Reduced {total} elements → {len(core_elements)} elements ({filtered_count} empty filtered) → {args.out}")


if __name__ == "__main__":
    main()
