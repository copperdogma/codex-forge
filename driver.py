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
from schemas import RunConfig


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

def _artifact_name_for_stage(stage_id: str, stage_type: str, outputs_map: Dict[str, str], stage_conf: Dict[str, Any] = None) -> str:
    # 1. Use stage-level out from recipe if provided
    if stage_conf and stage_conf.get("out"):
        return stage_conf["out"]

    # 2. Use recipe-level outputs mapping if provided
    if stage_id in outputs_map:
        return outputs_map[stage_id]

    # 3. Standard defaults by stage type
    if stage_type == "intake":
        return "pages_raw.jsonl"
    if stage_type == "extract":
        return "pages_raw.jsonl"
    if stage_type == "clean":
        return "pages_clean.jsonl"
    if stage_type == "portionize":
        return "portion_hypotheses.jsonl"
    if stage_type == "consensus":
        return "portions_locked.jsonl"
    if stage_type == "normalize":
        return "portions_normalized.jsonl"
    if stage_type == "resolve":
        return "portions_resolved.jsonl"
    if stage_type == "enrich":
        return "portions_enriched.jsonl"
    if stage_type == "build":
        return "gamebook.json"
    if stage_type == "validate":
        return "validation_report.json"
    if stage_type == "adapter":
        return "adapter_out.jsonl"
    if stage_type == "app":
        return "app_data.json"
    if stage_type == "export":
        return "gamebook.json"

    return f"{stage_id}_out.jsonl"


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


def _invalidate_downstream_outputs(run_dir: str, plan: Dict[str, Any], start_from: str,
                                   keep_downstream: bool, state_path: str,
                                   logger: "ProgressLogger") -> None:
    if not start_from or keep_downstream:
        return
    topo = plan.get("topo") or []
    if start_from not in topo:
        return
    start_idx = topo.index(start_from)
    if start_idx >= len(topo) - 1:
        return
    stage_ordinal_map = {sid: idx + 1 for idx, sid in enumerate(topo)}
    removed = []
    for stage_id in topo[start_idx + 1:]:
        node = plan["nodes"].get(stage_id, {})
        module_id = node.get("module")
        if module_id and stage_id in stage_ordinal_map:
            module_dir = os.path.join(run_dir, f"{stage_ordinal_map[stage_id]:02d}_{module_id}")
            if os.path.isdir(module_dir):
                shutil.rmtree(module_dir)
                removed.append(module_dir)
        artifact_name = node.get("artifact_name") or _artifact_name_for_stage(stage_id, node.get("stage"), {}, node)
        if artifact_name in ("gamebook.json", "validation_report.json"):
            artifact_path = os.path.join(run_dir, artifact_name)
            if os.path.exists(artifact_path):
                os.remove(artifact_path)
                removed.append(artifact_path)
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            stages = state.get("stages", {})
            for stage_id in topo[start_idx + 1:]:
                stages.pop(stage_id, None)
            state["stages"] = stages
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass
    if removed:
        logger.log("resume_invalidate", "warning", artifact=None, module_id=None,
                   message=f"Invalidated downstream outputs after {start_from}: removed {len(removed)} artifacts/dirs")


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
        stage_overrides = (recipe.get("stage_params") or {}).get(stage_id, {})
        merged_params = {}
        merged_params.update(conf.get("params") or {})
        merged_params.update(stage_overrides)
        params = _merge_params(entry.get("default_params", {}), merged_params, entry.get("param_schema"))
        # Validate params with awareness of stage inputs/out to avoid false missing-required errors.
        params_for_validation = dict(params)
        inputs = conf.get("inputs", {}) or {}
        props, required = _normalize_param_schema(entry.get("param_schema"))
        if "out" in required and params_for_validation.get("out") is None and conf.get("out"):
            params_for_validation["out"] = conf.get("out")
        for key in required:
            if params_for_validation.get(key) is not None:
                continue
            if key in inputs:
                params_for_validation[key] = inputs.get(key)
                continue
            if key == "gamebook" and inputs.get("input"):
                params_for_validation[key] = inputs.get("input")
                continue
            if key == "inputs" and inputs.get("inputs"):
                params_for_validation[key] = inputs.get("inputs")
        _validate_params(params_for_validation, entry.get("param_schema"), stage_id, module_id)
        artifact_name = _artifact_name_for_stage(stage_id, stage_type, outputs_map, conf)
        description = conf.get("description") or entry.get("notes") or entry.get("description")
        output_schema = entry.get("output_schema") or params.get("schema_version")
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
            "output_schema": output_schema,
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


def _default_run_id(base: str = "run") -> str:
    """
    Generate a timestamped run_id to avoid reuse of stale state/artifacts.
    Format: <base>-YYYYMMDD-HHMMSS-<6hex>
    """
    import uuid
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    rand = uuid.uuid4().hex[:6]
    return f"{base}-{ts}-{rand}"


def update_state(state_path: str, progress_path: str, stage_name: str, status: str, artifact: str, run_id: str = None,
                 module_id: str = None, schema_version: str = None, stage_description: str = None):
    logger = ProgressLogger(state_path=state_path, progress_path=progress_path, run_id=run_id)
    return logger.log(stage_name, status, artifact=artifact, module_id=module_id,
                      schema_version=schema_version, stage_description=stage_description)


def build_command(entrypoint: str, params: Dict[str, Any], stage_conf: Dict[str, Any], run_dir: str,
                  recipe_input: Dict[str, Any], state_path: str, progress_path: str, run_id: str,
                  artifact_inputs: Dict[str, str], artifact_index: Dict[str, Any] = None,
                  stage_ordinal_map: Dict[str, int] = None) -> (str, list, str):
    """
    Returns (artifact_path, cmd_list, cwd)
    """
    script, func = (entrypoint.split(":") + [None])[:2]
    script_path = os.path.join(os.getcwd(), script)
    module_name = None
    if script.endswith(".py") and script.startswith("modules/"):
        module_name = script[:-3].replace("/", ".")

    stage_id = stage_conf.get("id")
    module_id = stage_conf.get("module")
    stage_type = stage_conf.get("stage")

    artifact_name = stage_conf.get("artifact_name")
    if not artifact_name:
         artifact_name = _artifact_name_for_stage(stage_id, stage_type, {}, stage_conf)
    
    # Determine if this is a final output (stays in root)
    is_final_output = (artifact_name in ("gamebook.json", "validation_report.json"))
    
    if is_final_output:
        # Final outputs stay in root
        artifact_path = os.path.join(run_dir, artifact_name)
    else:
        # Intermediate artifacts go into module-specific folders (directly in run_dir)
        if stage_ordinal_map and stage_id and stage_id in stage_ordinal_map:
            ordinal = stage_ordinal_map[stage_id]
            if module_id:
                module_folder = f"{ordinal:02d}_{module_id}"
                module_dir = os.path.join(run_dir, module_folder)
                ensure_dir(module_dir)
                artifact_path = os.path.join(module_dir, artifact_name)
            else:
                # Fallback: if no module_id, use root (shouldn't happen in practice)
                artifact_path = os.path.join(run_dir, artifact_name)
        else:
            # Fallback: if no ordinal map provided, use root (backward compat during transition)
            artifact_path = os.path.join(run_dir, artifact_name)

    if module_name:
        cmd = [sys.executable, "-m", module_name]
    else:
        cmd = [sys.executable, script_path]

    flags_added = set()

    # Standard parameter conveniences by stage
    if stage_conf["stage"] in ("intake", "extract"):
        # Some extract stages are NOT PDF/image ingestors (e.g., extract_choices_v1 consumes JSONL portions).
        if stage_conf["module"] == "extract_choices_v1":
            in_path = artifact_inputs.get("inputs") or artifact_inputs.get("input")
            if not in_path:
                raise SystemExit(f"Stage {stage_conf['id']} missing inputs")
            cmd += ["--inputs", in_path, "--out", artifact_path]
            flags_added.update({"--inputs", "--out"})
        elif stage_conf["module"] == "crop_illustrations_guided_v1":
            # crop_illustrations_guided_v1 expects --ocr-manifest instead of --pages
            # It doesn't need --pdf (it gets page images from the OCR manifest's image_native field)
            # It uses --output-dir (not --outdir)
            ocr_manifest_path = artifact_inputs.get("ocr_manifest")
            if not ocr_manifest_path:
                raise SystemExit(f"Stage {stage_conf['id']} missing ocr_manifest input")
            module_outdir = os.path.dirname(artifact_path) if not is_final_output else run_dir
            cmd += ["--output-dir", module_outdir]; flags_added.add("--output-dir")
            cmd += ["--ocr-manifest", ocr_manifest_path]
            flags_added.add("--ocr-manifest")
        else:
            if "pdf" in recipe_input:
                cmd += ["--pdf", recipe_input["pdf"]]; flags_added.add("--pdf")
            if "images" in recipe_input:
                cmd += ["--images", recipe_input["images"]]; flags_added.add("--images")
            # Use module folder as outdir for intake/extract stages so artifacts go to module folder
            # (module subdirectories like images/, ocr_ensemble/ will be created in module folder)
            module_outdir = os.path.dirname(artifact_path) if not is_final_output else run_dir
            cmd += ["--outdir", module_outdir]; flags_added.add("--outdir")
            # Handle inputs for intake stages (e.g., pagelines_to_elements_v1)
            # Note: params.inputs might contain stage IDs - don't pass those, use resolved artifact_inputs instead
            if artifact_inputs:
                pages_path = artifact_inputs.get("pages") or artifact_inputs.get("input")
                if pages_path:
                    cmd += ["--pages", pages_path]
                    flags_added.add("--pages")
                    # Remove "inputs" from params if present to avoid passing stage ID strings
                    if "inputs" in (params or {}):
                        params = dict(params or {})
                        del params["inputs"]
    elif stage_conf["stage"] == "clean":
        # Handle repair_candidates_v1 specially - needs pagelines param
        if stage_conf["module"] == "repair_candidates_v1":
            portions_path = artifact_inputs.get("portions") or artifact_inputs.get("input")
            if not portions_path:
                raise SystemExit(f"Stage {stage_conf['id']} missing portions input")
            cmd += ["--portions", portions_path, "--out", artifact_path]
            # Handle pagelines param - resolve to absolute path in merge_ocr module folder
            if "pagelines" in params:
                pagelines_param = params["pagelines"]
                if not os.path.isabs(str(pagelines_param)):
                    # Try to find merge_ocr artifact from artifact_index first
                    resolved_pagelines = None
                    if artifact_index:
                        merge_ocr_artifact = artifact_index.get("merge_ocr", {}).get("path")
                        if merge_ocr_artifact:
                            merge_ocr_dir = os.path.dirname(merge_ocr_artifact)
                            resolved_pagelines = os.path.join(merge_ocr_dir, str(pagelines_param))
                    # Fallback: try to find it in run_dir by looking for merge_ocr module folder
                    if not resolved_pagelines and os.path.exists(run_dir):
                        try:
                            # Look for numbered folder starting with merge_ocr
                            for item in os.listdir(run_dir):
                                if item.startswith("06_") and "merge_ocr" in item.lower():
                                    resolved_pagelines = os.path.join(run_dir, item, str(pagelines_param))
                                    break
                        except (OSError, PermissionError):
                            pass
                    # Final fallback: construct expected path based on known structure (always works)
                    if not resolved_pagelines:
                        # Default: assume merge_ocr is stage 06 (from recipe order)
                        resolved_pagelines = os.path.join(run_dir, "06_merge_ocr_escalated_v1", str(pagelines_param))
                    # Always pass absolute path (repair_candidates_v1 treats relative paths as relative to its module dir)
                    cmd += ["--pagelines", os.path.abspath(resolved_pagelines)]
                    flags_added.add("--pagelines")
                    # Remove from params so it's not added again
                    del params["pagelines"]
            flags_added.update({"--portions", "--out"})
        else:
            # Standard clean stage handling
            portions_path = artifact_inputs.get("portions")
            if portions_path:
                cmd += ["--portions", portions_path]
                flags_added.add("--portions")
            else:
                pages_path = artifact_inputs.get("pages") or artifact_inputs.get("input")
                if not pages_path:
                    raise SystemExit(f"Stage {stage_conf['id']} missing pages/portions input")
                cmd += ["--pages", pages_path]
                flags_added.add("--pages")
            cmd += ["--out", artifact_path]
            flags_added.add("--out")
    elif stage_conf["stage"] == "portionize":
        # Some portionize modules are merges and do not accept --pages/--elements.
        if stage_conf.get("module") == "coarse_segment_merge_v1":
            params = dict(params or {})
            # Resolve upstream artifacts for required inputs.
            coarse_art = artifact_index.get("coarse_segment_semantic", {}).get("path") if artifact_index else None
            patt_art = artifact_index.get("coarse_segment_patterns", {}).get("path") if artifact_index else None
            ff_art = artifact_index.get("coarse_segment_ff_override", {}).get("path") if artifact_index else None

            if not coarse_art or not os.path.exists(coarse_art):
                raise SystemExit(f"Stage {stage_conf['id']} missing coarse_segment_semantic artifact")
            if not patt_art or not os.path.exists(patt_art):
                raise SystemExit(f"Stage {stage_conf['id']} missing coarse_segment_patterns artifact")

            cmd += ["--coarse-segments", os.path.abspath(coarse_art)]
            flags_added.add("--coarse-segments")
            cmd += ["--pattern-regions", os.path.abspath(patt_art)]
            flags_added.add("--pattern-regions")
            if ff_art and os.path.exists(ff_art):
                cmd += ["--ff-hints", os.path.abspath(ff_art)]
                flags_added.add("--ff-hints")

            cmd += ["--out", artifact_path]
            flags_added.add("--out")

            # Avoid re-adding these via the generic params loop below.
            for k in ("coarse_segments", "pattern_regions", "ff_hints", "out"):
                params.pop(k, None)
        else:
            # Handle various input names (pages, elements, input)
            pages_path = artifact_inputs.get("pages") or artifact_inputs.get("input")
            elements_path = artifact_inputs.get("elements")
            if not pages_path and not elements_path:
                # Fallback: try elements as input
                pages_path = artifact_inputs.get("elements") or artifact_inputs.get("input")
            if not pages_path:
                raise SystemExit(f"Stage {stage_conf['id']} missing pages/elements input")
            # Use --pages for compatibility (coarse_segment_v1 accepts both --pages and --elements)
            cmd += ["--pages", pages_path]
            flags_added.add("--pages")
            # Also pass --elements if specified (structure_globally_v1 needs both)
            if elements_path:
                cmd += ["--elements", elements_path]
                flags_added.add("--elements")
            if "boundaries" in artifact_inputs:
                cmd += ["--boundaries", artifact_inputs["boundaries"]]
            # detect_boundaries_code_first_v1 can optionally use coarse segments for gameplay filtering.
            if stage_conf["module"] == "detect_boundaries_code_first_v1" and artifact_inputs.get("coarse_segments"):
                cmd += ["--coarse-segments", os.path.abspath(artifact_inputs["coarse_segments"])]
            # Handle coarse-segments for fine_segment_frontmatter_v1
            if stage_conf["module"] == "fine_segment_frontmatter_v1" and artifact_index:
                coarse_segments_path = artifact_index.get("coarse_segment", {}).get("path")
                if coarse_segments_path:
                    cmd += ["--coarse-segments", os.path.abspath(coarse_segments_path)]
            cmd += ["--out", artifact_path]
            flags_added.add("--out")
    elif stage_conf["stage"] == "adapter":
        if stage_conf["module"] == "load_stub_v1":
            stub_path = params.get("stub")
            if not stub_path:
                raise SystemExit(f"Stage {stage_conf['id']} missing stub param")
            cmd += ["--stub", stub_path, "--out", artifact_path]
            if params.get("schema_version"):
                cmd += ["--schema-version", str(params["schema_version"])]
                flags_added.add("--schema_version")
            flags_added.update({"--stub", "--out"})
        elif stage_conf["module"] == "merge_boundaries_pref_v1":
            inputs_list = artifact_inputs.get("inputs")
            if not inputs_list or len(inputs_list) < 2:
                raise SystemExit(f"Stage {stage_conf['id']} missing primary/fallback inputs")
            cmd += ["--inputs", *inputs_list, "--out", artifact_path]
            if artifact_inputs.get("elements_core"):
                cmd += ["--elements-core", artifact_inputs["elements_core"]]
            flags_added.update({"--inputs", "--out"})
        elif stage_conf["module"] == "pick_best_engine_v1":
            # pick_best_engine_v1 needs the ocr_ensemble index from the intake stage
            input_paths = artifact_inputs.get("inputs")
            if not input_paths:
                raise SystemExit(f"Stage {stage_conf['id']} missing adapter inputs")
            cmd += ["--inputs", *input_paths, "--out", artifact_path]
            # Find intake stage's ocr_ensemble folder for the index
            if artifact_index:
                intake_artifact = artifact_index.get("intake", {}).get("path")
                if intake_artifact:
                    intake_dir = os.path.dirname(intake_artifact)
                    index_path = os.path.join(intake_dir, "ocr_ensemble", "pagelines_index.json")
                    if os.path.exists(index_path) or "--index" not in flags_added:
                        cmd += ["--index", index_path]
                        flags_added.add("--index")
                # Pass outdir explicitly to avoid run_dir inference issues
                module_outdir = os.path.dirname(artifact_path)
                cmd += ["--outdir", os.path.join(module_outdir, "ocr_ensemble_picked")]
                flags_added.add("--outdir")
            flags_added.update({"--inputs", "--out"})
        elif stage_conf["module"] == "inject_missing_headers_v1":
            # inject_missing_headers_v1 needs the ocr_ensemble_picked index from pick_best_engine stage
            input_paths = artifact_inputs.get("inputs")
            if not input_paths:
                raise SystemExit(f"Stage {stage_conf['id']} missing adapter inputs")
            cmd += ["--inputs", *input_paths, "--out", artifact_path]
            # Find pick_best_engine stage's ocr_ensemble_picked folder for the index
            if artifact_index:
                pick_best_artifact = artifact_index.get("pick_best_engine", {}).get("path")
                if pick_best_artifact:
                    pick_best_dir = os.path.dirname(pick_best_artifact)
                    index_path = os.path.join(pick_best_dir, "ocr_ensemble_picked", "pagelines_index.json")
                    if os.path.exists(index_path) or "--index" not in flags_added:
                        cmd += ["--index", index_path]
                        flags_added.add("--index")
                    # Pass outdir to avoid run_dir inference issues
                    module_outdir = os.path.dirname(artifact_path)
                    cmd += ["--outdir", os.path.join(module_outdir, "ocr_ensemble_injected")]
                    flags_added.add("--outdir")
            flags_added.update({"--inputs", "--out"})
        elif stage_conf["module"] == "ocr_escalate_gpt4v_v1":
            # ocr_escalate_gpt4v_v1 needs paths from intake stage (index, quality, images_dir)
            input_paths = artifact_inputs.get("inputs")
            if not input_paths:
                raise SystemExit(f"Stage {stage_conf['id']} missing adapter inputs")
            cmd += ["--inputs", *input_paths, "--out", artifact_path]
            # Find intake stage's ocr_ensemble folder for index, quality, and images
            if artifact_index:
                intake_artifact = artifact_index.get("intake", {}).get("path")
                if intake_artifact:
                    intake_dir = os.path.dirname(intake_artifact)
                    index_path = os.path.join(intake_dir, "ocr_ensemble", "pagelines_index.json")
                    quality_path = os.path.join(intake_dir, "ocr_ensemble", "ocr_quality_report.json")
                    images_dir = os.path.join(intake_dir, "images")
                    if os.path.exists(index_path) or "--index" not in flags_added:
                        cmd += ["--index", index_path]
                        flags_added.add("--index")
                    if os.path.exists(quality_path) or "--quality" not in flags_added:
                        cmd += ["--quality", quality_path]
                        flags_added.add("--quality")
                    if os.path.exists(images_dir) or "--images-dir" not in flags_added:
                        cmd += ["--images-dir", images_dir]
                        flags_added.add("--images-dir")
                # Pass outdir explicitly to avoid inference issues
                module_outdir = os.path.dirname(artifact_path)
                cmd += ["--outdir", os.path.join(module_outdir, "ocr_ensemble_gpt4v")]
                flags_added.add("--outdir")
            flags_added.update({"--inputs", "--out"})
        elif stage_conf["module"] == "merge_ocr_escalated_v1":
            # merge_ocr_escalated_v1 needs outdir to be the module folder so pagelines_final.jsonl is created there
            input_paths = artifact_inputs.get("inputs")
            if not input_paths or len(input_paths) < 2:
                raise SystemExit(f"Stage {stage_conf['id']} missing adapter inputs")
            cmd += ["--inputs", *input_paths, "--out", artifact_path]
            # Pass outdir explicitly to module folder
            module_outdir = os.path.dirname(artifact_path)
            cmd += ["--outdir", module_outdir]
            flags_added.add("--outdir")
            # Pass explicit index paths to avoid run_dir inference issues
            if artifact_index:
                pick_best_artifact = artifact_index.get("pick_best_engine", {}).get("path")
                escalate_artifact = artifact_index.get("escalate_vision", {}).get("path")
                if pick_best_artifact:
                    pick_best_dir = os.path.dirname(pick_best_artifact)
                    original_index = os.path.join(pick_best_dir, "ocr_ensemble_picked", "pagelines_index.json")
                    if os.path.exists(original_index) or "--original-index" not in flags_added:
                        cmd += ["--original-index", original_index]
                        flags_added.add("--original-index")
                if escalate_artifact:
                    escalate_dir = os.path.dirname(escalate_artifact)
                    escalated_index = os.path.join(escalate_dir, "ocr_ensemble_gpt4v", "pagelines_index.json")
                    if os.path.exists(escalated_index) or "--escalated-index" not in flags_added:
                        cmd += ["--escalated-index", escalated_index]
                        flags_added.add("--escalated-index")
            flags_added.update({"--inputs", "--out"})
        elif stage_conf["module"] == "reconstruct_text_v1":
            input_paths = artifact_inputs.get("inputs")
            if not input_paths:
                raise SystemExit(f"Stage {stage_conf['id']} missing adapter inputs")
            cmd += ["--inputs", *input_paths, "--out", artifact_path]
            # Handle params.input (pagelines_final.jsonl) - resolve to absolute path in merge_ocr module folder
            if "input" in params:
                input_param = params["input"]
                # If it's a relative path like "pagelines_final.jsonl", resolve it in merge_ocr module folder
                if not os.path.isabs(str(input_param)) and artifact_index:
                    merge_ocr_artifact = artifact_index.get("merge_ocr", {}).get("path")
                    if merge_ocr_artifact:
                        merge_ocr_dir = os.path.dirname(merge_ocr_artifact)
                        resolved_input = os.path.join(merge_ocr_dir, str(input_param))
                        if os.path.exists(resolved_input):
                            # Pass --input with absolute path explicitly (before params processing)
                            cmd += ["--input", resolved_input]
                            flags_added.add("--input")
                            # Remove from params dict so it's not added again (modify in place)
                            del params["input"]
            flags_added.update({"--inputs", "--out"})
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
        in_path = artifact_inputs.get("input") or artifact_inputs.get("gamebook")
        if not in_path:
            raise SystemExit(f"Stage {stage_conf['id']} missing input")
        # package_game_ready_v1 expects --out to be relative to run_dir, not the full artifact_path
        if stage_conf.get("module") == "package_game_ready_v1":
            # Use the "out" from recipe (should be "output") or fallback
            out_arg = stage_conf.get("out") or "output"
            cmd += ["--input", in_path, "--out", out_arg, "--run-dir", run_dir]
            flags_added.update({"--input", "--out", "--run-dir"})
        else:
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
        for extra_key, extra_val in artifact_inputs.items():
            if extra_key in {"pages", "portions"}:
                continue
            flag = "--" + extra_key.replace("_", "-")
            if flag in flags_added:
                continue
            cmd += [flag, str(extra_val)]
            flags_added.add(flag)
    elif stage_conf["stage"] == "enrich":
        pages_path = artifact_inputs.get("pages")
        portions_path = artifact_inputs.get("portions") or artifact_inputs.get("input")
        if not pages_path or not portions_path:
            raise SystemExit(f"Stage {stage_conf['id']} missing enrich inputs (pages/portions)")
        cmd += ["--pages", pages_path, "--portions", portions_path, "--out", artifact_path]
        flags_added.update({"--pages", "--portions", "--out"})
    elif stage_conf["stage"] == "transform":
        # Transform stages: handle associate_illustrations_to_sections_v1 specially
        if stage_conf["module"] == "associate_illustrations_to_sections_v1":
            gamebook_path = artifact_inputs.get("gamebook")
            illustrations_path = artifact_inputs.get("illustrations")
            pages_html_path = artifact_inputs.get("pages_html")
            if not gamebook_path or not illustrations_path:
                raise SystemExit(f"Stage {stage_conf['id']} missing transform inputs (gamebook/illustrations)")
            cmd += ["--gamebook", gamebook_path, "--illustrations", illustrations_path, "--output", artifact_path]
            flags_added.update({"--gamebook", "--illustrations", "--output"})
            if pages_html_path:
                cmd += ["--pages-html", pages_html_path]
                flags_added.add("--pages-html")
        else:
            # Generic transform: pass all artifact_inputs as flags
            for key, val in artifact_inputs.items():
                flag = "--" + key.replace("_", "-")
                if flag in flags_added:
                    continue
                cmd += [flag, str(val)]
                flags_added.add(flag)
            cmd += ["--out", artifact_path]
            flags_added.add("--out")
    elif stage_conf["stage"] == "validate":
        # Validation stages typically want input artifact(s) and explicit out path.
        gamebook_path = artifact_inputs.get("gamebook") or artifact_inputs.get("input")
        if gamebook_path:
            cmd += ["--gamebook", gamebook_path]; flags_added.add("--gamebook")
        
        # Pass all other artifact_inputs as flags (e.g. --portions, --boundaries)
        for extra_key, extra_val in artifact_inputs.items():
            if extra_key == "gamebook":
                continue
            flag = "--" + extra_key.replace("_", "-")
            if flag in flags_added:
                continue
            cmd += [flag, str(extra_val)]
            flags_added.add(flag)

        # Legacy special-case for forensics in ff_engine_v2
        if stage_conf["module"] == "validate_ff_engine_v2" and "--forensics" not in flags_added:
            cmd += ["--forensics"]; flags_added.add("--forensics")
            
        cmd += ["--out", artifact_path]
        flags_added.add("--out")

    # Additional params from recipe (skip flags already added)
    seen_flags = set(flags_added)
    for key, val in (params or {}).items():
        flag = f"--{key}"
        if key == "skip_ai":
            flag = "--skip-ai"
        # Special-case param flag normalization for modules that expect hyphens
        if stage_conf.get("module") == "fine_segment_frontmatter_v1" and key == "coarse_segments":
            flag = "--coarse-segments"
            # Prefer artifact from coarse_segment stage if available
            coarse_art = artifact_index.get("coarse_segment", {}).get("path")
            if coarse_art and os.path.exists(coarse_art):
                val = coarse_art
            else:
                val = os.path.abspath(val) if not os.path.isabs(str(val)) else val
        # coarse_segment_* modules use hyphenated flags and should receive resolved artifact paths.
        if stage_conf.get("module") in {"coarse_segment_ff_override_v1", "coarse_segment_merge_v1"}:
            if key == "coarse_segments":
                flag = "--coarse-segments"
                art = artifact_index.get("coarse_segment_semantic", {}).get("path") if artifact_index else None
                if art and os.path.exists(art):
                    val = art
                else:
                    val = os.path.abspath(val) if not os.path.isabs(str(val)) else val
            elif key == "pattern_regions":
                flag = "--pattern-regions"
                art = artifact_index.get("coarse_segment_patterns", {}).get("path") if artifact_index else None
                if art and os.path.exists(art):
                    val = art
                else:
                    val = os.path.abspath(val) if not os.path.isabs(str(val)) else val
            elif key == "ff_hints":
                flag = "--ff-hints"
                art = artifact_index.get("coarse_segment_ff_override", {}).get("path") if artifact_index else None
                if art and os.path.exists(art):
                    val = art
                else:
                    val = os.path.abspath(val) if not os.path.isabs(str(val)) else val
        if stage_conf.get("module") == "validate_game_ready_v1":
            if key == "expected_range_start":
                flag = "--expected-range-start"
            elif key == "expected_range_end":
                flag = "--expected-range-end"
            elif key == "known_missing":
                flag = "--known-missing"
        if stage_conf.get("module") == "associate_illustrations_to_sections_v1":
            if key == "image_base_path":
                flag = "--image-base-path"
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
    # Also skip for modules that don't support these flags
    skip_state_progress = (
        stage_conf["stage"] == "adapter" or
        stage_conf.get("module") == "crop_illustrations_guided_v1" or
        stage_conf.get("module") == "associate_illustrations_to_sections_v1"
    )
    if not skip_state_progress:
        cmd += ["--state-file", state_path, "--progress-file", progress_path]
        if run_id:
            cmd += ["--run-id", run_id]
    elif run_id and stage_conf.get("module") == "crop_illustrations_guided_v1":
        # crop_illustrations_guided_v1 accepts --run-id but not --state-file/--progress-file
        cmd += ["--run-id", run_id]

    return artifact_path, cmd, os.getcwd()


def stamp_artifact(artifact_path: str, schema_name: str, module_id: str, run_id: str):
    if schema_name not in SCHEMA_MAP:
        return
    model_cls = SCHEMA_MAP[schema_name]
    allowed_keys = set()
    if hasattr(model_cls, "__fields__"):
        allowed_keys = set(model_cls.__fields__.keys())
    elif hasattr(model_cls, "model_fields"):
        allowed_keys = set(model_cls.model_fields.keys())
    rows = []
    dropped_keys = set()
    for row in read_jsonl(artifact_path):
        if isinstance(row, dict) and row.get("error"):
            continue  # skip invalid rows
        try:
            if isinstance(row, dict) and allowed_keys:
                extra = set(row.keys()) - allowed_keys
                if extra:
                    dropped_keys.update(extra)
            row.setdefault("schema_version", schema_name)
            if not row.get("module_id"):
                row["module_id"] = module_id
            if not row.get("run_id"):
                row["run_id"] = run_id
            if not row.get("created_at"):
                row["created_at"] = datetime.utcnow().isoformat() + "Z"
            rows.append(model_cls(**row).dict())
        except Exception as e:
            print(f"[stamp-skip] skipping row due to validation error: {e}")
    save_jsonl(artifact_path, rows)
    print(f"[stamp] {artifact_path} stamped with {schema_name} ({len(rows)} rows)")
    if dropped_keys:
        dropped_list = ", ".join(sorted(dropped_keys))
        print(f"[stamp-warning] {artifact_path} dropped unknown fields not in schema {schema_name}: {dropped_list}")


def copy_key_artifact_to_root(artifact_path: str, run_dir: str, artifact_name: str, artifact_index: Dict[str, Any] = None) -> None:
    """
    Copy key intermediate artifacts to root for visibility.
    Key artifacts are major pipeline milestones that should be visible in root.
    """
    # List of key artifact names that should be copied to root
    key_artifacts = {
        "pagelines_final.jsonl",
        "pagelines_reconstructed.jsonl", 
        "elements_core.jsonl",
    }
    
    # Don't copy if already in root
    if os.path.dirname(artifact_path) == run_dir:
        return
    
    # Check if this is a primary artifact that should be copied
    if artifact_name in key_artifacts:
        root_path = os.path.join(run_dir, artifact_name)
        try:
            if os.path.exists(artifact_path):
                shutil.copy2(artifact_path, root_path)
                print(f"[copy-to-root] {artifact_name} -> {root_path}")
        except Exception as e:
            # Non-fatal - log but don't fail
            print(f"[copy-to-root-warning] Failed to copy {artifact_name} to root: {e}")
        return
    
    # Special handling: Check for secondary files that should be copied
    # pagelines_final.jsonl is created as a secondary file in merge_ocr module folder
    if artifact_name == "adapter_out.jsonl" and "merge_ocr" in artifact_path:
        # Check if pagelines_final.jsonl exists in the same module folder
        module_dir = os.path.dirname(artifact_path)
        pagelines_final_path = os.path.join(module_dir, "pagelines_final.jsonl")
        if os.path.exists(pagelines_final_path):
            root_path = os.path.join(run_dir, "pagelines_final.jsonl")
            try:
                shutil.copy2(pagelines_final_path, root_path)
                print(f"[copy-to-root] pagelines_final.jsonl -> {root_path}")
            except Exception as e:
                print(f"[copy-to-root-warning] Failed to copy pagelines_final.jsonl to root: {e}")


def mock_clean(pages_path: str, out_path: str, module_id: str, run_id: str):
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


def mock_portionize(pages_path: str, out_path: str, module_id: str, run_id: str):
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


def mock_consensus(in_path: str, out_path: str, module_id: str, run_id: str):
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
    parser.add_argument("--config", help="Path to run configuration YAML")
    parser.add_argument("--recipe", help="Path to recipe yaml (optional if --config is used)")
    parser.add_argument("--registry", default="modules", help="Module registry directory or yaml")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running")
    parser.add_argument("--skip-done", action="store_true", help="Skip stages marked done in pipeline_state.json")
    parser.add_argument("--no-validate", action="store_true", help="Skip validation step after stamping")
    parser.add_argument("--force", action="store_true", help="Run stages even if artifacts already exist (overwrites). Note: Expensive stages (OCR/extract) are protected from force-rerun; use --skip-done --start-from <stage> instead.")
    parser.add_argument("--mock", action="store_true", help="Use mock implementations for LLM stages to avoid API calls")
    parser.add_argument("--dump-plan", action="store_true", help="Print resolved DAG plan and exit")
    parser.add_argument("--instrument", action="store_true", help="Enable instrumentation (timing/cost)")
    parser.add_argument("--price-table", help="Path to model pricing YAML (prompt_per_1k/completion_per_1k)")
    parser.add_argument("--settings", help="Optional settings YAML to snapshot for reproducibility")
    parser.add_argument("--run-id", dest="run_id_override",
                        help="Use a specific run_id (default: auto-generate unique run_id/output_dir per run).")
    parser.add_argument("--allow-run-id-reuse", action="store_true",
                        help="Allow reusing the run_id/output_dir from the recipe; default is to auto-generate a fresh one to avoid stale artifacts.")
    parser.add_argument("--output-dir", dest="output_dir_override", help="Override output_dir from recipe (useful for smoke runs / temp dirs)")
    parser.add_argument("--input-pdf", dest="input_pdf_override", help="Override input.pdf from recipe (useful for smoke fixtures)")
    parser.add_argument("--start-from", dest="start_from", help="Start executing at this stage id (requires upstream artifacts present in state)")
    parser.add_argument("--keep-downstream", action="store_true",
                        help="When resuming with --start-from, keep downstream artifacts instead of invalidating them (not recommended)")
    parser.add_argument("--end-at", dest="end_at", help="Stop after executing this stage id (inclusive)")
    args = parser.parse_args()

    # Load from config if provided
    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        config = RunConfig(**config_data)
        
        # Apply config to args for backward compatibility in the rest of main()
        args.recipe = args.recipe or config.recipe
        args.registry = config.registry or args.registry
        args.settings = args.settings or config.settings
        args.input_pdf_override = args.input_pdf_override or config.input_pdf
        args.run_id_override = args.run_id_override or config.run_id
        args.output_dir_override = args.output_dir_override or config.output_dir
        
        args.dry_run = args.dry_run or config.execution.dry_run
        args.skip_done = args.skip_done or config.execution.skip_done
        args.force = args.force or config.execution.force
        args.start_from = args.start_from or config.execution.start_from
        args.end_at = args.end_at or config.execution.end_at
        
        args.mock = args.mock or config.options.mock
        args.no_validate = args.no_validate or config.options.no_validate
        args.allow_run_id_reuse = args.allow_run_id_reuse or config.options.allow_run_id_reuse
        args.dump_plan = args.dump_plan or config.options.dump_plan
        
        args.instrument = args.instrument or config.instrumentation.enabled
        args.price_table = args.price_table or config.instrumentation.price_table
        

    if not args.recipe:
        print("Error: Either --recipe or --config must be provided.")
        sys.exit(1)

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
    # Apply CLI overrides for smoke/testing convenience
    if args.input_pdf_override:
        recipe.setdefault("input", {})
        recipe["input"]["pdf"] = args.input_pdf_override

    instr_conf = recipe.get("instrumentation", {}) or {}
    instrument_enabled = bool(instr_conf.get("enabled") or args.instrument)
    price_table_path = args.price_table or instr_conf.get("price_table")
    if instrument_enabled and not price_table_path:
        price_table_path = "configs/pricing.default.yaml"
    pricing = _load_pricing(price_table_path) if (instrument_enabled and price_table_path) else None
    
    # Resolve Execution Context (RunConfig > Recipe)
    # We want to move towards RunConfig being the source of truth, but respect Recipe for back-compat.
    
    # 1. Run ID
    if args.run_id_override:
        run_id = args.run_id_override
    elif recipe.get("run_id"):
        run_id = recipe.get("run_id")
    else:
         # Auto-generate if not provided? Or strictly require?
         # User said "A run is a run attempt and should generate its own run id."
         # Let's auto-generate from recipe name to be friendly, but allow config to override.
         base_name = os.path.splitext(os.path.basename(args.recipe))[0]
         run_id = _default_run_id(base_name)
         print(f"ℹ️  Run ID autogenerated: {run_id}", file=sys.stderr)

    # 2. Output Directory
    if args.output_dir_override:
        # output_dir_override can be either parent directory (e.g., "output/runs") or full path - check if it ends with run_id
        if args.output_dir_override.endswith(run_id) or args.output_dir_override.endswith(os.path.join(os.sep, run_id)):
            run_dir = args.output_dir_override
        else:
            # output_dir_override is the parent directory, append run_id
            run_dir = os.path.join(args.output_dir_override, run_id)
    elif recipe.get("output_dir"):
        # Recipe output_dir can be either parent or full path - check if it ends with run_id
        recipe_output_dir = recipe.get("output_dir")
        if recipe_output_dir.endswith(run_id):
            run_dir = recipe_output_dir
        else:
            run_dir = os.path.join(recipe_output_dir, run_id)
    else:
        # Default behavior: output/runs/<run_id>
        run_dir = os.path.join("output", "runs", run_id)
        if not args.output_dir_override:
             print(f"ℹ️  Output directory inferred: {run_dir}", file=sys.stderr)

    # 3. Input
    # Input is inside 'recipe' dict, but we must check if it's effectively populated.
    input_conf = recipe.get("input") or {}
    if not input_conf.get("pdf") and not input_conf.get("images"):
        # If we have no input from override AND no input from recipe, we fail.
        print("\n❌ ERROR: No input specified.", file=sys.stderr)
        print("You must provide an input PDF or images directory via:", file=sys.stderr)
        print("  - Configuration YAML (recommended): input_pdf: ...", file=sys.stderr)
        print("  - CLI Override: --input-pdf ...", file=sys.stderr)
        print("  - Recipe (deprecated): input:\n      pdf: ...", file=sys.stderr)
        sys.exit(1)

    # Handle run ID reuse logic
    if args.allow_run_id_reuse:
        # If reusing, ensure we stick to the resolved run_dir
        pass 
    else:
        # If NOT reusing, we might need a unique ID if the resolved one conflicts. 
        # But 'run_id' resolution above already handled explicit overrides. 
        # The auto-generation logic uses timestamp, so it is unique.
        # If user EXPLICITLY provided a run_id that exists, and didn't say allow-reuse, we fail later at directory check.
        pass
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

    if args.start_from and args.force:
        print("⚠️  --force ignored because --start-from is set (resume mode).", file=sys.stderr)
        args.force = False

    # Validate output directory to prevent artifact mixing
    if os.path.exists(run_dir) and os.listdir(run_dir):
        if not (args.force or args.allow_run_id_reuse):
            print(f"\n❌ ERROR: Output directory already exists and contains files:", file=sys.stderr)
            print(f"  {run_dir}\n", file=sys.stderr)
            print("Reusing directories can mix artifacts from different runs, causing silent", file=sys.stderr)
            print("data corruption and hard-to-debug failures.\n", file=sys.stderr)
            print("Options:", file=sys.stderr)
            print("  --force              Delete existing directory and start fresh", file=sys.stderr)
            print("  --allow-run-id-reuse Continue/append to existing run (for resuming failed runs)", file=sys.stderr)
            print("  (or remove 'run_id:' from recipe to auto-generate unique timestamped IDs)\n", file=sys.stderr)
            sys.exit(1)
        elif args.force:
            # Delete and recreate directory
            norm_run_dir = os.path.normpath(run_dir)
            norm_root = os.path.normpath(os.path.join("output", "runs"))
            if norm_run_dir == norm_root:
                raise SystemExit("--force refused: output/runs is the runs root; set a run_id or output_dir to a subdir")
            print(f"⚠️  --force: Cleaning existing directory: {run_dir}")
            # Selective delete to preserve the config file if it's inside
            active_config_abs = os.path.abspath(args.config) if hasattr(args, 'config') and args.config else None
            for item in os.listdir(run_dir):
                item_path = os.path.join(run_dir, item)
                item_abs = os.path.abspath(item_path)
                if active_config_abs and item_abs == active_config_abs:
                    continue
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)

    ensure_dir(run_dir)
    state_path = os.path.join(run_dir, "pipeline_state.json")
    progress_path = os.path.join(run_dir, "pipeline_events.jsonl")
    logger = ProgressLogger(state_path=state_path, progress_path=progress_path, run_id=run_id)

    _invalidate_downstream_outputs(run_dir, plan, args.start_from, args.keep_downstream, state_path, logger)

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

    # Snapshot the actual RunConfig YAML if we loaded from one
    if hasattr(args, 'config') and args.config and os.path.exists(args.config):
        config_snapshot_path = os.path.join(run_dir, "snapshots", "run_config.yaml")
        try:
            shutil.copy2(args.config, config_snapshot_path)
            print(f"Snapshotted run configuration to {config_snapshot_path}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Failed to snapshot run config: {e}", file=sys.stderr)

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
    run_validation_failed = False

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

    def _compute_llm_totals(calls: List[Dict[str, Any]]):
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
            "calls": len(calls),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost": round(cost_total, 6),
        }
        return llm_totals, per_model

    def _resolve_stage_calls(stage_id: str, module_id: str):
        calls = stage_call_map.get(stage_id, [])
        if calls:
            return calls, stage_id
        # Back-compat for OCR: older runs used stage_id="extract"
        if module_id == "ocr_ai_gpt51_v1" and stage_call_map.get("extract"):
            return stage_call_map.get("extract", []), "extract"
        return [], stage_id

    def update_live_instrumentation(stage_id: str, module_id: str, stage_description: str,
                                    stage_started_at: str, stage_wall_start: float, stage_cpu_start):
        if not instrument_enabled or not instrumentation_run:
            return
        ingest_sink_events()
        calls, call_stage_id = _resolve_stage_calls(stage_id, module_id)
        llm_totals, per_model = _compute_llm_totals(calls)
        wall_seconds = round(time.perf_counter() - stage_wall_start, 6)

        # Replace any existing running entry for this stage
        instrumentation_run["stages"] = [
            s for s in instrumentation_run["stages"]
            if not (s.get("id") == stage_id and s.get("status") == "running")
        ]
        stage_entry = {
            "schema_version": "instrumentation_stage_v1",
            "id": stage_id,
            "stage": plan["nodes"][stage_id]["stage"],
            "module_id": module_id,
            "description": stage_description,
            "status": "running",
            "artifact": plan["nodes"][stage_id].get("artifact"),
            "schema_version_output": plan["nodes"][stage_id].get("output_schema"),
            "started_at": stage_started_at,
            "ended_at": None,
            "wall_seconds": wall_seconds,
            "cpu_user_seconds": None,
            "cpu_system_seconds": None,
            "llm_calls": calls,
            "llm_totals": llm_totals,
            "extra": {"per_model": per_model, "calls_stage_id": call_stage_id if call_stage_id != stage_id else None},
        }
        instrumentation_run["stages"].append(stage_entry)

        # Compute live totals (completed stages + current running)
        live_totals = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0, "per_model": {}, "wall_seconds": 0.0}
        for s in instrumentation_run["stages"]:
            totals = s.get("llm_totals") or {}
            live_totals["calls"] += int(totals.get("calls", 0))
            live_totals["prompt_tokens"] += int(totals.get("prompt_tokens", 0))
            live_totals["completion_tokens"] += int(totals.get("completion_tokens", 0))
            live_totals["cost"] = round(live_totals["cost"] + float(totals.get("cost", 0.0)), 6)
            for model, stats in (s.get("extra", {}).get("per_model") or {}).items():
                agg = live_totals["per_model"].setdefault(model, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0})
                agg["calls"] += stats["calls"]
                agg["prompt_tokens"] += stats["prompt_tokens"]
                agg["completion_tokens"] += stats["completion_tokens"]
                agg["cost"] = round(agg["cost"] + stats["cost"], 6)
        live_totals["wall_seconds"] = round(time.perf_counter() - run_wall_start, 6)
        instrumentation_run["totals"] = live_totals
        save_json(instr_json_path, instrumentation_run)

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
        calls, call_stage_id = _resolve_stage_calls(stage_id, module_id)
        if call_stage_id != stage_id:
            stage_call_map.pop(call_stage_id, None)
        else:
            stage_call_map.pop(stage_id, None)
        llm_totals, per_model = _compute_llm_totals(calls)
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
            "extra": {"per_model": per_model, "calls_stage_id": call_stage_id if call_stage_id != stage_id else None},
        }
        # Remove any running entry for this stage before appending final entry.
        instrumentation_run["stages"] = [
            s for s in instrumentation_run["stages"]
            if not (s.get("id") == stage_id and s.get("status") == "running")
        ]
        instrumentation_run["stages"].append(stage_entry)
        run_totals["calls"] += llm_totals["calls"]
        run_totals["prompt_tokens"] += llm_totals["prompt_tokens"]
        run_totals["completion_tokens"] += llm_totals["completion_tokens"]
        run_totals["cost"] = round(run_totals["cost"] + llm_totals["cost"], 6)
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

    # Build stage ordinal map for module folder naming (01_, 02_, etc.)
    stage_ordinal_map: Dict[str, int] = {}
    for idx, sid in enumerate(plan["topo"], start=1):
        stage_ordinal_map[sid] = idx

    start_gate_reached = not bool(args.start_from)
    stage_timings = {}
    for stage_id in plan["topo"]:
        if args.start_from and not start_gate_reached:
            if stage_id == args.start_from:
                start_gate_reached = True
            else:
                if stage_id not in artifact_index:
                    raise SystemExit(f"--start-from {args.start_from} provided, but upstream stage {stage_id} has no cached artifact in {state_path}")
                print(f"[skip-start] {stage_id} skipped due to --start-from (artifact reused)")
                # Ensure artifact_index is populated even for skipped stages (it should already be from _preload_artifacts_from_state, but verify)
                if stage_id in artifact_index:
                    continue
                # Fallback: try to load from state if not already in artifact_index
                try:
                    with open(state_path, "r", encoding="utf-8") as f:
                        state = json.load(f)
                    st = state.get("stages", {}).get(stage_id)
                    if st and st.get("status") == "done" and st.get("artifact") and os.path.exists(st.get("artifact")):
                        artifact_index[stage_id] = {"path": st.get("artifact"), "schema": st.get("schema_version")}
                except Exception:
                    pass
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

        # Guard: Prevent --force from re-running expensive stages unnecessarily
        # Expensive stages: extract (OCR), escalate_vision (GPT-4V), intake (OCR ensemble)
        if args.force and not args.dry_run and os.path.exists(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                st = state.get("stages", {}).get(stage_id)
                if st and st.get("status") == "done" and os.path.exists(st.get("artifact", "")):
                    expensive_stages = {"extract", "intake", "escalate_vision"}
                    if stage in expensive_stages or any(exp in stage_id.lower() for exp in ["ocr", "extract", "escalate", "intake"]):
                        print(f"[force-guard] Skipping expensive stage {stage_id} (already done). Use --skip-done --start-from <stage> to resume from a specific stage instead.")
                        logger.log(stage_id, "skipped", artifact=st.get("artifact"), module_id=module_id,
                                   message="Skipped due to force-guard (expensive stage already done)", stage_description=stage_description)
                        artifact_index[stage_id] = {"path": st.get("artifact"), "schema": st.get("schema_version")}
                        record_stage_instrumentation(stage_id, module_id, "skipped", st.get("artifact"), st.get("schema_version"),
                                                     stage_started_at, stage_wall_start, stage_cpu_start)
                        continue
            except Exception:
                pass

        # Skip if already done and skip-done requested (state + artifact exists)
        # Exception: package_game_ready_v1 should always run to ensure output folder is up to date
        always_run_modules = {"package_game_ready_v1"}
        if args.skip_done and os.path.exists(state_path) and module_id not in always_run_modules:
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
        if stage in ("intake", "extract"):
            # Handle intake stages that may have inputs (like pagelines_to_elements_v1)
            inputs_map = node.get("inputs", {}) or {}
            if inputs_map:
                for key, origin in inputs_map.items():
                    if origin in artifact_index:
                        artifact_inputs[key] = artifact_index[origin]["path"]
                    else:
                        artifact_inputs[key] = origin
        elif stage in {"clean", "portionize", "consensus", "dedupe", "normalize", "resolve", "build", "enrich", "adapter", "export", "app", "validate", "transform"}:
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
                # Pass through any extra build inputs (e.g., issues_report)
                for extra_key, extra_origin in inputs_map.items():
                    if extra_key in {"pages", "portions"}:
                        continue
                    if extra_origin in artifact_index:
                        artifact_inputs[extra_key] = artifact_index[extra_origin]["path"]
                    else:
                        artifact_inputs[extra_key] = extra_origin
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
                if node.get("module") == "merge_boundaries_pref_v1":
                    # Provide elements_core for filtering/sorting if available
                    if "reduce_ir" in artifact_index:
                        artifact_inputs["elements_core"] = artifact_index["reduce_ir"]["path"]
            elif stage == "transform":
                inputs_map = node.get("inputs", {}) or {}
                for key, origin in inputs_map.items():
                    if origin in artifact_index:
                        artifact_inputs[key] = artifact_index[origin]["path"]
                    else:
                        # In dry-run or when resuming, artifact_index might not be populated yet, so use the expected path
                        if origin in plan["nodes"]:
                            # Try to construct expected path from stage_id
                            # Get the origin node from the plan
                            origin_node = plan["nodes"][origin]
                            expected_artifact_name = origin_node.get("artifact_name") or _artifact_name_for_stage(origin, origin_node.get("stage", "extract"), {}, origin_node)
                            if stage_ordinal_map and origin in stage_ordinal_map:
                                ordinal = stage_ordinal_map[origin]
                                origin_module_id = origin_node.get("module")
                                if origin_module_id:
                                    module_folder = f"{ordinal:02d}_{origin_module_id}"
                                    module_dir = os.path.join(run_dir, module_folder)
                                    expected_path = os.path.join(module_dir, expected_artifact_name)
                                    # Only use expected path if file exists or in dry-run
                                    if args.dry_run or os.path.exists(expected_path):
                                        artifact_inputs[key] = expected_path
                                        continue
                        # Fallback: use origin as-is (might be a path string)
                        artifact_inputs[key] = origin
            elif stage == "validate":
                inputs_map = node.get("inputs", {}) or {}
                for key, origin in inputs_map.items():
                    if origin in artifact_index:
                        artifact_inputs[key] = artifact_index[origin]["path"]
                    else:
                        artifact_inputs[key] = origin
                # Provide defaults if not explicitly mapped
                if "boundaries" not in artifact_inputs:
                    if "assemble_boundaries" in artifact_index:
                        artifact_inputs["boundaries"] = artifact_index["assemble_boundaries"]["path"]
                if "elements" not in artifact_inputs:
                    if "intake" in artifact_index:
                        artifact_inputs["elements"] = artifact_index["intake"]["path"]
                if "elements_core" not in artifact_inputs:
                    if "reduce_ir" in artifact_index:
                        artifact_inputs["elements_core"] = artifact_index["reduce_ir"]["path"]
                if "portions" not in artifact_inputs:
                    if "ai_extract" in artifact_index:
                        artifact_inputs["portions"] = artifact_index["ai_extract"]["path"]
            else:
                inputs_map = node.get("inputs", {}) or {}
                origin = inputs_map.get("pages") or (needs[0] if needs else None)
                if not origin:
                    raise SystemExit(f"Stage {stage_id} missing upstream input")
                key = "pages" if stage in {"clean", "portionize"} else "input"
                artifact_inputs[key] = artifact_index[origin]["path"] if origin in artifact_index else origin
                # Capture any additional named inputs (e.g., boundaries) so modules can access them.
                for extra_key, extra_origin in inputs_map.items():
                    if extra_key == "pages":
                        continue
                    artifact_inputs[extra_key] = artifact_index.get(extra_origin, {}).get("path", extra_origin)
                producer_schema = artifact_index[origin].get("schema") if origin in artifact_index else None
                expected_schema = node.get("input_schema")
                if expected_schema and producer_schema and expected_schema != producer_schema:
                    raise SystemExit(f"Schema mismatch: {stage_id} expects {expected_schema} got {producer_schema} from {origin}")

        # In dry-run mode, populate artifact_index with expected paths before building command
        # so that downstream stages can resolve their inputs
        if args.dry_run:
            # Compute artifact_path early for dry-run so artifact_index can be populated
            artifact_name = node.get("artifact_name") or _artifact_name_for_stage(stage_id, stage, {}, node)
            is_final_output = (artifact_name in ("gamebook.json", "validation_report.json"))
            if is_final_output:
                artifact_path = os.path.join(run_dir, artifact_name)
            else:
                if stage_ordinal_map and stage_id and stage_id in stage_ordinal_map:
                    ordinal = stage_ordinal_map[stage_id]
                    module_id = node.get("module")
                    if module_id:
                        module_folder = f"{ordinal:02d}_{module_id}"
                        module_dir = os.path.join(run_dir, module_folder)
                        artifact_path = os.path.join(module_dir, artifact_name)
                    else:
                        artifact_path = os.path.join(run_dir, artifact_name)
                else:
                    artifact_path = os.path.join(run_dir, artifact_name)
            artifact_index[stage_id] = {"path": artifact_path, "schema": out_schema}

        artifact_path, cmd, cwd = build_command(entrypoint, node["params"], node, run_dir,
                                                recipe.get("input", {}), state_path, progress_path, run_id,
                                                artifact_inputs, artifact_index, stage_ordinal_map)
        

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
            pages_path = artifact_index[upstream]["path"]
            artifact_path = mock_clean(pages_path, artifact_path, module_id, run_id)
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
            pages_path = artifact_index[upstream]["path"]
            artifact_path = mock_portionize(pages_path, artifact_path, module_id, run_id)
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
            in_path = artifact_index[upstream]["path"]
            artifact_path = mock_consensus(in_path, artifact_path, module_id, run_id)
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
        env["PIPELINE_STAGE_ID"] = stage_id
        # Mitigate libomp SHM failures for EasyOCR/torch by forcing file-backed registration.
        if module_id == "extract_ocr_ensemble_v1":
            env.setdefault("KMP_USE_SHMEM", "0")
            env.setdefault("KMP_CREATE_SHMEM", "FALSE")
            # Some libomp builds use alternate env var names.
            env.setdefault("KMP_USE_SHM", "0")
            env.setdefault("KMP_CREATE_SHM", "0")
            env.setdefault("KMP_DISABLE_SHM", "1")
            env.setdefault("OMP_NUM_THREADS", "1")
            env.setdefault("KMP_AFFINITY", "disabled")
            env.setdefault("KMP_INIT_AT_FORK", "FALSE")
        if instrument_enabled:
            proc = subprocess.Popen(cmd, cwd=cwd, env=env)
            last_live_update = 0.0
            while True:
                rc = proc.poll()
                if rc is not None:
                    result = subprocess.CompletedProcess(cmd, rc)
                    break
                now = time.time()
                if now - last_live_update >= 2.0:
                    update_live_instrumentation(stage_id, module_id, stage_description,
                                                stage_started_at, stage_wall_start, stage_cpu_start)
                    last_live_update = now
                time.sleep(0.2)
        else:
            result = subprocess.run(cmd, cwd=cwd, env=env)
        if result.returncode != 0:
            # Treat validation failure as a successful stage completion for game-ready checks.
            if module_id == "validate_game_ready_v1" and result.returncode == 1:
                try:
                    update_state(state_path, progress_path, stage_id, "done", artifact_path, run_id, module_id, out_schema,
                                 stage_description=stage_description)
                    record_stage_instrumentation(stage_id, module_id, "done", artifact_path, out_schema,
                                                 stage_started_at, stage_wall_start, stage_cpu_start)
                    logger.log(stage_id, "warning", artifact=artifact_path, module_id=module_id,
                               message="Game-ready validation failed (report generated).", extra={"exit_code": 1})
                except Exception:
                    pass
                # Continue pipeline but mark run as failed at end.
                run_validation_failed = True
                continue
            update_state(state_path, progress_path, stage_id, "failed", artifact_path, run_id, module_id, out_schema,
                         stage_description=stage_description)
            record_stage_instrumentation(stage_id, module_id, "failed", artifact_path, out_schema,
                                         stage_started_at, stage_wall_start, stage_cpu_start)
            try:
                elapsed = time.perf_counter() - stage_wall_start
                logger.log(stage_id, "failed", artifact=artifact_path, module_id=module_id,
                           message=f"Stage failed after {elapsed:.2f}s", extra={"elapsed_seconds": round(elapsed, 2)})
            except Exception:
                pass
            try:
                if state_path and os.path.exists(state_path):
                    with open(state_path, "r", encoding="utf-8") as f:
                        state = json.load(f)
                    state["status"] = "failed"
                    state["status_reason"] = f"stage {stage_id} failed"
                    state["ended_at"] = datetime.utcnow().isoformat(timespec="microseconds") + "Z"
                    with open(state_path, "w", encoding="utf-8") as f:
                        json.dump(state, f, indent=2)
            except Exception:
                pass
            raise SystemExit(f"Stage {stage_id} failed with code {result.returncode}")
        # Stamp and validate if schema known
        if out_schema:
            stamp_artifact(artifact_path, out_schema, module_id, run_id)
            if not args.no_validate:
                model_cls = SCHEMA_MAP.get(out_schema)
                if model_cls:
                    errors = 0
                    total = 0
                    # Handle both JSONL and JSON files
                    # JSON files (like validation_report.json) are single objects, not line-delimited
                    if artifact_path.endswith('.json') and not artifact_path.endswith('.jsonl'):
                        try:
                            with open(artifact_path, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            total = 1
                            try:
                                model_cls(**data)
                            except Exception as e:
                                errors = 1
                                print(f"[validate error] {artifact_path}: {e}")
                        except json.JSONDecodeError as e:
                            errors = 1
                            print(f"[validate error] {artifact_path}: Invalid JSON: {e}")
                    else:
                        # JSONL files (line-delimited)
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
        
        # Copy key intermediate artifacts to root for visibility
        artifact_name = node.get("artifact_name", os.path.basename(artifact_path))
        copy_key_artifact_to_root(artifact_path, run_dir, artifact_name, artifact_index)
        
        record_stage_instrumentation(stage_id, module_id, "done", artifact_path, out_schema,
                                     stage_started_at, stage_wall_start, stage_cpu_start)
        stage_timings[stage_id] = time.perf_counter() - stage_wall_start
        # Don't log generic "Stage completed" message - let modules log their own summaries
        # This prevents overwriting module-specific messages with generic ones
        # wall_seconds is already captured in timing_summary from stage_timings

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

    # Lightweight summary (always emit, even on failure)
    timing_summary = {}
    for sid, seconds in stage_timings.items():
        timing_summary[sid] = {"wall_seconds": round(seconds, 2)}
    try:
        if progress_path and os.path.exists(progress_path):
            # Build mapping from module_id to recipe stage IDs (for modules used in multiple stages)
            module_to_stage_ids: Dict[str, List[str]] = {}
            for sid, node in plan["nodes"].items():
                module_id = node.get("module")
                if module_id:
                    module_to_stage_ids.setdefault(module_id, []).append(sid)
            
            last_messages = {}
            last_metrics = {}
            with open(progress_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        evt = json.loads(line)
                    except Exception:
                        continue
                    stage = evt.get("stage")
                    status = evt.get("status")
                    message = evt.get("message")
                    module_id = evt.get("module_id")
                    
                    # Map module stage name to recipe stage ID
                    # If stage is already a recipe stage ID, use it directly
                    # Otherwise, try to map via module_id
                    recipe_stage_id = stage
                    if stage and stage not in plan["nodes"] and module_id:
                        # Stage name doesn't match recipe ID, try to find via module_id
                        candidate_stages = module_to_stage_ids.get(module_id, [])
                        if len(candidate_stages) == 1:
                            # Only one stage uses this module, use it
                            recipe_stage_id = candidate_stages[0]
                        elif len(candidate_stages) > 1:
                            # Multiple stages use this module - need to disambiguate
                            # For now, prefer the one that matches the stage name pattern or use the first
                            # This is a heuristic - ideally modules would log with recipe stage IDs
                            recipe_stage_id = candidate_stages[0]  # Fallback to first
                    
                    if recipe_stage_id and message and status in {"done", "warning", "failed"}:
                        last_messages[recipe_stage_id] = message
                    if recipe_stage_id and status in {"done", "warning", "failed"}:
                        metrics = (evt.get("extra") or {}).get("summary_metrics")
                        if isinstance(metrics, dict):
                            last_metrics[recipe_stage_id] = metrics
            for sid, msg in last_messages.items():
                if sid not in timing_summary:
                    timing_summary[sid] = {}
                # Only add summary if it's not a generic "Stage completed in Xs" message
                # Those should just use wall_seconds instead
                if msg and not msg.startswith("Stage completed in"):
                    timing_summary[sid]["summary"] = msg
            for sid, metrics in last_metrics.items():
                if sid not in timing_summary:
                    timing_summary[sid] = {}
                timing_summary[sid]["metrics"] = metrics
            # Ensure all stages in timing_summary have wall_seconds (from stage_timings)
            # This should already be there, but ensure it for any stages added via messages/metrics
            for sid in list(timing_summary.keys()):
                if "wall_seconds" not in timing_summary[sid] and sid in stage_timings:
                    timing_summary[sid]["wall_seconds"] = round(stage_timings[sid], 2)
    except Exception:
        pass
    try:
        # Add pages/min for intake/extract when possible
        for sid, node in plan["nodes"].items():
            if node["stage"] in ("intake", "extract"):
                art_path = artifact_index.get(sid, {}).get("path")
                if art_path and os.path.exists(art_path):
                    with open(art_path, "r", encoding="utf-8") as f:
                        pages = sum(1 for _ in f if _.strip())
                    if pages and sid in timing_summary and timing_summary[sid]["wall_seconds"] > 0:
                        minutes = timing_summary[sid]["wall_seconds"] / 60.0
                        timing_summary[sid]["pages"] = pages
                        timing_summary[sid]["pages_per_min"] = round(pages / minutes, 2)
    except Exception:
        pass
    try:
        timing_path = os.path.join(run_dir, "timing_summary.json")
        # Build ordered summary using topological execution order
        ordered_summary = {}
        for sid in plan.get("topo", []):
            if sid in timing_summary:
                ordered_summary[sid] = timing_summary[sid]
        # Include any stages in timing_summary that aren't in topo (shouldn't happen, but be safe)
        for sid, data in timing_summary.items():
            if sid not in ordered_summary:
                ordered_summary[sid] = data
        save_json(timing_path, ordered_summary)
        print("[summary] run:", json.dumps(ordered_summary, indent=2))
    except Exception:
        pass

    # Stamp top-level run status for dashboards/monitors.
    try:
        state = {}
        if os.path.exists(state_path):
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
        if run_validation_failed:
            state["status"] = "failed"
            state["status_reason"] = "game_ready_validation_failed"
        else:
            state["status"] = "done"
        state["ended_at"] = datetime.utcnow().isoformat(timespec="microseconds") + "Z"
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass

    print("Recipe complete.")


if __name__ == "__main__":
    main()
