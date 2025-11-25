import argparse
import json
from typing import Dict, List, Set, Tuple

from modules.common.utils import read_jsonl


def load_payload(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_nodes(nodes: List[Dict], allow_unresolved: bool, start_id: str = None, check_reachability: bool = True) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    ids: Set[str] = set()
    for idx, n in enumerate(nodes, start=1):
        nid = n.get("id")
        if not nid:
            errors.append(f"[node {idx}] missing id")
            continue
        if nid in ids:
            errors.append(f"[node {idx}] duplicate id {nid}")
        ids.add(nid)
    for idx, n in enumerate(nodes, start=1):
        nid = n.get("id")
        for t in n.get("targets") or []:
            if t not in ids:
                (warnings if allow_unresolved else errors).append(f"[node {nid}] target {t} not found")
        if n.get("is_terminal") and (n.get("choices") or n.get("targets")):
            errors.append(f"[node {nid}] is_terminal true but has choices/targets")
        if not n.get("is_terminal") and not (n.get("choices") or n.get("targets")):
            errors.append(f"[node {nid}] non-terminal without choices/targets")
    if start_id and check_reachability:
        graph = {n.get("id"): n.get("targets") or [] for n in nodes if n.get("id")}
        visited: Set[str] = set()
        stack = [start_id]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            for t in graph.get(cur, []):
                if t in graph:
                    stack.append(t)
        unreachable = sorted([nid for nid in ids if nid not in visited])
        if unreachable:
            (warnings if allow_unresolved else errors).append(f"Unreachable nodes from {start_id}: {unreachable}")

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description="Validate app_data_v1 graph consistency.")
    parser.add_argument("--input", required=True, help="Path to data.json")
    parser.add_argument("--enriched", help="Optional enriched_portion JSONL for cross-check")
    parser.add_argument("--allow-unresolved-targets", action="store_true", help="Downgrade missing target nodes to warnings")
    parser.add_argument("--start-id", help="Root node id to check reachability from")
    parser.add_argument("--no-reachability", action="store_true", help="Skip reachability check even if start-id provided")
    args = parser.parse_args()

    payload = load_payload(args.input)
    if payload.get("schema_version") != "app_data_v1":
        raise SystemExit(f"Unexpected schema_version {payload.get('schema_version')}")

    nodes = payload.get("nodes") or []
    errors, warnings = validate_nodes(
        nodes,
        allow_unresolved=args.allow_unresolved_targets,
        start_id=args.start_id,
        check_reachability=not args.no_reachability,
    )

    if args.enriched:
        target_set = set()
        for row in read_jsonl(args.enriched):
            for ch in row.get("choices") or []:
                tgt = ch.get("target")
                if tgt:
                    target_set.add(tgt)
        node_ids = {n.get("id") for n in nodes if n.get("id")}
        missing_nodes = sorted(list(target_set - node_ids))
        if missing_nodes:
            (warnings if args.allow_unresolved_targets else errors).append(
                f"Targets referenced in enriched but missing in app_data: {missing_nodes}")

    if errors:
        print("Validation FAILED:")
        for e in errors:
            print(" -", e)
        if warnings:
            print("Warnings:")
            for w in warnings:
                print(" -", w)
        raise SystemExit(1)
    if warnings:
        print("Validation OK with warnings:")
        for w in warnings:
            print(" -", w)
    else:
        print(f"Validation OK: {len(nodes)} nodes")


if __name__ == "__main__":
    main()
