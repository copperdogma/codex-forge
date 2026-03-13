---
name: validate
description: Validate work against requirements using git diff analysis and graded scoring
user-invocable: true
---

# Validate Work Against Requirements

Thoroughly analyze what was done and how it compares to the original instructions using git diff and file analysis.

## Analysis Process

1. **Review Changes**
  Please review ALL local changes, including untracked files.
  Use these commands and include them in your analysis:

  git status --short
  git diff --stat
  git diff
  git ls-files --others --exclude-standard

  For any untracked files, open them and include them in the review. Treat untracked files as part of the change set.

2. **Examine Modified Files**
   - Open each changed file to understand what was implemented
   - Compare against original requirements/story/documentation
   - Check for completeness, quality, and adherence to specifications

2.5 **If there is a known story/ticket, validate against it**
   - **When a story is "known"**: the user provided a story path/ID/title, or a single story file is clearly in-scope (e.g., `docs/stories/story-*.md`) for the work being validated.
   - Open the story/ticket doc and extract:
     - `## Success Criteria` / `## Acceptance Criteria` / `## Requirements` (as applicable)
     - `## Tasks` checklist items (look for `- [ ]` / `- [x]`)
   - In the report, include a **Story Validation** section that:
     - Lists each story requirement/checklist item as **Met / Partial / Unmet** with evidence.
     - Explicitly calls out **all Unmet** (and Partial) items as "Remaining Story Gaps" with concrete next steps.
     - Suggests which story checkboxes appear ready to check off, and asks the user if they want the AI to apply those edits.
     - If the delivered slice is coherent but the remaining gaps have clearly been split into other stories, explicitly say whether the current story should be:
       - **Rescoped then closed**
       - **Kept open**
       - **Marked blocked**
     - Do not end in an ambiguous "not done" state without a firm recommendation.

3. **Score Each Requirement**
   - **A**: Fully implemented, high quality, exceeds expectations
   - **B**: Implemented well, minor improvements possible
   - **C**: Implemented but has notable issues or missing elements
   - **D**: Partially implemented or significant problems
   - **F**: Not implemented or completely incorrect

## Project Validation Checklist

### Architecture & Design
- [ ] Clear boundaries and responsibilities between modules/services
- [ ] Data contracts and interfaces documented and followed
- [ ] Error handling strategy consistent across layers
- [ ] Observability in place (logging/metrics/tracing) for critical paths

### Code Quality
- [ ] Code is readable, idiomatic, and follows project style conventions
- [ ] Dependencies are pinned/approved and minimal
- [ ] Memory/resource usage reasonable; no obvious leaks
- [ ] Security practices observed (input validation, secrets handling, authz)

### Functionality & UX
- [ ] Core requirements implemented as specified
- [ ] User interactions are clear, accessible, and responsive where applicable
- [ ] Integration between components/services is verified
- [ ] Edge/error cases handled gracefully with actionable errors

### Performance & Reliability
- [ ] Latency/throughput meets expectations or budgeted limits
- [ ] Concurrency/race conditions considered; retries/backoff where needed
- [ ] Start-up/shutdown, migrations, and rollbacks validated

### Testing & Validation
- [ ] Unit/integration/e2e tests cover happy path and key edge cases
- [ ] CI workflows are green; flaky tests identified or quarantined
- [ ] Manual validation notes captured where automation lacks coverage
- [ ] Docs updated (README, ADRs, API docs, changelog)

## Grading Criteria

### Grade A (90-100%)
- **Implementation**: Complete, exceeds requirements
- **Quality**: Excellent code quality, follows best practices
- **Testing**: Thoroughly tested, handles edge cases
- **Documentation**: Clear, comprehensive documentation
- **Innovation**: Shows creative problem-solving

### Grade B (80-89%)
- **Implementation**: Complete, meets all requirements
- **Quality**: Good code quality, minor improvements possible
- **Testing**: Well tested, some edge cases could be better
- **Documentation**: Good documentation, could be more detailed
- **Innovation**: Solid implementation, some creative elements

### Grade C (70-79%)
- **Implementation**: Mostly complete, minor gaps
- **Quality**: Adequate code quality, some areas need improvement
- **Testing**: Basic testing, some issues not covered
- **Documentation**: Basic documentation, could be clearer
- **Innovation**: Standard implementation, limited creativity

### Grade D (60-69%)
- **Implementation**: Partially complete, significant gaps
- **Quality**: Poor code quality, needs major improvements
- **Testing**: Limited testing, many issues not addressed
- **Documentation**: Minimal documentation, unclear
- **Innovation**: Basic implementation, no creative elements

### Grade F (Below 60%)
- **Implementation**: Incomplete or incorrect
- **Quality**: Very poor code quality, major problems
- **Testing**: No testing or completely inadequate
- **Documentation**: No documentation or completely unclear
- **Innovation**: No evidence of problem-solving

## Detailed Analysis Template

For each requirement, provide:

### Requirement: [Description]
- **Status**: [Implemented/Partially Implemented/Not Implemented]
- **Grade**: [A/B/C/D/F]
- **Evidence**: [Specific code/files that demonstrate implementation]
- **Quality Assessment**: [Code quality, error handling, performance]
- **Improvement Suggestions**: [If not A grade, specific recommendations]

### Example Analysis

#### Requirement: User authentication and session management
- **Status**: Implemented
- **Grade**: B
- **Evidence**: `services/auth/service.ts` session issuance and renewal; `web/routes/login.ts` form handling
- **Quality Assessment**: Follows project patterns; session expiry tested, but no CSRF protection on form POST
- **Improvement Suggestions**:
  - Add CSRF token validation for form submissions
  - Add rate limiting for login endpoint
  - Expand tests to cover password reset and simultaneous session revocation

## Final Scorecard

### Overall Grade: [A/B/C/D/F]

### Summary
- **Requirements Met**: X of Y requirements fully implemented
- **If a story/ticket was validated**: include a 1–2 line summary of whether the story is **Done / Not Done**, and name the remaining gaps.
- **If a story/ticket was validated**: include a one-line **Closure Recommendation**:
  - `Close now`
  - `Rescope then close`
  - `Keep open`
  - `Mark blocked`
- **Quality Score**: [High/Medium/Low] code quality
- **Testing Coverage**: [Comprehensive/Partial/Minimal]
- **Documentation**: [Excellent/Good/Adequate/Poor]

### Critical Issues (if any)
1. [Issue 1]: [Description and impact]
2. [Issue 2]: [Description and impact]

**Note:** If a story/ticket was validated, treat **Unmet** (and important **Partial**) story requirements as critical issues unless explicitly deferred. Critical issues should summarize "where we are", why the story is not done, and include the concrete next step(s) required to close each gap.

### Recommendations for Improvement
1. [Priority 1]: [Specific actionable improvement]
2. [Priority 2]: [Specific actionable improvement]
3. [Priority 3]: [Specific actionable improvement]

### Next Steps
- End with a single numbered plan the user can approve.
- When a story is not ready to close, the plan must start with the **recommended disposition** of the story:
  1) `Rescope then close`, `Keep open`, or `Mark blocked`
  2) Concrete edits needed to support that recommendation
  3) Remaining implementation work, if any
  4) Run tests/smoke and inspect outputs
  5) Re-validate or close

Ask one direct question:
- If recommending closure: `"Do you want me to apply that recommendation?"`
- If recommending more implementation first: `"Do you want me to proceed with these next steps?"`

Default behavior:
- If the implemented slice is coherent and the remaining gaps are explicitly moved to follow-up stories, prefer **`Rescope then close`** over leaving the story hanging in `In Progress`.
- Never silently weaken requirements. The report must say exactly what would be rescoped and why.


## ADDITIONAL NOTES FROM USER
(there may be none)

$ARGUMENTS
