import argparse
import json
import yaml
from pathlib import Path
from typing import List, Dict, Any

from modules.common.utils import ensure_dir, read_jsonl, save_jsonl


def load_catalog(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_signals(path: Path) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "signals" in data:
        return list(data["signals"])
    if isinstance(data, list):
        return list(data)
    raise ValueError("signals file must be a list or dict with 'signals'")


def load_plan(plan_path: Path) -> Dict[str, Any]:
    if not plan_path:
        return {}
    rows = list(read_jsonl(plan_path))
    return rows[0] if rows else {}


def compute_gaps(signals: List[str], catalog: Dict[str, Any], signal_evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cap_to_modules = {c["name"]: c.get("modules", []) for c in catalog.get("capabilities", [])}
    gaps = []
    for sig in signals:
        modules = cap_to_modules.get(sig, [])
        if not modules:
            pages = []
            for ev in signal_evidence:
                if ev.get("signal") == sig:
                    pages.extend(ev.get("pages", []))
            gaps.append({
                "capability": sig,
                "severity": "missing",
                "suggested_action": f"Add module for {sig} (none available)",
                "notes": None,
                "pages": pages,
            })
    return gaps


def main():
    parser = argparse.ArgumentParser(description="Analyze capability gaps for intake plan.")
    parser.add_argument("--plan-in", "--plan_in", dest="plan_in", help="Existing intake_plan_v1 JSON", default=None)
    parser.add_argument("--out", required=True, help="Path to write updated intake_plan_v1 JSON")
    parser.add_argument("--signals", help="JSON file with detected signals/capabilities", default=None)
    parser.add_argument("--catalog_path", default="modules/module_catalog.yaml", help="Module catalog YAML")
    parser.add_argument("--state-file", dest="state_file", help="pipeline state file (ignored)", default=None)
    parser.add_argument("--progress-file", dest="progress_file", help="pipeline progress log (ignored)", default=None)
    parser.add_argument("--run-id", dest="run_id", help="run id (ignored)", default=None)
    args, _unknown = parser.parse_known_args()

    plan = load_plan(Path(args.plan_in)) if args.plan_in else {}
    signals: List[str] = []
    if args.signals:
        signals = load_signals(Path(args.signals))
    plan_signals = plan.get("signals", [])
    combined_signals = list(dict.fromkeys(plan_signals + signals))

    catalog = load_catalog(Path(args.catalog_path))
    gaps = compute_gaps(combined_signals, catalog, plan.get("signal_evidence", []))

    plan.setdefault("schema_version", "intake_plan_v1")
    plan.setdefault("book_type", "other")
    plan.setdefault("sections", [])
    plan.setdefault("zoom_requests", [])
    plan.setdefault("assumptions", [])
    plan.setdefault("warnings", [])
    plan.setdefault("sheets", [])
    plan.setdefault("meta", {})
    plan["signals"] = combined_signals
    plan["capability_gaps"] = gaps

    if gaps:
        plan.setdefault("warnings", []).append("Missing capabilities: " + ", ".join({g['capability'] for g in gaps}))

    ensure_dir(Path(args.out).parent)
    save_jsonl(args.out, [plan])

    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
