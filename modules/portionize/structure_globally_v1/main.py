#!/usr/bin/env python3
"""
Global Structuring Module v1

Stage 2: Takes header_candidates.jsonl from Stage 1 and performs a single AI call
to create coherent global document structure with macro sections and game sections.
Uses strong constraints to ensure proper ordering and conservatively marks uncertain sections.
"""

import argparse
import json
import os
from typing import Dict, List, Optional, Any

from modules.common.openai_client import OpenAI
from modules.common.utils import read_jsonl, save_json, ensure_dir, ProgressLogger
from schemas import HeaderCandidate, SectionsStructured, MacroSection, GameSectionStructured, ElementCore
from .fixup import normalize_start_seq

# CYOA Document Profile (same as Stage 1)
CYOA_PROFILE = {
    "doc_type": "cyoa_gamebook",
    "expected_macro_sections": [
        "cover",
        "title_page",
        "publishing_info",
        "toc",
        "character_sheet",
        "rules",
        "introduction",
        "game_sections"
    ],
    "game_section_hint": {
        "numeric_range": [1, 400],
        "typical_layout": [
            "centered number alone on a line, followed by text",
            "image, then centered number alone on a line, followed by text"
        ]
    }
}

SYSTEM_PROMPT = """You are analyzing a Fighting Fantasy gamebook to identify its structure.

These books have a standard format:
- Front matter: Cover, title page, table of contents, publishing info
- Rules section: Instructions on combat, equipment, dice rolling
- Introduction: Transition to gameplay ("YOU ARE THE HERO", etc.)
- Gameplay sections: Numbered sections (typically 1-400) containing the adventure

Your task:
1. Identify where front_matter ends and game_sections begin
2. From the header candidates, identify which are real gameplay section headers
3. Assign section numbers and start positions (start_seq)

Important: Include all reasonable section candidates. Missing real sections is worse than including a few uncertain ones. Mark as "certain" if you're reasonably confident (confidence > 0.6), "uncertain" only if you have serious doubts."""


def create_compact_summary(header_candidates: List[Dict[str, Any]], max_seq: int) -> Dict[str, Any]:
    """
    Create compact summary of header candidates for AI processing.
    
    Filters to elements with header signals (macro_header != "none" or game_section_header == true)
    to keep payload smaller while maintaining context.
    """
    summary = {
        "doc_type": CYOA_PROFILE["doc_type"],
        "target_section_range": CYOA_PROFILE["game_section_hint"]["numeric_range"],
        "max_seq": max_seq,
        "elements": []
    }
    
    # Filter to candidates with header signals
    # Note: Exclude text from summary to keep prompt size manageable
    # Text will be merged back in enrich_with_text() after AI returns
    for candidate in header_candidates:
        if candidate.get("macro_header") != "none" or candidate.get("game_section_header", False):
            summary["elements"].append({
                "seq": candidate["seq"],
                "page": candidate["page"],
                "macro_header": candidate.get("macro_header", "none"),
                "game_section_header": candidate.get("game_section_header", False),
                "claimed_section_number": candidate.get("claimed_section_number"),
                "confidence": candidate.get("confidence", 0.0)
                # Note: text field excluded from prompt to reduce size
            })
    
    return summary


def create_global_structure_prompt(summary: Dict[str, Any]) -> str:
    """Create prompt for global structure analysis."""
    num_elements = len(summary["elements"])
    section_range = f"{summary['target_section_range'][0]}-{summary['target_section_range'][1]}"
    
    # Compact JSON for elements
    elements_json = json.dumps(summary["elements"], separators=(',', ':'))
    
    prompt = f"""Analyze {num_elements} header candidates from a Fighting Fantasy gamebook.

Expected structure: Front matter → Rules → Introduction → Numbered gameplay sections ({section_range})
Document spans seq 0 to {summary['max_seq']}

Your task:
1. Identify macro sections:
   - "front_matter": Cover, title, TOC, rules, introduction (everything before gameplay starts)
   - "game_sections": The numbered gameplay sections region

2. Identify real gameplay sections:
   - From the candidates, determine which are actual section headers
   - Assign each section its number and start position (start_seq)
   - Sections should be in order: 1, 2, 3, ... (may have gaps, but should increase)
   - Include all reasonable candidates - missing real sections is worse than including uncertain ones
   - Mark as "certain" if reasonably confident, "uncertain" only if seriously doubtful

Return JSON with this structure:
{{
  "macro_sections": [
    {{
      "id": "front_matter",
      "start_seq": 0,
      "end_seq": 86,
      "confidence": 0.9
    }},
    {{
      "id": "game_sections",
      "start_seq": 87,
      "end_seq": {summary['max_seq']},
      "confidence": 0.95
    }}
  ],
  "game_sections": [
    {{
      "id": 1,
      "start_seq": 87,
      "status": "certain",
      "confidence": 0.98
    }},
    {{
      "id": 2,
      "start_seq": 113,
      "status": "certain",
      "confidence": 0.97
    }}
  ]
}}

Header candidates:
{elements_json}"""
    
    return prompt


def call_structure_llm(client: OpenAI, model: str, prompt: str, max_tokens: int, timeout: float = 45.0) -> Dict[str, Any]:
    """Call AI to create global structure."""
    try:
        # gpt-5 uses max_completion_tokens instead of max_tokens
        create_kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
        }
        # Use appropriate parameter based on model
        if model.startswith("gpt-5"):
            create_kwargs["max_completion_tokens"] = max_tokens
            create_kwargs["temperature"] = 1  # gpt-5 disallows temperature=0
        else:
            create_kwargs["max_tokens"] = max_tokens
            create_kwargs["temperature"] = 0.0  # deterministic where supported
        
        completion = client.chat.completions.create(timeout=timeout, **create_kwargs)
        
        
        # Parse response
        response_text = completion.choices[0].message.content
        if not response_text:
            raise ValueError("Empty response from LLM")
        
        # Try to parse JSON with better error reporting
        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError as json_err:
            # Log helpful debug info
            print(f"❌ JSON decode error at position {json_err.pos}")
            print(f"   Response length: {len(response_text)} chars")
            print(f"   First 500 chars: {response_text[:500]}")
            print(f"   Last 500 chars: {response_text[-500:]}")
            print(f"   Max tokens was: {max_tokens}")
            raise ValueError(f"LLM returned invalid JSON: {json_err}") from json_err
        
        return payload
        
    except Exception as e:
        print(f"Error calling LLM for global structure: {e}")
        import traceback
        traceback.print_exc()
        raise


def validate_structure(structure: Dict[str, Any], max_seq: int) -> List[str]:
    """Validate structure against constraints, return list of errors."""
    errors = []
    
    # Validate macro sections
    if "macro_sections" not in structure:
        errors.append("Missing 'macro_sections' field")
        return errors
    
    macro_sections = structure["macro_sections"]
    if not isinstance(macro_sections, list):
        errors.append("'macro_sections' must be a list")
        return errors
    
    # Validate game sections
    if "game_sections" not in structure:
        errors.append("Missing 'game_sections' field")
        return errors
    
    game_sections = structure["game_sections"]
    if not isinstance(game_sections, list):
        errors.append("'game_sections' must be a list")
        return errors
    
    # Validate game sections: strict ordering constraints (certain only)
    certain_sections = [gs for gs in game_sections if gs.get("status") == "certain"]
    if certain_sections:
        # Sort by id
        certain_sections.sort(key=lambda x: x.get("id", 0))
        
        prev_id = None
        prev_seq = None
        for gs in certain_sections:
            gs_id = gs.get("id")
            gs_seq = gs.get("start_seq")
            
            if gs_id is None:
                errors.append(f"Game section missing 'id' field")
                continue
            
            if gs_seq is None:
                errors.append(f"Game section {gs_id} marked 'certain' but missing 'start_seq'")
                continue
            
            if not (0 <= gs_seq <= max_seq):
                errors.append(f"Game section {gs_id} has start_seq {gs_seq} outside valid range [0, {max_seq}]")
            
            if prev_id is not None:
                if gs_id <= prev_id:
                    errors.append(f"Game section {gs_id} has id not strictly greater than previous {prev_id}")
                if gs_seq <= prev_seq:
                    errors.append(f"Game section {gs_id} has start_seq {gs_seq} not strictly greater than previous {prev_seq}")
            
            prev_id = gs_id
            prev_seq = gs_seq
    
    return errors


def enrich_with_text(structure: Dict[str, Any], elements_core_path: str) -> Dict[str, Any]:
    """
    Enrich structure with full text from elements_core.jsonl.
    
    For each game section with start_seq, extracts FULL text starting from that seq
    until the next section's start_seq (or end of elements). This helps verify
    boundary correctness - if too much text is included, it will be obvious.
    """
    if not elements_core_path or not os.path.exists(elements_core_path):
        print(f"⚠️ elements_core.jsonl not found at {elements_core_path}, skipping text enrichment")
        return structure
    
    # Load elements_core into lookup by seq
    elements_by_seq = {}
    for elem_dict in read_jsonl(elements_core_path):
        elem = ElementCore(**elem_dict)
        elements_by_seq[elem.seq] = elem
    
    print(f"Loaded {len(elements_by_seq)} elements from elements_core.jsonl for text enrichment")
    
    # Build map of start_seq -> section for boundary detection
    section_starts = {}
    for gs in structure.get("game_sections", []):
        if gs.get("status") == "certain" and gs.get("start_seq") is not None:
            section_starts[gs["start_seq"]] = gs.get("id")
    
    # Get max seq for boundary detection
    max_seq = max(elements_by_seq.keys()) if elements_by_seq else 0
    
    # Enrich game sections with full text
    enriched_sections = []
    for gs in structure.get("game_sections", []):
        enriched_gs = gs.copy()
        
        if gs.get("status") == "certain" and gs.get("start_seq") is not None:
            start_seq = gs["start_seq"]
            
            # Determine end boundary: next section's start_seq or max_seq+1
            end_seq = max_seq + 1
            for other_start in sorted(section_starts.keys()):
                if other_start > start_seq:
                    end_seq = other_start
                    break
            
            # Extract full text from start_seq until end_seq
            text_parts = []
            current_seq = start_seq
            
            while current_seq < end_seq and current_seq in elements_by_seq:
                elem = elements_by_seq[current_seq]
                text = elem.text.strip()
                if text:
                    text_parts.append(text)
                current_seq += 1
            
            if text_parts:
                full_text = "\n\n".join(text_parts)
                enriched_gs["text"] = full_text
                enriched_gs["text_length"] = len(full_text)
            else:
                enriched_gs["text"] = ""
                enriched_gs["text_length"] = 0
        
        # Ensure confidence exists (default to 0.5 if missing)
        if "confidence" not in enriched_gs:
            enriched_gs["confidence"] = 0.5

        enriched_sections.append(enriched_gs)
    
    structure["game_sections"] = enriched_sections
    return structure


def main():
    parser = argparse.ArgumentParser(
        description="Create global document structure from header candidates"
    )
    parser.add_argument("--pages", required=True,
                       help="Input header_candidates.jsonl path (uses --pages for driver compatibility)")
    parser.add_argument("--elements", required=False,
                       help="Path to elements_core.jsonl for text enrichment (required for verification)")
    parser.add_argument("--input", required=False,
                       help="Alias for --elements (driver compatibility)")
    parser.add_argument("--out", required=True,
                       help="Output sections_structured.json path")
    parser.add_argument("--model", default="gpt-4o",
                       help="OpenAI model to use (gpt-4o recommended for complex reasoning)")
    parser.add_argument("--max_tokens", type=int, default=16000,
                       help="Max tokens for AI response (increased for complex structures)")
    parser.add_argument("--min_sections", type=int, default=300,
                       help="Minimum total gameplay sections required to continue")
    parser.add_argument("--retry_model", default=None,
                       help="Optional stronger model to retry if coverage is below min_sections")
    parser.add_argument("--max_retries", type=int, default=1,
                       help="Maximum coverage retries with retry_model")
    parser.add_argument("--skip-ai", "--skip_ai", action="store_true", dest="skip_ai",
                       help="Skip AI call and copy stub instead")
    parser.add_argument("--stub",
                       help="Stub sections_structured.json to use when --skip-ai is set")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()
    
    elements_path = args.elements or args.input
    if not elements_path:
        # Fallback: assume elements_core.jsonl lives beside header_candidates.jsonl
        candidate = os.path.join(os.path.dirname(args.pages), "elements_core.jsonl")
        if os.path.exists(candidate):
            elements_path = candidate
        else:
            parser.error("Missing --elements (or --input) path to elements_core.jsonl")

    logger = ProgressLogger(
        state_path=args.state_file,
        progress_path=args.progress_file,
        run_id=args.run_id,
    )
    
    ensure_dir(os.path.dirname(args.out) or ".")

    if args.skip_ai:
        if not args.stub:
            raise SystemExit("--skip-ai set but no --stub provided for structure_globally_v1")
        with open(args.stub, "r", encoding="utf-8") as f:
            stub_obj = json.load(f)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(stub_obj, f, indent=2)
        print(f"[skip-ai] structure_globally_v1 copied stub → {args.out}")
        logger.log("portionize", "done", current=1, total=1,
                   message="Loaded sections_structured stub", artifact=args.out, module_id="structure_globally_v1")
        return
    
    # Read header candidates
    logger.log(
        "portionize",
        "running",
        current=0,
        total=None,
        message="Loading header_candidates.jsonl",
        module_id="structure_globally_v1",
    )
    
    header_candidates = []
    max_seq = 0
    for candidate_dict in read_jsonl(args.pages):
        # Validate HeaderCandidate schema
        candidate = HeaderCandidate(**candidate_dict)
        header_candidates.append(candidate.model_dump(exclude_none=True))
        max_seq = max(max_seq, candidate.seq)
    
    logger.log(
        "portionize",
        "running",
        current=0,
        total=len(header_candidates),
        message=f"Loaded {len(header_candidates)} header candidates (max_seq={max_seq})",
        module_id="structure_globally_v1",
    )
    
    # Create compact summary
    summary = create_compact_summary(header_candidates, max_seq)
    print(f"Created summary with {len(summary['elements'])} header candidates (of {len(header_candidates)} total elements)")
    
    # Create prompt (optionally include macro hint if available)
    macro_hint_path = os.path.join(os.path.dirname(args.pages), "macro_sections.json")
    macro_hint = None
    if os.path.exists(macro_hint_path):
        try:
            macro_hint = json.load(open(macro_hint_path))
        except Exception:
            macro_hint = None
    prompt = create_global_structure_prompt(summary)
    if macro_hint and isinstance(macro_hint, dict):
        hint_page = None
        for sec in macro_hint.get("sections", []):
            if sec.get("section_name") == "main_content":
                hint_page = sec.get("page")
        if hint_page:
            prompt += f"\n\nSecondary hint: main content likely begins near page {hint_page}. Use this only as a tie-breaker; rely on text evidence."
    
    # Call AI
    logger.log(
        "portionize",
        "running",
        current=len(header_candidates),
        total=len(header_candidates),
        message="Calling AI for global structure analysis",
        module_id="structure_globally_v1",
    )
    
    print(f"Calling {args.model} for global structure analysis...")
    client = OpenAI(timeout=120.0)  # Longer timeout for complex reasoning

    attempt = 0
    structure = None
    last_err = None
    model_used = args.model
    while attempt <= args.max_retries and structure is None:
        try:
            structure = call_structure_llm(client, model_used, prompt, args.max_tokens)
        except Exception as e:
            last_err = e
            attempt += 1
            if attempt > args.max_retries or not args.retry_model:
                break
            model_used = args.retry_model
            print(f"[structure_globally] retrying with {model_used} (attempt {attempt}/{args.max_retries}) due to error: {e}")

    if structure is None:
        raise SystemExit(f"Global structure failed: {last_err}")
    
    # Validate structure
    errors = validate_structure(structure, max_seq)
    if errors:
        print(f"⚠️ Validation errors found:")
        for error in errors:
            print(f"  - {error}")
        # Continue anyway - validation is a warning, not fatal
    
    # Ensure all sections have required fields (confidence, status)
    for gs in structure.get("game_sections", []):
        if "confidence" not in gs:
            gs["confidence"] = 0.5  # Default confidence
        if "status" not in gs:
            gs["status"] = "uncertain"  # Default status
    
    # Enrich with full text from elements_core (merge after AI returns)
    print(f"Enriching structure with full text from {elements_path}...")
    structure = enrich_with_text(structure, elements_path)
    
    # Enforce monotonic start_seq ordering (certain first), then uncertain
    certain = [gs for gs in structure.get("game_sections", []) if gs.get("status") == "certain"]
    uncertain = [gs for gs in structure.get("game_sections", []) if gs.get("status") != "certain"]
    certain_sorted = normalize_start_seq(certain)
    uncertain_sorted = normalize_start_seq(uncertain)
    structure["game_sections"] = certain_sorted + uncertain_sorted

    # Parse into schema
    try:
        structured = SectionsStructured(**structure)
    except Exception as e:
        print(f"❌ Error parsing structure into schema: {e}")
        raise
    
    # Save output (with full text if enriched)
    save_json(args.out, structured.model_dump(exclude_none=True))
    
    macro_count = len(structured.macro_sections)
    game_certain = sum(1 for gs in structured.game_sections if gs.status == "certain")
    game_uncertain = sum(1 for gs in structured.game_sections if gs.status == "uncertain")

    total_sections = game_certain + game_uncertain
    if total_sections < args.min_sections and args.retry_model and model_used != args.retry_model and attempt < args.max_retries:
        # Coverage too low: try retry_model once for coverage (without re-enriching text to keep payload small)
        attempt += 1
        model_used = args.retry_model
        print(f"[structure_globally] coverage {total_sections} < {args.min_sections}; retrying with {model_used}")
        structure = call_structure_llm(client, model_used, prompt, args.max_tokens)
        certain = [gs for gs in structure.get("game_sections", []) if gs.get("status") == "certain"]
        uncertain = [gs for gs in structure.get("game_sections", []) if gs.get("status") != "certain"]
        structure["game_sections"] = normalize_start_seq(certain) + normalize_start_seq(uncertain)
        structured = SectionsStructured(**structure)
        macro_count = len(structured.macro_sections)
        game_certain = sum(1 for gs in structured.game_sections if gs.status == "certain")
        game_uncertain = sum(1 for gs in structured.game_sections if gs.status == "uncertain")
        total_sections = game_certain + game_uncertain

    if total_sections < args.min_sections:
        raise SystemExit(f"Global structure coverage too low: {total_sections} < min_sections={args.min_sections}")
    
    logger.log(
        "portionize",
        "done",
        current=len(header_candidates),
        total=len(header_candidates),
        message=f"Created global structure: {macro_count} macro sections, {game_certain} certain game sections, {game_uncertain} uncertain",
        module_id="structure_globally_v1",
        artifact=args.out,
    )
    
    print(f"Created global structure → {args.out}")
    print(f"  Macro sections: {macro_count}")
    print(f"  Game sections: {game_certain} certain, {game_uncertain} uncertain")


if __name__ == "__main__":
    main()