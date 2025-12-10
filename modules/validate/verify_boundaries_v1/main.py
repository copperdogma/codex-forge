#!/usr/bin/env python3
"""
Stage 4: Boundary Verification

Runs deterministic checks plus optional AI spot-checks to validate
section_boundaries.jsonl before extraction. Flags ordering issues,
missing element IDs, mid-sentence starts, and duplicates.
"""

import argparse
import json
import os
import random
from typing import Dict, List, Any

from openai import OpenAI

from modules.common.utils import read_jsonl, save_json, ProgressLogger, ensure_dir, log_llm_usage
from schemas import SectionBoundary, ElementCore, BoundaryIssue, BoundaryVerificationReport


def load_elements(elements_path: str) -> Dict[str, ElementCore]:
    """Load elements_core.jsonl into id->ElementCore map."""
    elements = {}
    for elem_dict in read_jsonl(elements_path):
        elem = ElementCore(**elem_dict)
        elements[elem.id] = elem
    return elements


def seq_lookup(elements: Dict[str, ElementCore]) -> Dict[str, int]:
    """Create id->seq map."""
    return {elem.id: elem.seq for elem in elements.values()}


def deterministic_checks(boundaries: List[SectionBoundary], elements: Dict[str, ElementCore]) -> List[BoundaryIssue]:
    """Run deterministic validation checks."""
    issues: List[BoundaryIssue] = []

    id_to_seq = seq_lookup(elements)
    seen_sections = set()
    prev_seq = -1

    # Sort by document order (start_seq) for validation, not section_id
    # Sections may be out of order by ID, but boundaries must respect document position
    for b in sorted(boundaries, key=lambda x: id_to_seq.get(x.start_element_id, 999999)):
        # duplicate section_id
        if b.section_id in seen_sections:
            issues.append(BoundaryIssue(
                section_id=b.section_id,
                severity="error",
                message="Duplicate section_id in boundaries",
                start_element_id=b.start_element_id,
            ))
        seen_sections.add(b.section_id)

        # element existence
        if b.start_element_id not in id_to_seq:
            issues.append(BoundaryIssue(
                section_id=b.section_id,
                severity="error",
                message="start_element_id not found in elements_core",
                start_element_id=b.start_element_id,
            ))
            continue

        start_seq = id_to_seq[b.start_element_id]

        if start_seq <= prev_seq:
            issues.append(BoundaryIssue(
                section_id=b.section_id,
                severity="error",
                message=f"Non-increasing start sequence ({start_seq} <= {prev_seq})",
                start_element_id=b.start_element_id,
            ))
        prev_seq = start_seq

        # heuristic mid-sentence detection
        prev_element = elements.get(get_prev_id(start_seq, id_to_seq, elements))
        start_elem = elements.get(b.start_element_id)
        if start_elem:
            if looks_mid_sentence(prev_element, start_elem):
                issues.append(BoundaryIssue(
                    section_id=b.section_id,
                    severity="warning",
                    message="Start appears mid-sentence (heuristic)",
                    start_element_id=b.start_element_id,
                    page=start_elem.page,
                ))

    return issues


def get_prev_id(start_seq: int, id_to_seq: Dict[str, int], elements: Dict[str, ElementCore]) -> str:
    """Return element id with seq immediately before start_seq, if any."""
    target_seq = start_seq - 1
    for eid, seq in id_to_seq.items():
        if seq == target_seq:
            return eid
    return ""


def looks_mid_sentence(prev_elem: ElementCore, start_elem: ElementCore) -> bool:
    """Simple heuristic: previous text does not end a sentence and start text begins lowercase."""
    if not start_elem:
        return False
    start_text = (start_elem.text or "").strip()
    if not start_text:
        return False

    # lower-case start of line is suspicious
    if start_text and start_text[0].islower():
        return True

    if not prev_elem:
        return False
    prev_text = (prev_elem.text or "").strip()
    if not prev_text:
        return False

    sentence_end = prev_text.endswith((".", "!", "?", ":"))
    capital_start = start_text[0].isupper()
    return (not sentence_end) and capital_start


def ai_spot_checks(boundaries: List[SectionBoundary], elements: Dict[str, ElementCore],
                   sample_count: int, model: str) -> List[Dict[str, Any]]:
    """Ask AI to judge sampled boundaries."""
    if sample_count <= 0:
        return []
    if not boundaries:
        return []

    client = OpenAI()
    samples = random.sample(boundaries, k=min(sample_count, len(boundaries)))
    results = []

    for b in samples:
        start_elem = elements.get(b.start_element_id)
        if not start_elem:
            continue
        # build context
        context = f"Section {b.section_id} starts with:\n{start_elem.text}\n"
        # include previous text if available
        prev_id = get_prev_id(start_elem.seq, {e.id: e.seq for e in elements.values()}, elements)
        if prev_id and prev_id in elements:
            context = f"Previous text:\n{elements[prev_id].text}\n\n" + context

        user_prompt = f"""You are validating section boundaries in a Fighting Fantasy gamebook.

{context}

Question: Does this look like a plausible start of a numbered gameplay section? Answer with JSON: {{"looks_valid": true/false, "reason": "..."}}"""

        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a meticulous QA assistant for book section boundaries."},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=300,
            temperature=0,
        )

        usage = getattr(completion, "usage", None)
        log_llm_usage(model=model,
                      prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                      completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                      request_ms=None)

        resp = completion.choices[0].message.content
        verdict = json.loads(resp)
        verdict["section_id"] = b.section_id
        verdict["start_element_id"] = b.start_element_id
        results.append(verdict)

    return results


def main():
    parser = argparse.ArgumentParser(description="Verify section boundaries with deterministic checks and AI spot-checks.")
    parser.add_argument("--boundaries", required=True, help="section_boundaries.jsonl")
    parser.add_argument("--elements", required=True, help="elements_core.jsonl")
    parser.add_argument("--out", required=True, help="boundary_verification.json")
    parser.add_argument("--sample-count", "--sample_count", type=int, default=8, dest="sample_count",
                        help="Number of AI samples to check")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model for spot checks")
    parser.add_argument("--skip-ai", "--skip_ai", action="store_true", dest="skip_ai",
                        help="Skip AI spot checks and optionally copy stub report")
    parser.add_argument("--stub", help="Stub boundary_verification.json to use when --skip-ai is set")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    logger.log("validate", "running", current=0, total=1,
               message="Loading inputs", artifact=args.out, module_id="verify_boundaries_v1")

    if args.skip_ai and args.stub:
        with open(args.stub, "r", encoding="utf-8") as f:
            stub_obj = json.load(f)
        save_json(args.out, stub_obj)
        logger.log("validate", "done", current=1, total=1,
                   message="Loaded boundary verification stub", artifact=args.out,
                   module_id="verify_boundaries_v1", schema_version="boundary_verification_v1")
        print(f"[skip-ai] verify_boundaries_v1 copied stub → {args.out}")
        return

    boundaries = [SectionBoundary(**b) for b in read_jsonl(args.boundaries)]
    elements = load_elements(args.elements)

    logger.log("validate", "running", current=0, total=1,
               message="Running deterministic checks", artifact=args.out, module_id="verify_boundaries_v1")

    deterministic_issues = deterministic_checks(boundaries, elements)

    if args.skip_ai:
        args.sample_count = 0
        logger.log("validate", "running", current=0, total=1,
                   message="Skipping AI spot checks (--skip-ai)", artifact=args.out,
                   module_id="verify_boundaries_v1")
    else:
        logger.log("validate", "running", current=0, total=1,
                   message=f"Running AI spot checks (n={args.sample_count})", artifact=args.out,
                   module_id="verify_boundaries_v1")

    ai_results = []
    if args.sample_count > 0:
        try:
            ai_results = ai_spot_checks(boundaries, elements, args.sample_count, args.model)
        except Exception as e:
            # Non-fatal; record warning
            deterministic_issues.append(BoundaryIssue(
                section_id="*",
                severity="warning",
                message=f"AI spot checks skipped due to error: {e}",
            ))

    errors = [i for i in deterministic_issues if i.severity == "error"]
    warnings = [i for i in deterministic_issues if i.severity == "warning"]

    report = BoundaryVerificationReport(
        checked=len(boundaries),
        errors=errors,
        warnings=warnings,
        ai_samples=ai_results,
        is_valid=len(errors) == 0,
        run_id=args.run_id,
    )

    ensure_dir(os.path.dirname(args.out) or ".")
    save_json(args.out, report.model_dump(exclude_none=True))

    status = "done" if report.is_valid else "failed"
    logger.log("validate", status, current=1, total=1,
               message=f"Verification {'passed' if report.is_valid else 'failed'} "
                       f"({len(errors)} errors, {len(warnings)} warnings)",
               artifact=args.out, module_id="verify_boundaries_v1")

    if not report.is_valid:
        raise SystemExit("Boundary verification failed")


if __name__ == "__main__":
    main()
