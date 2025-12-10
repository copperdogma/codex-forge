#!/usr/bin/env python3
"""
Stage 3: Boundaries Assembly

Converts sections_structured.json (Stage 2 output) into section_boundaries.jsonl
for downstream extraction. Deterministically computes end_seq from start_seq of
the next section, maps seq → element IDs using elements_core.jsonl, and enforces
ordering/uniqueness constraints.
"""

import argparse
import os
from typing import Dict, List, Any

from modules.common.utils import read_jsonl, save_jsonl, ensure_dir, ProgressLogger
from schemas import SectionsStructured, ElementCore, SectionBoundary


def load_elements_map(elements_path: str) -> Dict[int, ElementCore]:
    """Load elements_core.jsonl into a seq→ElementCore map."""
    elements_by_seq: Dict[int, ElementCore] = {}
    for elem_dict in read_jsonl(elements_path):
        elem = ElementCore(**elem_dict)
        elements_by_seq[elem.seq] = elem
    return elements_by_seq


def assemble_boundaries(structure: SectionsStructured, elements_by_seq: Dict[int, ElementCore],
                        confidence_default: float, run_id: str = None) -> List[Dict[str, Any]]:
    """Create SectionBoundary records from structured sections."""
    # Sort by start_seq (document order) to compute boundaries correctly
    # Sections may be out of order by ID, but boundaries must respect document position
    # Sort by document position; drop duplicate section ids by keeping earliest start_seq
    dedup_seen = set()
    game_sections_by_seq = []
    for gs in sorted([gs for gs in structure.game_sections if gs.start_seq is not None],
                     key=lambda gs: gs.start_seq):
        if gs.id in dedup_seen:
            continue
        dedup_seen.add(gs.id)
        game_sections_by_seq.append(gs)

    boundaries: List[Dict[str, Any]] = []

    # Precompute max seq for end boundary of last section
    max_seq = max(elements_by_seq.keys()) if elements_by_seq else 0

    for idx, gs in enumerate(game_sections_by_seq):
        start_seq = gs.start_seq
        start_elem = elements_by_seq.get(start_seq)
        if start_elem is None:
            # Skip if we can't map seq to element id
            continue

        # Determine end_seq as the element just before the next section start (by document order)
        next_start_seq = None
        if idx + 1 < len(game_sections_by_seq):
            next_start_seq = game_sections_by_seq[idx + 1].start_seq

        end_seq = (next_start_seq - 1) if next_start_seq is not None else max_seq
        end_elem = elements_by_seq.get(end_seq)

        confidence = gs.confidence if gs.confidence is not None else confidence_default

        boundary = SectionBoundary(
            section_id=str(gs.id),
            start_element_id=start_elem.id,
            end_element_id=end_elem.id if end_elem else None,
            confidence=confidence,
            evidence=f"start_seq={start_seq}, end_seq={end_seq}",
            module_id="assemble_boundaries_v1",
            run_id=run_id,
        )
        boundaries.append(boundary.model_dump(exclude_none=True))

    # Sort final output by section_id for consistency (even though computed by start_seq)
    boundaries.sort(key=lambda x: int(x["section_id"]) if x["section_id"].isdigit() else 999999)
    
    return boundaries


def validate_boundaries(boundaries: List[Dict[str, Any]], elements_by_seq: Dict[int, ElementCore]) -> List[str]:
    """Validate ordering/uniqueness; return list of error strings."""
    errors: List[str] = []

    # Check uniqueness of section_id
    seen = set()
    for b in boundaries:
        sid = b["section_id"]
        if sid in seen:
            errors.append(f"Duplicate section_id detected: {sid}")
        seen.add(sid)

    # Build id -> seq map for quick lookup
    id_to_seq = {elem.id: seq for seq, elem in elements_by_seq.items()}

    # Check that boundaries are in document order (by start_seq, not section_id)
    # Sections may be out of order by ID, but boundaries must respect document position
    previous_seq = -1
    for b in sorted(boundaries, key=lambda x: id_to_seq.get(x["start_element_id"], 999999)):
        start_elem_id = b["start_element_id"]
        seq = id_to_seq.get(start_elem_id)
        if seq is None:
            errors.append(f"start_element_id {start_elem_id} not found in elements_core")
            continue
        if seq <= previous_seq:
            errors.append(f"Non-increasing start sequence at section {b['section_id']} (seq {seq} after {previous_seq})")
        previous_seq = seq

    return errors


def main():
    parser = argparse.ArgumentParser(description="Assemble section_boundaries.jsonl from structured sections")
    parser.add_argument("--structure", required=False, help="sections_structured.json path")
    parser.add_argument("--pages", required=False, help="Alias for --structure (driver compatibility)")
    parser.add_argument("--elements", required=False, help="elements_core.jsonl path")
    parser.add_argument("--input", required=False, help="Alias for --elements (driver compatibility)")
    parser.add_argument("--out", required=True, help="Output section_boundaries.jsonl path")
    parser.add_argument("--confidence-default", "--confidence_default", type=float, default=0.7,
                        dest="confidence_default",
                        help="Fallback confidence when structure lacks confidence field")
    parser.add_argument("--skip-ai", "--skip_ai", action="store_true", dest="skip_ai",
                        help="Skip assembly logic and copy stub instead")
    parser.add_argument("--stub", help="Stub section_boundaries.jsonl to use when --skip-ai is set")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    structure_path = args.structure or args.pages
    if not structure_path:
        # Fallback: look beside output path
        candidate = os.path.join(os.path.dirname(args.out), "sections_structured.json")
        if os.path.exists(candidate):
            structure_path = candidate
        else:
            parser.error("Missing --structure/--pages path to sections_structured.json")

    elements_path = args.elements or args.input
    if not elements_path:
        candidate = os.path.join(os.path.dirname(structure_path), "elements_core.jsonl")
        if os.path.exists(candidate):
            elements_path = candidate
        else:
            parser.error("Missing --elements/--input path to elements_core.jsonl")

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    logger.log("portionize", "running", current=0, total=1,
               message="Loading structured sections", artifact=args.out, module_id="assemble_boundaries_v1")

    if args.skip_ai:
        if not args.stub:
            raise SystemExit("--skip-ai set but no --stub provided for assemble_boundaries_v1")
        stub_rows = list(read_jsonl(args.stub))
        ensure_dir(os.path.dirname(args.out) or ".")
        save_jsonl(args.out, stub_rows)
        logger.log("portionize", "done", current=len(stub_rows), total=len(stub_rows),
                   message="Loaded section_boundaries stubs", artifact=args.out, module_id="assemble_boundaries_v1")
        print(f"[skip-ai] assemble_boundaries_v1 copied stubs → {args.out}")
        return

    # Load inputs
    with open(structure_path, "r", encoding="utf-8") as f:
        structure_obj = SectionsStructured.model_validate_json(f.read())
    elements_by_seq = load_elements_map(elements_path)

    logger.log("portionize", "running", current=0, total=1,
               message="Assembling boundaries", artifact=args.out, module_id="assemble_boundaries_v1")

    boundaries = assemble_boundaries(structure_obj, elements_by_seq, args.confidence_default, run_id=args.run_id)

    # Span widening guard: if a boundary would produce zero-length span, extend end by 1 when possible
    widened = 0
    id_to_seq = {elem.id: seq for seq, elem in elements_by_seq.items()}
    seq_to_elem = {seq: elem for seq, elem in elements_by_seq.items()}
    for b in boundaries:
        start_seq = id_to_seq.get(b["start_element_id"])
        end_seq = id_to_seq.get(b.get("end_element_id")) if b.get("end_element_id") else None
        if end_seq is not None and start_seq is not None and end_seq == start_seq:
            next_seq = end_seq + 1
            if next_seq in seq_to_elem:
                b["end_element_id"] = seq_to_elem[next_seq].id
                widened += 1
    if widened:
        print(f"[assemble_boundaries] widened {widened} zero-length spans")

    errors = validate_boundaries(boundaries, elements_by_seq)
    if errors:
        for err in errors:
            print(f"❌ {err}")
        raise SystemExit(f"Validation failed with {len(errors)} errors")

    ensure_dir(os.path.dirname(args.out) or ".")
    save_jsonl(args.out, boundaries)

    logger.log("portionize", "done", current=1, total=1,
               message=f"Wrote {len(boundaries)} boundaries", artifact=args.out, module_id="assemble_boundaries_v1")


if __name__ == "__main__":
    main()
