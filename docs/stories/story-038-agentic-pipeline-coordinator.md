# Story: Agentic Pipeline Coordinator

**Status**: To Do  
**Created**: 2025-01-27  
**Priority**: Medium

---

## Goal

Transform the pipeline from a passive executor into an intelligent, agentic coordinator that actively monitors, validates, and repairs artifacts at each stage. The AI coordinator takes ownership of quality assurance, making autonomous decisions about when to apply fixes, when to re-read source material, and when to escalate to the user. The system presents either a high-confidence final artifact or the best possible artifact with a clear report of remaining issues and suggested fixes.

This represents a fundamental shift from "run modules and hope" to "run modules, verify, fix, and report."

### Known input caveat (from Story 037)
- The current working PDF for “Deathtrap Dungeon” is missing sections/pages 169–170. They exist in the Internet Archive copy but not in our source. Coordinator should treat repeated failures to recover 169–170 as “absent-from-source” evidence, not a pipeline bug, and surface that in reports.

---

## Acceptance Criteria

### Success Path
- The AI coordinator reviews each artifact after every stage completion.
- For each artifact, the coordinator:
  - Performs spot checks (samples 5-10 entries, reads actual content).
  - Runs automated validation and interprets results.
  - Performs sanity checks (counts, coverage, expected patterns).
  - Compares against upstream artifacts to detect regressions.
- If all checks pass with high confidence, the coordinator proceeds to the next stage.
- At pipeline completion, the coordinator presents the final artifact with a confidence report indicating no issues detected.

### Issue Detection & Autonomous Remediation
- When issues are detected, the coordinator:
  - Identifies the specific problem (missing sections, garbled text, validation failures, etc.).
  - Attempts autonomous fixes using available modules:
    - Re-runs problematic stages with adjusted parameters.
    - Applies spot-fix modules (e.g., text repair, boundary correction).
    - Re-reads source material using vision models when OCR/text quality is suspect.
  - Tracks all remediation attempts in a remediation log.
- The coordinator can make intelligent decisions about:
  - Which pages/portions need re-OCR (using vision model on original images).
  - When to apply text repair modules vs. when to re-extract.
  - When boundary detection failed and needs correction.
  - When to re-run consensus/resolution stages with different parameters.

### User Escalation
- When autonomous remediation fails or confidence remains low:
  - The coordinator presents a structured issue report:
    - Problem description with specific examples.
    - All remediation attempts made (with outcomes).
    - Evidence from source material (screenshots, text samples).
    - Suggested manual fixes or input-specific patches.
  - The system supports user intervention:
    - Manual artifact editing interface.
    - Input-specific "patch" files that override pipeline output.
    - User-provided corrections that are preserved through subsequent runs.
- The coordinator can distinguish between:
  - Pipeline/system failures (fixable with module improvements).
  - Input quality issues (ripped pages, missing pages, misprints, smudges).

### Final Artifact Presentation
- **Success case**: Coordinator presents final artifact with:
  - High-confidence report (all stages verified, no issues detected).
  - Summary statistics (sections found, choices detected, coverage metrics).
  - Sample spot-check results from each stage.
- **Issues case**: Coordinator presents:
  - Best available final artifact (despite known issues).
  - Highlighted problem areas with:
    - Specific locations (page numbers, section IDs, portion indices).
    - Problem descriptions with examples.
    - Confidence scores for each problematic area.
  - Suggested fixes organized by:
    - Module improvements (code changes to fix systemic issues).
    - Pipeline configuration changes (parameter tuning, stage reordering).
    - System-level improvements (better OCR engines, new validation rules).
  - Remediation log showing all autonomous attempts.

---

## Tasks

### Priority 1: Artifact Review Framework
- [ ] Design artifact review interface:
  - Coordinator can load any artifact from `output/runs/<run_id>/`.
  - Coordinator can sample entries (random or targeted).
  - Coordinator can read full artifact content.
  - Coordinator can access upstream artifacts for comparison.
- [ ] Implement spot-check logic:
  - Sample 5-10 entries per artifact.
  - Read actual content (not just structure).
  - Verify expected patterns (e.g., sections have text, choices have targets).
  - Check for obvious errors (empty fields, malformed data, duplicates).
- [ ] Integrate automated validation:
  - Run `validate_artifact.py` on each artifact.
  - Parse validation output (errors, warnings, statistics).
  - Interpret validation results in context (not just pass/fail).
- [ ] Implement sanity checks:
  - Count-based checks (expected ranges for sections, portions, etc.).
  - Coverage checks (all expected pages/portions present).
  - Cross-stage consistency (downstream artifacts match upstream).
- [ ] Create review report format:
  - Per-artifact review results.
  - Confidence scores (high/medium/low).
  - Specific issues found with examples.
  - Recommendations for next steps.

### Priority 2: Autonomous Remediation System
- [ ] Design remediation decision framework:
  - Map issue types to available remediation modules.
  - Define confidence thresholds for autonomous action.
  - Track remediation attempts to avoid loops.
- [ ] Implement spot-fix execution:
  - Coordinator can invoke specific modules on subsets of data.
  - Coordinator can re-run stages with adjusted parameters.
  - Coordinator can apply text repair modules to specific portions.
  - Coordinator can re-run boundary detection on problematic pages.
- [ ] Implement vision-based source re-reading:
  - Coordinator can identify low-confidence OCR/text regions.
  - Coordinator can call vision model on original page images.
  - Coordinator can replace problematic text with vision model output.
  - Track which pages were re-read (for cost/audit purposes).
- [ ] Create remediation log:
  - Record all remediation attempts (issue → action → outcome).
  - Track success/failure of each attempt.
  - Prevent infinite remediation loops (max attempts per issue).
- [ ] Implement remediation orchestration:
  - Coordinator decides when to attempt fixes vs. escalate.
  - Coordinator can chain multiple remediation attempts.
  - Coordinator evaluates remediation success before proceeding.

### Priority 3: User Escalation Interface
- [ ] Design issue report format:
  - Structured problem descriptions.
  - Evidence (text samples, screenshots, validation errors).
  - Remediation history (what was tried, what worked/failed).
  - Suggested fixes (manual edits, patches, module improvements).
- [ ] Implement user intervention support:
  - Manual artifact editing (JSON/JSONL editor with validation).
  - Input-specific patch files (override pipeline output for specific entries).
  - Patch application logic (merge user patches with pipeline output).
  - Patch persistence (patches survive re-runs unless input changes).
- [ ] Implement issue categorization:
  - Distinguish pipeline failures (fixable) from input quality issues (not fixable).
  - Flag truly broken inputs (missing pages, unreadable scans).
  - Suggest when input replacement is needed vs. pipeline fixes.
- [ ] Create escalation UI:
  - Present issues in a clear, actionable format.
  - Allow user to review evidence and remediation attempts.
  - Support user corrections that feed back into pipeline.
  - Track user decisions for future learning.

### Priority 4: Final Artifact Presentation
- [ ] Implement success report generation:
  - High-confidence summary with verification details.
  - Stage-by-stage spot-check results.
  - Overall statistics and metrics.
  - Sample entries from final artifact.
- [ ] Implement issues report generation:
  - Best available artifact (despite known issues).
  - Problem map (locations, descriptions, confidence scores).
  - Suggested fixes organized by type (module/pipeline/system).
  - Remediation log summary.
- [ ] Create artifact presentation interface:
  - Human-readable summary report.
  - Interactive artifact browser (highlight problem areas).
  - Export options (JSON, markdown report, HTML dashboard).
- [ ] Integrate with existing dashboard:
  - Extend pipeline visibility dashboard to show coordinator reviews.
  - Highlight problem areas in artifact views.
  - Show remediation attempts and outcomes.

### Priority 5: Coordinator Intelligence & Learning
- [ ] Design coordinator prompt system:
  - Stage-specific review prompts (what to check for each artifact type).
  - Remediation decision prompts (when to fix vs. escalate).
  - Issue categorization prompts (pipeline vs. input problems).
- [ ] Implement context-aware review:
  - Coordinator understands book type and expected structure.
  - Coordinator knows what "good" looks like for each stage.
  - Coordinator can reason about upstream/downstream relationships.
- [ ] Add learning from user feedback:
  - Track which remediations users approve/reject.
  - Learn which issues are worth fixing autonomously.
  - Improve decision thresholds over time.
- [ ] Create coordinator configuration:
  - Confidence thresholds (when to escalate).
  - Remediation limits (max attempts per issue).
  - Cost controls (max vision model calls per run).

---

## Design Considerations

### Coordinator Architecture
- The coordinator should be a separate agentic layer that wraps the existing driver.
- Coordinator can be invoked:
  - After each stage (incremental review).
  - At pipeline completion (final review).
  - On-demand (user requests review of specific artifact).
- Coordinator maintains state:
  - Review history for current run.
  - Remediation attempts and outcomes.
  - User escalation decisions.

### Remediation Module Integration
- Existing modules should support "spot-fix" mode:
  - Can process subsets of data (not just full artifacts).
  - Can accept hints/parameters from coordinator.
  - Can report confidence in their output.
- New remediation modules may be needed:
  - Vision-based text extraction for specific pages.
  - Targeted text repair for specific portions.
  - Boundary correction for specific regions.

### User Patch System
- Patches should be:
  - Input-specific (tied to source file hash or run ID).
  - Preserved across re-runs (unless input changes).
  - Mergeable with pipeline output (not just overwrites).
  - Versioned and auditable.
- Patch format:
  - JSON/JSONL files in `input/patches/<run_id>/`.
  - Specify target artifact and entry identifiers.
  - Provide replacement or correction data.

### Cost & Performance
- Coordinator adds overhead:
  - LLM calls for review and decision-making.
  - Potential re-runs of stages/modules.
  - Vision model calls for source re-reading.
- Mitigations:
  - Review only when confidence is needed (not every single entry).
  - Cache review results (don't re-review unchanged artifacts).
  - Limit remediation attempts (prevent infinite loops).
  - Cost tracking and reporting (show coordinator spend).

---

## Artifacts

### Coordinator Outputs
- `output/runs/<run_id>/coordinator/reviews/<artifact_name>_review.json`
  - Per-artifact review results with spot-checks, validation, sanity checks.
- `output/runs/<run_id>/coordinator/remediation_log.jsonl`
  - Chronological log of all remediation attempts (issue → action → outcome).
- `output/runs/<run_id>/coordinator/final_report.json`
  - Success report or issues report with problem map and suggested fixes.
- `output/runs/<run_id>/coordinator/final_report.md`
  - Human-readable summary report.
- `input/patches/<run_id>/<artifact_name>_patches.jsonl`
  - User-provided patches/corrections (if any).

### Integration Points
- Coordinator reads from: `output/runs/<run_id>/` (all artifacts).
- Coordinator invokes: modules (via driver), validation (via `validate_artifact.py`), vision models (via API).
- Coordinator writes to: `output/runs/<run_id>/coordinator/` (reviews, logs, reports).

---

## Success Metrics

### Quality Improvements
- Reduction in undetected errors reaching final artifact.
- Increase in issues caught and fixed autonomously.
- Reduction in manual intervention required.

### User Experience
- Users receive either high-confidence artifacts or clear issue reports.
- Users spend less time manually inspecting artifacts.
- Users have clear path to fix remaining issues (patches, module improvements).

### System Reliability
- Coordinator catches regressions before they propagate.
- Coordinator prevents "silent failures" (modules that run but produce garbage).
- Coordinator provides audit trail of all quality decisions.

---

## Notes

### Relationship to Existing Stories
- Builds on story-031 (pipeline redesign) — coordinator ensures quality of redesigned pipeline.
- Complements story-037 (OCR ensemble) — coordinator can decide when to use vision escalation.
- Enhances story-019 (pipeline visibility) — coordinator provides intelligent review layer.
- May inform story-011 (AI planner) — coordinator decisions could inform future pipeline planning.

### Implementation Strategy
- Start with review framework (Priority 1) — get basic artifact inspection working.
- Add simple remediation (Priority 2, subset) — re-run stages, apply text repair.
- Add user escalation (Priority 3) — get user feedback loop working.
- Enhance with vision re-reading (Priority 2, advanced) — add intelligent source re-reading.
- Polish presentation (Priority 4) — make reports actionable and clear.

### Future Enhancements
- Coordinator learns from user corrections (improves decision-making over time).
- Coordinator suggests new modules when gaps are identified.
- Coordinator can propose pipeline optimizations based on observed issues.
- Coordinator integrates with cost/perf benchmarking (story-013) to optimize remediation decisions.

---

## Work Log

### 2025-01-27: Initial story creation
- **Result**: Created comprehensive story document for agentic pipeline coordinator.
- **Scope**: Covers artifact review, autonomous remediation, user escalation, and final presentation.
- **Next**: Prioritize implementation order and identify first concrete tasks.
