"""
Benchmark harness for running driver recipes with instrumentation enabled and aggregating
cost/time/token metrics into JSONL/CSV.
"""

import argparse
import copy
import csv
import datetime as dt
import json
import os
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Tuple

import yaml


def parse_slices(spec: str) -> List[Tuple[int, int]]:
    """
    Parse slice specification like "1-1,15-15,42" into list of (start, end) tuples.
    """
    slices: List[Tuple[int, int]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s or start_s)
        else:
            start = end = int(part)
        if end < start:
            start, end = end, start
        slices.append((start, end))
    return slices


def load_recipe(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_recipe(path: str, recipe: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(recipe, f, sort_keys=False)


def slugify(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in text).strip("-_")


def run_driver(recipe_path: str, *, settings: str = None, instrument: bool = True) -> int:
    cmd = [sys.executable, "driver.py", "--recipe", recipe_path]
    if settings:
        cmd += ["--settings", settings]
    if instrument:
        cmd.append("--instrument")
    # force rerun so slices stay isolated
    cmd.append("--force")
    proc = subprocess.run(cmd, capture_output=False)
    return proc.returncode


def load_instrumentation(run_dir: str) -> Dict[str, Any]:
    path = os.path.join(run_dir, "instrumentation.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def make_variant_recipe(
    base: Dict[str, Any],
    *,
    run_id: str,
    run_dir: str,
    slice_range: Tuple[int, int],
    model: str,
    boost_model: str = None,
    portion_window: int = None,
    price_table: str = None,
) -> Dict[str, Any]:
    recipe = copy.deepcopy(base)
    recipe["run_id"] = run_id
    recipe["output_dir"] = run_dir
    recipe.setdefault("name", run_id)
    recipe["instrumentation"] = {
        "enabled": True,
        "price_table": price_table or recipe.get("instrumentation", {}).get("price_table"),
    }

    start, end = slice_range
    input_cfg = recipe.get("input") or {}
    for st in recipe.get("stages", []):
        params = st.setdefault("params", {})
        if st.get("stage") == "extract" and "pdf" in input_cfg:
            params["start"] = start
            params["end"] = end
        if model and "model" in params:
            params["model"] = model
        if boost_model and "boost_model" in params:
            params["boost_model"] = boost_model
        if portion_window and st.get("stage") == "portionize":
            params["window"] = portion_window
    return recipe


def aggregate_row(run_meta: Dict[str, Any], *, variant: str, slice_range: Tuple[int, int], model: str, boost_model: str, window: int, run_dir: str) -> Dict[str, Any]:
    totals = (run_meta or {}).get("totals", {}) or {}
    return {
        "run_id": (run_meta or {}).get("run_id"),
        "variant": variant,
        "slice_start": slice_range[0],
        "slice_end": slice_range[1],
        "model": model,
        "boost_model": boost_model,
        "window": window,
        "wall_seconds": totals.get("wall_seconds"),
        "calls": totals.get("calls"),
        "prompt_tokens": totals.get("prompt_tokens"),
        "completion_tokens": totals.get("completion_tokens"),
        "cost": totals.get("cost"),
        "run_dir": run_dir,
    }


def write_outputs(rows: Iterable[Dict[str, Any]], out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    rows = list(rows)
    csv_path = os.path.join(out_dir, "bench_metrics.csv")
    if rows:
        fieldnames = list(rows[0].keys())
    else:
        fieldnames = ["run_id", "variant", "slice_start", "slice_end", "model", "boost_model", "window", "wall_seconds", "calls", "prompt_tokens", "completion_tokens", "cost", "run_dir"]
    with open(csv_path, "w", newline="", encoding="utf-8") as cf:
        writer = csv.DictWriter(cf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    jsonl_path = os.path.join(out_dir, "bench_metrics.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as jf:
        for row in rows:
            jf.write(json.dumps(row) + "\n")


def write_metadata(session_dir: str, *, session_id: str, tag: str, recipe_path: str, price_table: str,
                   slices: List[Tuple[int, int]], models: List[str], portion_window: int = None,
                   boost_model: str = None, rows: List[Dict[str, Any]] = None) -> None:
    meta = {
        "schema_version": "bench_session_v1",
        "session_id": session_id,
        "tag": tag,
        "created_at": dt.datetime.utcnow().isoformat() + "Z",
        "base_recipe": recipe_path,
        "price_table": price_table,
        "slices": slices,
        "models": models,
        "portion_window": portion_window,
        "boost_model": boost_model,
        "runs": rows or [],
    }
    path = os.path.join(session_dir, "metadata.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Run cost/perf benchmarks across slices and model variants.")
    parser.add_argument("--recipe", required=True, help="Base recipe YAML to clone per run.")
    parser.add_argument("--slices", default="1-2", help="Comma-separated page slices (start-end). Example: 1-1,15-15,42-42")
    parser.add_argument("--models", nargs="+", default=None, help="Model list to sweep (applies to stages with 'model' param).")
    parser.add_argument("--boost-model", help="Override boost_model param where present.")
    parser.add_argument("--portion-window", type=int, help="Override portionize window.")
    parser.add_argument("--settings", help="Optional settings file passed to driver.")
    parser.add_argument("--price-table", default="configs/pricing.default.yaml", help="Pricing table for instrumentation.")
    parser.add_argument("--tag", default="cost-perf", help="Tag for bench session.")
    parser.add_argument("--session", help="Optional session id; defaults to bench-<tag>-<timestamp>.")
    parser.add_argument("--output-root", default="output/runs", help="Directory to store bench session and run outputs.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned runs without executing driver.")
    args = parser.parse_args()

    base_recipe = load_recipe(args.recipe)
    models = args.models or [base_recipe.get("stages", [{}])[0].get("params", {}).get("model") or "gpt-4.1-mini"]
    slices = parse_slices(args.slices)

    ts = dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    session_id = args.session or f"bench-{slugify(args.tag)}-{ts}"
    session_dir = os.path.join(args.output_root, session_id)

    planned_rows: List[Dict[str, Any]] = []

    for model in models:
        for start, end in slices:
            variant = f"{slugify(model)}-p{start:03d}-{end:03d}"
            run_id = f"{session_id}-{variant}"
            run_dir = os.path.join(session_dir, variant)
            recipe = make_variant_recipe(
                base_recipe,
                run_id=run_id,
                run_dir=run_dir,
                slice_range=(start, end),
                model=model,
                boost_model=args.boost_model,
                portion_window=args.portion_window,
                price_table=args.price_table,
            )
            recipe_path = os.path.join(run_dir, "recipe.bench.yaml")
            write_recipe(recipe_path, recipe)
            if args.dry_run:
                print(f"[dry-run] would run model={model} slice={start}-{end} -> {recipe_path}")
                continue
            code = run_driver(recipe_path, settings=args.settings, instrument=True)
            if code != 0:
                print(f"[warn] driver exited with code {code} for run {run_id}")
            run_meta = load_instrumentation(run_dir)
            boost = args.boost_model
            portion_window = args.portion_window
            if boost is None:
                for st in recipe.get("stages", []):
                    if "boost_model" in st.get("params", {}):
                        boost = st["params"]["boost_model"]
                        break
            if portion_window is None:
                for st in recipe.get("stages", []):
                    if st.get("stage") == "portionize":
                        portion_window = st.get("params", {}).get("window")
                        break
            row = aggregate_row(
                run_meta,
                variant=variant,
                slice_range=(start, end),
                model=model,
                boost_model=boost,
                window=portion_window,
                run_dir=run_dir,
            )
            planned_rows.append(row)

    write_outputs(planned_rows, session_dir)
    write_metadata(
        session_dir,
        session_id=session_id,
        tag=args.tag,
        recipe_path=args.recipe,
        price_table=args.price_table,
        slices=slices,
        models=models,
        portion_window=args.portion_window,
        boost_model=args.boost_model,
        rows=planned_rows,
    )
    print(f"[done] wrote {len(planned_rows)} rows to {session_dir}/bench_metrics.csv")


if __name__ == "__main__":
    main()
