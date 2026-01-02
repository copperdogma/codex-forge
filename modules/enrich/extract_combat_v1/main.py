import argparse
import json
import re
import os
from typing import Any, Dict, List, Optional, Tuple

from modules.common.openai_client import OpenAI
from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from modules.common.html_utils import html_to_text
from schemas import Combat, CombatEnemy, EnrichedPortion

# Common Fighting Fantasy combat patterns
# Stat block pattern: NAME followed by SKILL and STAMINA (sometimes on new lines)
STAT_BLOCK_PATTERN = re.compile(r"\b([A-Z][A-Z\s\-]{2,})\s+(?:SKILL|skill)\s*[:]?\s*(\d+)\s*(?:STAMINA|stamina)\s*[:]?\s*(\d+)", re.MULTILINE)
# Table-like or separated pattern
SEP_STAT_PATTERN = re.compile(r"(?:SKILL|skill)\s*[:]?\s*(\d+).*?(?:STAMINA|stamina)\s*[:]?\s*(\d+)", re.IGNORECASE | re.DOTALL)
WIN_PATTERNS = [
    re.compile(r"if\s+you\s+win,\s+turn\s+to\s+(\d+)", re.IGNORECASE),
    re.compile(r"as\s+soon\s+as\s+you\s+win(?:\s+your)?(?:\s+(?:first|second|third))?\s+attack\s+round,\s*turn\s+to\s+(\d+)", re.IGNORECASE),
    re.compile(r"if\s+you\s+(?:manage\s+to\s+)?(?:defeat|kill|slay)\b.*?\bturn\s+to\s+(\d+)", re.IGNORECASE | re.DOTALL),
]
LOSS_PATTERNS = [
    re.compile(r"if\s+you\s+lose,\s+turn\s+to\s+(\d+)", re.IGNORECASE),
    re.compile(r"attack\s+strength\s+totals?\s+\d+\s*,?\s*turn\s+to\s+(\d+)", re.IGNORECASE),
    re.compile(r"attack\s+strength\s+(?:is|was)\s+(?:greater|higher)\s+than\s+(?:your|yours).*?\bturn\s+to\s+(\d+)", re.IGNORECASE | re.DOTALL),
    re.compile(r"wins?\s+(?:an\s+)?attack\s+round.*?\bturn\s+to\s+(\d+)", re.IGNORECASE | re.DOTALL),
]
ESCAPE_PATTERN = re.compile(r"if\s+you\s+wish\s+to\s+escape,\s+turn\s+to\s+(\d+)", re.IGNORECASE)
ESCAPE_FLEX_PATTERN = re.compile(r"\bescape\b.{0,80}?\bturn\s+to\s+(\d+)", re.IGNORECASE | re.DOTALL)
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
FIGHT_SINGLY_PATTERN = re.compile(r"\b(one\s+at\s+a\s+time|fight\s+them\s+one\s+at\s+a\s+time)\b", re.IGNORECASE)
BOTH_ATTACK_PATTERN = re.compile(r"\bboth\b.{0,80}?\battack\b.{0,80}?\beach(?:\s+attack)?\s+round\b", re.IGNORECASE | re.DOTALL)
CHOOSE_TARGET_PATTERN = re.compile(r"\bchoose\b.{0,40}?\bfight\b", re.IGNORECASE | re.DOTALL)
CANNOT_WOUND_PATTERN = re.compile(r"\b(cannot|can't|will\s+not)\s+(?:wound|harm|hurt)\b", re.IGNORECASE)
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

SYSTEM_PROMPT = """You are an expert at parsing Fighting Fantasy gamebook sections.
Extract combat encounter information from the provided text into a JSON list of combat events.
The text may contain multiple enemies, sometimes in a table-like format with columns for SKILL and STAMINA.

Each combat object MUST have:
- enemies: list of { enemy, skill, stamina }

Optional fields when present in text:
- outcomes: { win, lose, escape } where each is { targetSection: "X" } or { terminal: { kind: "continue" } }
- mode: "single" | "sequential" | "simultaneous" | "split-target"
- rules: list of structured rules
- modifiers: list of stat changes (use scope: "combat" for combat-only)
- triggers: list of conditional outcome triggers

Return a JSON object with a "combat" key containing the list:
{
  "combat": [
    {
      "enemies": [{ "enemy": "SKELETON WARRIOR", "skill": 8, "stamina": 6 }],
      "outcomes": { "win": { "targetSection": "71" } }
    }
  ]
}

If no combat is found, return {"combat": []}."""

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
    escape_match = ESCAPE_PATTERN.search(text) or ESCAPE_FLEX_PATTERN.search(text)
    if escape_match:
        escape_section = escape_match.group(1)
    if win_section is None:
        for cue in WIN_CONTINUE_CUES:
            if cue.search(text):
                win_section = "continue"
                break
    return win_section, loss_section, escape_section


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
    return None


def _normalize_outcome_ref(outcome: Optional[Any]) -> Optional[Dict[str, Any]]:
    if outcome is None:
        return None
    if isinstance(outcome, dict):
        if outcome.get("terminal"):
            return {"terminal": outcome.get("terminal")}
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
    }
    for key, value in ordinal_map.items():
        if key in lower:
            return value
    if lower in ordinal_map:
        return ordinal_map[lower]
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
        if kind == "player_round_win":
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
    if "escape" in text.lower():
        return outcomes
    trimmed = dict(outcomes)
    trimmed.pop("escape", None)
    return trimmed


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
    match = re.search(
        r"(two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(?:of\s+its\s+)?([a-z\-]+?)(?:s)?\b",
        lower,
    )
    if match:
        raw_count = match.group(1)
        part = match.group(2)
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
    else:
        match = re.search(r"each\s+(?:of\s+its\s+)?([a-z\-]+?)(?:s)?\b", lower)
        if match:
            part = match.group(1)
        if "pair" in lower or "both" in lower or "two" in lower:
            count = 2
        else:
            count = 2

    if not count or count < 2:
        return

    base_enemy = combat.enemies[0]
    base_name = base_enemy.enemy or "Enemy"
    label = (part or "Part").replace("-", " ").title()
    combat.enemies = [
        CombatEnemy(enemy=f"{base_name} - {label} {idx + 1}", skill=base_enemy.skill, stamina=base_enemy.stamina)
        for idx in range(count)
    ]


def _normalize_mode(mode: Optional[str], rules: Optional[List[Dict[str, Any]]]) -> Optional[str]:
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

    combat = Combat(
        enemies=enemies,
        outcomes=outcomes or None,
        mode=mode,
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
        if "skill" in item and "stamina" in item:
            try:
                skill = int(item.get("skill"))
                stamina = int(item.get("stamina"))
            except (TypeError, ValueError):
                continue
            enemies.append({
                "enemy": item.get("enemy") or item.get("name") or "Creature",
                "skill": skill,
                "stamina": stamina,
            })
    return enemies


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
                    confidence=0.95,
                ))
        return combats, usage
    except Exception as e:
        print(f"LLM extraction error: {e}")
        return [], {}

# Normal ranges for Fighting Fantasy stats (generous to include bosses)
MIN_SKILL = 1
MAX_SKILL = 15
MIN_STAMINA = 1
MAX_STAMINA = 40

def validate_combat(combats: List[Combat]) -> bool:
    """Returns True if all extracted combats look realistic."""
    if not combats:
        return True # Empty is valid if no combat present
    
    for c in combats:
        if not c.enemies:
            return False
        for enemy in c.enemies:
            if enemy.skill is None or enemy.stamina is None:
                return False
            if not (MIN_SKILL <= enemy.skill <= MAX_SKILL):
                return False
            if not (MIN_STAMINA <= enemy.stamina <= MAX_STAMINA):
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

def main():
    parser = argparse.ArgumentParser(description="Extract combat encounters from enriched portions.")
    parser.add_argument("--portions", required=True, help="Input enriched_portion_v1 JSONL")
    parser.add_argument("--pages", help="Input page_html_blocks_v1 JSONL (for driver compatibility)")
    parser.add_argument("--out", required=True, help="Output enriched_portion_v1 JSONL")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--use-ai", "--use_ai", action="store_true", default=True)
    parser.add_argument("--no-ai", "--no_ai", dest="use_ai", action="store_false")
    parser.add_argument("--max-ai-calls", "--max_ai_calls", type=int, default=50)
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
                    combat.mode = _normalize_mode(combat.mode, combat.rules)
        
        combats = _merge_sequential_combats(combats, text)
        for combat in combats:
            combat.rules = _prune_redundant_rules(combat.rules, combat.triggers)
            combat.outcomes = _strip_spurious_escape(combat.outcomes, text)
            combat.mode = _normalize_mode(combat.mode, combat.rules)
            _prune_split_target_enemies(combat, text)
            _expand_split_target_enemies(combat, text)
        portion.combat = combats
        out_portions.append(portion.model_dump(exclude_none=True))
        
        if (idx + 1) % 50 == 0:
            logger.log("extract_combat", "running", current=idx+1, total=total_portions, 
                       message=f"Processed {idx+1}/{total_portions} portions (AI calls: {ai_calls})")

    save_jsonl(args.out, out_portions)
    logger.log("extract_combat", "done", message=f"Extracted combat for {total_portions} portions. Total AI calls: {ai_calls}", artifact=args.out)

if __name__ == "__main__":
    main()
