# Story: Run Configuration Simplification

**Status**: Done

---

## Problem Statement

Running the pipeline is currently error-prone, especially when AI agents attempt to execute runs. Common failures include:

- **CLI argument confusion**: Wrong flag names (e.g., `--outdir` vs `--output-dir`), incorrect dashes (`--pdf` when module doesn't accept it), or mismatched parameter names
- **Resume complexity**: Resuming from a specific stage requires remembering exact stage IDs and ensuring upstream artifacts exist
- **Parameter discovery**: It's unclear which parameters are available, what their valid values are, or which are required vs optional
- **Reproducibility**: While config snapshots exist, creating a new run requires manually constructing a complex CLI command with many flags

Example failure pattern:
```
Driver was passing --pdf argument (module doesn't accept it) — fixed
Driver was using --outdir instead of --output-dir — fixed
Driver was passing --state-file and --progress-file (module doesn't accept them) — fixed
```

The current `driver.py` has 15+ CLI arguments with inconsistent naming conventions (some use `--kebab-case`, some use `--snake_case`, some use `dest=` overrides), making it difficult for both humans and AI to construct correct commands.

## Goals

- Simplify run creation and execution to reduce errors
- Make parameter discovery and validation explicit
- Support easy resumption from any stage
- Maintain backward compatibility with existing recipes and CLI usage
- Improve developer and AI agent experience

## Research Phase (Step 1)

Before implementing, research best practices for:

1. **Configuration file patterns**: JSON vs YAML vs TOML for run configs
2. **CLI simplification strategies**: 
   - Config file + minimal CLI (e.g., `docker-compose`, `kubectl apply -f`)
   - Preset/template systems (e.g., `npm init`, `cargo new`)
   - Interactive configurators (e.g., `create-react-app`)
3. **Resume/checkpoint patterns**: How other pipelines handle partial execution and resumption
4. **Parameter validation**: Schema validation for run configs (JSON Schema, Pydantic, etc.)
5. **Migration path**: How to transition existing workflows without breaking changes

### Research Tasks

- [x] Survey similar tools (ML pipelines, build systems, CI/CD tools) for configuration patterns
- [x] Evaluate JSON Schema vs Pydantic for config validation
- [x] Design config file structure that captures all current CLI arguments
- [x] Design resume/checkpoint mechanism that integrates with existing `pipeline_state.json`
- [x] Propose migration strategy for existing recipes and scripts

## Proposed Solution (Initial Idea)

**Note**: This is a starting point; research phase may suggest better alternatives.

### Run Config File Approach

1. **Create run config**: `create-run my-new-run` generates `runs/my-new-run.json` with:
   - All possible parameters (most blank/default)
   - Comments/documentation for each parameter
   - Schema validation hints
   - Template sections for common run types

2. **Edit config**: AI/human edits `runs/my-new-run.json` to fill in:
   - Recipe path
   - Input PDF
   - Output directory
   - Start/resume point (`start_from` stage ID)
   - Any overrides (settings, run-id, etc.)

3. **Execute run**: `execute-run my-new-run` reads the config and:
   - Validates all parameters
   - Constructs the correct `driver.py` command
   - Handles resume logic automatically
   - Provides clear error messages for invalid configs

### Example Config Structure

```json
{
  "$schema": "schemas/run-config.schema.json",
  "run_id": "my-new-run",
  "recipe": "configs/recipes/recipe-ff-ai-ocr-gpt51.yaml",
  "settings": "configs/settings.ff-ai-ocr-gpt51-smoke-20.yaml",
  "input": {
    "pdf": "input/06 deathtrap dungeon.pdf"
  },
  "output": {
    "dir": "output/runs/my-new-run"
  },
  "execution": {
    "start_from": null,
    "end_at": null,
    "skip_done": false,
    "force": false,
    "dry_run": false
  },
  "options": {
    "instrument": true,
    "mock": false,
    "allow_run_id_reuse": false
  },
  "overrides": {
    "run_id": null,
    "output_dir": null,
    "input_pdf": null
  }
}
```

### Alternative Approaches to Consider

1. **YAML-based configs** (matches existing recipe format)
2. **Template system** (preset configs for common scenarios)
3. **Interactive CLI** (prompts for missing required params)
4. **Hybrid approach** (config file + minimal CLI flags for overrides)

## Acceptance Criteria

- [x] Research phase completed with documented findings and recommendations
- [x] Run config file format defined and validated
- [x] `create-run <name>` command generates template config file
- [x] `execute-run <name>` command validates and executes from config
- [x] Config supports all current CLI arguments and options
- [x] Resume functionality works via `start_from` in config
- [x] Clear error messages for invalid/missing config values
- [x] Backward compatibility: existing CLI usage still works
- [x] Documentation updated with new workflow
- [x] At least one real run successfully executed via config file
- [x] AI agent can successfully create and execute runs without argument errors

## Implementation Tasks (Step 2)

### Phase 1: Research & Design
- [x] Complete research phase (see above)
- [x] Inventory current `driver.py` CLI args and map to config fields + defaults
- [x] Decide config format (YAML vs JSON) with rationale and AI-editability notes
- [x] Design config file schema (JSON Schema or Pydantic model)
- [x] Define config precedence rules (config vs CLI overrides vs env)
- [x] Design CLI commands (`create-run`, `execute-run`)
- [x] Design migration path for existing workflows

### Phase 2: Core Implementation
- [x] Implement config file schema/validator
- [x] Implement `create-run` command (template generator)
- [x] Implement `execute-run` command (config reader + driver invocation)
- [x] Add config validation with helpful error messages
- [x] Integrate with existing `driver.py` (avoid duplication)

### Phase 3: Resume/Checkpoint Support
- [x] Implement `start_from` logic in config
- [x] Validate upstream artifacts exist when resuming
- [x] Add `end_at` support for partial runs
- [x] Document resume workflow

### Phase 4: Testing & Documentation
- [x] Unit tests for config validation
- [x] Integration tests for `create-run` and `execute-run`
- [x] Test resume functionality
- [x] Update README with new workflow
- [x] Add examples to documentation

### Phase 5: Migration & Polish
- [x] Create example config files for common scenarios
- [x] Add config file templates for different run types
- [x] Update any scripts that call `driver.py` directly
- [x] Update retroactive run configuration with `skip_done: false` logic

## Technical Considerations

- **Config location**: `runs/` directory at project root (gitignored for user configs, but templates can be committed)
- **Schema validation**: Use Pydantic for Python-native validation, or JSON Schema for language-agnostic validation
- **CLI tool location**: New `tools/run_manager.py` or extend `driver.py` with subcommands?
- **State management**: Integrate with existing `pipeline_state.json` for resume detection
- **Error handling**: Provide actionable error messages (e.g., "Parameter X is required but missing. See runs/example.json for template.")

## Open Questions

- Should config files be YAML (matches recipes) or JSON (easier for AI to edit)?
- Should we support environment variable interpolation in configs?
- Should `create-run` support templates (e.g., `create-run my-run --template smoke`)?
- How to handle secrets/API keys in configs? (probably not in config, use env vars)
- Should we generate TypeScript types or JSON Schema for AI tooling?

## Work Log

<!-- Append-only log entries. -->
### 20260106-0356 — Implemented RunConfig, run_manager.py, and driver integration
- **Result:** Success.
- **Notes:** Added `RunConfig` and supporting Pydantic models to `schemas.py`. Created `tools/run_manager.py` with `create-run` and `execute-run` commands. Updated `driver.py` to support `--config` flag. Verified with unit and integration tests. Updated `README.md` with new workflow.
- **Next:** Story complete.
