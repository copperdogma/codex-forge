import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

from utils import ensure_dir, ProgressLogger, append_jsonl
from validate_artifact import SCHEMA_MAP
from utils import read_jsonl, save_jsonl


DEFAULT_OUTPUTS = {
    "extract": "pages_raw.jsonl",
    "clean": "pages_clean.jsonl",
    "portionize": "window_hypotheses.jsonl",
    "adapter": "adapter_out.jsonl",
    "consensus": "portions_locked.jsonl",
    "dedupe": "portions_locked_dedup.jsonl",
    "normalize": "portions_locked_normalized.jsonl",
    "resolve": "portions_resolved.jsonl",
    "build": "portions_final_raw.json",
    "enrich": "portions_enriched.jsonl",
}

def _artifact_name_for_stage(stage_id: str, stage_type: str, outputs_map: Dict[str, str]) -> str:
    return outputs_map.get(stage_id) or DEFAULT_OUTPUTS.get(stage_type, f"{stage_id}.jsonl")


def _is_dag_recipe(stages: List[Dict[str, Any]]) -> bool:
    return any("id" in s or "needs" in s or "inputs" in s for s in stages)


def _toposort(graph: Dict[str, Set[str]]) -> List[str]:
    indeg = {n: 0 for n in graph}
    for n, deps in graph.items():
        for d in deps:
            indeg[n] += 1
    queue = [n for n, deg in indeg.items() if deg == 0]
    ordered: List[str] = []
    while queue:
        current = queue.pop(0)
        ordered.append(current)
        for neighbor, deps in graph.items():
            if current in deps:
                indeg[neighbor] -= 1
                if indeg[neighbor] == 0:
                    queue.append(neighbor)
    if len(ordered) != len(graph):
        raise SystemExit("Cycle detected in recipe stages")
    return ordered


def build_plan(recipe: Dict[str, Any], registry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a plan for either DAG or legacy linear recipes.
    Returns dict with nodes (id -> node dict) and topo list order.
    Each node: {id, stage, module, needs, params, inputs, artifact_name, entrypoint, input_schema, output_schema}
    """
    stages = recipe.get("stages", [])
    outputs_map = recipe.get("outputs", {}) or {}
    nodes: Dict[str, Any] = {}

    linear = not _is_dag_recipe(stages)
    prior_id: Optional[str] = None

    for idx, conf in enumerate(stages):
        stage_type = conf["stage"]
        stage_id = conf.get("id") or stage_type
        if stage_id in nodes:
            raise SystemExit(f"Duplicate stage id '{stage_id}' in recipe")
        module_id = conf["module"]
        if module_id not in registry:
            raise SystemExit(f"Module {module_id} not found in registry")
        entry = registry[module_id]
        if entry.get("stage") and entry["stage"] != stage_type:
            raise SystemExit(f"Stage '{stage_type}' for id '{stage_id}' mismatches module stage '{entry['stage']}'")
        needs = conf.get("needs")
        if needs is None:
            needs = [prior_id] if prior_id else []
        needs = [n for n in needs if n]  # drop Nones
        inputs = conf.get("inputs", {})
        params = {**entry.get("default_params", {}), **(conf.get("params") or {})}
        artifact_name = _artifact_name_for_stage(stage_id, stage_type, outputs_map)
        nodes[stage_id] = {
            "id": stage_id,
            "stage": stage_type,
            "module": module_id,
            "needs": needs,
            "params": params,
            "inputs": inputs,
            "artifact_name": artifact_name,
            "entrypoint": entry["entrypoint"],
            "input_schema": entry.get("input_schema"),
            "output_schema": entry.get("output_schema"),
        }
        prior_id = stage_id if linear else prior_id

    # validate needs references
    for node in nodes.values():
        for dep in node["needs"]:
            if dep not in nodes:
                raise SystemExit(f"Stage {node['id']} needs unknown stage '{dep}'")

    graph = {sid: set(n["needs"]) for sid, n in nodes.items()}
    topo = _toposort(graph) if graph else []
    return {"nodes": nodes, "topo": topo}


def validate_plan_schemas(plan: Dict[str, Any]) -> None:
    """
    Lightweight schema compatibility validation: for each stage with an input_schema,
    ensure at least one dependency produces that schema. Build stage is allowed to have
    mixed schemas as long as one matches the declared input_schema.
    """
    nodes = plan["nodes"]
    for sid, node in nodes.items():
        deps = node.get("needs", [])
        if not deps:
            continue
        input_schema = node.get("input_schema")
        if not input_schema:
            continue
        dep_schemas = [nodes[d]["output_schema"] for d in deps if d in nodes]
        if not dep_schemas:
            raise SystemExit(f"Stage {sid} has input_schema {input_schema} but no dependencies listed")
        if input_schema not in dep_schemas:
            # build stage can accept pages + portions; allow mismatch as long as one matches
            if node["stage"] == "build" and input_schema in dep_schemas:
                continue
            raise SystemExit(f"Schema mismatch: {sid} expects {input_schema} but deps provide {dep_schemas}")


def artifact_schema_matches(path: str, expected: Optional[str]) -> bool:
    if not expected or not os.path.exists(path):
        return False
    try:
        count = 0
        for row in read_jsonl(path):
            schema = row.get("schema_version")
            if schema:
                return schema == expected
            count += 1
            if count >= 5:
                break
    except Exception:
        return False
    return False


def concat_dedupe_jsonl(inputs: List[str], output: str, key_field: str = "portion_id") -> None:
    """
    Concatenate multiple JSONL files into output with stable order and de-dupe by key_field (fallback to full line).
    """
    seen = set()
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as out_f:
        for path in inputs:
            if not os.path.exists(path):
                raise SystemExit(f"Missing input for merge: {path}")
            with open(path, "r", encoding="utf-8") as in_f:
                for line in in_f:
                    if not line.strip():
                        continue
                    key = None
                    try:
                        obj = json.loads(line)
                        key = obj.get(key_field)
                    except Exception:
                        pass
                    key = key or line
                    if key in seen:
                        continue
                    seen.add(key)
                    out_f.write(line.rstrip("\n") + "\n")


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


def update_state(state_path: str, progress_path: str, stage_name: str, status: str, artifact: str, run_id: str = None,
                 module_id: str = None, schema_version: str = None):
    logger = ProgressLogger(state_path=state_path, progress_path=progress_path, run_id=run_id)
    return logger.log(stage_name, status, artifact=artifact, module_id=module_id, schema_version=schema_version)


def build_command(entrypoint: str, params: Dict[str, Any], stage_conf: Dict[str, Any], run_dir: str,
                  recipe_input: Dict[str, Any], state_path: str, progress_path: str, run_id: str,
                  artifact_inputs: Dict[str, str]) -> (str, list, str):
    """
    Returns (artifact_path, cmd_list, cwd)
    """
    script, func = (entrypoint.split(":") + [None])[:2]
    script_path = os.path.join(os.getcwd(), script)
    artifact_name = stage_conf["artifact_name"]
    artifact_path = os.path.join(run_dir, artifact_name)

    cmd = [sys.executable, script_path]

    flags_added = set()

    # Standard parameter conveniences by stage
    if stage_conf["stage"] == "extract":
        if "pdf" in recipe_input:
            cmd += ["--pdf", recipe_input["pdf"]]; flags_added.add("--pdf")
        if "images" in recipe_input:
            cmd += ["--images", recipe_input["images"]]; flags_added.add("--images")
        cmd += ["--outdir", run_dir]; flags_added.add("--outdir")
    elif stage_conf["stage"] == "clean":
        pages_path = artifact_inputs.get("pages") or artifact_inputs.get("input")
        if not pages_path:
            raise SystemExit(f"Stage {stage_conf['id']} missing pages input")
        cmd += ["--pages", pages_path]
        cmd += ["--out", artifact_path]
        flags_added.update({"--pages", "--out"})
    elif stage_conf["stage"] == "portionize":
        pages_path = artifact_inputs.get("pages") or artifact_inputs.get("input")
        if not pages_path:
            raise SystemExit(f"Stage {stage_conf['id']} missing pages input")
        cmd += ["--pages", pages_path]
        cmd += ["--out", artifact_path]
        flags_added.update({"--pages", "--out"})
    elif stage_conf["stage"] == "adapter":
        input_paths = artifact_inputs.get("inputs")
        if not input_paths:
            raise SystemExit(f"Stage {stage_conf['id']} missing adapter inputs")
        cmd += ["--inputs", *input_paths, "--out", artifact_path]
        if "dedupe_field" in params:
            cmd += ["--dedupe_field", str(params["dedupe_field"])]
            flags_added.add("--dedupe_field")
        flags_added.update({"--inputs", "--out"})
    elif stage_conf["stage"] == "consensus":
        hyp_path = artifact_inputs.get("hypotheses") or artifact_inputs.get("input")
        if not hyp_path:
            raise SystemExit(f"Stage {stage_conf['id']} missing hypotheses input")
        cmd += ["--hypotheses", hyp_path]
        cmd += ["--out", artifact_path]
        flags_added.update({"--hypotheses", "--out"})
    elif stage_conf["stage"] == "dedupe":
        in_path = artifact_inputs.get("input")
        if not in_path:
            raise SystemExit(f"Stage {stage_conf['id']} missing input")
        cmd += ["--input", in_path]
        cmd += ["--out", artifact_path]
        flags_added.update({"--input", "--out"})
    elif stage_conf["stage"] == "normalize":
        in_path = artifact_inputs.get("input")
        if not in_path:
            raise SystemExit(f"Stage {stage_conf['id']} missing input")
        cmd += ["--input", in_path]
        cmd += ["--out", artifact_path]
        flags_added.update({"--input", "--out"})
    elif stage_conf["stage"] == "resolve":
        in_path = artifact_inputs.get("input")
        if not in_path:
            raise SystemExit(f"Stage {stage_conf['id']} missing input")
        cmd += ["--input", in_path]
        cmd += ["--out", artifact_path]
        flags_added.update({"--input", "--out"})
    elif stage_conf["stage"] == "build":
        pages_path = artifact_inputs.get("pages")
        portions_path = artifact_inputs.get("portions")
        if not pages_path or not portions_path:
            raise SystemExit(f"Stage {stage_conf['id']} missing build inputs (pages/portions)")
        cmd += ["--pages", pages_path, "--portions", portions_path, "--out", artifact_path]
        flags_added.update({"--pages", "--portions", "--out"})
    elif stage_conf["stage"] == "enrich":
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

    # Progress/state plumbing (skip for adapter modules that don't accept these flags)
    if stage_conf["stage"] not in {"adapter"}:
        cmd += ["--state-file", state_path, "--progress-file", progress_path]
        if run_id:
            cmd += ["--run-id", run_id]

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


def register_run(run_id: str, run_dir: str, recipe: Dict[str, Any]):
    if not run_id:
        return
    manifest_path = os.path.join("output", "run_manifest.jsonl")
    ensure_dir(os.path.dirname(manifest_path))
    existing = set()
    if os.path.exists(manifest_path):
        try:
            for row in read_jsonl(manifest_path):
                if row.get("run_id"):
                    existing.add(row["run_id"])
        except Exception:
            existing = set()
    if run_id in existing:
        return
    entry = {
        "run_id": run_id,
        "path": run_dir,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "recipe": recipe.get("name") or os.path.basename(recipe.get("recipe_path", "")) or None,
        "input": recipe.get("input", {})
    }
    append_jsonl(manifest_path, entry)


def main():
    parser = argparse.ArgumentParser(description="Pipeline driver that executes a recipe and module registry.")
    parser.add_argument("--recipe", required=True, help="Path to recipe yaml")
    parser.add_argument("--registry", default="modules", help="Module registry directory or yaml")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running")
    parser.add_argument("--skip-done", action="store_true", help="Skip stages marked done in pipeline_state.json")
    parser.add_argument("--no-validate", action="store_true", help="Skip validation step after stamping")
    parser.add_argument("--force", action="store_true", help="Run stages even if artifacts already exist (overwrites)")
    parser.add_argument("--mock", action="store_true", help="Use mock implementations for LLM stages to avoid API calls")
    parser.add_argument("--dump-plan", action="store_true", help="Print resolved DAG plan and exit")
    args = parser.parse_args()

    registry = load_registry(args.registry)["modules"]
    recipe = load_recipe(args.recipe)
    recipe["recipe_path"] = args.recipe

    run_id = recipe.get("run_id")
    run_dir = recipe.get("output_dir", os.path.join("output", "runs", run_id))
    ensure_dir(run_dir)
    register_run(run_id, run_dir, recipe)

    state_path = os.path.join(run_dir, "pipeline_state.json")
    progress_path = os.path.join(run_dir, "pipeline_events.jsonl")
    logger = ProgressLogger(state_path=state_path, progress_path=progress_path, run_id=run_id)

    plan = build_plan(recipe, registry)
    validate_plan_schemas(plan)
    if args.dump_plan:
        print(json.dumps({"topo": plan["topo"], "nodes": plan["nodes"]}, indent=2))
        return

    artifact_index: Dict[str, Dict[str, str]] = {}

    for stage_id in plan["topo"]:
        node = plan["nodes"][stage_id]
        stage = node["stage"]
        module_id = node["module"]
        entrypoint = node["entrypoint"]
        out_schema = node.get("output_schema")

        # Skip if already done and skip-done requested (state + artifact exists)
        if args.skip_done and os.path.exists(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                st = state.get("stages", {}).get(stage_id)
                if st and st.get("status") == "done" and os.path.exists(st.get("artifact", "")) and not args.force:
                    schema_ok = True
                    if out_schema:
                        recorded = st.get("schema_version")
                        file_match = artifact_schema_matches(st.get("artifact", ""), out_schema)
                        schema_ok = (recorded == out_schema) and file_match
                    if schema_ok:
                        print(f"[skip] {stage_id} already done per state and artifact present")
                        logger.log(stage_id, "skipped", artifact=st.get("artifact"), module_id=module_id,
                                   message="Skipped due to --skip-done")
                        artifact_index[stage_id] = {"path": st.get("artifact"), "schema": st.get("schema_version")}
                        continue
                    else:
                        print(f"[redo] {stage_id} redo due to schema mismatch or unreadable artifact")
            except Exception:
                pass

        # Input resolution
        artifact_inputs: Dict[str, str] = {}
        needs = node.get("needs", [])
        if stage in {"clean", "portionize", "consensus", "dedupe", "normalize", "resolve", "build", "adapter"}:
            # adapters fall-through below
            if stage == "build":
                inputs_map = node.get("inputs", {}) or {}
                pages_from = inputs_map.get("pages") or (needs[0] if needs else None)
                portions_from = inputs_map.get("portions") or (needs[1] if len(needs) > 1 else None)
                if not pages_from or not portions_from:
                    raise SystemExit(f"Stage {stage_id} requires pages+portions inputs; specify via inputs map")
                artifact_inputs["pages"] = artifact_index[pages_from]["path"]
                artifact_inputs["portions"] = artifact_index[portions_from]["path"]
                # Schema checks
                pages_schema = artifact_index[pages_from].get("schema")
                portions_schema = artifact_index[portions_from].get("schema")
                if node.get("input_schema") and portions_schema and node["input_schema"] != portions_schema:
                    raise SystemExit(f"Schema mismatch: {stage_id} expects {node['input_schema']} got {portions_schema} from {portions_from}")
            elif stage == "consensus":
                if len(needs) > 1:
                    # merge multiple portion hypotheses into a temp concat
                    merged_path = os.path.join(run_dir, f"{stage_id}_merged.jsonl")
                    merged_schema = artifact_index[needs[0]].get("schema")
                    if not args.dry_run:
                        for dep in needs:
                            dep_schema = artifact_index[dep].get("schema")
                            if merged_schema and dep_schema and dep_schema != merged_schema:
                                raise SystemExit(f"Schema mismatch in consensus inputs: {dep_schema} vs {merged_schema}")
                        concat_dedupe_jsonl([artifact_index[d]["path"] for d in needs], merged_path, key_field="portion_id")
                    artifact_inputs["hypotheses"] = merged_path
                    artifact_inputs["merged_schema"] = merged_schema
                else:
                    origin = needs[0] if needs else None
                    if not origin:
                        raise SystemExit(f"Stage {stage_id} missing hypotheses input")
                    artifact_inputs["hypotheses"] = artifact_index[origin]["path"]
                expected_schema = node.get("input_schema")
                source_schema = artifact_inputs.get("merged_schema") or (artifact_index[needs[0]].get("schema") if needs else None)
                if expected_schema and source_schema and expected_schema != source_schema:
                    raise SystemExit(f"Schema mismatch: {stage_id} expects {expected_schema} got {source_schema}")
            elif stage == "adapter":
                if not needs:
                    raise SystemExit(f"Stage {stage_id} missing adapter inputs")
                artifact_inputs["inputs"] = [artifact_index[n]["path"] for n in needs]
                expected_schema = node.get("input_schema")
                for dep in needs:
                    producer_schema = artifact_index[dep].get("schema")
                    if expected_schema and producer_schema and expected_schema != producer_schema:
                        raise SystemExit(f"Schema mismatch: {stage_id} expects {expected_schema} got {producer_schema} from {dep}")
            else:
                origin = needs[0] if needs else None
                if not origin:
                    raise SystemExit(f"Stage {stage_id} missing upstream input")
                key = "pages" if stage in {"clean", "portionize"} else "input"
                artifact_inputs[key] = artifact_index[origin]["path"]
                producer_schema = artifact_index[origin].get("schema")
                expected_schema = node.get("input_schema")
                if expected_schema and producer_schema and expected_schema != producer_schema:
                    raise SystemExit(f"Schema mismatch: {stage_id} expects {expected_schema} got {producer_schema} from {origin}")

        artifact_path, cmd, cwd = build_command(entrypoint, node["params"], node, run_dir,
                                                recipe.get("input", {}), state_path, progress_path, run_id,
                                                artifact_inputs)

        if args.dry_run:
            print(f"[dry-run] {stage_id} -> {' '.join(cmd)}")
            artifact_index[stage_id] = {"path": artifact_path, "schema": out_schema}
            continue

        logger.log(stage_id, "running", artifact=artifact_path, module_id=module_id, message="started")

        # Mock shortcuts for expensive stages
        if args.mock and stage == "clean":
            upstream = needs[0] if needs else None
            if not upstream:
                raise SystemExit(f"Mock clean needs upstream extract output")
            mock_outputs = {
                "extract": os.path.relpath(artifact_index[upstream]["path"], run_dir),
                "clean": node["artifact_name"],
            }
            artifact_path = mock_clean(run_dir, mock_outputs, module_id, run_id)
            update_state(state_path, progress_path, stage_id, "done", artifact_path, run_id, module_id, out_schema)
            artifact_index[stage_id] = {"path": artifact_path, "schema": out_schema}
            continue
        if args.mock and stage == "portionize":
            upstream = needs[0] if needs else None
            if not upstream:
                raise SystemExit(f"Mock portionize needs upstream clean output")
            mock_outputs = {
                "clean": os.path.relpath(artifact_index[upstream]["path"], run_dir),
                "portionize": node["artifact_name"],
            }
            artifact_path = mock_portionize(run_dir, mock_outputs, module_id, run_id)
            update_state(state_path, progress_path, stage_id, "done", artifact_path, run_id, module_id, out_schema)
            artifact_index[stage_id] = {"path": artifact_path, "schema": out_schema}
            continue
        if args.mock and stage == "consensus":
            upstream = needs[0] if needs else None
            if not upstream:
                raise SystemExit(f"Mock consensus needs upstream portionize output")
            mock_outputs = {
                "portionize": os.path.relpath(artifact_index[upstream]["path"], run_dir),
                "consensus": node["artifact_name"],
            }
            artifact_path = mock_consensus(run_dir, mock_outputs, module_id, run_id)
            update_state(state_path, progress_path, stage_id, "done", artifact_path, run_id, module_id, out_schema)
            artifact_index[stage_id] = {"path": artifact_path, "schema": out_schema}
            continue

        print(f"[run] {stage_id} ({module_id})")
        result = subprocess.run(cmd, cwd=cwd)
        if result.returncode != 0:
            update_state(state_path, progress_path, stage_id, "failed", artifact_path, run_id, module_id, out_schema)
            raise SystemExit(f"Stage {stage_id} failed with code {result.returncode}")
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
                        update_state(state_path, progress_path, stage_id, "failed", artifact_path, run_id, module_id, out_schema)
                        raise SystemExit(f"Validation failed for {artifact_path}: {errors} errors")
        update_state(state_path, progress_path, stage_id, "done", artifact_path, run_id, module_id, out_schema)
        artifact_index[stage_id] = {"path": artifact_path, "schema": out_schema}

    print("Recipe complete.")


if __name__ == "__main__":
    main()
