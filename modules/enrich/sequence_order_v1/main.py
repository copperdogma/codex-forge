import argparse
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from modules.common.utils import read_jsonl, save_jsonl


def _extract_anchor_order(raw_html: str) -> List[str]:
    if not raw_html:
        return []
    return [m.group(1).strip() for m in re.finditer(r'href\s*=\s*["\']#([^"\']+)["\']', raw_html, flags=re.IGNORECASE)]


def _extract_anchor_positions(raw_html: str) -> List[Tuple[str, int]]:
    if not raw_html:
        return []
    matches = []
    for m in re.finditer(r'href\s*=\s*["\']#([^"\']+)["\']', raw_html, flags=re.IGNORECASE):
        matches.append((m.group(1).strip(), m.start()))
    return matches


def _extract_turn_to_positions(raw_html: str) -> List[Tuple[str, int]]:
    if not raw_html:
        return []
    matches = []
    for m in re.finditer(r"\bturn\s+to\s+(\d+)\b", raw_html, flags=re.IGNORECASE):
        matches.append((m.group(1).strip(), m.start()))
    return matches


def _order_choices_by_html(raw_html: str, choice_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not raw_html or not choice_events:
        return choice_events
    order = _extract_anchor_order(raw_html)
    if not order:
        order = [target for target, _ in _extract_turn_to_positions(raw_html)]
    if not order:
        return choice_events
    order_map: Dict[str, int] = {}
    for idx, target in enumerate(order):
        if target not in order_map:
            order_map[target] = idx
    decorated = []
    for idx, entry in enumerate(choice_events):
        target = entry.get("targetSection")
        decorated.append((order_map.get(target, len(order_map) + idx), idx, entry))
    decorated.sort(key=lambda x: (x[0], x[1]))
    return [entry for _, __, entry in decorated]


def _extract_stat_change_positions(raw_html: str) -> Dict[str, List[int]]:
    if not raw_html:
        return {}
    lower = raw_html.lower()
    pattern = re.compile(
        r"\b(lose|lost|reduce|reduced|reduces|gain|gained|increase|increased|add|subtract)\b(.{0,120}?)\b(stamina|skill|luck)\b",
        flags=re.IGNORECASE | re.DOTALL,
    )
    positions: Dict[str, List[int]] = {"stamina": [], "skill": [], "luck": []}
    for m in pattern.finditer(lower):
        stat = m.group(3).lower()
        positions.setdefault(stat, []).append(m.start())
    return positions


def _extract_stat_check_positions(raw_html: str) -> Dict[str, List[int]]:
    if not raw_html:
        return {}
    lower = raw_html.lower()
    positions: Dict[str, List[int]] = {"stamina": [], "skill": [], "luck": []}
    for m in re.finditer(r"\broll\b.{0,80}?\b(skill|stamina|luck)\b", lower, flags=re.IGNORECASE | re.DOTALL):
        stat = m.group(1).lower()
        positions.setdefault(stat, []).append(m.start())
    for m in re.finditer(r"\btest\s+(?:your\s+)?(skill|stamina|luck)\b", lower, flags=re.IGNORECASE):
        stat = m.group(1).lower()
        positions.setdefault(stat, []).append(m.start())
    return positions


def _extract_item_positions(raw_html: str, item_events: List[Dict[str, Any]]) -> Dict[int, int]:
    if not raw_html or not item_events:
        return {}
    lower = raw_html.lower()
    positions: Dict[int, int] = {}
    num_words = {
        1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
        6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
    }
    for idx, event in enumerate(item_events):
        name = event.get("name") or event.get("itemName") or event.get("conditionText")
        if not name and isinstance(event.get("itemsAll"), list) and event.get("itemsAll"):
            name = event.get("itemsAll")[0]
        if not name:
            continue
        key = str(name).lower()
        candidates = [key]
        match = re.match(r"^(\d+)\s+(.*)", key)
        if match:
            qty = int(match.group(1))
            rest = match.group(2)
            candidates.append(rest)
            word = num_words.get(qty)
            if word:
                candidates.append(f"{word} {rest}")
        best = None
        for cand in candidates:
            pos = lower.find(cand)
            if pos != -1 and (best is None or pos < best):
                best = pos
        if best is not None:
            positions[idx] = best
    return positions


def _is_state_check_name(name: str) -> bool:
    lower = str(name or "").strip().lower()
    if not lower:
        return False
    if lower.startswith(("read ", "seen ", "previously ")):
        return True
    if "previously read" in lower or "previously seen" in lower:
        return True
    return False


def _normalize_item_check_name(name: str) -> str:
    cleaned = str(name or "").strip()
    lowered = cleaned.lower()
    if lowered.startswith("found "):
        cleaned = cleaned[6:].strip()
    if lowered.startswith("previously found "):
        cleaned = cleaned[len("previously found "):].strip()
    cleaned = re.sub(r"^(a|an|the)\s+", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def _split_compound_item_names(name: str) -> List[str]:
    lowered = str(name or "").lower()
    if " and " not in lowered:
        return []
    parts = [p.strip() for p in re.split(r"\s+and\s+", name) if p.strip()]
    if len(parts) < 2:
        return []
    cleaned = []
    for part in parts:
        part = re.sub(r"^(a|an|the)\s+", "", part, flags=re.IGNORECASE).strip()
        if part:
            cleaned.append(part)
    return cleaned if len(cleaned) >= 2 else []


def _extract_test_luck_positions(raw_html: str) -> List[int]:
    if not raw_html:
        return []
    lower = raw_html.lower()
    return [m.start() for m in re.finditer(r"\btest\s+your\s+luck\b", lower)]


def _extract_conditional_item_stat_events(raw_html: str, sequence: List[Dict[str, Any]]) -> Tuple[List[Tuple[int, Dict[str, Any]]], set, set]:
    if not raw_html or not sequence:
        return [], set(), set()
    lower = raw_html.lower()
    item_positions = _extract_item_positions(raw_html, sequence)
    stat_positions = _extract_stat_change_positions(raw_html)
    conditional_events: List[Tuple[int, Dict[str, Any]]] = []
    used_items: set = set()
    used_stats: set = set()
    for idx, pos in item_positions.items():
        ev = sequence[idx]
        if ev.get("kind") != "item" or ev.get("action") != "remove":
            continue
        name = str(ev.get("name") or "").strip()
        if not name:
            continue
        window = lower[max(0, pos - 60):pos + 60]
        if not any(phrase in window for phrase in ("if you have", "if you possess", "if you are carrying")):
            continue
        best_stat_idx = None
        best_stat_pos = None
        for sidx, sev in enumerate(sequence):
            if sev.get("kind") != "stat_change":
                continue
            stat = sev.get("stat")
            if not stat:
                continue
            for spos in stat_positions.get(str(stat).lower(), []):
                if abs(spos - pos) > 140:
                    continue
                if best_stat_pos is None or abs(spos - pos) < abs(best_stat_pos - pos):
                    best_stat_pos = spos
                    best_stat_idx = sidx
        then_events = [ev]
        position = pos
        if best_stat_idx is not None:
            then_events.append(sequence[best_stat_idx])
            used_stats.add(best_stat_idx)
            position = min(position, best_stat_pos or position)
        conditional_events.append((
            position,
            {
                "kind": "conditional",
                "condition": {
                    "kind": "item",
                    "itemName": name,
                    "operator": "has",
                },
                "then": then_events,
            },
        ))
        used_items.add(idx)
    return conditional_events, used_items, used_stats

def _extract_plain_dice_check(raw_html: str) -> Optional[Dict[str, Any]]:
    if not raw_html:
        return None
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = re.sub(r"\s+", " ", text.lower())
    pattern = re.compile(
        r"roll\s+(one|two|three|four|five|six|\d+)\s+(?:die|dice).*?"
        r"if\s+the\s+total\s+is\s+less\s+than\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten).*?turn\s+to\s+(\d+).*?"
        r"if\s+the\s+total\s+is\s+(?:\2\s+or\s+higher|greater\s+than\s+\2|more\s+than\s+\2).*?turn\s+to\s+(\d+)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return None
    dice_word = m.group(1).lower()
    dice_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
    dice_count = dice_map.get(dice_word, int(dice_word) if dice_word.isdigit() else 2)
    threshold_raw = m.group(2).lower()
    word_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    threshold = word_map.get(threshold_raw, int(threshold_raw) if threshold_raw.isdigit() else 0)
    pass_section = m.group(3)
    fail_section = m.group(4)
    return {
        "kind": "custom",
        "data": {
            "type": "dice_check",
            "diceRoll": f"{dice_count}d6",
            "passCondition": f"total < {threshold}",
            "failCondition": f"total >= {threshold}",
            "pass": {"targetSection": str(pass_section)},
            "fail": {"targetSection": str(fail_section)},
        },
    }


def _extract_combat_positions(raw_html: str, sequence: List[Dict[str, Any]]) -> Dict[int, int]:
    if not raw_html:
        return {}
    lower = raw_html.lower()
    positions: Dict[int, int] = {}
    keyword_positions = [m.start() for m in re.finditer(r"\b(fight|attack|combat)\b", lower)]
    for idx, event in enumerate(sequence):
        if event.get("kind") != "combat":
            continue
        best = min(keyword_positions) if keyword_positions else None
        if best is None:
            enemies = event.get("enemies") or []
            for enemy in enemies:
                name = enemy.get("enemy")
                if not name:
                    continue
                pos = lower.find(str(name).lower())
                if pos != -1 and (best is None or pos < best):
                    best = pos
        if best is not None:
            positions[idx] = best
    return positions


def _reorder_stat_and_choice_by_html(sequence: List[Dict[str, Any]], raw_html: str) -> List[Dict[str, Any]]:
    if not raw_html or not sequence:
        return sequence
    lower = raw_html.lower()

    anchor_positions = _extract_anchor_positions(raw_html)
    if not anchor_positions:
        anchor_positions = _extract_turn_to_positions(raw_html)
    anchor_map: Dict[str, List[int]] = {}
    for target, pos in anchor_positions:
        anchor_map.setdefault(target, []).append(pos)

    stat_positions = _extract_stat_change_positions(raw_html)
    check_positions = _extract_stat_check_positions(raw_html)
    item_positions = _extract_item_positions(raw_html, sequence)
    luck_positions = _extract_test_luck_positions(raw_html)
    combat_positions = _extract_combat_positions(raw_html, sequence)

    indices: List[int] = []
    decorated: List[Tuple[int, Dict[str, Any]]] = []

    for idx, event in enumerate(sequence):
        kind = event.get("kind")
        if kind == "choice":
            target = event.get("targetSection")
            if target and target in anchor_map and anchor_map[target]:
                indices.append(idx)
                decorated.append((anchor_map[target].pop(0), event))
        elif kind == "stat_change":
            stat = event.get("stat")
            stat_key = str(stat).lower() if stat is not None else None
            if stat_key and stat_key in stat_positions and stat_positions[stat_key]:
                indices.append(idx)
                decorated.append((stat_positions[stat_key].pop(0), event))
        elif kind == "stat_check":
            stat = event.get("stat")
            stat_key = str(stat).lower() if stat is not None else None
            if stat_key and stat_key in check_positions and check_positions[stat_key]:
                indices.append(idx)
                decorated.append((check_positions[stat_key].pop(0), event))
        elif kind == "test_luck" and luck_positions:
            indices.append(idx)
            decorated.append((luck_positions.pop(0), event))
        elif kind in {"item", "item_check", "state_check"} and idx in item_positions:
            indices.append(idx)
            decorated.append((item_positions[idx], event))
        elif kind == "conditional":
            condition = event.get("condition") or {}
            if isinstance(condition, dict) and condition.get("kind") == "item":
                item_name = str(condition.get("itemName") or "").lower().strip()
                if item_name:
                    pos = lower.find(item_name)
                    if pos != -1:
                        indices.append(idx)
                        decorated.append((pos, event))
        elif kind == "combat" and idx in combat_positions:
            indices.append(idx)
            decorated.append((combat_positions[idx], event))

    if len(decorated) < 2:
        return sequence

    ordered = [event for _, event in sorted(decorated, key=lambda x: x[0])]
    for i, idx in enumerate(indices):
        sequence[idx] = ordered[i]
    return sequence


def _normalize_target(raw: Optional[Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    if raw is None:
        return None, None
    if isinstance(raw, (int, float)):
        s = str(int(raw)) if isinstance(raw, float) and raw.is_integer() else str(raw)
        if s == "0":
            return None, None
        return s, None
    s = str(raw).strip()
    if not s:
        return None, None
    if s.isdigit():
        if s == "0":
            return None, None
        return s, None
    lower = s.lower()
    if any(k in lower for k in ("death", "die", "dead", "killed", "kill", "slain")):
        return None, {"kind": "death", "message": s}
    match = re.search(r"\b(\d+)\b", s)
    if match:
        return match.group(1), None
    if any(phrase in lower for phrase in ("continue", "still alive", "if alive", "if you're alive", "if you are alive", "if you survive")):
        return None, None
    return s, None


def _outcome_ref(target: Optional[str], terminal: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if target is not None:
        return {"targetSection": str(target)}
    if terminal is not None:
        return {"terminal": terminal}
    return None


def _should_prepend_mechanics(raw_html: str, mechanics_events: List[Dict[str, Any]]) -> bool:
    if not raw_html or not mechanics_events:
        return False
    lower = raw_html.lower()
    first_anchor = lower.find("<a")
    hint_positions = []
    for pattern in (
        "roll",
        "test your",
        "test the",
        "dice",
        "die",
        "combat",
        "fight",
        "attack",
        "lose",
        "gain",
        "reduce",
        "increase",
        "add",
        "subtract",
        "stamina",
        "skill",
        "luck",
        "find",
    ):
        idx = lower.find(pattern)
        if idx != -1:
            hint_positions.append(idx)
    if not hint_positions:
        return False
    stat_hint = min(hint_positions)
    if first_anchor == -1:
        return True
    return stat_hint < first_anchor


def _is_survival_damage_check(
    check: Dict[str, Any],
    stat_events: List[Dict[str, Any]],
    section_id: str,
) -> bool:
    stat = check.get("stat")
    if stat is None:
        return False
    stat_key = str(stat).lower()
    if not any(
        event.get("kind") == "stat_change" and str(event.get("stat")).lower() == stat_key
        for event in stat_events
    ):
        return False
    pass_target, pass_terminal = _normalize_target(check.get("pass_section"))
    fail_target, fail_terminal = _normalize_target(check.get("fail_section"))
    pass_continues = pass_target is None or pass_target == section_id
    fail_is_terminal = fail_terminal is not None and fail_target is None
    return pass_continues and fail_is_terminal and pass_terminal is None


def _append_choice(events: List[Dict[str, Any]], seen: set, *, target: Optional[Any], choice_text: Optional[str] = None) -> None:
    if target is None:
        return
    entry: Dict[str, Any] = {
        "kind": "choice",
        "targetSection": str(target),
    }
    if choice_text:
        entry["choiceText"] = choice_text
    key = (entry.get("targetSection"), entry.get("choiceText"))
    if key in seen:
        return
    seen.add(key)
    events.append(entry)


def build_sequence_from_portion(portion: Dict[str, Any], section_id: str) -> List[Dict[str, Any]]:
    choice_events: List[Dict[str, Any]] = []
    mechanics_events: List[Dict[str, Any]] = []
    choice_seen: set = set()

    for choice in portion.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        _append_choice(choice_events, choice_seen, target=choice.get("target"), choice_text=choice.get("text"))
    if not choice_events:
        for tgt in portion.get("targets") or []:
            _append_choice(choice_events, choice_seen, target=tgt)

    choice_events = _order_choices_by_html(portion.get("raw_html", ""), choice_events)

    stat_events: List[Dict[str, Any]] = []
    for mod in portion.get("stat_modifications") or []:
        if not isinstance(mod, dict):
            continue
        if mod.get("stat") is None or mod.get("amount") is None:
            continue
        stat_events.append({
            "kind": "stat_change",
            "stat": mod.get("stat"),
            "amount": mod.get("amount"),
            "permanent": mod.get("permanent", False),
        })

    stat_checks = [c for c in (portion.get("stat_checks") or []) if isinstance(c, dict)]
    plain_dice_check = _extract_plain_dice_check(portion.get("raw_html", ""))
    if plain_dice_check:
        mechanics_events.append(plain_dice_check)
    for check in stat_checks:
        if _is_survival_damage_check(check, stat_events, section_id):
            continue
        if check.get("stat") is None:
            continue
        stat_event: Dict[str, Any] = {
            "kind": "stat_check",
            "stat": check.get("stat"),
            "diceRoll": check.get("dice_roll", "2d6"),
        }
        if check.get("pass_condition"):
            stat_event["passCondition"] = check.get("pass_condition")
        if check.get("fail_condition"):
            stat_event["failCondition"] = check.get("fail_condition")
        pass_target, pass_terminal = _normalize_target(check.get("pass_section"))
        fail_target, fail_terminal = _normalize_target(check.get("fail_section"))
        pass_ref = _outcome_ref(pass_target, pass_terminal)
        fail_ref = _outcome_ref(fail_target, fail_terminal)
        if not pass_ref and not fail_ref:
            continue
        if pass_ref:
            stat_event["pass"] = pass_ref
        if fail_ref:
            stat_event["fail"] = fail_ref
        mechanics_events.append(stat_event)

    mechanics_events.extend(stat_events)

    for item in portion.get("items") or []:
        if not isinstance(item, dict):
            continue
        action = item.get("action")
        if action == "check":
            continue
        name = item.get("name")
        if not action or not name:
            continue
        mechanics_events.append({
            "kind": "item",
            "action": action,
            "name": name,
        })

    inv = portion.get("inventory")
    if inv and isinstance(inv, dict):
        for item in inv.get("items_gained", []):
            if not isinstance(item, dict) or not item.get("item"):
                continue
            mechanics_events.append({
                "kind": "item",
                "action": "add",
                "name": f"{item.get('quantity', 1)} {item.get('item')}" if item.get("quantity", 1) > 1 else item.get("item"),
            })
        for item in inv.get("items_lost", []):
            if not isinstance(item, dict) or not item.get("item"):
                continue
            mechanics_events.append({
                "kind": "item",
                "action": "remove",
                "name": item.get("item"),
            })
        for item in inv.get("items_used", []):
            if not isinstance(item, dict) or not item.get("item"):
                continue
            mechanics_events.append({
                "kind": "item",
                "action": "remove",
                "name": item.get("item"),
            })

    if inv and isinstance(inv, dict):
        check_map: Dict[str, Dict[str, Any]] = {}
        check_order: List[str] = []
        for check in inv.get("inventory_checks", []):
            if not isinstance(check, dict):
                continue
            item_name = check.get("item")
            if not item_name:
                continue
            target, terminal = _normalize_target(check.get("target_section"))
            outcome = _outcome_ref(target, terminal)
            if not outcome:
                continue
            normalized_name = _normalize_item_check_name(item_name)
            key = str(normalized_name).lower().strip()
            if key == "key":
                candidates = [k for k in check_map.keys() if k.endswith(" key")]
                if len(candidates) == 1:
                    key = candidates[0]
            if key not in check_map:
                if _is_state_check_name(item_name):
                    check_map[key] = {"kind": "state_check", "conditionText": item_name}
                else:
                    items_all = _split_compound_item_names(item_name)
                    if items_all:
                        check_map[key] = {"kind": "item_check", "itemsAll": items_all}
                    else:
                        check_map[key] = {"kind": "item_check", "itemName": normalized_name}
                check_order.append(key)
            condition = str(check.get("condition") or "").lower()
            if "do not have" in condition or "have not" in condition or "missing" in condition:
                check_map[key]["missing"] = outcome
            else:
                check_map[key]["has"] = outcome
        for key in check_order:
            mechanics_events.append(check_map[key])

    for item in portion.get("items") or []:
        if not isinstance(item, dict):
            continue
        if item.get("action") != "check":
            continue
        has_target, has_terminal = _normalize_target(item.get("checkSuccessSection"))
        no_target, no_terminal = _normalize_target(item.get("checkFailureSection"))
        item_name = item.get("name")
        normalized_name = _normalize_item_check_name(item_name)
        if _is_state_check_name(item_name):
            event = {
                "kind": "state_check",
                "conditionText": item_name,
            }
        else:
            items_all = _split_compound_item_names(item_name)
            event = {
                "kind": "item_check",
                "itemName": normalized_name,
            }
            if items_all:
                event["itemsAll"] = items_all
        has_ref = _outcome_ref(has_target, has_terminal)
        no_ref = _outcome_ref(no_target, no_terminal)
        if has_ref:
            event["has"] = has_ref
        if no_ref:
            event["missing"] = no_ref
        mechanics_events.append(event)

    portion_luck = portion.get("test_luck") or portion.get("testYourLuck") or []
    if not isinstance(portion_luck, list):
        portion_luck = [portion_luck]
    luck_seen: set = set()
    for l in portion_luck:
        if not isinstance(l, dict):
            continue
        lucky_target, lucky_terminal = _normalize_target(l.get("lucky_section") or l.get("luckySection"))
        unlucky_target, unlucky_terminal = _normalize_target(l.get("unlucky_section") or l.get("unluckySection"))
        key = (str(lucky_target) if lucky_target is not None else None,
               str(unlucky_target) if unlucky_target is not None else None)
        if key in luck_seen:
            continue
        luck_seen.add(key)
        event = {"kind": "test_luck"}
        lucky_ref = _outcome_ref(lucky_target, lucky_terminal)
        unlucky_ref = _outcome_ref(unlucky_target, unlucky_terminal)
        if lucky_ref:
            event["lucky"] = lucky_ref
        if unlucky_ref:
            event["unlucky"] = unlucky_ref
        mechanics_events.append(event)

    portion_combat = portion.get("combat") or []
    if not isinstance(portion_combat, list):
        portion_combat = [portion_combat]
    enemies = []
    combat_outcomes: Dict[str, Any] = {}
    for c in portion_combat:
        if not isinstance(c, dict):
            continue
        if c.get("skill") is None or c.get("stamina") is None:
            continue
        enemies.append({
            "enemy": c.get("enemy") or c.get("name") or "Creature",
            "skill": c.get("skill"),
            "stamina": c.get("stamina"),
        })
        if c.get("special_rules") and isinstance(c.get("special_rules"), str):
            enemies[-1]["special_rules"] = c.get("special_rules")
        win_target, win_terminal = _normalize_target(c.get("win_section") or c.get("winSection"))
        lose_target, lose_terminal = _normalize_target(c.get("loss_section") or c.get("loseSection"))
        escape_target, escape_terminal = _normalize_target(c.get("escape_section") or c.get("escapeSection"))
        win_ref = _outcome_ref(win_target, win_terminal)
        lose_ref = _outcome_ref(lose_target, lose_terminal)
        escape_ref = _outcome_ref(escape_target, escape_terminal)
        if win_ref:
            combat_outcomes["win"] = win_ref
        if lose_ref:
            combat_outcomes["lose"] = lose_ref
        if escape_ref:
            combat_outcomes["escape"] = escape_ref
    if enemies:
        combat_event: Dict[str, Any] = {"kind": "combat", "enemies": enemies}
        if combat_outcomes:
            combat_event["outcomes"] = combat_outcomes
        mechanics_events.append(combat_event)

    for death in portion.get("deathConditions") or []:
        if not isinstance(death, dict):
            continue
        death_target, death_terminal = _normalize_target(death.get("deathSection"))
        outcome = _outcome_ref(death_target, death_terminal)
        if not outcome:
            continue
        mechanics_events.append({
            "kind": "death",
            "outcome": outcome,
            "description": death.get("description"),
        })

    conditional_events, used_items, used_stats = _extract_conditional_item_stat_events(
        portion.get("raw_html", ""),
        mechanics_events,
    )
    if conditional_events:
        mechanics_events = [
            ev for idx, ev in enumerate(mechanics_events)
            if idx not in used_items and idx not in used_stats
        ]
        mechanics_events.extend([event for _, event in conditional_events])

    check_items = {
        str(ev.get("itemName", "")).lower().strip()
        for ev in mechanics_events
        if ev.get("kind") == "item_check"
    }
    seen_items = set()
    deduped: List[Dict[str, Any]] = []
    for ev in mechanics_events:
        if ev.get("kind") == "item":
            if ev.get("action") == "remove" and str(ev.get("name", "")).lower().strip() in check_items:
                continue
            key = (ev.get("action"), str(ev.get("name", "")).lower().strip())
            if key in seen_items:
                continue
            seen_items.add(key)
        deduped.append(ev)
    mechanics_events = deduped

    if _should_prepend_mechanics(portion.get("raw_html", ""), mechanics_events):
        ordered = mechanics_events + choice_events
    else:
        ordered = choice_events + mechanics_events

    return _reorder_stat_and_choice_by_html(ordered, portion.get("raw_html", ""))


def main() -> None:
    parser = argparse.ArgumentParser(description="Order gameplay sequence events for enriched portions.")
    parser.add_argument("--portions", required=True, help="Input portions (jsonl).")
    parser.add_argument("--out", required=True, help="Output path (jsonl).")
    parser.add_argument("--pages", help="(ignored; driver compatibility)")
    parser.add_argument("--state-file")
    parser.add_argument("--progress-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    rows = list(read_jsonl(args.portions))
    out_rows: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            out_rows.append(row)
            continue
        sid = str(row.get("section_id") or row.get("portion_id"))
        if row.get("is_gameplay") is False:
            row["sequence"] = []
        else:
            row["sequence"] = build_sequence_from_portion(row, sid)
        out_rows.append(row)

    save_jsonl(args.out, out_rows)
    print(f"Wrote ordered sequences -> {args.out}")


if __name__ == "__main__":
    main()
