#!/usr/bin/env python3
"""Generate edge-case patch JSONL via targeted AI analysis."""
import argparse
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from modules.common.openai_client import OpenAI
from modules.common.utils import ProgressLogger


SYSTEM_PROMPT = """You are an expert verifier for Fighting Fantasy gamebook JSON.
Your task is to confirm whether the existing JSON matches the section HTML and the schema rules.
You will receive:
- The section JSON (full object)
- The section's presentation_html
- A list of edge-case issue codes for this section

Return a JSON object with:
{
  "confidence": "high" | "medium" | "low",
  "patches": [
    {
      "section_id": "143",
      "reason_code": "survival_gate_damage",
      "path": "/sections/143/sequence/0",
      "op": "replace",
      "value": {...},
      "ai_rationale": "short explanation"
    }
  ],
  "findings": [
    {"issue": "...", "evidence": "short quote or paraphrase"}
  ]
}

Critical rules:
- Assume the JSON is correct unless the HTML provides explicit evidence of mismatch.
- If the JSON is correct, return an empty patches list.
- Only propose patches that directly fix the listed issue codes.
- Use op = add/replace/remove only.
- Prefer minimal change; keep existing structure if possible.
- If the schema cannot represent the fix (e.g., stat-based survival gates), return no patches.

Allowed sequence event kinds: choice, stat_change, stat_check, test_luck, item, item_check, state_check,
conditional (item-only condition), combat, death, custom.

Schema constraints:
- Events MUST use "kind" (not "type").
- conditional.condition must be { kind: "item", itemName: "...", operator?: "has"|"missing" }.
- death event: { kind: "death", outcome: { terminal: { kind: "death" } }, description?: "..." }.

Do not invent new event kinds or fields.
If no patch is needed, return {"confidence":"high","patches":[],"findings":[]}.
"""


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _load_scan(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        line = f.readline().strip()
    return json.loads(line) if line else {}


def _group_issues(issues: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for issue in issues:
        sid = str(issue.get("section_id") or "")
        if not sid:
            continue
        grouped.setdefault(sid, []).append(issue)
    return grouped


def _load_gamebook(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_prompt(section_id: str, section: Dict[str, Any], issues: List[Dict[str, Any]]) -> str:
    return json.dumps({
        "section_id": section_id,
        "presentation_html": section.get("presentation_html"),
        "section_json": section,
        "issues": [{
            "reason_code": i.get("reason_code"),
            "signal": i.get("signal"),
            "snippet": i.get("snippet"),
        } for i in issues],
    }, ensure_ascii=True, indent=2)


def _valid_sequence_event(event: Dict[str, Any]) -> bool:
    if not isinstance(event, dict):
        return False
    kind = event.get("kind")
    if not kind or not isinstance(kind, str):
        return False
    if kind == "conditional":
        condition = event.get("condition")
        if not isinstance(condition, dict):
            return False
        if condition.get("kind") != "item":
            return False
    if kind == "death":
        outcome = event.get("outcome")
        if not isinstance(outcome, dict):
            return False
        terminal = outcome.get("terminal")
        if not isinstance(terminal, dict) or terminal.get("kind") != "death":
            return False
    return True


def _patch_value_valid(path: str, value: Any) -> bool:
    if "/sequence" not in path:
        return True
    if isinstance(value, list):
        return all(_valid_sequence_event(ev) for ev in value)
    if isinstance(value, dict):
        return _valid_sequence_event(value)
    return False


def _coerce_patch(patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(patch, dict):
        return None
    required = ("section_id", "reason_code", "path", "op")
    if not all(patch.get(k) for k in required):
        return None
    op = patch.get("op")
    if op not in {"add", "replace", "remove"}:
        return None
    if op != "remove" and "value" not in patch:
        return None
    if op != "remove" and not _patch_value_valid(patch.get("path"), patch.get("value")):
        return None
    return patch


def _extract_patches(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {"confidence": "low", "patches": []}
    confidence = payload.get("confidence", "low")
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    patches = payload.get("patches")
    if not isinstance(patches, list):
        patches = []
    return {"confidence": confidence, "patches": patches}


def _metrics_path(out_path: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(out_path))
    return os.path.join(base_dir, "edgecase_ai_patch_metrics.json")


def _write_metrics(out_path: str, metrics: Dict[str, Any]) -> str:
    path = _metrics_path(out_path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=True, indent=2)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate edge-case patches using AI.")
    parser.add_argument("--scan", help="edgecase_scan.jsonl")
    parser.add_argument("--gamebook", help="gamebook.json")
    parser.add_argument("--inputs", nargs="*", help="Driver adapter input list (scan, gamebook)")
    parser.add_argument("--out", required=True, help="Output patch JSONL")
    parser.add_argument("--model", default="gpt-5")
    parser.add_argument("--max-sections", type=int, default=25)
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    scan_path = args.scan
    gamebook_path = args.gamebook
    if args.inputs:
        if len(args.inputs) >= 1 and not scan_path:
            scan_path = args.inputs[0]
        if len(args.inputs) >= 2 and not gamebook_path:
            gamebook_path = args.inputs[1]
        if len(args.inputs) == 1 and scan_path and not gamebook_path:
            run_dir = os.path.abspath(os.path.join(os.path.dirname(scan_path), ".."))
            candidate = os.path.join(run_dir, "gamebook.json")
            if os.path.exists(candidate):
                gamebook_path = candidate
    if not scan_path or not gamebook_path:
        raise SystemExit("edgecase_ai_patch_v1 requires --scan and --gamebook (or --inputs with both paths)")

    scan = _load_scan(scan_path)
    issues = scan.get("issues") or []
    grouped = _group_issues(issues)

    gamebook = _load_gamebook(gamebook_path)
    client = OpenAI()

    out_rows: List[Dict[str, Any]] = []
    processed = 0
    sections_no_change = 0
    sections_patched = 0
    sections_low_confidence = 0
    for section_id, section_issues in grouped.items():
        if processed >= args.max_sections:
            break
        section = gamebook.get("sections", {}).get(section_id)
        if not isinstance(section, dict):
            continue
        prompt = _build_prompt(section_id, section, section_issues)
        try:
            response = client.chat.completions.create(
                model=args.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            extracted = _extract_patches(data)
            confidence = extracted["confidence"]
            patches = extracted["patches"]
            if confidence != "high":
                sections_low_confidence += 1
                patches = []
            if not patches:
                sections_no_change += 1
            for patch in patches:
                coerced = _coerce_patch(patch)
                if coerced:
                    coerced.setdefault("schema_version", "edgecase_patch_v1")
                    coerced.setdefault("module_id", "edgecase_ai_patch_v1")
                    coerced.setdefault("run_id", args.run_id)
                    coerced.setdefault("created_at", _utc())
                    out_rows.append(coerced)
            if patches:
                sections_patched += 1
        except Exception as exc:
            logger.log(
                "edgecase_ai_patch",
                "warning",
                message=f"AI patch generation failed for section {section_id}: {exc}",
                module_id="edgecase_ai_patch_v1",
            )
        processed += 1

    with open(args.out, "w", encoding="utf-8") as f:
        for row in out_rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    metrics = {
        "patch_count": len(out_rows),
        "sections_processed": processed,
        "sections_no_change": sections_no_change,
        "sections_patched": sections_patched,
        "sections_low_confidence": sections_low_confidence,
    }
    metrics_path = _write_metrics(args.out, metrics)

    logger.log(
        "edgecase_ai_patch",
        "done",
        current=processed,
        total=len(grouped),
        message=f"Generated {len(out_rows)} patches from {processed} sections",
        artifact=args.out,
        module_id="edgecase_ai_patch_v1",
        schema_version="edgecase_patch_v1",
        extra={"summary_metrics": metrics},
    )
    print(f"[summary] edgecase_ai_patch_v1: {len(out_rows)} patches from {processed} sections → {args.out}")
    print(f"[metrics] edgecase_ai_patch_v1: {metrics_path}")


if __name__ == "__main__":
    main()
