import argparse
import base64
import json
import re
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

from modules.common.openai_client import OpenAI
from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from modules.common.html_utils import html_to_text
from modules.common.turn_to_claims import merge_turn_to_claims
from schemas import Combat, CombatEnemy, EnrichedPortion, TurnToLinkClaimInline

# Common Fighting Fantasy combat patterns
# Stat block pattern: NAME followed by SKILL and STAMINA (sometimes on new lines)
STAT_BLOCK_PATTERN = re.compile(r"\b([A-Z][A-Z\s\-]{2,})\s+(?:SKILL|skill)\s*[:]?\s*(\d+)\s*(?:STAMINA|stamina)\s*[:]?\s*(\d+)", re.MULTILINE)
# Vehicle/robot stat block pattern: NAME followed by FIREPOWER and ARMOUR
VEHICLE_STAT_PATTERN = re.compile(r"\b([A-Z][A-Z\s\-]{2,})\s+(?:FIREPOWER|firepower)\s*[:]?\s*(\d+)\s*(?:ARMOUR|armour|armor)\s*[:]?\s*(\d+)", re.MULTILINE)
# Table-like or separated pattern
SEP_STAT_PATTERN = re.compile(r"(?:SKILL|skill)\s*[:]?\s*(\d+).*?(?:STAMINA|stamina)\s*[:]?\s*(\d+)", re.IGNORECASE | re.DOTALL)
ARMOUR_PATTERN = re.compile(r"\bARMOUR\b\s*[: ]?\s*(\d+)", re.IGNORECASE)
FIREPOWER_PATTERN = re.compile(r"\bFIREPOWER\b\s*[: ]?\s*(\d+)", re.IGNORECASE)
SPEED_PATTERN = re.compile(r"\bSPEED\b\s*[: ]?\s*([A-Za-z]+)", re.IGNORECASE)
WIN_PATTERNS = [
    re.compile(r"if\s+you\s+win,\s+turn\s+to\s+(\d+)", re.IGNORECASE),
    re.compile(r"as\s+soon\s+as\s+you\s+win(?:\s+your)?(?:\s+(?:first|second|third))?\s+attack\s+round,\s*turn\s+to\s+(\d+)", re.IGNORECASE),
    re.compile(r"if\s+you\s+(?:manage\s+to\s+)?(?:defeat|kill|slay)\b.*?\bturn\s+to\s+(\d+)", re.IGNORECASE | re.DOTALL),
]
LOSS_PATTERNS = [
    re.compile(r"if\s+you\s+lose\b.*?\bturn\s+to\s+(\d+)", re.IGNORECASE | re.DOTALL),
    re.compile(r"if\s+you\s+lose\s+the\s+(?:fight|combat|battle)\b.*?\bturn\s+to\s+(\d+)", re.IGNORECASE | re.DOTALL),
    re.compile(r"if\s+you\s+are\s+(?:defeated|killed)\b.*?\bturn\s+to\s+(\d+)", re.IGNORECASE | re.DOTALL),
    re.compile(r"if\s+.*?(?:armour|armor|stamina)\s+.*?(?:reduced|reduction)\s+to\s+zero\b.*?\bturn\s+to\s+(\d+)", re.IGNORECASE | re.DOTALL),
    re.compile(r"if\s+.*?(?:armour|armor|stamina)\s+.*?\bto\s+0\b.*?\bturn\s+to\s+(\d+)", re.IGNORECASE | re.DOTALL),
]
ESCAPE_PATTERN = re.compile(r"if\s+you\s+wish\s+to\s+escape,\s+turn\s+to\s+(\d+)", re.IGNORECASE)
ESCAPE_FLEX_PATTERN = re.compile(r"\bescape\b.{0,80}?\bturn\s+to\s+(\d+)", re.IGNORECASE | re.DOTALL)
ESCAPE_CHOICE_PATTERN = re.compile(r"\b(?:may|can|choose)\s+escape\b.{0,80}?\bturn\s+to\s+(\d+)", re.IGNORECASE | re.DOTALL)
ESCAPE_AFTER_PATTERN = re.compile(r"\bescape\s+after\b.{0,120}?\bturn\s+to\s+(\d+)", re.IGNORECASE | re.DOTALL)
WIN_CONTINUE_CUES = [
    re.compile(r"\bas\s+soon\s+as\s+you\s+win\b", re.IGNORECASE),
    re.compile(r"\bif\s+you\s+win\b", re.IGNORECASE),
    re.compile(r"\bif\s+you\s+(?:manage\s+to\s+)?(?:defeat|kill|slay)\b", re.IGNORECASE),
]
PLAYER_ROUND_WIN_TURN_PATTERN = re.compile(
    r"(?:as\s+soon\s+as\s+|if\s+)(?:you\s+)?win\s+your\s+([a-z0-9]+)(?:st|nd|rd|th)?\s+attack\s+round[^.]*?\bturn\s+to\s+(\d+)",
    re.IGNORECASE | re.DOTALL,
)
PLAYER_ROUND_WIN_TEST_LUCK_PATTERN = re.compile(
    r"(?:as\s+soon\s+as\s+|if\s+)(?:you\s+)?win\s+your\s+([a-z0-9]+)(?:st|nd|rd|th)?\s+attack\s+round[^.]*?\btest\s+your\s+luck\b",
    re.IGNORECASE | re.DOTALL,
)
ATTACK_STRENGTH_PENALTY_PATTERN = re.compile(
    r"reduc(?:e|ing)\s+your\s+(?:attack\s+strength|skill)\s+by\s+(\d+)",
    re.IGNORECASE,
)
FIREPOWER_PENALTY_PATTERN = re.compile(
    r"reduc(?:e|ing)\s+your\s+firepower\s+by\s+(\d+)",
    re.IGNORECASE,
)
FIGHT_SINGLY_PATTERN = re.compile(r"\b(one\s+at\s+a\s+time|fight\s+them\s+one\s+at\s+a\s+time)\b", re.IGNORECASE)
BOTH_ATTACK_PATTERN = re.compile(r"\bboth\b.{0,80}?\battack\b.{0,80}?\beach(?:\s+attack)?\s+round\b", re.IGNORECASE | re.DOTALL)
CHOOSE_TARGET_PATTERN = re.compile(
    r"\bchoose\b.{0,60}?\b(?:fight|fire|shoot|target)\b",
    re.IGNORECASE | re.DOTALL,
)
CANNOT_WOUND_PATTERN = re.compile(
    r"\b(cannot|can't|will\s+not)\s+(?:wound|harm|hurt|damage)\b",
    re.IGNORECASE,
)
ATTACK_STRENGTH_TOTAL_PATTERN = re.compile(
    r"attack\s+strength\s+totals?\s+(\d+).{0,80}?\bturn\s+to\s+(\d+)",
    re.IGNORECASE | re.DOTALL,
)
ENEMY_ROUND_WIN_PATTERN = re.compile(
    r"wins?\s+(?:an|any)\s+attack\s+round.{0,80}?\bturn\s+to\s+(\d+)",
    re.IGNORECASE | re.DOTALL,
)
ENEMY_STRENGTH_GREATER_PATTERN = re.compile(
    r"attack\s+strength\s+(?:is|was)\s+(?:greater|higher)\s+than\s+(?:your|yours).{0,80}?\bturn\s+to\s+(\d+)",
    re.IGNORECASE | re.DOTALL,
)


def _walk_targets(obj: Any, prefix: str = "") -> Iterable[Tuple[str, str]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}/{key}" if prefix else f"/{key}"
            if key == "targetSection" and value is not None:
                yield (str(value), path)
            else:
                yield from _walk_targets(value, path)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            path = f"{prefix}/{idx}" if prefix else f"/{idx}"
            yield from _walk_targets(item, path)


def _combat_claims(combats: List[Combat]) -> List[Dict[str, Any]]:
    claims: List[Dict[str, Any]] = []
    for idx, combat in enumerate(combats or []):
        data = combat.model_dump(exclude_none=True) if hasattr(combat, "model_dump") else combat
        for target, path in _walk_targets(data, f"/combat/{idx}"):
            claims.append({
                "target": str(target),
                "claim_type": "combat",
                "module_id": "extract_combat_v1",
                "evidence_path": path,
            })
    return claims


def _coerce_turn_to_claims(claims: Iterable[Any]) -> List[TurnToLinkClaimInline]:
    coerced: List[TurnToLinkClaimInline] = []
    for claim in claims or []:
        if isinstance(claim, TurnToLinkClaimInline):
            coerced.append(claim)
        elif isinstance(claim, dict):
            coerced.append(TurnToLinkClaimInline(**claim))
        elif hasattr(claim, "model_dump"):
            coerced.append(TurnToLinkClaimInline(**claim.model_dump()))
        elif hasattr(claim, "dict"):
            coerced.append(TurnToLinkClaimInline(**claim.dict()))
    return coerced

SYSTEM_PROMPT = """You are an expert at parsing Fighting Fantasy gamebook sections.
Extract combat encounter information from the provided text into a JSON list of combat events.
The text may contain multiple enemies, sometimes in a table-like format with columns for SKILL and STAMINA,
or vehicle/robot stats like ARMOUR, FIREPOWER, SPEED.

Each combat object MUST have:
- enemies: list of enemy objects. Use fields as available: enemy, skill, stamina, armour, firepower, speed.

Optional fields when present in text:
- style: "standard" | "hand" | "shooting" | "robot" | "vehicle"
- outcomes: { win, lose, escape } where each is { targetSection: "X" } or { terminal: { kind: "continue" } }
- mode: "single" | "sequential" | "simultaneous" | "split-target"
- rules: list of structured rules
- modifiers: list of stat changes (use scope: "combat" for combat-only)
- triggers: list of conditional outcome triggers

Return a JSON object with a "combat" key containing the list:
{
  "combat": [
    {
      "style": "standard",
      "enemies": [{ "enemy": "SKELETON WARRIOR", "skill": 8, "stamina": 6 }],
      "outcomes": { "win": { "targetSection": "71" } }
    }
  ]
}

If no combat is found, return {"combat": []}."""

VISION_HINT = "Use the image as ground truth when text appears incomplete or missing stats."

def _infer_win_from_anchors(raw_html: Optional[str], loss_section: Optional[str], win_section: Optional[str]) -> Optional[str]:
    if win_section or not raw_html or not loss_section:
        return win_section
    anchors = [m.group(1) for m in re.finditer(r'href\s*=\s*["\']#(\d+)["\']', raw_html, flags=re.IGNORECASE)]
    seen = []
    for a in anchors:
        if a not in seen:
            seen.append(a)
    if loss_section in seen:
        others = [a for a in seen if a != loss_section]
        if len(others) == 1:
            return others[0]
    return win_section


def _detect_outcomes(text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    win_section = None
    loss_section = None
    escape_section = None
    for pattern in WIN_PATTERNS:
        match = pattern.search(text)
        if match:
            win_section = match.group(1)
            break
    for pattern in LOSS_PATTERNS:
        match = pattern.search(text)
        if match:
            loss_section = match.group(1)
            break
    escape_match = (
        ESCAPE_PATTERN.search(text)
        or ESCAPE_AFTER_PATTERN.search(text)
        or ESCAPE_CHOICE_PATTERN.search(text)
        or ESCAPE_FLEX_PATTERN.search(text)
    )
    if escape_match:
        escape_section = escape_match.group(1)
    if win_section is None:
        for cue in WIN_CONTINUE_CUES:
            if cue.search(text):
                win_section = "continue"
                break
    return win_section, loss_section, escape_section


def _ensure_win_outcome_from_triggers(outcomes: Optional[Dict[str, Any]], triggers: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """
    The engine schema requires a win outcome for combat events. Some FF combats instead express the
    "win" as a trigger like "If you survive four Attack Rounds, turn to 334.".
    If we have such a trigger and no explicit win outcome, promote it to outcomes.win.
    """
    triggers = triggers or []
    existing = outcomes if isinstance(outcomes, dict) else {}
    if existing.get("win"):
        return existing
    for trig in triggers:
        if not isinstance(trig, dict):
            continue
        kind = str(trig.get("kind") or "").lower()
        if kind not in {"survive_rounds", "player_round_win"}:
            continue
        outcome = trig.get("outcome")
        normalized = _normalize_outcome_ref(outcome)
        if normalized:
            merged = dict(existing)
            merged["win"] = normalized
            return merged
    # Fallback: if the book doesn't specify where to go on victory, treat it as
    # "continue reading" in the same section after the combat.
    merged = dict(existing)
    merged["win"] = {"terminal": {"kind": "continue"}}
    return merged


def _infer_combat_style(text: str, enemies: List[CombatEnemy]) -> Optional[str]:
    lower = (text or "").lower()
    if any(e.firepower is not None for e in enemies) or "vehicle combat" in lower or "interceptor" in lower or "machine-gun" in lower:
        return "vehicle"
    if any(e.armour is not None for e in enemies) or "robot combat" in lower:
        return "robot"
    if any(term in lower for term in ("shooting", "rifle", "gun", "bullet", "bow", "arrow", "revolver")):
        return "shooting"
    if any(term in lower for term in ("hand fighting", "hand-to-hand")):
        return "hand"
    return "standard"


def _build_outcomes(win_section: Optional[str], loss_section: Optional[str], escape_section: Optional[str]) -> Dict[str, Any]:
    outcomes: Dict[str, Any] = {}
    if win_section:
        if str(win_section).lower() == "continue":
            outcomes["win"] = {"terminal": {"kind": "continue"}}
        else:
            outcomes["win"] = {"targetSection": str(win_section)}
    if loss_section:
        outcomes["lose"] = {"targetSection": str(loss_section)}
    if escape_section:
        outcomes["escape"] = {"targetSection": str(escape_section)}
    return outcomes


def _extract_combat_rules(text: str, enemy_count: int) -> Tuple[Optional[str], List[Dict[str, Any]], List[Dict[str, Any]]]:
    mode = None
    rules: List[Dict[str, Any]] = []
    modifiers: List[Dict[str, Any]] = []
    lower = text.lower()

    if enemy_count <= 1:
        mode = "single"
    if FIGHT_SINGLY_PATTERN.search(text):
        rules.append({"kind": "fight_singly"})
        mode = "sequential"
    if BOTH_ATTACK_PATTERN.search(text) or CHOOSE_TARGET_PATTERN.search(text):
        if BOTH_ATTACK_PATTERN.search(text):
            rules.append({"kind": "both_attack_each_round"})
        rules.append({"kind": "choose_target_each_round"})
        rules.append({"kind": "secondary_enemy_defense_only"})
        mode = "split-target"
    if CANNOT_WOUND_PATTERN.search(text):
        rules.append({"kind": "secondary_target_no_damage"})

    for match in FIREPOWER_PENALTY_PATTERN.finditer(text):
        amount = int(match.group(1))
        modifiers.append({
            "kind": "stat_change",
            "stat": "firepower",
            "amount": -amount,
            "scope": "combat",
            "reason": "combat penalty",
        })

    for match in ATTACK_STRENGTH_PENALTY_PATTERN.finditer(text):
        amount = int(match.group(1))
        modifiers.append({
            "kind": "stat_change",
            "stat": "skill",
            "amount": -amount,
            "scope": "combat",
            "reason": "combat penalty",
        })

    return mode, rules, modifiers


def _extract_combat_triggers(text: str) -> List[Dict[str, Any]]:
    triggers: List[Dict[str, Any]] = []
    seen = set()
    survive_pattern = re.compile(
        r"if\s+you\s+survive\s+([a-z0-9]+)\s+attack\s+rounds?.{0,60}?\bturn\s+to\s+(\d+)",
        re.IGNORECASE | re.DOTALL,
    )
    for match in survive_pattern.finditer(text):
        count = _parse_round_count(match.group(1))
        outcome = {"targetSection": match.group(2)}
        key = ("survive_rounds", count, match.group(2))
        if key in seen:
            continue
        seen.add(key)
        entry = {"kind": "survive_rounds", "outcome": outcome}
        if count is not None:
            entry["count"] = count
        triggers.append(entry)
    for match in ATTACK_STRENGTH_TOTAL_PATTERN.finditer(text):
        value = int(match.group(1))
        target = match.group(2)
        key = ("enemy_attack_strength_total", value, target)
        if key in seen:
            continue
        seen.add(key)
        triggers.append({
            "kind": "enemy_attack_strength_total",
            "value": value,
            "outcome": {"targetSection": target},
        })
    for match in ENEMY_ROUND_WIN_PATTERN.finditer(text):
        target = match.group(1)
        key = ("enemy_round_win", target)
        if key in seen:
            continue
        seen.add(key)
        triggers.append({
            "kind": "enemy_round_win",
            "outcome": {"targetSection": target},
        })
    for match in ENEMY_STRENGTH_GREATER_PATTERN.finditer(text):
        target = match.group(1)
        key = ("enemy_round_win", target)
        if key in seen:
            continue
        seen.add(key)
        triggers.append({
            "kind": "enemy_round_win",
            "outcome": {"targetSection": target},
        })
    win_turn = PLAYER_ROUND_WIN_TURN_PATTERN.search(text)
    if win_turn:
        count = _parse_round_count(win_turn.group(1))
        entry = {
            "kind": "player_round_win",
            "outcome": {"targetSection": win_turn.group(2)},
        }
        if count is not None:
            entry["count"] = count
        triggers.append(entry)
    else:
        win_luck = PLAYER_ROUND_WIN_TEST_LUCK_PATTERN.search(text)
        if win_luck:
            count = _parse_round_count(win_luck.group(1))
            entry = {
                "kind": "player_round_win",
                "outcome": {"terminal": {"kind": "continue"}},
            }
            if count is not None:
                entry["count"] = count
            triggers.append(entry)
    return triggers


def _normalize_stat_name(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    lower = str(raw).strip().lower()
    if "skill" in lower:
        return "skill"
    if "stamina" in lower:
        return "stamina"
    if "luck" in lower:
        return "luck"
    if "firepower" in lower:
        return "firepower"
    if "armour" in lower or "armor" in lower:
        return "armour"
    return None


def _normalize_outcome_ref(outcome: Optional[Any]) -> Optional[Dict[str, Any]]:
    if outcome is None:
        return None
    if isinstance(outcome, dict):
        if outcome.get("terminal"):
            terminal = outcome.get("terminal")
            if isinstance(terminal, dict):
                kind = terminal.get("kind")
                if isinstance(kind, str) and kind.lower() in {"death", "victory", "defeat", "end", "continue"}:
                    return {"terminal": {"kind": kind.lower(), **{k: v for k, v in terminal.items() if k != "kind"}}}
            return None
        target = outcome.get("targetSection")
        if isinstance(target, (int, float)):
            return {"targetSection": str(int(target))}
        if isinstance(target, str):
            target = target.strip()
            if target.isdigit():
                return {"targetSection": target}
            if "continue" in target.lower():
                return {"terminal": {"kind": "continue"}}
        return None
    if isinstance(outcome, (int, float)):
        return {"targetSection": str(int(outcome))}
    if isinstance(outcome, str):
        text = outcome.strip()
        if text.isdigit():
            return {"targetSection": text}
        if "continue" in text.lower():
            return {"terminal": {"kind": "continue"}}
    return None


def _normalize_modifiers(modifiers: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    if not modifiers:
        return None
    normalized: List[Dict[str, Any]] = []
    for mod in modifiers:
        if not isinstance(mod, dict):
            continue
        stat = _normalize_stat_name(mod.get("stat") or mod.get("statName"))
        amount = mod.get("amount")
        if amount is None:
            amount = mod.get("modifier")
        if stat is None or amount is None:
            continue
        scope = str(mod.get("scope") or "combat").lower()
        if scope not in ("permanent", "section", "combat", "round"):
            scope = "combat"
        entry = {
            "kind": "stat_change",
            "stat": stat,
            "amount": amount,
            "scope": scope,
        }
        reason = mod.get("reason")
        if reason:
            entry["reason"] = reason
        normalized.append(entry)
    return normalized or None


def _parse_round_count(token: Optional[str]) -> Optional[int]:
    if not token:
        return None
    lower = str(token).strip().lower()
    ordinal_map = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
        "sixth": 6,
        "seventh": 7,
        "eighth": 8,
        "ninth": 9,
        "tenth": 10,
    }
    for key, value in ordinal_map.items():
        if key in lower:
            return value
    if lower in ordinal_map:
        return ordinal_map[lower]
    word_map = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    if lower in word_map:
        return word_map[lower]
    digits = re.sub(r"[^0-9]", "", lower)
    if digits.isdigit():
        return int(digits)
    return None


def _normalize_triggers(triggers: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    if not triggers:
        return None
    normalized: List[Dict[str, Any]] = []
    for trig in triggers:
        if not isinstance(trig, dict):
            continue
        kind_raw = str(trig.get("kind") or "").strip().lower()
        if not kind_raw and trig.get("trigger"):
            kind_raw = str(trig.get("trigger")).strip().lower()
        if kind_raw in ("enemy_attack_strength_total", "attack_strength_total"):
            kind = "enemy_attack_strength_total"
        elif kind_raw in ("enemy_round_win", "round_win", "wins_round"):
            kind = "enemy_round_win"
        elif kind_raw in ("no_enemy_round_wins", "no_round_wins"):
            kind = "no_enemy_round_wins"
        elif kind_raw in ("player_round_win", "player_attack_round_win", "winfirstattackround", "winsecondattackround"):
            kind = "player_round_win"
        elif kind_raw in ("survive_rounds", "player_survive_rounds", "survive_attack_rounds"):
            kind = "survive_rounds"
        else:
            continue
        outcome = _normalize_outcome_ref(trig.get("outcome"))
        if not outcome and isinstance(trig.get("action"), dict):
            action = trig.get("action") or {}
            if "testLuck" in action or "test_luck" in action:
                outcome = {"terminal": {"kind": "continue"}}
            else:
                direct = action.get("targetSection")
                outcome = _normalize_outcome_ref(direct)
                if not outcome:
                    for value in action.values():
                        if isinstance(value, dict) and "targetSection" in value:
                            outcome = _normalize_outcome_ref(value.get("targetSection"))
                            if outcome:
                                break
        if not outcome:
            continue
        entry: Dict[str, Any] = {"kind": kind, "outcome": outcome}
        if kind == "enemy_attack_strength_total":
            value = trig.get("value")
            if isinstance(value, (int, float)):
                entry["value"] = int(value)
            elif isinstance(value, str) and value.strip().isdigit():
                entry["value"] = int(value.strip())
            else:
                continue
        if kind in ("player_round_win", "survive_rounds"):
            count = trig.get("count") or _parse_round_count(trig.get("round") or trig.get("rounds"))
            if count is None and isinstance(trig.get("trigger"), str):
                count = _parse_round_count(trig.get("trigger"))
            if count is not None:
                entry["count"] = count
        normalized.append(entry)
    return normalized or None


def _normalize_rules(rules: Optional[List[Dict[str, Any]]], triggers: Optional[List[Dict[str, Any]]]) -> Tuple[Optional[List[Dict[str, Any]]], Optional[List[Dict[str, Any]]]]:
    normalized_triggers = _normalize_triggers(triggers)
    if not rules:
        return None, normalized_triggers
    normalized_rules: List[Dict[str, Any]] = []
    normalized_triggers = list(normalized_triggers or [])
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        kind_raw = str(rule.get("kind") or "").strip().lower()
        if kind_raw in {"fight_singly", "choose_target_each_round", "secondary_target_no_damage", "secondary_enemy_defense_only"}:
            normalized_rules.append({"kind": kind_raw})
            continue
        if kind_raw in {"note", ""}:
            continue
        # Convert rule-shaped triggers to triggers list when possible.
        if kind_raw in {"trigger", "condition"} or rule.get("condition"):
            condition = str(rule.get("condition") or rule.get("text") or "").lower()
            target = rule.get("targetSection")
            effect = rule.get("effect")
            if target is None and isinstance(effect, dict):
                target = effect.get("targetSection")
                if target is None:
                    target = effect.get("outcome") if isinstance(effect.get("outcome"), str) else None
            outcome = _normalize_outcome_ref(target)
            if outcome:
                if "attack strength totals" in condition:
                    value_match = re.search(r"attack strength totals?\s+(\\d+)", condition)
                    if value_match:
                        normalized_triggers.append({
                            "kind": "enemy_attack_strength_total",
                            "value": int(value_match.group(1)),
                            "outcome": outcome,
                        })
                        continue
                if "attack strength is greater" in condition or "wins" in condition or "attack round" in condition:
                    normalized_triggers.append({
                        "kind": "enemy_round_win",
                        "outcome": outcome,
                    })
                    continue
        # Fallback: drop unrecognized rule text instead of emitting notes.
    return normalized_rules or None, _normalize_triggers(normalized_triggers)


def _merge_fallback_outcomes(outcomes: Optional[Dict[str, Any]], fallback: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not outcomes:
        return fallback or None
    if not fallback:
        return outcomes
    # If LLM returned conditional outcomes, prefer deterministic fallback (schema doesn't support conditions here).
    win_block = outcomes.get("win") if isinstance(outcomes, dict) else None
    if isinstance(win_block, dict) and any(key in win_block for key in ("conditions", "condition")):
        return fallback or None
    merged = dict(outcomes)
    fallback_win = fallback.get("win")
    if fallback_win:
        is_continue = isinstance(fallback_win, dict) and fallback_win.get("terminal", {}).get("kind") == "continue"
        if is_continue:
            merged["win"] = fallback_win
        else:
            merged.setdefault("win", fallback_win)
    for key in ("lose", "escape"):
        if key in fallback:
            merged.setdefault(key, fallback[key])
    return merged or None


def _coerce_conditional_outcomes(outcomes: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not outcomes or not isinstance(outcomes, dict):
        return outcomes
    win_block = outcomes.get("win")
    if not isinstance(win_block, dict):
        return outcomes
    conditional = win_block.get("conditional")
    if not isinstance(conditional, list):
        return outcomes
    mapped: Dict[str, Any] = {}
    for entry in conditional:
        if not isinstance(entry, dict):
            continue
        condition = str(entry.get("condition") or "").lower()
        target = entry.get("targetSection") or entry.get("target")
        target_ref = _normalize_outcome_ref(target)
        if not target_ref:
            continue
        if "escape" in condition:
            mapped.setdefault("escape", target_ref)
            continue
        if "win" in condition or "defeat" in condition:
            mapped.setdefault("win", target_ref)
            continue
        if "lose" in condition or "defeated" in condition:
            mapped.setdefault("lose", target_ref)
            continue
        if any(tok in condition for tok in ("armour", "armor", "stamina")):
            if "reduced to zero" in condition or "reduced to 0" in condition or "to zero" in condition:
                mapped.setdefault("lose", target_ref)
            elif "left" in condition or "remaining" in condition or "some" in condition:
                mapped.setdefault("win", target_ref)
    if mapped:
        for key in ("win", "lose", "escape"):
            if key in outcomes and key not in mapped and isinstance(outcomes.get(key), dict):
                existing = _normalize_outcome_ref(outcomes.get(key))
                if existing:
                    mapped[key] = existing
        return mapped
    return outcomes


def _merge_rules(existing: Optional[List[Dict[str, Any]]], fallback: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    if not existing:
        return fallback or None
    if not fallback:
        return existing
    merged = list(existing)
    existing_kinds = {r.get("kind") for r in existing if isinstance(r, dict) and r.get("kind")}
    for rule in fallback:
        if isinstance(rule, dict):
            kind = rule.get("kind")
            if kind and kind in existing_kinds:
                continue
        merged.append(rule)
    return merged or None


def _merge_modifiers(existing: Optional[List[Dict[str, Any]]], fallback: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    if not existing:
        return fallback or None
    if not fallback:
        return existing
    merged = list(existing)
    seen = {}
    for idx, mod in enumerate(existing):
        if not isinstance(mod, dict):
            continue
        key = (mod.get("stat"), mod.get("amount"), mod.get("scope"))
        seen[key] = idx
    for mod in fallback:
        if not isinstance(mod, dict):
            continue
        key = (mod.get("stat"), mod.get("amount"), mod.get("scope"))
        if key in seen:
            existing_idx = seen[key]
            existing_mod = merged[existing_idx] if existing_idx < len(merged) else None
            if isinstance(existing_mod, dict) and not existing_mod.get("reason") and mod.get("reason"):
                merged[existing_idx] = mod
            continue
        seen[key] = len(merged)
        merged.append(mod)
    return merged or None


def _prune_redundant_rules(rules: Optional[List[Dict[str, Any]]], triggers: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    if not rules:
        return None
    pruned = [r for r in rules if isinstance(r, dict) and r.get("kind") != "note"]
    if not pruned:
        return None
    structured_kinds = {
        r.get("kind")
        for r in pruned
        if isinstance(r, dict) and r.get("kind") in {
            "fight_singly",
            "both_attack_each_round",
            "choose_target_each_round",
            "secondary_enemy_defense_only",
            "secondary_target_no_damage",
        }
    }
    if not structured_kinds:
        return pruned
    return pruned or None


def _strip_spurious_escape(outcomes: Optional[Dict[str, Any]], text: str) -> Optional[Dict[str, Any]]:
    if not outcomes or "escape" not in outcomes:
        return outcomes
    lower = text.lower() if text else ""
    if re.search(r"\b(?:cannot|may not|must not|can't)\s+escape\b", lower):
        trimmed = dict(outcomes)
        trimmed.pop("escape", None)
        return trimmed
    if "escape" in lower:
        return outcomes
    trimmed = dict(outcomes)
    trimmed.pop("escape", None)
    return trimmed


def _strip_spurious_loss(outcomes: Optional[Dict[str, Any]], text: str, triggers: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    if not outcomes or "lose" not in outcomes:
        return outcomes
    lower = text.lower()
    if re.search(r"\bif\s+you\s+lose\b", lower) or re.search(r"\bif\s+you\s+are\s+(?:defeated|killed)\b", lower):
        return outcomes
    loss_target = outcomes.get("lose", {}).get("targetSection") if isinstance(outcomes.get("lose"), dict) else None
    if loss_target and triggers:
        for trig in triggers:
            outcome = trig.get("outcome") if isinstance(trig, dict) else None
            if isinstance(outcome, dict) and outcome.get("targetSection") == loss_target:
                trimmed = dict(outcomes)
                trimmed.pop("lose", None)
                return trimmed
    return outcomes


def _prune_split_target_enemies(combat: Combat, text: str) -> None:
    if combat.mode != "split-target":
        return
    if not text:
        return
    lower = text.lower()
    if "pincer" not in lower:
        return
    if "separate creature" not in lower and "separate creatures" not in lower:
        return
    if len(combat.enemies) <= 2:
        return
    pincers = [e for e in combat.enemies if e.enemy and "pincer" in e.enemy.lower()]
    if len(pincers) >= 2:
        combat.enemies = pincers


def _expand_split_target_enemies(combat: Combat, text: str) -> None:
    if combat.mode != "split-target":
        return
    if not text or len(combat.enemies) != 1:
        return
    lower = text.lower()
    part_nouns = ("pincer", "head", "arm", "tentacle", "jaw", "claw", "hand", "fist", "tail", "mouth", "leg", "eye")
    cue = "separate creature" in lower or "separate creatures" in lower
    if not cue and "each" in lower and any(p in lower for p in part_nouns):
        cue = True
    if not cue and re.search(r"(two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(?:of\s+its\s+)?[a-z\-]+s\b", lower):
        cue = True
    if not cue:
        return

    count = None
    part = None
    for noun in part_nouns:
        if noun in lower:
            part = noun
            break

    if not part:
        return

    match = re.search(
        rf"(two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(?:of\s+its\s+)?{re.escape(part)}(?:s)?\b",
        lower,
    )
    if match:
        raw_count = match.group(1)
        word_map = {
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
        }
        if raw_count in word_map:
            count = word_map[raw_count]
        elif raw_count.isdigit():
            count = int(raw_count)

    if count is None:
        if "pair" in lower or "both" in lower or "two" in lower:
            count = 2

    if part and part not in part_nouns:
        return
    if not count or count < 2:
        return
    if count > 10:
        return

    base_enemy = combat.enemies[0]
    base_name = base_enemy.enemy or "Enemy"
    label = (part or "Part").replace("-", " ").title()
    combat.enemies = [
        CombatEnemy(
            enemy=f"{base_name} - {label} {idx + 1}",
            skill=base_enemy.skill,
            stamina=base_enemy.stamina,
            armour=base_enemy.armour,
            firepower=base_enemy.firepower,
            speed=base_enemy.speed,
        )
        for idx in range(count)
    ]


def _prune_ally_assisted_combat(combat: Combat, text: str) -> None:
    if not text or not combat.enemies or len(combat.enemies) <= 1:
        return
    lower = text.lower()
    ally_pattern = re.compile(
        r"\b(throm|your companion|your friend|the dwarf|the elf|the barbarian)\b[^.]{0,120}?\battack(?:s|ed)?\b[^.]{0,60}?\b(first|before you|one)\b",
        re.IGNORECASE,
    )
    you_pattern = re.compile(
        r"\byou\b[^.]{0,140}?\battack(?:s|ed)?\b[^.]{0,80}?\b(second|other)\b",
        re.IGNORECASE,
    )
    if not ally_pattern.search(lower) or not you_pattern.search(lower):
        return
    combat.enemies = [combat.enemies[0]]
    combat.mode = "single"


def _normalize_mode(mode: Optional[str], rules: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    valid_modes = {"single", "sequential", "simultaneous", "split-target"}
    if mode and mode not in valid_modes:
        mode = None
    if not rules:
        return mode
    kinds = {r.get("kind") for r in rules if isinstance(r, dict)}
    if "choose_target_each_round" in kinds:
        return "split-target"
    if "fight_singly" in kinds:
        return "sequential"
    return mode


def _merge_triggers(existing: Optional[List[Dict[str, Any]]], fallback: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    if not existing:
        return fallback or None
    if not fallback:
        return existing
    merged = list(existing)
    seen = set()
    for trig in existing:
        try:
            key = json.dumps(trig, sort_keys=True)
        except TypeError:
            key = str(trig)
        seen.add(key)
    for trig in fallback:
        try:
            key = json.dumps(trig, sort_keys=True)
        except TypeError:
            key = str(trig)
        if key in seen:
            continue
        seen.add(key)
        merged.append(trig)
    return merged or None


def _merge_sequential_combats(combats: List[Combat], text: str) -> List[Combat]:
    if len(combats) < 2:
        return combats
    if not FIGHT_SINGLY_PATTERN.search(text):
        return combats
    if not all(len(c.enemies) == 1 for c in combats):
        return combats
    first = combats[0]
    def _norm(obj: Any) -> str:
        try:
            return json.dumps(obj, sort_keys=True, default=str)
        except TypeError:
            return str(obj)
    if any(_norm(c.outcomes) != _norm(first.outcomes) for c in combats):
        return combats
    if any(_norm(c.modifiers) != _norm(first.modifiers) for c in combats):
        return combats
    if any(_norm(c.triggers) != _norm(first.triggers) for c in combats):
        return combats
    merged_enemies: List[CombatEnemy] = []
    for c in combats:
        merged_enemies.extend(c.enemies)
    merged_rules = _merge_rules(first.rules, [{"kind": "fight_singly"}])
    return [Combat(
        enemies=merged_enemies,
        outcomes=first.outcomes,
        mode="sequential",
        rules=merged_rules,
        modifiers=first.modifiers,
        triggers=first.triggers,
        confidence=first.confidence,
    )]


def extract_combat_regex(text: str, raw_html: Optional[str] = None) -> List[Combat]:
    enemies: List[Dict[str, Any]] = []

    # Find all stat blocks
    matches = STAT_BLOCK_PATTERN.finditer(text)

    for match in matches:
        enemy_name = match.group(1).strip()
        skill = int(match.group(2))
        stamina = int(match.group(3))
        enemies.append({
            "enemy": enemy_name,
            "skill": skill,
            "stamina": stamina,
        })

    if not enemies:
        vehicle_matches = VEHICLE_STAT_PATTERN.finditer(text)
        for match in vehicle_matches:
            enemy_name = match.group(1).strip()
            firepower = int(match.group(2))
            armour = int(match.group(3))
            enemies.append({
                "enemy": enemy_name,
                "firepower": firepower,
                "armour": armour,
            })

    if not enemies:
        # Second pass: look for separated stats
        sep_matches = SEP_STAT_PATTERN.finditer(text)
        for match in sep_matches:
            skill = int(match.group(1))
            stamina = int(match.group(2))
            enemies.append({
                "enemy": "Unknown",
                "skill": skill,
                "stamina": stamina,
            })

    if not enemies:
        return []

    # Outcomes
    win_section, loss_section, escape_section = _detect_outcomes(text)
    win_section = _infer_win_from_anchors(raw_html, loss_section, win_section)
    outcomes = _build_outcomes(win_section, loss_section, escape_section)

    # Rules/modifiers/mode
    mode, rules, modifiers = _extract_combat_rules(text, len(enemies))
    modifiers = _normalize_modifiers(modifiers)
    triggers = _extract_combat_triggers(text)
    outcomes = _ensure_win_outcome_from_triggers(outcomes, triggers)

    combat = Combat(
        enemies=enemies,
        outcomes=outcomes or None,
        mode=mode,
        style=_infer_combat_style(text, [CombatEnemy(**e) for e in enemies]),
        rules=rules or None,
        modifiers=modifiers,
        triggers=triggers or None,
        confidence=0.9,
    )

    return [combat]

def _coerce_enemies(raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enemies: List[Dict[str, Any]] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        enemy_name = item.get("enemy") or item.get("name") or "Creature"
        try:
            skill = int(item.get("skill")) if item.get("skill") is not None else None
        except (TypeError, ValueError):
            skill = None
        try:
            stamina = int(item.get("stamina")) if item.get("stamina") is not None else None
        except (TypeError, ValueError):
            stamina = None
        try:
            armour = int(item.get("armour")) if item.get("armour") is not None else None
        except (TypeError, ValueError):
            armour = None
        try:
            firepower = int(item.get("firepower")) if item.get("firepower") is not None else None
        except (TypeError, ValueError):
            firepower = None
        speed = item.get("speed")
        if skill is None and stamina is None and armour is None and firepower is None:
            continue
        entry = {"enemy": enemy_name}
        if skill is not None:
            entry["skill"] = skill
        if stamina is not None:
            entry["stamina"] = stamina
        if armour is not None:
            entry["armour"] = armour
        if firepower is not None:
            entry["firepower"] = firepower
        if speed:
            entry["speed"] = speed
        enemies.append(entry)
    return enemies


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def extract_combat_llm(text: str, model: str, client: OpenAI) -> Tuple[List[Combat], Dict[str, Any]]:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"}
        )
        
        usage = {
            "model": model,
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
        }
        
        content = response.choices[0].message.content
        data = json.loads(content)
        
        raw_list = data.get("combat") if isinstance(data, dict) and "combat" in data else data
        if not isinstance(raw_list, list):
            raw_list = []

        combats: List[Combat] = []
        if raw_list and isinstance(raw_list[0], dict) and any(k in raw_list[0] for k in ("enemies", "outcomes", "rules", "modifiers", "triggers", "mode")):
            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                enemies = _coerce_enemies(item.get("enemies") or [])
                if not enemies:
                    continue
                outcomes = item.get("outcomes")
                if not outcomes:
                    outcomes = _build_outcomes(
                        item.get("win_section"),
                        item.get("loss_section"),
                        item.get("escape_section"),
                    )
                rules, triggers = _normalize_rules(item.get("rules"), item.get("triggers"))
                combats.append(Combat(
                    enemies=enemies,
                    outcomes=outcomes or None,
                    mode=item.get("mode"),
                    style=item.get("style"),
                    rules=rules,
                    modifiers=_normalize_modifiers(item.get("modifiers")),
                    triggers=triggers,
                    confidence=0.95,
                ))
        else:
            enemies = _coerce_enemies(raw_list)
            if enemies:
                combats.append(Combat(
                    enemies=enemies,
                    style=_infer_combat_style(text, [CombatEnemy(**e) for e in enemies]),
                    confidence=0.95,
                ))
        return combats, usage
    except Exception as e:
        print(f"LLM extraction error: {e}")
        return [], {}


def extract_combat_llm_vision(
    text: str,
    images: List[str],
    model: str,
    client: OpenAI,
) -> Tuple[List[Combat], Dict[str, Any]]:
    try:
        content: List[Dict[str, Any]] = [
            {"type": "text", "text": f"{VISION_HINT}\n\n{text}"},
        ]
        for img in images:
            content.append({"type": "image_url", "image_url": {"url": _encode_image(img)}})
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
        )
        usage = {
            "model": model,
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
        }
        content = response.choices[0].message.content
        data = json.loads(content)
        raw_list = data.get("combat") if isinstance(data, dict) and "combat" in data else data
        if not isinstance(raw_list, list):
            raw_list = []
        combats: List[Combat] = []
        if raw_list and isinstance(raw_list[0], dict) and any(k in raw_list[0] for k in ("enemies", "outcomes", "rules", "modifiers", "triggers", "mode", "style")):
            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                enemies = _coerce_enemies(item.get("enemies") or [])
                if not enemies:
                    continue
                outcomes = item.get("outcomes")
                if not outcomes:
                    outcomes = _build_outcomes(
                        item.get("win_section"),
                        item.get("loss_section"),
                        item.get("escape_section"),
                    )
                rules, triggers = _normalize_rules(item.get("rules"), item.get("triggers"))
                combats.append(Combat(
                    enemies=enemies,
                    outcomes=outcomes or None,
                    mode=item.get("mode"),
                    style=item.get("style"),
                    rules=rules,
                    modifiers=_normalize_modifiers(item.get("modifiers")),
                    triggers=triggers,
                    confidence=0.95,
                ))
        else:
            enemies = _coerce_enemies(raw_list)
            if enemies:
                combats.append(Combat(
                    enemies=enemies,
                    style=_infer_combat_style(text, [CombatEnemy(**e) for e in enemies]),
                    confidence=0.95,
                ))
        return combats, usage
    except Exception as e:
        print(f"LLM vision extraction error: {e}")
        return [], {}

# Normal ranges for Fighting Fantasy stats (generous to include bosses)
MIN_SKILL = 1
MAX_SKILL = 15
MIN_STAMINA = 1
MAX_STAMINA = 40
MIN_ARMOUR = 1
MAX_ARMOUR = 50
MIN_FIREPOWER = 1
MAX_FIREPOWER = 20

def validate_combat(combats: List[Combat]) -> bool:
    """Returns True if all extracted combats look realistic."""
    if not combats:
        return True # Empty is valid if no combat present
    
    for c in combats:
        if not c.enemies:
            return False
        for enemy in c.enemies:
            skill = enemy.skill
            stamina = enemy.stamina
            armour = enemy.armour
            firepower = enemy.firepower
            has_standard = skill is not None and stamina is not None
            has_robot = skill is not None and armour is not None
            has_vehicle = firepower is not None and armour is not None
            if not (has_standard or has_robot or has_vehicle):
                return False
            if skill is not None and not (MIN_SKILL <= skill <= MAX_SKILL):
                return False
            if stamina is not None and not (MIN_STAMINA <= stamina <= MAX_STAMINA):
                return False
            if armour is not None and not (MIN_ARMOUR <= armour <= MAX_ARMOUR):
                return False
            if firepower is not None and not (MIN_FIREPOWER <= firepower <= MAX_FIREPOWER):
                return False
    return True


def _has_special_cues(text: str) -> bool:
    lower = text.lower()
    cues = (
        "one at a time",
        "attack round",
        "attack strength",
        "both",
        "choose which",
        "bare-handed",
        "during this combat",
        "during the combat",
        "reduce your skill",
    )
    return any(cue in lower for cue in cues)


def _is_combat_continuation(text: str) -> bool:
    lower = text.lower()
    if "combat" in lower and ("during this" in lower or "attack round" in lower):
        return True
    if "combat" in lower and "if you win" in lower:
        return True
    return False


def _needs_combat_outcomes(combats: List[Combat]) -> bool:
    for combat in combats:
        outcomes = combat.outcomes if isinstance(combat, Combat) else getattr(combat, "outcomes", None)
        if not isinstance(outcomes, dict) or not outcomes.get("win"):
            return True
    return False

def main():
    parser = argparse.ArgumentParser(description="Extract combat encounters from enriched portions.")
    parser.add_argument("--portions", required=True, help="Input enriched_portion_v1 JSONL")
    parser.add_argument("--pages", help="Input page_html_blocks_v1 JSONL (for driver compatibility)")
    parser.add_argument("--out", required=True, help="Output enriched_portion_v1 JSONL")
    parser.add_argument("--model", default="gpt-5.1")
    parser.add_argument("--use-ai", "--use_ai", action="store_true", default=True)
    parser.add_argument("--no-ai", "--no_ai", dest="use_ai", action="store_false")
    parser.add_argument("--max-ai-calls", "--max_ai_calls", type=int, default=50)
    parser.add_argument("--vision-model", "--vision_model", default="gpt-5.2")
    parser.add_argument("--vision-max-images", "--vision_max_images", type=int, default=1)
    parser.add_argument("--state-file")
    parser.add_argument("--progress-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    
    portions = list(read_jsonl(args.portions))
    total_portions = len(portions)
    
    client = OpenAI() if args.use_ai else None
    ai_calls = 0
    
    out_portions = []
    pending_idx: Optional[int] = None
    pending_section_id: Optional[int] = None
    last_combat_idx: Optional[int] = None
    last_combat_section_id: Optional[int] = None
    
    for idx, row in enumerate(portions):
        portion = EnrichedPortion(**row)
        text = portion.raw_text
        if not text and portion.raw_html:
            text = html_to_text(portion.raw_html)
        if not text:
            text = ""
        
        # 1. TRY: Regex attempt
        combats = extract_combat_regex(text, portion.raw_html)
        
        # 2. VALIDATE
        is_valid = validate_combat(combats)
        
        # 3. ESCALATE: LLM fallback if regex missed something, validation failed, 
        # or for complex cases (multiple enemies, special rules).
        
        needs_ai = False
        if not is_valid:
            needs_ai = True
        elif any(
            enemy.enemy == "Unknown"
            for combat in combats
            for enemy in combat.enemies
        ):
            needs_ai = True
        elif not combats:
            # Check if text mentions SKILL or STAMINA but regex missed the block
            upper_text = text.upper()
            if "SKILL" in upper_text and "STAMINA" in upper_text:
                needs_ai = True
            elif "FIREPOWER" in upper_text:
                needs_ai = True
            elif "ARMOUR" in upper_text and "SKILL" in upper_text:
                needs_ai = True
        elif any(len(combat.enemies) > 1 for combat in combats) or "special" in text.lower() or "rules" in text.lower() or _has_special_cues(text):
            # Multiple enemies or mentions of rules might need LLM to parse correctly
            needs_ai = True
            
        if needs_ai and args.use_ai and ai_calls < args.max_ai_calls:
            # If plain text is empty or very short, use HTML for better context (tables)
            llm_input = text
            if len(text) < 50 and portion.raw_html:
                llm_input = f"HTML SOURCE:\n{portion.raw_html}\n\nPLAIN TEXT:\n{text}"
            
            combats_llm, usage = extract_combat_llm(llm_input, args.model, client)
            ai_calls += 1
            if combats_llm:
                combats = combats_llm
                win_section, loss_section, escape_section = _detect_outcomes(text)
                win_section = _infer_win_from_anchors(portion.raw_html, loss_section, win_section)
                fallback_outcomes = _build_outcomes(win_section, loss_section, escape_section)
                fallback_triggers = _normalize_triggers(_extract_combat_triggers(text))
                fallback_mode, fallback_rules, fallback_modifiers = _extract_combat_rules(text, len(combats[0].enemies) if combats else 0)
                fallback_rules = _merge_rules(None, fallback_rules)
                fallback_modifiers = _normalize_modifiers(fallback_modifiers)
                for combat in combats:
                    combat.outcomes = _merge_fallback_outcomes(combat.outcomes, fallback_outcomes)
                    combat.triggers = _merge_triggers(combat.triggers, fallback_triggers)
                    if not combat.mode and fallback_mode:
                        combat.mode = fallback_mode
                    combat.rules = _merge_rules(combat.rules, fallback_rules)
                    combat.modifiers = _merge_modifiers(combat.modifiers, fallback_modifiers)
                    combat.rules = _prune_redundant_rules(combat.rules, combat.triggers)
                    combat.outcomes = _strip_spurious_escape(combat.outcomes, text)
                    combat.outcomes = _strip_spurious_loss(combat.outcomes, text, combat.triggers)
                    combat.mode = _normalize_mode(combat.mode, combat.rules)
                    if not combat.style:
                        combat.style = _infer_combat_style(text, combat.enemies)

        if combats and not validate_combat(combats) and args.use_ai and ai_calls < args.max_ai_calls:
            images = portion.source_images or []
            if images:
                combats_vision, usage = extract_combat_llm_vision(
                    text,
                    images[: args.vision_max_images],
                    args.vision_model,
                    client,
                )
                ai_calls += 1
                if combats_vision:
                    combats = combats_vision
        
        combats = _merge_sequential_combats(combats, text)
        for combat in combats:
            combat.rules = _prune_redundant_rules(combat.rules, combat.triggers)
            combat.outcomes = _strip_spurious_escape(combat.outcomes, text)
            combat.outcomes = _strip_spurious_loss(combat.outcomes, text, combat.triggers)
            combat.outcomes = _coerce_conditional_outcomes(combat.outcomes)
            combat.outcomes = _ensure_win_outcome_from_triggers(combat.outcomes, combat.triggers)
            combat.mode = _normalize_mode(combat.mode, combat.rules)
            if not combat.style:
                combat.style = _infer_combat_style(text, combat.enemies)
            _prune_split_target_enemies(combat, text)
            _expand_split_target_enemies(combat, text)
            _prune_ally_assisted_combat(combat, text)

        # If the next section contains combat continuation outcomes, attach them to the prior combat.
        if pending_idx is not None:
            section_id = portion.section_id
            if isinstance(section_id, str) and section_id.isdigit() and pending_section_id is not None:
                if int(section_id) > pending_section_id + 1:
                    pending_idx = None
                    pending_section_id = None
        if not combats and pending_idx is not None and _is_combat_continuation(text):
            section_id = portion.section_id
            if isinstance(section_id, str) and section_id.isdigit() and pending_section_id is not None:
                if int(section_id) == pending_section_id + 1:
                    win_section, loss_section, escape_section = _detect_outcomes(text)
                    win_section = _infer_win_from_anchors(portion.raw_html, loss_section, win_section)
                    fallback_outcomes = _build_outcomes(win_section, loss_section, escape_section)
                    if fallback_outcomes:
                        prev = out_portions[pending_idx]
                        prev_combats = prev.get("combat") or []
                        if prev_combats:
                            prev_outcomes = prev_combats[0].get("outcomes")
                            prev_combats[0]["outcomes"] = _merge_fallback_outcomes(prev_outcomes, fallback_outcomes)
                            prev["combat"] = prev_combats
                            pending_idx = None
                            pending_section_id = None

        # If this section is a continuation of the prior combat (often rules/mode/style without restating stats),
        # merge rules/triggers/style/mode onto the previous combat event. This is common in FF books where the
        # enemy stat block is in section N, and "During this X Combat..." rules are in section N+1.
        if not combats and last_combat_idx is not None and _is_combat_continuation(text):
            section_id = portion.section_id
            if isinstance(section_id, str) and section_id.isdigit() and last_combat_section_id is not None:
                if int(section_id) == last_combat_section_id + 1:
                    prev = out_portions[last_combat_idx]
                    prev_combats = prev.get("combat") or []
                    if prev_combats:
                        prev0 = prev_combats[0]
                        enemies = prev0.get("enemies") or []
                        # outcomes
                        win_section, loss_section, escape_section = _detect_outcomes(text)
                        win_section = _infer_win_from_anchors(portion.raw_html, loss_section, win_section)
                        fallback_outcomes = _build_outcomes(win_section, loss_section, escape_section)
                        if fallback_outcomes:
                            prev0["outcomes"] = _merge_fallback_outcomes(prev0.get("outcomes"), fallback_outcomes)
                        # mode/rules/modifiers/triggers
                        fallback_mode, fallback_rules, fallback_mods = _extract_combat_rules(text, len(enemies) if isinstance(enemies, list) else 0)
                        fallback_mods = _normalize_modifiers(fallback_mods)
                        fallback_triggers = _normalize_triggers(_extract_combat_triggers(text))
                        prev0["rules"] = _merge_rules(prev0.get("rules"), fallback_rules)
                        prev0["modifiers"] = _merge_modifiers(prev0.get("modifiers"), fallback_mods)
                        prev0["triggers"] = _merge_triggers(prev0.get("triggers"), fallback_triggers)
                        # mode: only upgrade from missing/single -> specialized
                        if not prev0.get("mode") and fallback_mode:
                            prev0["mode"] = fallback_mode
                        else:
                            prev0["mode"] = _normalize_mode(prev0.get("mode"), prev0.get("rules"))
                        # style: continuation text often carries the real style label ("Shooting Combat", etc)
                        current_style = prev0.get("style")
                        inferred_style = _infer_combat_style(text, [CombatEnemy(**e) for e in enemies] if isinstance(enemies, list) else [])
                        if inferred_style and (not current_style or current_style == "standard"):
                            prev0["style"] = inferred_style
                        prev["combat"] = prev_combats

        portion.combat = combats
        portion.turn_to_claims = _coerce_turn_to_claims(
            merge_turn_to_claims(
                portion.turn_to_claims,
                _combat_claims(combats),
            )
        )
        out_portions.append(portion.model_dump(exclude_none=True))

        # Track most recent combat-bearing section for continuation merges.
        if combats:
            section_id = portion.section_id
            if isinstance(section_id, str) and section_id.isdigit():
                last_combat_idx = len(out_portions) - 1
                last_combat_section_id = int(section_id)

        if combats and _needs_combat_outcomes(combats):
            section_id = portion.section_id
            if isinstance(section_id, str) and section_id.isdigit():
                pending_idx = len(out_portions) - 1
                pending_section_id = int(section_id)

        if (idx + 1) % 50 == 0:
            logger.log("extract_combat", "running", current=idx+1, total=total_portions, 
                       message=f"Processed {idx+1}/{total_portions} portions (AI calls: {ai_calls})")

    save_jsonl(args.out, out_portions)
    logger.log("extract_combat", "done", message=f"Extracted combat for {total_portions} portions. Total AI calls: {ai_calls}", artifact=args.out)

if __name__ == "__main__":
    main()
