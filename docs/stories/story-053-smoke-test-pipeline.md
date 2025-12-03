# Story: Pipeline Smoke Test (Static Sample, No External Calls)

**Status**: Open  
**Created**: 2025-12-02  

## Goal
Add a repeatable smoke test that runs the full pipeline on a static image sample set, with all external API calls mocked, to catch integration breakages early.

## Success Criteria
- [ ] Static sample images (user-provided) checked into testdata or referenced path.
- [ ] Smoke test script/target runs pipeline stages end-to-end (intake → headers → loops → build → validate) with mocked APIs (OCR/LLM).
- [ ] Test asserts pipeline completes without errors and produces expected stub artifacts.
- [ ] Document how to run the smoke locally and in CI.

## Tasks
- [ ] Add static sample image set path (to be provided) and minimal pagelines fixture.
- [ ] Mock external API calls (OCR/LLM) for the smoke path; ensure determinism.
- [ ] Create a smoke test target (Makefile or script) that invokes the pipeline with mocks and fails on stage errors.
- [ ] Integrate into CI (or document manual invocation) and add pass/fail reporting.

## Work Log
- 2025-12-02 — Story created; awaiting sample images; scope set to mocked end-to-end smoke.
