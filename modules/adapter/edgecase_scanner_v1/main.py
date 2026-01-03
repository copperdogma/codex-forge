#!/usr/bin/env python3
"""Scan gamebook.json for special-case mechanics and emit a JSONL report."""
import argparse
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from modules.common.utils import ensure_dir, ProgressLogger
from modules.common.html_utils import html_to_text


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _sentence_at(text: str, start: int, end: int) -> str:
    if not text:
        return ""
    left = max(text.rfind(".", 0, start), text.rfind("!", 0, start), text.rfind("?", 0, start))
    right_candidates = [text.find(".", end), text.find("!", end), text.find("?", end)]
    right_candidates = [c for c in right_candidates if c != -1]
    right = min(right_candidates) if right_candidates else len(text)
    if left == -1:
        left = 0
    else:
        left = left + 1
    snippet = text[left:right].strip()
    return snippet or text[max(0, start - 80):min(len(text), end + 80)].strip()


def _first_sentence(text: str) -> str:
    if not text:
        return ""
    parts = re.split(r"[.!?]", text)
    for part in parts:
        snippet = part.strip()
        if snippet:
            return snippet
    return text[:200].strip()


def _combat_is_special(event: Dict[str, Any]) -> bool:
    if not isinstance(event, dict):
        return False
    # Targeted: only flag combats with explicit mechanics beyond basic fights.
    if event.get("special_rules"):
        return True
    enemies = event.get("enemies") or []
    if isinstance(enemies, list):
        for enemy in enemies:
            if isinstance(enemy, dict) and enemy.get("special_rules"):
                return True
    if event.get("rules") or event.get("modifiers") or event.get("triggers"):
        return True
    return False


def _add_issue(
    issues: List[Dict[str, Any]],
    *,
    section_id: str,
    reason_code: str,
    signal: str,
    snippet: str,
    page_start: Optional[Any],
    page_end: Optional[Any],
) -> None:
    issues.append({
        "section_id": section_id,
        "reason_code": reason_code,
        "signal": signal,
        "snippet": snippet,
        "pageStart": page_start,
        "pageEnd": page_end,
    })


def _scan_text(
    section_id: str,
    text: str,
    page_start: Optional[Any],
    page_end: Optional[Any],
    *,
    sequence_kinds: Optional[set],
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    if not text:
        return issues
    lower = text.lower()
    kinds = sequence_kinds or set()

    def has_any_kind(candidates: Tuple[str, ...]) -> bool:
        return any(kind in kinds for kind in candidates)

    complexity_score = 0
    complexity_signals: List[str] = []
    if "combat" in kinds:
        complexity_score += 2
        complexity_signals.append("combat")
    if "luck_check" in kinds:
        complexity_score += 1
        complexity_signals.append("luck_check")
    if "skill_check" in kinds:
        complexity_score += 1
        complexity_signals.append("skill_check")
    if "item_check" in kinds:
        complexity_score += 1
        complexity_signals.append("item_check")
    if "conditional_choice" in kinds:
        complexity_score += 1
        complexity_signals.append("conditional_choice")
    if "stat_change" in kinds:
        complexity_score += 1
        complexity_signals.append("stat_change")
    if "damage" in kinds:
        complexity_score += 1
        complexity_signals.append("damage")

    if re.search(r"\btest your luck\b", lower):
        complexity_score += 1
        complexity_signals.append("text:test_your_luck")
    if re.search(r"\bone at a time\b", lower):
        complexity_score += 2
        complexity_signals.append("text:one_at_a_time")
    if re.search(r"\broll\b.{0,40}\b(die|dice)\b", lower):
        complexity_score += 1
        complexity_signals.append("text:roll_die")
    if re.search(r"\bif you have both\b.{0,140}?\bturn to\b", lower) or re.search(r"\bif you have\b[^.]{0,80}\band\b[^.]{0,80}\bturn to\b", lower):
        complexity_score += 1
        complexity_signals.append("text:multi_item")

    if complexity_score >= 5:
        _add_issue(
            issues,
            section_id=section_id,
            reason_code="high_complexity",
            signal="; ".join(complexity_signals) if complexity_signals else "complexity_score>=5",
            snippet=_first_sentence(text),
            page_start=page_start,
            page_end=page_end,
        )

    alive_match = re.search(r"\bif you (?:are|re) still alive\b|\bif you survive\b|\bif you are alive\b|\bif you are still alive\b|\bif you're alive\b", lower)
    damage_match = re.search(r"\b(lose|reduce|deduct|subtract)\b.{0,40}\bstamina\b", lower)
    roll_match = re.search(r"\broll\b.{0,40}\b(die|dice)\b", lower)
    if alive_match and (damage_match or roll_match) and not has_any_kind(("stat_change", "damage", "luck_check", "skill_check")):
        snippet = _sentence_at(text, alive_match.start(), alive_match.end())
        _add_issue(
            issues,
            section_id=section_id,
            reason_code="survival_gate_damage",
            signal="damage+survival gate",
            snippet=snippet,
            page_start=page_start,
            page_end=page_end,
        )

    pos_branch = re.search(r"\bif you (?:do(?!\s+not)|choose|decide|wish|want|agree|take|drink|eat|attack|fight|enter|open|pull|push|climb|run)\b.{0,140}?\bturn to\b\s*(\d+)", lower)
    neg_branch = re.search(r"\bif you (?:do not|don't|refuse|decline|would rather not|do not wish)\b.{0,140}?\bturn to\b\s*(\d+)", lower)
    if pos_branch and neg_branch and not has_any_kind(("choice", "conditional_choice", "item_check")):
        snippet = _sentence_at(text, pos_branch.start(), pos_branch.end())
        _add_issue(
            issues,
            section_id=section_id,
            reason_code="conditional_choice_branch",
            signal="explicit do/do-not branch",
            snippet=snippet,
            page_start=page_start,
            page_end=page_end,
        )

    has_item = re.search(r"\bif you (?:have|possess|carry)\b.{0,140}?\bturn to\b\s*(\d+)", lower)
    missing_item = re.search(r"\bif you (?:do not have|don't have|do not possess|lack)\b.{0,140}?\bturn to\b\s*(\d+)", lower)
    if has_item and missing_item and not has_any_kind(("item_check", "choice", "conditional_choice")):
        snippet = _sentence_at(text, has_item.start(), has_item.end())
        _add_issue(
            issues,
            section_id=section_id,
            reason_code="dual_item_check",
            signal="has/missing item branches",
            snippet=snippet,
            page_start=page_start,
            page_end=page_end,
        )

    state_check = re.search(r"\bhave you (?:previously |ever )?(?:read|seen|visited)\b.{0,140}?\bturn to\b\s*(\d+)", lower)
    if state_check and not has_any_kind(("state_check", "choice", "conditional_choice")):
        snippet = _sentence_at(text, state_check.start(), state_check.end())
        _add_issue(
            issues,
            section_id=section_id,
            reason_code="dual_state_check",
            signal="state check phrasing",
            snippet=snippet,
            page_start=page_start,
            page_end=page_end,
        )

    sentence_chunks = re.split(r"[.!?]", text)
    for chunk in sentence_chunks:
        chunk_lower = chunk.lower()
        if "turn to" in chunk_lower:
            continue
        if re.search(r"\broll\b.{0,40}\b(die|dice)\b", chunk_lower) and re.search(r"\b(lose|reduce|deduct|subtract)\b.{0,40}\bstamina\b", chunk_lower):
            if has_any_kind(("stat_change", "damage", "luck_check", "skill_check")):
                continue
            snippet = chunk.strip()
            if snippet:
                _add_issue(
                    issues,
                    section_id=section_id,
                    reason_code="dice_damage_no_branch",
                    signal="dice-based stamina loss without branch",
                    snippet=snippet,
                    page_start=page_start,
                    page_end=page_end,
                )
                break

    if (re.search(r"\bif you have both\b.{0,140}?\bturn to\b", lower) or re.search(r"\bif you have\b[^.]{0,80}\band\b[^.]{0,80}\bturn to\b", lower)) and not has_any_kind(("item_check", "choice", "conditional_choice")):
        match = re.search(r"\bif you have\b", lower)
        snippet = _sentence_at(text, match.start(), match.end()) if match else ""
        _add_issue(
            issues,
            section_id=section_id,
            reason_code="multi_item_requirement",
            signal="multiple items required",
            snippet=snippet,
            page_start=page_start,
            page_end=page_end,
        )

    return issues


def scan_gamebook(gamebook: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    sections = gamebook.get("sections") or {}
    for sid, section in sections.items():
        if not isinstance(section, dict):
            continue
        presentation_html = section.get("presentation_html") or section.get("html") or ""
        text = html_to_text(presentation_html) if presentation_html else ""
        sequence = section.get("sequence") or []
        kinds = {item.get("kind") for item in sequence if isinstance(item, dict) and item.get("kind")}
        if "combat" in kinds:
            for item in sequence:
                if isinstance(item, dict) and item.get("kind") == "combat":
                    if _combat_is_special(item):
                        _add_issue(
                            issues,
                            section_id=str(sid),
                            reason_code="special_combat",
                            signal="combat has special rules or extra metadata",
                            snippet=_first_sentence(text),
                            page_start=section.get("pageStart"),
                            page_end=section.get("pageEnd"),
                        )
                        break
        issues.extend(_scan_text(
            section_id=str(sid),
            text=text,
            page_start=section.get("pageStart"),
            page_end=section.get("pageEnd"),
            sequence_kinds=kinds,
        ))
    return issues


def _build_summary(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for issue in issues:
        code = issue.get("reason_code") or "unknown"
        counts[code] = counts.get(code, 0) + 1
    summary = {
        "issue_count": len(issues),
        "by_reason": counts,
    }
    return summary


def _load_unclaimed(path: str) -> List[Dict[str, Any]]:
    if not path:
        return []
    with open(path, "r", encoding="utf-8") as f:
        line = f.readline().strip()
    if not line:
        return []
    data = json.loads(line)
    return data.get("issues") or []


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan gamebook.json for special-case mechanics.")
    parser.add_argument("--input", help="Path to gamebook.json")
    parser.add_argument("--inputs", nargs="*", help="Alias for --input (driver compatibility)")
    parser.add_argument("--gamebook", help="Alias for --input")
    parser.add_argument("--unclaimed", help="Optional turn_to_unclaimed.jsonl to merge")
    parser.add_argument("--out", required=True, help="Output JSONL report path")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    out_path = os.path.abspath(args.out)
    ensure_dir(os.path.dirname(out_path))

    gamebook_path = args.input or args.gamebook
    if not gamebook_path and args.inputs:
        gamebook_path = args.inputs[0]
    if not args.unclaimed and args.inputs and len(args.inputs) > 1:
        args.unclaimed = args.inputs[1]
    if not gamebook_path:
        raise SystemExit("edgecase_scanner_v1 requires --input or --gamebook")

    with open(gamebook_path, "r", encoding="utf-8") as f:
        gamebook = json.load(f)

    issues = scan_gamebook(gamebook)
    if args.unclaimed:
        issues.extend(_load_unclaimed(args.unclaimed))
    summary = _build_summary(issues)

    row = {
        "schema_version": "edgecase_scan_v1",
        "module_id": "edgecase_scanner_v1",
        "run_id": args.run_id,
        "created_at": _utc(),
        "summary": summary,
        "issues": issues,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    status = "warning" if issues else "done"
    logger.log(
        "edgecase_scanner",
        status,
        current=summary["issue_count"],
        total=summary["issue_count"],
        message=f"Edge-case scan found {summary['issue_count']} issues → {out_path}",
        artifact=out_path,
        module_id="edgecase_scanner_v1",
        schema_version="edgecase_scan_v1",
        extra={"summary_metrics": summary},
    )
    print(f"[summary] edgecase_scanner_v1: {summary['issue_count']} issues → {out_path}")


if __name__ == "__main__":
    main()
