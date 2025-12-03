# Story: FF Ending Detection Verification

**Status**: Open  
**Created**: 2025-12-02  

## Goal
Use a reference list of confirmed endgame sections to verify the generic pipeline’s ending detection. **Do not tune the pipeline to this list; use it only for evaluation.** Improvements must remain generic.

## Reference (for verification only)
Confirmed endgame sections (manual ground truth):
`2,3,4,7,8,17,19,34,44,61,70,85,96,101,116,140,193,219,233,255,268,272,276,317,325,329,333,334,347,359,366,372`

## Tasks
- [ ] Add an evaluation step that reports precision/recall of detected end_game sections against the reference list (no tuning to the list).
- [ ] Document any false positives/negatives and propose generic system changes (not list-specific hacks).
- [ ] Keep the reference list isolated (no code conditioning or prompt hints based on these IDs).

## Work Log
- 2025-12-02 — Story created; imported verification list; rule: verification-only, no tuning to IDs.
