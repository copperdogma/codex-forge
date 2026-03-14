---
name: check-in-diff
description: Audit git changes and, when explicitly requested, commit, sync with main, validate, and land work safely
user-invocable: true
---

# /check-in-diff [--autonomous] [--cleanup]

> Decision check: If this task affects workflow, release process, schema compatibility, or cross-cutting project behavior, read relevant ADRs in `docs/decisions/` plus any supporting runbooks, scout docs, or notes before choosing an approach. If none apply, say so explicitly.

Audit current git changes. When the user explicitly requests check-in, execute the repo's commit, sync, validate, and landing workflow.

Companion runbook: `docs/runbooks/check-in-worktree-landing.md`

## Modes

- **Audit-only (default)** — review the diff, flag risks, update `CHANGELOG.md` if needed, and propose the next step
- **Task-branch landing** — if the current branch is not `main`, commit the intended changes, push the branch, sync with latest `origin/main`, validate, then fast-forward `main`
- **Main fallback** — if the current branch is `main`, do not panic; if sync with `origin/main` requires integration work, create a temporary `codex/checkin-*` branch and resolve there instead of resolving conflicts directly on `main`

## Steps

1. **Inspect git context:**
   - `git branch --show-current`
   - `git status --short`
   - `git diff`
   - `git diff --staged`
   - `git worktree list`
   - `git fetch origin main`
   - Identify:
     - current branch
     - whether this is a task branch or `main`
     - whether another worktree already holds `main`
     - whether local changes are ahead of or diverged from `origin/main`
     - whether `origin/main` is already an ancestor of `HEAD` or integration work is required before landing

2. **Flag risks:**
   - Secrets, API keys, credentials, .env files?
   - Large binary files or build artifacts?
   - Changes outside the scope of the current story?
   - Schema changes in `schemas.py` without corresponding module or artifact updates?
   - Deleted tests or weakened assertions?
   - Dirty worktree problems or unrelated changes that should not be included in the check-in?

3. **Check alignment:**
   - Do changes match the story's task list?
   - Do changes match any relevant ADR or decision-doc constraints?
   - Are docs updated for any behavioral changes?
   - Are new files in the right locations per project structure?

4. **Ensure CHANGELOG.md is updated:**
   - Check whether `CHANGELOG.md` appears in `git diff --stat` or `git status --short`.
   - If `CHANGELOG.md` is already in the diff, verify the entry covers the current changes.
   - If `CHANGELOG.md` is absent from the diff, write an entry now:
     - Analyze the changes to determine what was added, changed, or fixed.
     - Prepend a new entry after the `# Changelog` header using Keep a Changelog format:

       ```
       ## [YYYY-MM-DD-NN] - Short summary

       ### Added
       - ...

       ### Changed
       - ...

       ### Fixed
       - ...
       ```

     - Use today's date. **Versioning (CalVer)**: `YYYY-MM-DD-NN` where `NN` is the sequence for that day. Check the previous entry to increment correctly.
     - Only include subsections that apply.
     - Include CHANGELOG.md in the staging plan.

5. **Draft commit message:**
   - Summary line (imperative, <72 chars)
   - Body: what changed and why
   - Reference story number if applicable

6. **Propose staging plan:**
   - Which files to stage (specific files, not `git add .`)
   - Any files to exclude from this commit
   - Always include CHANGELOG.md
   - Suggest splitting into multiple commits if changes are unrelated

7. **Stop here by default:**
   - If the user did not explicitly request commit, push, or landing, stop after the audit summary
   - Recommend the next step
   - If the user already explicitly requested the full check-in flow, continue without asking again

8. **Choose the execution branch before committing:**
   - **Task branch mode** — current branch is not `main`
   - **Main direct mode** — current branch is `main` and `origin/main` is already an ancestor of `HEAD`
   - **Main integration mode** — current branch is `main` and integration with `origin/main` is required; create a temporary `codex/checkin-<timestamp>` branch before staging or committing

9. **Commit intended changes on the execution branch:**
   - Stage intended files only
   - Commit them on the chosen execution branch
   - If the execution branch is not `main`, push it now
   - If the execution branch is `main`, keep it local until validation succeeds

10. **Sync the execution branch with latest `origin/main` when needed:**
   - If the execution branch is not `main`, prefer `git rebase origin/main`
   - If rebase is unsuitable, merge `origin/main` into the execution branch instead
   - If the execution branch is `main` in Main direct mode, skip integration and move to validation
   - Never resolve integration conflicts directly on `main`

11. **Resolve conflicts on the non-main execution branch:**
   - Record which files conflicted
   - If conflicts cannot be resolved cleanly, stop and report

12. **Run relevant validation after integration:**
   - If Python code changed: `make test` and `make lint`
   - If agent tooling changed: `make skills-check`
   - If pipeline behavior changed: run `make smoke` or the narrowest real `driver.py` path that proves the change, then inspect artifacts
   - If validation fails, stop and report

13. **Land the validated branch tip onto `main`:**
   - If the validated branch is `main`, push updated `main`
   - If the validated branch is not `main`:
     - Update local `main` from `origin/main`
     - If another worktree already has `main` checked out, use git-only commands there for the landing step and do not edit project files in that sibling worktree
     - Fast-forward only: `git merge --ff-only <validated-branch>`
     - Push updated `main`
   - Never create a merge commit into `main`

14. **Optional cleanup:**
   - Delete the finished branch or remove its worktree only if the user explicitly requested cleanup

15. **Report results:**
   - branch checked in
   - whether rebase or merge-from-main was used
   - whether conflicts occurred
   - which files had conflicts, if any
   - whether tests, lint, skills checks, or pipeline smoke passed
   - whether `main` was fast-forwarded and pushed
   - whether branch or worktree cleanup was performed

## Guardrails

- NEVER commit or push without explicit request from the user
- NEVER suggest committing secrets, credentials, .env files, or build artifacts
- NEVER use `git add .` or `git add -A` — always stage specific files
- NEVER do a non-fast-forward merge into `main`
- NEVER resolve integration conflicts directly on `main`
- NEVER push `main` before validation when using the main fallback path
- NEVER fail just because the current branch is `main`; use the main fallback path instead
- If the branch cannot be cleanly integrated and validated, stop and report
- Flag any changes that look unintentional or outside current story scope
