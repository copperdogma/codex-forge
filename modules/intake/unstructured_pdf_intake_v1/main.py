#!/usr/bin/env python3
"""
Unstructured PDF Intake Module v1

Partitions a PDF using the Unstructured library and serializes elements
to JSON with minimal transformation, preserving Unstructured's native
element types and all metadata.

Outputs:
- elements.jsonl: Stream of Unstructured elements (one per line)
- unstructured_raw.json (optional): Raw Unstructured output for debugging
"""

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from modules.common.utils import ensure_dir, save_jsonl, ProgressLogger
from schemas import UnstructuredElement, CodexMetadata


def make_json_serializable(val: Any) -> Any:
    """
    Convert non-JSON-serializable types to serializable equivalents.

    Handles: frozenset, set, tuple, mappingproxy, custom objects, etc.
    """
    if val is None:
        return None

    # Handle sets and frozensets
    if isinstance(val, (set, frozenset)):
        return sorted(list(val))  # Convert to sorted list for consistency

    # Handle tuples (convert to list)
    if isinstance(val, tuple):
        return list(val)

    # Handle mappingproxy (convert to regular dict)
    import types
    if isinstance(val, types.MappingProxyType):
        return {k: make_json_serializable(v) for k, v in val.items()}

    # Handle regular dicts (recursively serialize values)
    if isinstance(val, dict):
        return {k: make_json_serializable(v) for k, v in val.items()}

    # Handle lists (recursively serialize items)
    if isinstance(val, list):
        return [make_json_serializable(item) for item in val]

    # Handle objects with to_dict() method
    if hasattr(val, "to_dict") and callable(val.to_dict):
        return val.to_dict()

    # Handle objects with __dict__ (complex objects)
    if hasattr(val, "__dict__"):
        try:
            obj_dict = vars(val)
            # Recursively serialize nested objects
            return {k: make_json_serializable(v) for k, v in obj_dict.items()}
        except:
            return str(val)

    # For primitives and already-serializable types, return as-is
    return val


def serialize_element(
    element,
    source_file: str,
    sequence: int,
    run_id: Optional[str] = None,
    module_id: str = "unstructured_pdf_intake_v1",
) -> Dict[str, Any]:
    """
    Serialize an Unstructured element to JSON with minimal transformation.

    Preserves:
    - element.id, element.type, element.text (core fields)
    - element.metadata.* (all Unstructured metadata as-is)

    Adds:
    - _codex namespace with run_id, module_id, sequence, created_at
    """
    # Extract core fields
    element_id = getattr(element, "id", None) or str(uuid.uuid4())
    element_type = getattr(element, "type", "Unknown")
    text = getattr(element, "text", "") or ""

    # Extract metadata as dict
    metadata_dict = {}
    if hasattr(element, "metadata"):
        # Convert ElementMetadata object to dict
        metadata_obj = element.metadata
        for attr in dir(metadata_obj):
            if not attr.startswith("_"):
                val = getattr(metadata_obj, attr, None)
                # Skip methods
                if callable(val):
                    continue
                # Convert all values to JSON-serializable forms
                if val is not None:
                    metadata_dict[attr] = make_json_serializable(val)

    # Create UnstructuredElement with _codex namespace
    elem = UnstructuredElement(
        id=str(element_id),
        type=element_type,
        text=text,
        metadata=metadata_dict,
        codex=CodexMetadata(
            run_id=run_id,
            module_id=module_id,
            sequence=sequence,
            created_at=datetime.now(timezone.utc).isoformat(),
        ),
    )

    # Serialize with alias (codex → _codex)
    return elem.model_dump(by_alias=True, exclude_none=False)


def partition_pdf_with_unstructured(
    pdf_path: str,
    strategy: str,
    infer_table_structure: bool,
    extract_images: bool,
    start_page: Optional[int],
    end_page: Optional[int],
) -> List:
    """
    Partition PDF using Unstructured library.

    Returns list of Unstructured element objects.
    """
    try:
        from unstructured.partition.pdf import partition_pdf
    except ImportError as e:
        raise SystemExit(
            f"Unstructured library not installed. "
            f"Run: pip install -r requirements.txt\n{e}"
        )

    kwargs = {
        "filename": pdf_path,
        "strategy": strategy,
        "infer_table_structure": infer_table_structure,
        "extract_images_in_pdf": extract_images,
    }

    elements = partition_pdf(**kwargs)

    # Filter by page range if specified
    if start_page is not None or end_page is not None:
        filtered = []
        for elem in elements:
            page_num = getattr(elem.metadata, "page_number", None)
            if page_num is None:
                continue
            if start_page is not None and page_num < start_page:
                continue
            if end_page is not None and page_num > end_page:
                continue
            filtered.append(elem)
        elements = filtered

    return elements


def main():
    parser = argparse.ArgumentParser(
        description="Partition PDF with Unstructured into elements.jsonl"
    )
    parser.add_argument("--pdf", required=True, help="Path to input PDF")
    parser.add_argument("--outdir", required=True, help="Output directory")
    parser.add_argument(
        "--strategy",
        default="hi_res",
        choices=["auto", "fast", "hi_res", "ocr_only"],
        help="Unstructured partitioning strategy",
    )
    parser.add_argument(
        "--infer-table-structure",
        "--infer_table_structure",
        dest="infer_table_structure",
        action="store_true",
        default=True,
        help="Infer table structure and extract HTML",
    )
    parser.add_argument(
        "--no-infer-table-structure",
        dest="infer_table_structure",
        action="store_false",
        help="Disable table structure inference",
    )
    parser.add_argument(
        "--extract-images",
        "--extract_images",
        dest="extract_images",
        action="store_true",
        default=False,
        help="Extract embedded images",
    )
    parser.add_argument(
        "--start-page",
        "--start_page",
        dest="start_page",
        type=int,
        help="First page to process (1-based)",
    )
    parser.add_argument(
        "--end-page",
        "--end_page",
        dest="end_page",
        type=int,
        help="Last page to process (inclusive)",
    )
    parser.add_argument(
        "--save-raw",
        "--save_raw",
        dest="save_raw",
        action="store_true",
        default=False,
        help="Save raw Unstructured output for debugging",
    )
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    logger = ProgressLogger(
        state_path=args.state_file,
        progress_path=args.progress_file,
        run_id=args.run_id,
    )

    ensure_dir(args.outdir)

    # Log start
    logger.log(
        "intake",
        "running",
        current=0,
        total=None,
        message=f"Partitioning PDF with strategy={args.strategy}",
        module_id="unstructured_pdf_intake_v1",
    )

    # Partition PDF
    try:
        elements = partition_pdf_with_unstructured(
            pdf_path=args.pdf,
            strategy=args.strategy,
            infer_table_structure=args.infer_table_structure,
            extract_images=args.extract_images,
            start_page=args.start_page,
            end_page=args.end_page,
        )
    except Exception as e:
        logger.log(
            "intake",
            "failed",
            current=0,
            total=None,
            message=f"Unstructured partitioning failed: {e}",
            module_id="unstructured_pdf_intake_v1",
        )
        raise

    logger.log(
        "intake",
        "running",
        current=1,
        total=2,
        message=f"Partitioned {len(elements)} elements, serializing to JSON",
        module_id="unstructured_pdf_intake_v1",
    )

    # Save raw Unstructured output if requested
    if args.save_raw:
        raw_output = []
        for elem in elements:
            raw_output.append({
                "type": getattr(elem, "type", None),
                "text": getattr(elem, "text", None),
                "metadata": {
                    k: str(v) for k, v in vars(getattr(elem, "metadata", {})).items()
                    if not k.startswith("_")
                },
            })
        raw_path = os.path.join(args.outdir, "unstructured_raw.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(raw_output, f, indent=2, ensure_ascii=False, default=str)
        print(f"Saved raw Unstructured output to {raw_path}")

    # Serialize elements to JSON
    serialized_elements = []
    for idx, elem in enumerate(elements):
        serialized = serialize_element(
            element=elem,
            source_file=os.path.abspath(args.pdf),
            sequence=idx,
            run_id=args.run_id,
        )
        serialized_elements.append(serialized)

    # Count elements by type for logging
    type_counts: Dict[str, int] = {}
    page_set = set()
    for elem in serialized_elements:
        elem_type = elem.get("type", "Unknown")
        type_counts[elem_type] = type_counts.get(elem_type, 0) + 1
        page_num = elem.get("metadata", {}).get("page_number")
        if page_num:
            page_set.add(page_num)

    # Write elements as JSONL
    elements_path = os.path.join(args.outdir, "elements.jsonl")
    save_jsonl(elements_path, serialized_elements)

    # Log completion
    summary = ", ".join(f"{k}={v}" for k, v in sorted(type_counts.items()))
    logger.log(
        "intake",
        "done",
        current=2,
        total=2,
        message=f"Elements: {len(serialized_elements)} across {len(page_set)} pages ({summary})",
        artifact=elements_path,
        module_id="unstructured_pdf_intake_v1",
        schema_version="unstructured_element_v1",
    )

    print(f"✓ Wrote {len(serialized_elements)} elements to {elements_path}")
    print(f"  Pages: {len(page_set)}")
    print(f"  Types: {summary}")


if __name__ == "__main__":
    main()
