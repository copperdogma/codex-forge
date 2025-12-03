import argparse
import json
import os
import re
import subprocess
import sys
import time
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import resource
except ImportError:  # pragma: no cover - resource not on Windows
    resource = None

import yaml

from modules.common.utils import ensure_dir, ProgressLogger, append_jsonl, read_jsonl, save_json
from validate_artifact import SCHEMA_MAP
from modules.common.utils import save_jsonl


DEFAULT_OUTPUTS = {
    "intake": "elements.jsonl",
    "extract": "pages_raw.jsonl",
    "image_crop": "image_crops.jsonl",
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

def cleanup_artifact(artifact_path: str, force: bool):
    """
    Delete existing artifact when forcing a rerun to avoid duplicate appends.
    """
    if force and os.path.exists(artifact_path):
        os.remove(artifact_path)
        print(f"[force-clean] removed existing {artifact_path}")

def _artifact_name_for_stage(stage_id: str, stage_type: str, outputs_map: Dict[str, str]) -> str:
    return outputs_map.get(stage_id) or DEFAULT_OUTPUTS.get(stage_type, f"{stage_id}.jsonl")


def _load_pricing(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    models = data.get("models", {})
    default = data.get("default", {})
    currency = data.get("currency", "USD")
    return {"models": models, "default": default, "currency": currency, "source": path}


def _preload_artifacts_from_state(state_path: str) -> Dict[str, Dict[str, str]]:
    """
    Load artifacts from an existing pipeline_state so upstream stages can be skipped
    via --start-from/--end-at while still resolving inputs.
    """
    if not os.path.exists(state_path):
        return {}
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        return {}
    artifacts: Dict[str, Dict[str, str]] = {}
    for sid, st in (state.get("stages") or {}).items():
        art = st.get("artifact")
        if st.get("status") == "done" and art and os.path.exists(art):
            artifacts[sid] = {"path": art, "schema": st.get("schema_version")}
    return artifacts


def _calc_cost(model: str, prompt_tokens: int, completion_tokens: int, pricing: Dict[str, Any]) -> float:
    if not pricing:
        return 0.0
    models = pricing.get("models", {})
    default = pricing.get("default", {})
    entry = models.get(model) or default
    if not entry:
        return 0.0
    prompt_rate = entry.get("prompt_per_1k", 0) / 1000
    completion_rate = entry.get("completion_per_1k", 0) / 1000
    return round(prompt_tokens * prompt_rate + completion_tokens * completion_rate, 6)


def _get_cpu_times():
    if not resource:
        return None
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime, usage.ru_stime


def _render_instrumentation_md(run_data: Dict[str, Any], path: str):
    lines = []
    lines.append(f"# Instrumentation Report — {run_data.get('run_id')}")
    lines.append("")
    totals = run_data.get("totals", {})
    currency = (run_data.get("pricing") or {}).get("currency", "USD")
    lines.append(f"- Run started: {run_data.get('started_at')}")
    lines.append(f"- Run ended: {run_data.get('ended_at')}")
    lines.append(f"- Wall time: {totals.get('wall_seconds') or run_data.get('wall_seconds') or 'n/a'} seconds")
    lines.append(f"- Total cost: {totals.get('cost', 0):.6f} {currency}")
    lines.append("")
    lines.append("## Per-model cost")
    per_model = totals.get("per_model", {})
    if per_model:
        lines.append("| model | prompt_tokens | completion_tokens | cost |")
        lines.append("|---|---:|---:|---:|")
        for model, stats in per_model.items():
            lines.append(f"| {model} | {stats.get('prompt_tokens',0)} | {stats.get('completion_tokens',0)} | {stats.get('cost',0):.6f} |")
    else:
        lines.append("_no LLM calls recorded_")
    lines.append("")
    lines.append("## Stage timings")
    lines.append("| stage | status | wall_s | user_s | sys_s | cost | calls |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for st in run_data.get("stages", []):
        lt = st.get("llm_totals", {})
        lines.append(
            f"| {st.get('id')} | {st.get('status')} | {st.get('wall_seconds') or 0:.3f} | "
            f"{st.get('cpu_user_seconds') or 0:.3f} | {st.get('cpu_system_seconds') or 0:.3f} | "
            f"{lt.get('cost',0):.6f} | {lt.get('calls',0)} |"
        )
    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _subset_registry_for_plan(plan: Dict[str, Any], registry: Dict[str, Any]) -> Dict[str, Any]:
    used = {node["module"] for node in plan.get("nodes", {}).values()}
    return {mid: registry.get(mid) for mid in sorted(used) if mid in registry}


def snapshot_run_config(run_dir: str, recipe: Dict[str, Any], plan: Dict[str, Any], registry: Dict[str, Any],
                        registry_source: Optional[str] = None, settings_path: Optional[str] = None,
                        pricing_path: Optional[str] = None, instrumentation_conf: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """
    Persist the runnable configuration for reproducibility:
    - recipe (as loaded by driver)
    - resolved plan (nodes + topo)
    - registry subset for modules used in the plan
    - optional settings file (if provided and exists)
    - optional pricing table used for instrumentation
    - optional instrumentation config blob
    Returns mapping of snapshot name -> absolute path.
    """
    snap_dir = os.path.join(run_dir, "snapshots")
    ensure_dir(snap_dir)

    recipe_path = os.path.join(snap_dir, "recipe.yaml")
    with open(recipe_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(recipe, f, sort_keys=False)

    plan_path = os.path.join(snap_dir, "plan.json")
    save_json(plan_path, plan)

    registry_payload = {
        "source": registry_source,
        "modules": _subset_registry_for_plan(plan, registry),
    }
    registry_path = os.path.join(snap_dir, "registry.json")
    save_json(registry_path, registry_payload)

    settings_snapshot = None
    if settings_path:
        if os.path.exists(settings_path):
            ext = os.path.splitext(settings_path)[1] or ".yaml"
            settings_snapshot = os.path.join(snap_dir, f"settings{ext}")
            shutil.copyfile(settings_path, settings_snapshot)
        else:
            print(f"[warn] settings path not found for snapshot: {settings_path}")

    pricing_snapshot = None
    if pricing_path:
        if os.path.exists(pricing_path):
            ext = os.path.splitext(pricing_path)[1] or ".yaml"
            pricing_snapshot = os.path.join(snap_dir, f"pricing{ext}")
            shutil.copyfile(pricing_path, pricing_snapshot)
        else:
            print(f"[warn] pricing table not found for snapshot: {pricing_path}")

    instrumentation_snapshot = None
    if instrumentation_conf:
        instrumentation_snapshot = os.path.join(snap_dir, "instrumentation.json")
        save_json(instrumentation_snapshot, instrumentation_conf)

    snapshots = {
        "recipe": recipe_path,
        "plan": plan_path,
        "registry": registry_path,
    }
    if settings_snapshot:
        snapshots["settings"] = settings_snapshot
    if pricing_snapshot:
        snapshots["pricing"] = pricing_snapshot
    if instrumentation_snapshot:
        snapshots["instrumentation"] = instrumentation_snapshot
    return snapshots

def _normalize_param_schema(schema: Any) -> Tuple[Dict[str, Dict[str, Any]], Set[str]]:
    """
    Accept either JSON-Schema-lite {"properties": {...}, "required": [...]} or a direct mapping of param -> spec.
    Returns (properties_map, required_set).
    """
    if not schema:
        return {}, set()
    if isinstance(schema, dict) and "properties" in schema:
        props = schema.get("properties") or {}
        required = set(schema.get("required") or [])
    elif isinstance(schema, dict):
        props = schema
        required = {k for k, v in props.items() if isinstance(v, dict) and v.get("required")}
    else:
        raise SystemExit(f"param_schema must be a mapping, got {type(schema)}")
    return props, required


def _type_matches(val: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(val, str)
    if expected == "boolean":
        return isinstance(val, bool)
    if expected == "integer":
        return isinstance(val, int) and not isinstance(val, bool)
    if expected == "number":
        return isinstance(val, (int, float)) and not isinstance(val, bool)
    return True


def _validate_params(params: Dict[str, Any], schema: Any, stage_id: str, module_id: str) -> None:
    props, required = _normalize_param_schema(schema)
    if not props:
        return

    allowed = set(props.keys())
    for key in params.keys():
        if key not in allowed:
            raise SystemExit(f"Unknown param '{key}' for stage '{stage_id}' (module {module_id})")

    missing = [k for k in required if params.get(k) is None]
    if missing:
        raise SystemExit(f"Missing required params {missing} for stage '{stage_id}' (module {module_id})")

    for key, spec in props.items():
        if not isinstance(spec, dict):
            continue
        val = params.get(key)
        if val is None:
            continue
        expected_type = spec.get("type")
        if expected_type and not _type_matches(val, expected_type):
            raise SystemExit(f"Param '{key}' on stage '{stage_id}' (module {module_id}) expected type {expected_type}, got {type(val).__name__}")
        if "enum" in spec and val not in spec["enum"]:
            raise SystemExit(f"Param '{key}' on stage '{stage_id}' (module {module_id}) must be one of {spec['enum']}, got {val}")
        if expected_type in {"number", "integer"}:
            if "minimum" in spec and val < spec["minimum"]:
                raise SystemExit(f"Param '{key}' on stage '{stage_id}' (module {module_id}) must be >= {spec['minimum']}")
            if "maximum" in spec and val > spec["maximum"]:
                raise SystemExit(f"Param '{key}' on stage '{stage_id}' (module {module_id}) must be <= {spec['maximum']}")
        if expected_type == "string" and "pattern" in spec:
            if not re.fullmatch(spec["pattern"], str(val)):
                raise SystemExit(f"Param '{key}' on stage '{stage_id}' (module {module_id}) failed pattern {spec['pattern']}")


def _merge_params(defaults: Dict[str, Any], overrides: Dict[str, Any], schema: Any) -> Dict[str, Any]:
    params = dict(defaults or {})
    props, _ = _normalize_param_schema(schema)
    # apply schema defaults if provided
    for key, spec in props.items():
        if isinstance(spec, dict) and "default" in spec and key not in params:
            params[key] = spec["default"]
    if overrides:
        params.update(overrides)
    return params


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
        params = _merge_params(entry.get("default_params", {}), conf.get("params") or {}, entry.get("param_schema"))
        _validate_params(params, entry.get("param_schema"), stage_id, module_id)
        artifact_name = conf.get("out") or _artifact_name_for_stage(stage_id, stage_type, outputs_map)
        description = conf.get("description") or entry.get("notes") or entry.get("description")
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
            "description": description,
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
                 module_id: str = None, schema_version: str = None, stage_description: str = None):
    logger = ProgressLogger(state_path=state_path, progress_path=progress_path, run_id=run_id)
    return logger.log(stage_name, status, artifact=artifact, module_id=module_id,
                      schema_version=schema_version, stage_description=stage_description)


def build_command(entrypoint: str, params: Dict[str, Any], stage_conf: Dict[str, Any], run_dir: str,
                  recipe_input: Dict[str, Any], state_path: str, progress_path: str, run_id: str,
                  artifact_inputs: Dict[str, str]) -> (str, list, str):
    """
    Returns (artifact_path, cmd_list, cwd)
    """
    script, func = (entrypoint.split(":") + [None])[:2]
    script_path = os.path.join(os.getcwd(), script)
    module_name = None
    if script.endswith(".py") and script.startswith("modules/"):
        module_name = script[:-3].replace("/", ".")

    artifact_name = stage_conf["artifact_name"]
    artifact_path = os.path.join(run_dir, artifact_name)

    if module_name:
        cmd = [sys.executable, "-m", module_name]
    else:
        cmd = [sys.executable, script_path]

    flags_added = set()

    # Standard parameter conveniences by stage
    if stage_conf["stage"] in ("intake", "extract"):
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
        if stage_conf["module"] == "load_stub_v1":
            stub_path = params.get("stub")
            if not stub_path:
                raise SystemExit(f"Stage {stage_conf['id']} missing stub param")
            cmd += ["--stub", stub_path, "--out", artifact_path]
            if params.get("schema_version"):
                cmd += ["--schema-version", str(params["schema_version"])]
            flags_added.update({"--stub", "--out"})
        else:
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
    elif stage_conf["stage"] in {"app", "export"}:
        in_path = artifact_inputs.get("input")
        if not in_path:
            raise SystemExit(f"Stage {stage_conf['id']} missing input")
        cmd += ["--input", in_path, "--out", artifact_path]
        flags_added.update({"--input", "--out"})
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
        pages_path = artifact_inputs.get("pages")
        portions_path = artifact_inputs.get("portions") or artifact_inputs.get("input")
        if not pages_path or not portions_path:
            raise SystemExit(f"Stage {stage_conf['id']} missing enrich inputs (pages/portions)")
        cmd += ["--pages", pages_path, "--portions", portions_path, "--out", artifact_path]
        flags_added.update({"--pages", "--portions", "--out"})

    # Additional params from recipe (skip flags already added)
    # Additional params from recipe (skip flags already added)
    seen_flags = set(flags_added)
    for key, val in (params or {}).items():
        flag = f"--{key}"
        if flag in seen_flags:
            continue
        if val is None:
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
        if not row.get("module_id"):
            row["module_id"] = module_id
        if not row.get("run_id"):
            row["run_id"] = run_id
        if not row.get("created_at"):
            row["created_at"] = datetime.utcnow().isoformat() + "Z"
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


def register_run(run_id: str, run_dir: str, recipe: Dict[str, Any], instrumentation: Optional[Dict[str, str]] = None,
                 snapshots: Optional[Dict[str, str]] = None):
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
    def _rel(path: Optional[str]) -> Optional[str]:
        if not path:
            return None
        try:
            return os.path.relpath(path)
        except Exception:
            return path

    entry = {
        "run_id": run_id,
        "path": run_dir,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "recipe": recipe.get("name") or os.path.basename(recipe.get("recipe_path", "")) or None,
        "input": recipe.get("input", {}),
    }
    if instrumentation:
        entry["instrumentation"] = {k: _rel(v) for k, v in instrumentation.items()}
    if snapshots:
        entry["snapshots"] = {k: _rel(v) for k, v in snapshots.items()}
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
    parser.add_argument("--instrument", action="store_true", help="Enable instrumentation (timing/cost)")
    parser.add_argument("--price-table", help="Path to model pricing YAML (prompt_per_1k/completion_per_1k)")
    parser.add_argument("--settings", help="Optional settings YAML to snapshot for reproducibility")
    parser.add_argument("--run-id", dest="run_id_override", help="Override run_id from recipe (useful for smoke runs)")
    parser.add_argument("--output-dir", dest="output_dir_override", help="Override output_dir from recipe (useful for smoke runs / temp dirs)")
    parser.add_argument("--input-pdf", dest="input_pdf_override", help="Override input.pdf from recipe (useful for smoke fixtures)")
    parser.add_argument("--start-from", dest="start_from", help="Start executing at this stage id (requires upstream artifacts present in state)")
    parser.add_argument("--end-at", dest="end_at", help="Stop after executing this stage id (inclusive)")
    args = parser.parse_args()

    registry = load_registry(args.registry)["modules"]
    recipe = load_recipe(args.recipe)
    recipe["recipe_path"] = args.recipe

    # Optional settings merge (shallow-deep) for smoke/testing convenience
    settings_path = args.settings or recipe.get("settings") or recipe.get("settings_path")
    if settings_path and os.path.exists(settings_path):
        with open(settings_path, "r", encoding="utf-8") as f:
            settings_yaml = yaml.safe_load(f) or {}
        def deep_merge(dst, src):
            for k, v in src.items():
                if isinstance(v, dict) and isinstance(dst.get(k), dict):
                    deep_merge(dst[k], v)
                else:
                    dst[k] = v
        deep_merge(recipe, settings_yaml)

    # Apply CLI overrides for smoke/testing convenience
    if args.input_pdf_override:
        recipe.setdefault("input", {})
        recipe["input"]["pdf"] = args.input_pdf_override
    if args.run_id_override:
        recipe["run_id"] = args.run_id_override
    if args.output_dir_override:
        recipe["output_dir"] = args.output_dir_override

    instr_conf = recipe.get("instrumentation", {}) or {}
    instrument_enabled = bool(instr_conf.get("enabled") or args.instrument)
    price_table_path = args.price_table or instr_conf.get("price_table")
    if instrument_enabled and not price_table_path:
        price_table_path = "configs/pricing.default.yaml"
    pricing = _load_pricing(price_table_path) if (instrument_enabled and price_table_path) else None

    run_id = recipe.get("run_id")
    run_dir = recipe.get("output_dir", os.path.join("output", "runs", run_id))
    instrumentation_paths = None
    instr_json_path = os.path.join(run_dir, "instrumentation.json")
    instr_md_path = os.path.join(run_dir, "instrumentation.md")
    if instrument_enabled:
        instrumentation_paths = {"json": instr_json_path, "md": instr_md_path}

    plan = build_plan(recipe, registry)
    validate_plan_schemas(plan)
    if args.start_from and args.start_from not in plan["topo"]:
        raise SystemExit(f"--start-from {args.start_from} not found in recipe stages")
    if args.end_at and args.end_at not in plan["topo"]:
        raise SystemExit(f"--end-at {args.end_at} not found in recipe stages")
    if args.start_from and args.end_at:
        start_idx = plan["topo"].index(args.start_from)
        end_idx = plan["topo"].index(args.end_at)
        if start_idx > end_idx:
            raise SystemExit("--start-from must precede or equal --end-at")

    if args.dump_plan:
        print(json.dumps({"topo": plan["topo"], "nodes": plan["nodes"]}, indent=2))
        return

    ensure_dir(run_dir)
    state_path = os.path.join(run_dir, "pipeline_state.json")
    progress_path = os.path.join(run_dir, "pipeline_events.jsonl")
    logger = ProgressLogger(state_path=state_path, progress_path=progress_path, run_id=run_id)

    settings_path = args.settings or recipe.get("settings") or recipe.get("settings_path")
    snapshots = snapshot_run_config(
        run_dir,
        recipe,
        plan,
        registry,
        registry_source=args.registry,
        settings_path=settings_path,
        pricing_path=price_table_path,
        instrumentation_conf=instr_conf if instrument_enabled or instr_conf else None,
    )

    register_run(run_id, run_dir, recipe, instrumentation=instrumentation_paths, snapshots=snapshots)

    run_started_at = datetime.utcnow().isoformat() + "Z"
    run_wall_start = time.perf_counter()
    run_cpu_start = _get_cpu_times()

    artifact_index: Dict[str, Dict[str, str]] = _preload_artifacts_from_state(state_path)

    sink_path = os.path.join(run_dir, "instrumentation_calls.jsonl") if instrument_enabled else None
    if instrument_enabled and args.force and sink_path and os.path.exists(sink_path):
        os.remove(sink_path)
    sink_offset = 0
    stage_call_map: Dict[str, List[Dict[str, Any]]] = {}

    run_totals = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0, "per_model": {}, "wall_seconds": 0.0}
    instrumentation_run = None
    if instrument_enabled:
        instrumentation_run = {
            "schema_version": "instrumentation_run_v1",
            "run_id": run_id,
            "recipe_name": recipe.get("name"),
            "recipe_path": recipe.get("recipe_path"),
            "started_at": run_started_at,
            "pricing": pricing,
            "stages": [],
            "totals": run_totals,
            "env": {"python_version": sys.version, "platform": sys.platform},
        }

    def ingest_sink_events():
        nonlocal sink_offset
        if not instrument_enabled or not sink_path or not os.path.exists(sink_path):
            return
        with open(sink_path, "r", encoding="utf-8") as f:
            f.seek(sink_offset)
            data = f.read()
            sink_offset = f.tell()
        if not data:
            return
        for line in data.splitlines():
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            sid = ev.get("stage_id")
            if sid:
                stage_call_map.setdefault(sid, []).append(ev)

    def record_stage_instrumentation(stage_id: str, module_id: str, status: str, artifact_path: str,
                                     schema_version: str, stage_started_at: str,
                                     stage_wall_start: float, stage_cpu_start):
        if not instrument_enabled:
            return
        ingest_sink_events()
        ended_at = datetime.utcnow().isoformat() + "Z"
        wall_seconds = round(time.perf_counter() - stage_wall_start, 6)
        cpu_user = cpu_sys = None
        end_cpu = _get_cpu_times()
        if stage_cpu_start and end_cpu:
            cpu_user = round(end_cpu[0] - stage_cpu_start[0], 6)
            cpu_sys = round(end_cpu[1] - stage_cpu_start[1], 6)
        calls = stage_call_map.pop(stage_id, [])
        call_total = len(calls)
        prompt_tokens = sum(int(c.get("prompt_tokens", 0)) for c in calls)
        completion_tokens = sum(int(c.get("completion_tokens", 0)) for c in calls)
        cost_total = 0.0
        per_model: Dict[str, Dict[str, Any]] = {}
        for c in calls:
            model = c.get("model") or "unknown"
            ev_cost = c.get("cost")
            if ev_cost is None:
                ev_cost = _calc_cost(model, int(c.get("prompt_tokens", 0)), int(c.get("completion_tokens", 0)), pricing)
            cost_total += ev_cost
            pm = per_model.setdefault(model, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0})
            pm["calls"] += 1
            pm["prompt_tokens"] += int(c.get("prompt_tokens", 0))
            pm["completion_tokens"] += int(c.get("completion_tokens", 0))
            pm["cost"] += ev_cost
        llm_totals = {
            "calls": call_total,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost": round(cost_total, 6),
        }
        stage_entry = {
            "schema_version": "instrumentation_stage_v1",
            "id": stage_id,
            "stage": plan["nodes"][stage_id]["stage"],
            "module_id": module_id,
            "description": plan["nodes"][stage_id].get("description"),
            "status": status,
            "artifact": artifact_path,
            "schema_version_output": schema_version,
            "started_at": stage_started_at,
            "ended_at": ended_at,
            "wall_seconds": wall_seconds,
            "cpu_user_seconds": cpu_user,
            "cpu_system_seconds": cpu_sys,
            "llm_calls": calls,
            "llm_totals": llm_totals,
            "extra": {},
        }
        instrumentation_run["stages"].append(stage_entry)
        run_totals["calls"] += call_total
        run_totals["prompt_tokens"] += prompt_tokens
        run_totals["completion_tokens"] += completion_tokens
        run_totals["cost"] = round(run_totals["cost"] + cost_total, 6)
        for model, stats in per_model.items():
            agg = run_totals["per_model"].setdefault(model, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0})
            agg["calls"] += stats["calls"]
            agg["prompt_tokens"] += stats["prompt_tokens"]
            agg["completion_tokens"] += stats["completion_tokens"]
            agg["cost"] = round(agg["cost"] + stats["cost"], 6)
        run_totals["wall_seconds"] = round(time.perf_counter() - run_wall_start, 6)
        instrumentation_run["totals"] = run_totals
        save_json(instr_json_path, instrumentation_run)
        _render_instrumentation_md(instrumentation_run, instr_md_path)

    start_gate_reached = not bool(args.start_from)
    for stage_id in plan["topo"]:
        if args.start_from and not start_gate_reached:
            if stage_id == args.start_from:
                start_gate_reached = True
            else:
                if stage_id not in artifact_index:
                    raise SystemExit(f"--start-from {args.start_from} provided, but upstream stage {stage_id} has no cached artifact in {state_path}")
                print(f"[skip-start] {stage_id} skipped due to --start-from (artifact reused)")
                continue
        node = plan["nodes"][stage_id]
        stage = node["stage"]
        module_id = node["module"]
        entrypoint = node["entrypoint"]
        out_schema = node.get("output_schema")
        stage_description = node.get("description")
        stage_started_at = datetime.utcnow().isoformat() + "Z"
        stage_wall_start = time.perf_counter()
        stage_cpu_start = _get_cpu_times()

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
                                   message="Skipped due to --skip-done", stage_description=stage_description)
                        artifact_index[stage_id] = {"path": st.get("artifact"), "schema": st.get("schema_version")}
                        record_stage_instrumentation(stage_id, module_id, "skipped", st.get("artifact"), st.get("schema_version"),
                                                     stage_started_at, stage_wall_start, stage_cpu_start)
                        continue
                    else:
                        print(f"[redo] {stage_id} redo due to schema mismatch or unreadable artifact")
            except Exception:
                pass

        # Input resolution
        artifact_inputs: Dict[str, str] = {}
        needs = node.get("needs", [])
        if stage in {"clean", "portionize", "consensus", "dedupe", "normalize", "resolve", "build", "enrich", "adapter", "export", "app"}:
            # adapters fall-through below
            if stage == "build":
                inputs_map = node.get("inputs", {}) or {}
                pages_from = inputs_map.get("pages")
                portions_from = inputs_map.get("portions")
                # Default resolution for single-branch recipes: assume first upstream clean and resolve
                if not pages_from:
                    pages_from = needs[0] if needs else None
                if not portions_from:
                    portions_from = needs[1] if len(needs) > 1 else (needs[0] if needs else None)
                if not pages_from or not portions_from:
                    raise SystemExit(f"Stage {stage_id} requires pages+portions inputs; specify via inputs map")
                artifact_inputs["pages"] = artifact_index[pages_from]["path"]
                artifact_inputs["portions"] = artifact_index[portions_from]["path"]
                # Schema checks
                pages_schema = artifact_index[pages_from].get("schema")
                portions_schema = artifact_index[portions_from].get("schema")
                if node.get("input_schema") and portions_schema and node["input_schema"] != portions_schema:
                    raise SystemExit(f"Schema mismatch: {stage_id} expects {node['input_schema']} got {portions_schema} from {portions_from}")
            elif stage == "enrich":
                inputs_map = node.get("inputs", {}) or {}
                pages_from = inputs_map.get("pages")
                portions_from = inputs_map.get("portions") or (needs[0] if needs else None)
                if not pages_from:
                    # heuristic: pick nearest clean stage
                    for dep in needs:
                        if (artifact_index[dep].get("schema") or "").endswith("page_v1"):
                            pages_from = dep
                            break
                if not pages_from or not portions_from:
                    raise SystemExit(f"Stage {stage_id} requires pages+portions inputs; specify via inputs map")
                artifact_inputs["pages"] = artifact_index[pages_from]["path"]
                artifact_inputs["portions"] = artifact_index[portions_from]["path"]
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
            elif stage in {"app", "export"}:
                origin = needs[0] if needs else None
                if not origin:
                    raise SystemExit(f"Stage {stage_id} missing upstream input")
                artifact_inputs["input"] = artifact_index[origin]["path"]
                producer_schema = artifact_index[origin].get("schema")
                expected_schema = node.get("input_schema")
                if expected_schema and producer_schema and expected_schema != producer_schema:
                    raise SystemExit(f"Schema mismatch: {stage_id} expects {expected_schema} got {producer_schema} from {origin}")
            elif stage == "adapter":
                if not needs:
                    # Allow stub loaders with no upstream
                    if node.get("module") == "load_stub_v1":
                        pass
                    else:
                        raise SystemExit(f"Stage {stage_id} missing adapter inputs")
                else:
                    artifact_inputs["inputs"] = [artifact_index[n]["path"] for n in needs]
                    expected_schema = node.get("input_schema")
                    for dep in needs:
                        producer_schema = artifact_index[dep].get("schema")
                        if expected_schema and producer_schema and expected_schema != producer_schema:
                            raise SystemExit(f"Schema mismatch: {stage_id} expects {expected_schema} got {producer_schema} from {dep}")
            else:
                inputs_map = node.get("inputs", {}) or {}
                origin = inputs_map.get("pages") or (needs[0] if needs else None)
                if not origin:
                    raise SystemExit(f"Stage {stage_id} missing upstream input")
                key = "pages" if stage in {"clean", "portionize"} else "input"
                artifact_inputs[key] = artifact_index[origin]["path"] if origin in artifact_index else origin
                producer_schema = artifact_index[origin].get("schema") if origin in artifact_index else None
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

        cleanup_artifact(artifact_path, args.force)

        logger.log(stage_id, "running", artifact=artifact_path, module_id=module_id,
                   message="started", stage_description=stage_description)

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
            update_state(state_path, progress_path, stage_id, "done", artifact_path, run_id, module_id, out_schema,
                         stage_description=stage_description)
            artifact_index[stage_id] = {"path": artifact_path, "schema": out_schema}
            record_stage_instrumentation(stage_id, module_id, "done", artifact_path, out_schema,
                                         stage_started_at, stage_wall_start, stage_cpu_start)
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
            update_state(state_path, progress_path, stage_id, "done", artifact_path, run_id, module_id, out_schema,
                         stage_description=stage_description)
            artifact_index[stage_id] = {"path": artifact_path, "schema": out_schema}
            record_stage_instrumentation(stage_id, module_id, "done", artifact_path, out_schema,
                                         stage_started_at, stage_wall_start, stage_cpu_start)
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
            update_state(state_path, progress_path, stage_id, "done", artifact_path, run_id, module_id, out_schema,
                         stage_description=stage_description)
            artifact_index[stage_id] = {"path": artifact_path, "schema": out_schema}
            record_stage_instrumentation(stage_id, module_id, "done", artifact_path, out_schema,
                                         stage_started_at, stage_wall_start, stage_cpu_start)
            continue

        print(f"[run] {stage_id} ({module_id})")
        env = os.environ.copy()
        if instrument_enabled:
            env["INSTRUMENT_SINK"] = sink_path
            env["INSTRUMENT_STAGE"] = stage_id
            env["RUN_ID"] = run_id or ""
            env["INSTRUMENT_ENABLED"] = "1"
        result = subprocess.run(cmd, cwd=cwd, env=env)
        if result.returncode != 0:
            update_state(state_path, progress_path, stage_id, "failed", artifact_path, run_id, module_id, out_schema,
                         stage_description=stage_description)
            record_stage_instrumentation(stage_id, module_id, "failed", artifact_path, out_schema,
                                         stage_started_at, stage_wall_start, stage_cpu_start)
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
                        update_state(state_path, progress_path, stage_id, "failed", artifact_path, run_id, module_id, out_schema,
                                     stage_description=stage_description)
                        record_stage_instrumentation(stage_id, module_id, "failed", artifact_path, out_schema,
                                                     stage_started_at, stage_wall_start, stage_cpu_start)
                        raise SystemExit(f"Validation failed for {artifact_path}: {errors} errors")
        update_state(state_path, progress_path, stage_id, "done", artifact_path, run_id, module_id, out_schema,
                     stage_description=stage_description)
        artifact_index[stage_id] = {"path": artifact_path, "schema": out_schema}
        record_stage_instrumentation(stage_id, module_id, "done", artifact_path, out_schema,
                                     stage_started_at, stage_wall_start, stage_cpu_start)

        if args.end_at and stage_id == args.end_at:
            print(f"[end-at] stopping after {stage_id} per --end-at")
            break

    if instrument_enabled and instrumentation_run:
        instrumentation_run["ended_at"] = datetime.utcnow().isoformat() + "Z"
        instrumentation_run["wall_seconds"] = round(time.perf_counter() - run_wall_start, 6)
        if run_cpu_start:
            end_cpu_run = _get_cpu_times()
            if end_cpu_run:
                instrumentation_run["cpu_user_seconds"] = round(end_cpu_run[0] - run_cpu_start[0], 6)
                instrumentation_run["cpu_system_seconds"] = round(end_cpu_run[1] - run_cpu_start[1], 6)
        save_json(instr_json_path, instrumentation_run)
        _render_instrumentation_md(instrumentation_run, instr_md_path)

    print("Recipe complete.")


if __name__ == "__main__":
    main()
