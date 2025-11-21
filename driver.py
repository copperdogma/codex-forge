import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Dict, Any

import yaml

from utils import ensure_dir
from validate_artifact import SCHEMA_MAP
from utils import read_jsonl, save_jsonl


DEFAULT_OUTPUTS = {
    "extract": "pages_raw.jsonl",
    "clean": "pages_clean.jsonl",
    "portionize": "window_hypotheses.jsonl",
    "consensus": "portions_locked.jsonl",
    "dedupe": "portions_locked_dedup.jsonl",
    "normalize": "portions_locked_normalized.jsonl",
    "resolve": "portions_resolved.jsonl",
    "build": "portions_final_raw.json",
    "enrich": "portions_enriched.jsonl",
}


def load_registry(path: str) -> Dict[str, Any]:
    # If path is a directory, scan for module.yaml files; else treat as single registry yaml
    if os.path.isdir(path):
        modules = {}
        for root, dirs, files in os.walk(path):
            if "module.yaml" in files:
                with open(os.path.join(root, "module.yaml"), "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    mid = data["module_id"]
                    modules[mid] = data
        return {"modules": modules}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_recipe(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def update_state(state_path: str, stage_name: str, status: str, artifact: str):
    state = {}
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}
    stages = state.get("stages", {})
    stages[stage_name] = {
        "status": status,
        "artifact": artifact,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    state["stages"] = stages
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def build_command(entrypoint: str, params: Dict[str, Any], outputs: Dict[str, str], stage: str, run_dir: str,
                  recipe_input: Dict[str, Any]) -> (str, list, str):
    """
    Returns (artifact_path, cmd_list, cwd)
    """
    script, func = (entrypoint.split(":") + [None])[:2]
    script_path = os.path.join(os.getcwd(), script)
    artifact_name = outputs.get(stage, f"{stage}.jsonl")
    artifact_path = os.path.join(run_dir, artifact_name)

    cmd = [sys.executable, script_path]

    flags_added = set()

    # Standard parameter conveniences by stage
    if stage == "extract":
        if "pdf" in recipe_input:
            cmd += ["--pdf", recipe_input["pdf"]]; flags_added.add("--pdf")
        if "images" in recipe_input:
            cmd += ["--images", recipe_input["images"]]; flags_added.add("--images")
        cmd += ["--outdir", run_dir]; flags_added.add("--outdir")
    elif stage == "clean":
        cmd += ["--pages", os.path.join(run_dir, outputs["extract"])]
        cmd += ["--out", artifact_path]
        flags_added.update({"--pages", "--out"})
    elif stage == "portionize":
        cmd += ["--pages", os.path.join(run_dir, outputs.get("clean", "pages_clean.jsonl"))]
        cmd += ["--out", artifact_path]
        flags_added.update({"--pages", "--out"})
    elif stage == "consensus":
        cmd += ["--hypotheses", os.path.join(run_dir, outputs.get("portionize", "window_hypotheses.jsonl"))]
        cmd += ["--out", artifact_path]
        flags_added.update({"--hypotheses", "--out"})
    elif stage == "dedupe":
        cmd += ["--input", os.path.join(run_dir, outputs.get("consensus", "portions_locked.jsonl"))]
        cmd += ["--out", artifact_path]
        flags_added.update({"--input", "--out"})
    elif stage == "normalize":
        cmd += ["--input", os.path.join(run_dir, outputs.get("dedupe", "portions_locked_dedup.jsonl"))]
        cmd += ["--out", artifact_path]
        flags_added.update({"--input", "--out"})
    elif stage == "resolve":
        cmd += ["--input", os.path.join(run_dir, outputs.get("normalize", "portions_locked_normalized.jsonl"))]
        cmd += ["--out", artifact_path]
        flags_added.update({"--input", "--out"})
    elif stage == "build":
        cmd += [
            "--pages",
            os.path.join(run_dir, outputs.get("clean", "pages_clean.jsonl")),
            "--portions",
            os.path.join(run_dir, outputs.get("resolve", "portions_resolved.jsonl")),
            "--out",
            artifact_path,
        ]
        flags_added.update({"--pages", "--portions", "--out"})
    elif stage == "enrich":
        # placeholder; enrichment not implemented
        pass

    # Additional params from recipe (skip flags already added)
    # Additional params from recipe (skip flags already added)
    seen_flags = set(flags_added)
    for key, val in (params or {}).items():
        flag = f"--{key}"
        if flag in seen_flags:
            continue
        if isinstance(val, bool):
            if val:
                cmd.append(flag); seen_flags.add(flag)
        else:
            cmd += [flag, str(val)]; seen_flags.add(flag)

    return artifact_path, cmd, os.getcwd()


def stamp_artifact(artifact_path: str, schema_name: str, module_id: str, run_id: str):
    if schema_name not in SCHEMA_MAP:
        return
    model_cls = SCHEMA_MAP[schema_name]
    rows = []
    for row in read_jsonl(artifact_path):
        row.setdefault("schema_version", schema_name)
        row.setdefault("module_id", module_id)
        row.setdefault("run_id", run_id)
        row.setdefault("created_at", datetime.utcnow().isoformat() + "Z")
        rows.append(model_cls(**row).dict())
    save_jsonl(artifact_path, rows)
    print(f"[stamp] {artifact_path} stamped with {schema_name} ({len(rows)} rows)")


def mock_clean(run_dir: str, outputs: Dict[str, str], module_id: str, run_id: str):
    pages_path = os.path.join(run_dir, outputs["extract"])
    out_path = os.path.join(run_dir, outputs["clean"])
    rows = []
    for row in read_jsonl(pages_path):
        row_out = {
            "schema_version": "clean_page_v1",
            "module_id": module_id,
            "run_id": run_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "page": row["page"],
            "image": row.get("image"),
            "raw_text": row.get("text", ""),
            "clean_text": row.get("text", ""),
            "confidence": 1.0,
        }
        rows.append(row_out)
    save_jsonl(out_path, rows)
    print(f"[mock] clean wrote {len(rows)} rows to {out_path}")
    return out_path


def mock_portionize(run_dir: str, outputs: Dict[str, str], module_id: str, run_id: str):
    pages_path = os.path.join(run_dir, outputs["clean"])
    out_path = os.path.join(run_dir, outputs["portionize"])
    rows = []
    for row in read_jsonl(pages_path):
        page = row["page"]
        hyp = {
            "schema_version": "portion_hyp_v1",
            "module_id": module_id,
            "run_id": run_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "portion_id": f"P{page:03d}",
            "page_start": page,
            "page_end": page,
            "title": None,
            "type": "page",
            "confidence": 1.0,
            "notes": "mock",
            "source_window": [page],
            "source_pages": [page],
            "continuation_of": None,
            "continuation_confidence": None,
        }
        rows.append(hyp)
    save_jsonl(out_path, rows)
    print(f"[mock] portionize wrote {len(rows)} rows to {out_path}")
    return out_path


def mock_consensus(run_dir: str, outputs: Dict[str, str], module_id: str, run_id: str):
    in_path = os.path.join(run_dir, outputs["portionize"])
    out_path = os.path.join(run_dir, outputs["consensus"])
    rows = []
    for row in read_jsonl(in_path):
        locked = {
            "schema_version": "locked_portion_v1",
            "module_id": module_id,
            "run_id": run_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "portion_id": row.get("portion_id") or f"P{row['page_start']:03d}",
            "page_start": row["page_start"],
            "page_end": row["page_end"],
            "title": row.get("title"),
            "type": row.get("type"),
            "confidence": row.get("confidence", 1.0),
            "source_images": [],
        }
        rows.append(locked)
    save_jsonl(out_path, rows)
    print(f"[mock] consensus wrote {len(rows)} rows to {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Pipeline driver that executes a recipe and module registry.")
    parser.add_argument("--recipe", required=True, help="Path to recipe yaml")
    parser.add_argument("--registry", default="modules", help="Module registry directory or yaml")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running")
    parser.add_argument("--skip-done", action="store_true", help="Skip stages marked done in pipeline_state.json")
    parser.add_argument("--no-validate", action="store_true", help="Skip validation step after stamping")
    parser.add_argument("--force", action="store_true", help="Run stages even if artifacts already exist (overwrites)")
    parser.add_argument("--mock", action="store_true", help="Use mock implementations for LLM stages to avoid API calls")
    args = parser.parse_args()

    registry = load_registry(args.registry)["modules"]
    recipe = load_recipe(args.recipe)

    run_id = recipe.get("run_id")
    run_dir = recipe.get("output_dir", os.path.join("output", "runs", run_id))
    ensure_dir(run_dir)

    state_path = os.path.join(run_dir, "pipeline_state.json")

    outputs = dict(DEFAULT_OUTPUTS)  # copy
    stages = recipe.get("stages", [])
    for stage_conf in stages:
        stage = stage_conf["stage"]
        module_id = stage_conf["module"]
        params = stage_conf.get("params", {})
        if module_id not in registry:
            raise SystemExit(f"Module {module_id} not found in registry")
        entry = registry[module_id]
        entrypoint = entry["entrypoint"]
        out_schema = entry.get("output_schema")
        # Skip if already done and skip-done requested (state + artifact exists)
        if args.skip_done and os.path.exists(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                st = state.get("stages", {}).get(stage)
                if st and st.get("status") == "done" and os.path.exists(st.get("artifact", "")) and not args.force:
                    print(f"[skip] {stage} already done per state and artifact present")
                    continue
            except Exception:
                pass

        # merge default params from module
        params = {**entry.get("default_params", {}), **params}

        artifact_path, cmd, cwd = build_command(entrypoint, params, outputs, stage, run_dir, recipe.get("input", {}))

        if args.dry_run:
            print(f"[dry-run] {stage} -> {' '.join(cmd)}")
            continue

        # Mock shortcuts for expensive stages
        if args.mock and stage == "clean":
            artifact_path = mock_clean(run_dir, outputs, module_id, run_id)
            update_state(state_path, stage, "done", artifact_path)
            continue
        if args.mock and stage == "portionize":
            artifact_path = mock_portionize(run_dir, outputs, module_id, run_id)
            update_state(state_path, stage, "done", artifact_path)
            continue
        if args.mock and stage == "consensus":
            artifact_path = mock_consensus(run_dir, outputs, module_id, run_id)
            update_state(state_path, stage, "done", artifact_path)
            continue

        print(f"[run] {stage} ({module_id})")
        result = subprocess.run(cmd, cwd=cwd)
        if result.returncode != 0:
            update_state(state_path, stage, "failed", artifact_path)
            raise SystemExit(f"Stage {stage} failed with code {result.returncode}")
        # Stamp and validate if schema known
        if out_schema:
            stamp_artifact(artifact_path, out_schema, module_id, run_id)
            if not args.no_validate:
                model_cls = SCHEMA_MAP.get(out_schema)
                if model_cls:
                    errors = 0
                    total = 0
                    for row in read_jsonl(artifact_path):
                        total += 1
                        try:
                            model_cls(**row)
                        except Exception as e:
                            errors += 1
                            print(f"[validate error] {artifact_path} row {total}: {e}")
                    if errors:
                        update_state(state_path, stage, "failed", artifact_path)
                        raise SystemExit(f"Validation failed for {artifact_path}: {errors} errors")
        update_state(state_path, stage, "done", artifact_path)

    print("Recipe complete.")


if __name__ == "__main__":
    main()
