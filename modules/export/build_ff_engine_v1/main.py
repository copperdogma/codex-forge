import argparse
import json
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from modules.common.utils import read_jsonl, save_json, ProgressLogger
from modules.common.combat_styles import collect_combat_styles, resolve_combat_styles
from modules.common.html_utils import html_to_text


def _append_choice(
    events: List[Dict[str, Any]],
    seen: set,
    *,
    target: Optional[Any],
    choice_text: Optional[str] = None,
    effects: Optional[List[Dict[str, Any]]] = None,
) -> None:
    if target is None:
        return
    entry: Dict[str, Any] = {
        "kind": "choice",
        "targetSection": str(target),
    }
    if choice_text:
        entry["choiceText"] = choice_text
    if effects:
        entry["effects"] = effects
    key = (
        entry.get("targetSection"),
        entry.get("choiceText"),
        tuple((e.get("action"), e.get("name")) for e in (effects or [])),
    )
    if key in seen:
        return
    seen.add(key)
    events.append(entry)


def _clean_choice_item_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", name or "").strip()
    cleaned = re.sub(r"^from\s+(?:the|a|an|some)?\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^of\s+(?:the|a|an|some)?\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^just\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:the|a|an|some|your|his|her|their|my)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:drink|eat|use)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:the|a|an|some|your|his|her|their|my)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bwith you if you wish\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\bwith you\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\bif you wish\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\binto\s+your\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\bon\s+your\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\boff\s+(?:your|his|her|their|the)\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\byourself\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\b(?:then|and)\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\bturn\s+to\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s*-\s*$", "", cleaned).strip()
    return cleaned.strip(" .,:;!?()")


def _is_bad_choice_item_name(name: str) -> bool:
    if not name:
        return True
    lower = name.lower()
    if len(lower) < 3:
        return True
    # Reject pronouns/quantifiers and other non-item phrases that often appear in
    # "collect/take ..." clauses but do not represent a concrete inventory item.
    if re.search(r"\b(?:it|them|this|that|these|those)\b", lower):
        return True
    if re.search(r"\b(?:all|everything|anything|something|nothing)\b", lower):
        return True
    if "them all" in lower or lower.strip() in {"all", "them", "it"}:
        return True
    for phrase in (
        "turn to", "left passage", "right passage", "corridor", "tunnel", "passage",
        "door", "stairs", "later", "shape", "nearby being", "room", "floor",
        "fours", "crawl", "out of the room", "holding the skull", "with you",
        "if you wish", "liquid",
        "return",
        "gulp", "gulps", "gift",
    ):
        if phrase in lower:
            return True
    for phrase in ("escape", "window"):
        if phrase in lower:
            return True
    if "fountain" in lower:
        return True
    if lower.startswith("drink ") or lower.startswith("eat ") or lower.startswith("use "):
        return True
    return False


def _extract_choice_item_effects(text: Optional[str]) -> List[Dict[str, Any]]:
    if not text:
        return []
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    lower_text = text.lower()
    turn_idx = lower_text.rfind("turn to")
    if turn_idx != -1:
        text = text[max(0, turn_idx - 80):turn_idx + 40]
        lower_text = text.lower()
    if "if you have" in lower_text:
        return []
    effects: List[Dict[str, Any]] = []
    patterns = [
        (re.compile(r"\b(?:take|pick\s+up|grab|collect|buy|accept|pocket|take\s+with\s+you|put\s+on|wear)\b\s+(?:the|a|an|some)?\s*([A-Za-z][A-Za-z\-\' ]{2,60})", re.IGNORECASE), "add"),
        (re.compile(r"\btaking\s+just\s+(?:the|a|an|some)?\s*([A-Za-z][A-Za-z\-\' ]{2,60})", re.IGNORECASE), "add"),
        (re.compile(r"\btaking\s+(?:the|a|an|some)?\s*([A-Za-z][A-Za-z\-\' ]{2,60})\s+with\s+you\b", re.IGNORECASE), "add"),
        (re.compile(r"\b(?:eat|drink|use|consume|quaff|swallow|rub|apply)\b\s+(?:the|a|an|some)?\s*([A-Za-z][A-Za-z\-\' ]{2,60})", re.IGNORECASE), "remove"),
    ]
    seen = set()
    for pattern, action in patterns:
        for match in pattern.finditer(text):
            raw = match.group(1)
            if not raw:
                continue
            match_text = match.group(0).lower()
            if "take part" in match_text:
                continue
            if match_text.startswith("accept") and "offer" in match_text:
                continue
            if "take on" in match.group(0).lower():
                continue
            parts = [raw]
            if " and " in raw:
                parts = [p.strip() for p in raw.split(" and ") if p.strip()]
            for part in parts:
                name = _clean_choice_item_name(part)
                if _is_bad_choice_item_name(name):
                    continue
                key = (action, name.lower())
                if key in seen:
                    continue
                seen.add(key)
                effects.append({
                    "kind": "item",
                    "action": action,
                    "name": name,
                })
    return effects


def _choice_effect_text(raw_html: str, target: Optional[Any], fallback: Optional[str]) -> Optional[str]:
    if not raw_html or target is None:
        return fallback
    target_str = str(target)
    match = re.search(
        rf'href\s*=\s*["\']#{re.escape(target_str)}["\']',
        raw_html,
        flags=re.IGNORECASE,
    )
    if not match:
        return fallback
    if "<tr" in raw_html.lower():
        tr_start = raw_html.rfind("<tr", 0, match.start())
        tr_end = raw_html.find("</tr", match.end())
        if tr_start != -1 and tr_end != -1:
            snippet = raw_html[tr_start:tr_end]
            snippet = re.sub(r"<[^>]+>", " ", snippet)
            snippet = re.sub(r"\s+", " ", snippet).strip()
            return snippet or fallback
    for tag in ("p", "li"):
        tag_start = raw_html.rfind(f"<{tag}", 0, match.start())
        tag_end = raw_html.find(f"</{tag}", match.end())
        if tag_start != -1 and tag_end != -1:
            snippet = raw_html[tag_start:tag_end]
            if len(re.findall(r'href\s*=\s*["\']#', snippet, flags=re.IGNORECASE)) == 1:
                snippet = re.sub(r"<[^>]+>", " ", snippet)
                snippet = re.sub(r"\s+", " ", snippet).strip()
                return snippet or fallback
    punct = ".!?"
    start = max(raw_html.rfind(".", 0, match.start()), raw_html.rfind("!", 0, match.start()), raw_html.rfind("?", 0, match.start()))
    if start == -1:
        start = max(0, match.start() - 140)
    else:
        start = start + 1
    next_positions = [raw_html.find(p, match.end()) for p in punct if raw_html.find(p, match.end()) != -1]
    if next_positions:
        end = min(next_positions) + 1
    else:
        end = min(len(raw_html), match.end() + 40)
    snippet = raw_html[start:end]
    if len(re.findall(r'href\s*=\s*["\']#', snippet, flags=re.IGNORECASE)) > 1:
        local_start = max(start, match.start() - 70)
        local_end = min(len(raw_html), match.end() + 20)
        snippet = raw_html[local_start:local_end]
    snippet = re.sub(r"<[^>]+>", " ", snippet)
    snippet = re.sub(r"\s+", " ", snippet).strip()
    if snippet:
        simple = re.sub(r"\s+", " ", snippet).strip().lower()
        if simple.startswith("turn to") and len(simple.split()) <= 4:
            local_start = max(0, match.start() - 120)
            local_end = min(len(raw_html), match.end() + 20)
            expanded = raw_html[local_start:local_end]
            expanded = re.sub(r"<[^>]+>", " ", expanded)
            expanded = re.sub(r"\s+", " ", expanded).strip()
            return expanded or snippet or fallback
    if snippet and len(snippet.split()) <= 3:
        local_start = max(0, match.start() - 120)
        local_end = min(len(raw_html), match.end() + 20)
        expanded = raw_html[local_start:local_end]
        expanded = re.sub(r"<[^>]+>", " ", expanded)
        expanded = re.sub(r"\s+", " ", expanded).strip()
        return expanded or snippet or fallback
    return snippet or fallback


def _reorder_combat_outcomes(sequence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not sequence:
        return sequence
    seq = list(sequence)
    for idx, event in enumerate(list(seq)):
        if event.get("kind") != "combat":
            continue
        outcomes = event.get("outcomes") or {}
        targets = set()
        for ref in outcomes.values():
            if isinstance(ref, dict):
                target = ref.get("targetSection")
                if target is not None:
                    targets.add(str(target))
        if not targets:
            continue
        first_choice_idx = None
        for j, ev in enumerate(seq):
            if ev.get("kind") == "choice" and str(ev.get("targetSection")) in targets:
                first_choice_idx = j
                break
        if first_choice_idx is None or idx <= first_choice_idx:
            continue
        combat_event = seq.pop(idx)
        seq.insert(first_choice_idx, combat_event)
    return seq


def _drop_combat_outcome_choices(sequence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not sequence:
        return sequence
    outcome_targets = set()
    for ev in sequence:
        if ev.get("kind") != "combat":
            continue
        outcomes = ev.get("outcomes") or {}
        for ref in outcomes.values():
            if isinstance(ref, dict) and ref.get("targetSection") is not None:
                outcome_targets.add(str(ref.get("targetSection")))
    if not outcome_targets:
        return sequence
    filtered = []
    for ev in sequence:
        if ev.get("kind") != "choice":
            filtered.append(ev)
            continue
        target = str(ev.get("targetSection") or "")
        if target not in outcome_targets:
            filtered.append(ev)
            continue
        text = ev.get("choiceText")
        if text and re.match(rf"^\s*turn\s+to\s+{re.escape(target)}\s*\.?\s*$", text, re.IGNORECASE) and not ev.get("effects"):
            continue
        filtered.append(ev)
    return filtered


def _drop_mechanic_outcome_choices(sequence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not sequence:
        return sequence
    outcome_targets = set()
    for ev in sequence:
        kind = ev.get("kind")
        if kind == "test_luck":
            for key in ("lucky", "unlucky"):
                ref = ev.get(key) or {}
                target = ref.get("targetSection")
                if target is not None:
                    outcome_targets.add(str(target))
        elif kind == "stat_check":
            for key in ("pass", "fail"):
                ref = ev.get(key) or {}
                target = ref.get("targetSection")
                if target is not None:
                    outcome_targets.add(str(target))
        elif kind in {"item_check", "state_check"}:
            for key in ("has", "missing"):
                ref = ev.get(key) or {}
                target = ref.get("targetSection")
                if target is not None:
                    outcome_targets.add(str(target))
        elif kind == "conditional":
            for branch in ("then", "else"):
                for ev2 in ev.get(branch) or []:
                    if ev2.get("kind") == "choice" and ev2.get("targetSection") is not None:
                        outcome_targets.add(str(ev2.get("targetSection")))
    if not outcome_targets:
        return sequence
    filtered = []
    for ev in sequence:
        if ev.get("kind") != "choice":
            filtered.append(ev)
            continue
        target = str(ev.get("targetSection") or "")
        if target not in outcome_targets:
            filtered.append(ev)
            continue
        text = ev.get("choiceText")
        if text and re.match(rf"^\s*turn\s+to\s+{re.escape(target)}\s*\.?\s*$", text, re.IGNORECASE) and not ev.get("effects"):
            continue
        filtered.append(ev)
    return filtered


def _drop_choice_remove_duplicates(sequence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not sequence:
        return sequence
    remove_names = []
    for ev in sequence:
        if ev.get("kind") != "choice":
            continue
        for eff in ev.get("effects") or []:
            if eff.get("kind") == "item" and eff.get("action") == "remove":
                name = str(eff.get("name") or "").strip().lower()
                if name:
                    remove_names.append(name)
    if not remove_names:
        return sequence
    filtered = []
    for ev in sequence:
        if ev.get("kind") == "item" and ev.get("action") == "remove":
            name = str(ev.get("name") or "").strip().lower()
            if any(name == n or name in n or n in name for n in remove_names):
                continue
        filtered.append(ev)
    return filtered


def _dedupe_stat_events(sequence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not sequence:
        return sequence
    seen = set()
    deduped = []
    for ev in sequence:
        if ev.get("kind") != "stat_change":
            deduped.append(ev)
            continue
        key = (
            str(ev.get("stat") or "").lower(),
            str(ev.get("amount")),
            str(ev.get("scope") or "section").lower(),
            str(ev.get("reason") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ev)
    return deduped


def _apply_optional_take_choices(sequence: List[Dict[str, Any]], raw_html: str) -> None:
    if not raw_html or not sequence:
        return
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = re.sub(r"\s+", " ", text)
    def _item_found_in_container(item_name: str) -> bool:
        if not item_name:
            return False
        lower = text.lower()
        name = item_name.lower().strip()
        if name not in lower:
            return False
        pattern = rf"inside[^.]{{0,80}}you\s+find[^.]{{0,80}}{re.escape(name)}"
        return re.search(pattern, lower) is not None
    pattern = re.compile(
        r"if you (?:wish|want|decide|choose)[^\\.]{0,140}?"
        r"(?:take|pick up|grab|keep|collect)\s+"
        r"(?:the|a|an|some)?\s*([A-Za-z][A-Za-z\\-\\' ]{2,60})\s*,?\s*turn to\s+(\d+)",
        re.IGNORECASE,
    )
    pattern_no = re.compile(
        r"if you (?:do not|don't|would rather not|do not wish|would rather)[^\\.]{0,140}?"
        r"(?:take|pick up|grab|keep|collect)\s+"
        r"(?:the|a|an|some)?\s*([A-Za-z][A-Za-z\\-\\' ]{2,60})\s*,?\s*turn to\s+(\d+)",
        re.IGNORECASE,
    )
    for match in list(pattern.finditer(text)) + list(pattern_no.finditer(text)):
        raw_item = match.group(1)
        target = match.group(2)
        item = _clean_choice_item_name(raw_item)
        if _is_bad_choice_item_name(item):
            continue
        keep_unconditional = _item_found_in_container(item)
        # Remove first unconditional add for this item.
        if not keep_unconditional:
            for idx, ev in enumerate(list(sequence)):
                if ev.get("kind") == "item" and ev.get("action") == "add":
                    name = str(ev.get("name") or "").strip().lower()
                    if name and (item.lower() == name or item.lower() in name or name in item.lower()):
                        sequence.pop(idx)
                        break
        # Optional-take choices should not mutate inventory here; remove any effects for this item.
        for ev in sequence:
            if ev.get("kind") != "choice":
                continue
            if str(ev.get("targetSection")) != str(target):
                continue
            effects = list(ev.get("effects") or [])
            if not effects:
                continue
            item_effects = [
                e for e in effects
                if e.get("kind") == "item"
                and str(e.get("name") or "").strip().lower() == item.lower()
            ]
            if item_effects and len(item_effects) == len(effects):
                ev.pop("effects", None)


def _enrich_choice_effects(sequence: List[Dict[str, Any]], raw_html: str) -> None:
    if not raw_html:
        return
    added_items: List[str] = []
    for event in sequence:
        if event.get("kind") == "item" and event.get("action") == "add":
            name = str(event.get("name") or "").strip().lower()
            if name:
                added_items.append(name)
        if event.get("kind") != "choice":
            continue
        if event.get("effects"):
            continue
        effect_text = _choice_effect_text(raw_html, event.get("targetSection"), event.get("choiceText"))
        effects = _extract_choice_item_effects(effect_text)
        if effects:
            filtered = []
            for eff in effects:
                if eff.get("action") == "add":
                    name = str(eff.get("name") or "").strip().lower()
                    if name:
                        if any(name == existing or name in existing or existing in name for existing in added_items):
                            continue
                filtered.append(eff)
            if filtered:
                event["effects"] = filtered

def _extract_anchor_order(raw_html: str) -> List[str]:
    if not raw_html:
        return []
    return [m.group(1).strip() for m in re.finditer(r'href\s*=\s*["\']#([^"\']+)["\']', raw_html, flags=re.IGNORECASE)]


def _order_choices_by_html(raw_html: str, choice_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not raw_html or not choice_events:
        return choice_events
    order = _extract_anchor_order(raw_html)
    if not order:
        return choice_events
    order_map = {}
    for idx, target in enumerate(order):
        if target not in order_map:
            order_map[target] = idx
    decorated = []
    for idx, entry in enumerate(choice_events):
        target = entry.get("targetSection")
        decorated.append((order_map.get(target, len(order_map) + idx), idx, entry))
    decorated.sort(key=lambda x: (x[0], x[1]))
    return [entry for _, __, entry in decorated]


def _normalize_target(raw: Optional[Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    if raw is None:
        return None, None
    if isinstance(raw, (int, float)):
        s = str(int(raw)) if isinstance(raw, float) and raw.is_integer() else str(raw)
        return s, None
    s = str(raw).strip()
    if not s:
        return None, None
    if s.isdigit():
        return s, None
    match = re.search(r'\b(\d+)\b', s)
    if match:
        return match.group(1), None
    lower = s.lower()
    if re.search(r"\bcontinue\b", lower) or any(phrase in lower for phrase in ("still alive", "if alive", "if you're alive", "if you are alive", "if you survive")):
        return None, {"kind": "continue", "message": s}
    if any(k in lower for k in ("death", "die", "dead", "killed", "kill", "slain")):
        return None, {"kind": "death", "message": s}
    return s, None


def _normalize_outcome_ref(outcome: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(outcome, dict):
        return None
    if outcome.get("terminal"):
        return {"terminal": outcome.get("terminal")}
    target_raw = outcome.get("targetSection")
    if isinstance(target_raw, str) and not re.search(r"\d", target_raw):
        if not re.search(r"\bcontinue\b", target_raw.lower()):
            return None
    target, terminal = _normalize_target(target_raw)
    if terminal:
        return {"terminal": terminal}
    if target:
        return {"targetSection": target}
    return None


def _normalize_sequence_targets(sequence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for event in sequence:
        if not isinstance(event, dict):
            continue
        kind = event.get("kind")
        if kind == "stat_check":
            if "pass" in event:
                ref = _normalize_outcome_ref(event.get("pass"))
                if ref:
                    event["pass"] = ref
                else:
                    event.pop("pass", None)
            if "fail" in event:
                ref = _normalize_outcome_ref(event.get("fail"))
                if ref:
                    event["fail"] = ref
                else:
                    event.pop("fail", None)
        elif kind == "test_luck":
            if "lucky" in event:
                ref = _normalize_outcome_ref(event.get("lucky"))
                if ref:
                    event["lucky"] = ref
                else:
                    event.pop("lucky", None)
            if "unlucky" in event:
                ref = _normalize_outcome_ref(event.get("unlucky"))
                if ref:
                    event["unlucky"] = ref
                else:
                    event.pop("unlucky", None)
        elif kind in {"item_check", "state_check"}:
            if "has" in event:
                ref = _normalize_outcome_ref(event.get("has"))
                if ref:
                    event["has"] = ref
                else:
                    event.pop("has", None)
            if "missing" in event:
                ref = _normalize_outcome_ref(event.get("missing"))
                if ref:
                    event["missing"] = ref
                else:
                    event.pop("missing", None)
        elif kind == "combat":
            outcomes = event.get("outcomes")
            if isinstance(outcomes, dict):
                for key in ("win", "lose", "escape"):
                    if key in outcomes:
                        ref = _normalize_outcome_ref(outcomes.get(key))
                        if ref:
                            outcomes[key] = ref
                        else:
                            outcomes.pop(key, None)
                if outcomes:
                    event["outcomes"] = outcomes
                else:
                    event.pop("outcomes", None)
        elif kind == "death":
            ref = _normalize_outcome_ref(event.get("outcome"))
            if ref:
                event["outcome"] = ref
            else:
                continue
        elif kind == "conditional":
            if "then" in event:
                event["then"] = _normalize_sequence_targets(event.get("then") or [])
            if "else" in event:
                event["else"] = _normalize_sequence_targets(event.get("else") or [])
        normalized.append(event)
    return normalized


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
    for pattern in ("roll", "test your", "test the", "dice", "die", "combat", "fight", "attack"):
        idx = lower.find(pattern)
        if idx != -1:
            hint_positions.append(idx)
    if not hint_positions:
        return False
    stat_hint = min(hint_positions)
    if first_anchor == -1:
        return True
    return stat_hint < first_anchor


def _is_state_check_name(name: Optional[str]) -> bool:
    lower = str(name or "").strip().lower()
    if not lower:
        return False
    if lower.startswith(("read ", "seen ", "found ", "previously ")):
        return True
    if "previously read" in lower or "previously seen" in lower:
        return True
    if " and " in lower:
        return True
    return False


def _read_validator_version() -> Optional[str]:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    pkg_path = os.path.join(
        base_dir,
        "validate",
        "validate_ff_engine_node_v1",
        "validator",
        "package.json",
    )
    if not os.path.exists(pkg_path):
        return None
    try:
        with open(pkg_path, "r", encoding="utf-8") as f:
            pkg = json.load(f)
        name = pkg.get("name")
        version = pkg.get("version")
        if name and version:
            return f"{name}@{version}"
        return version or None
    except Exception:
        return None


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
    return pass_continues and fail_is_terminal and (pass_terminal is None or pass_terminal.get("kind") == "continue")


def make_sequence(portion: Dict[str, Any], section_id: str) -> List[Dict[str, Any]]:
    choice_events: List[Dict[str, Any]] = []
    mechanics_events: List[Dict[str, Any]] = []
    choice_seen: set = set()

    for choice in portion.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        effect_text = _choice_effect_text(
            portion.get("raw_html", ""),
            choice.get("target"),
            choice.get("text"),
        )
        effects = _extract_choice_item_effects(effect_text)
        _append_choice(
            choice_events,
            choice_seen,
            target=choice.get("target"),
            choice_text=choice.get("text"),
            effects=effects,
        )
    if not choice_events:
        for tgt in portion.get("targets") or []:
            _append_choice(choice_events, choice_seen, target=tgt)

    choice_events = _order_choices_by_html(portion.get("raw_html", ""), choice_events)

    stat_events: List[Dict[str, Any]] = []
    stat_seen = set()
    for mod in portion.get("stat_modifications") or []:
        if not isinstance(mod, dict):
            continue
        if mod.get("stat") is None or mod.get("amount") is None:
            continue
        key = (
            str(mod.get("stat")).lower(),
            str(mod.get("amount")),
            str(mod.get("scope") or "section").lower(),
            str(mod.get("reason") or ""),
        )
        if key in stat_seen:
            continue
        stat_seen.add(key)
        stat_event = {
            "kind": "stat_change",
            "stat": mod.get("stat"),
            "amount": mod.get("amount"),
            "scope": mod.get("scope", "section"),
        }
        if mod.get("reason"):
            stat_event["reason"] = mod.get("reason")
        stat_events.append(stat_event)

    stat_checks = [c for c in (portion.get("stat_checks") or []) if isinstance(c, dict)]
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

    item_seen = set()
    for item in portion.get("items") or []:
        if not isinstance(item, dict):
            continue
        action = item.get("action")
        if action == "check":
            continue
        name = item.get("name")
        if not action or not name:
            continue
        key = (str(action).lower(), str(name).strip().lower())
        if key in item_seen:
            continue
        item_seen.add(key)
        mechanics_events.append({
            "kind": "item",
            "action": action,
            "name": name,
        })

    for item in portion.get("items") or []:
        if not isinstance(item, dict):
            continue
        if item.get("action") != "check":
            continue
        has_target, has_terminal = _normalize_target(item.get("checkSuccessSection"))
        no_target, no_terminal = _normalize_target(item.get("checkFailureSection"))
        item_name = item.get("name")
        if _is_state_check_name(item_name):
            event = {
                "kind": "state_check",
                "conditionText": item_name,
            }
        else:
            event = {
                "kind": "item_check",
                "itemName": item_name,
            }
        has_ref = _outcome_ref(has_target, has_terminal)
        no_ref = _outcome_ref(no_target, no_terminal)
        if has_ref:
            event["has"] = has_ref
        if no_ref:
            event["missing"] = no_ref
        mechanics_events.append(event)

    portion_combat = portion.get("combat") or []
    if not isinstance(portion_combat, list):
        portion_combat = [portion_combat]
    for c in portion_combat:
        if not isinstance(c, dict):
            continue
        enemies = c.get("enemies") or []
        if not isinstance(enemies, list) or not enemies:
            continue
        combat_event: Dict[str, Any] = {"kind": "combat", "enemies": enemies}
        for field in ("mode", "rules", "modifiers", "triggers"):
            value = c.get(field)
            if value:
                combat_event[field] = value
        outcomes = c.get("outcomes")
        if isinstance(outcomes, dict):
            normalized: Dict[str, Any] = {}
            for key in ("win", "lose", "escape"):
                raw = outcomes.get(key)
                if isinstance(raw, dict):
                    ref = _normalize_outcome_ref(raw)
                else:
                    target, terminal = _normalize_target(raw)
                    ref = _outcome_ref(target, terminal)
                if ref:
                    normalized[key] = ref
            if normalized:
                combat_event["outcomes"] = normalized
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

    if _should_prepend_mechanics(portion.get("raw_html", ""), mechanics_events):
        return mechanics_events + choice_events
    return choice_events + mechanics_events


def classify_type(section_id: str, portion: Dict[str, Any], text_body: str) -> str:
    allowed_types = {
        "section",
        "front_cover",
        "back_cover",
        "title_page",
        "publishing_info",
        "toc",
        "intro",
        "rules",
        "adventure_sheet",
        "template",
        "background",
    }
    if portion.get("section_type") in allowed_types:
        return portion["section_type"]
    if portion.get("type") in allowed_types:
        return portion["type"]
    if section_id.isdigit():
        return "section"
    if section_id.lower() == "background":
        return "intro"

    lower = (text_body or "").lower()
    if "table of contents" in lower or "contents" in lower:
        return "toc"
    if "introduction" in lower or lower.startswith("introduction") or "story so far" in lower:
        return "intro"
    if ("rules" in lower or "how to play" in lower or "how to fight" in lower or
            "rules of the game" in lower or "how to use this book" in lower):
        return "rules"
    if "adventure sheet" in lower or "character sheet" in lower or "equipment" in lower or "possessions" in lower:
        return "adventure_sheet"
    if "published" in lower or "isbn" in lower:
        return "publishing_info"
    return "template"


def is_gameplay(section_id: str, portion: Dict[str, Any], candidate_type: Optional[str] = None) -> bool:
    if portion.get("is_gameplay") is not None:
        return bool(portion["is_gameplay"])
    if candidate_type == "section" or section_id.isdigit():
        return True
    if section_id.lower() == "background":
        return True
    if portion.get("sequence") is not None:
        return True
    if portion.get("choices") or portion.get("combat") or portion.get("test_luck") or portion.get("item_effects"):
        return True
    return False


def build_section(portion: Dict[str, Any], emit_text: bool, emit_provenance_text: bool) -> tuple[str, Dict[str, Any]]:
    """
    Build a Fighting Fantasy Engine section from an EnrichedPortion.

    Simplified for AI-first pipeline - raw_text is always provided by portionize_ai_extract_v1.
    """
    section_id = str(portion.get("section_id") or portion.get("portion_id"))
    page_start = int(portion.get("page_start"))
    page_end = int(portion.get("page_end"))
    page_start_original = portion.get("page_start_original")
    page_end_original = portion.get("page_end_original")

    html_body = portion.get("raw_html", "")
    text_body = portion.get("raw_text") or html_to_text(html_body)
    raw_body = text_body

    sequence = portion.get("sequence")
    if sequence is None:
        sequence = make_sequence(portion, section_id)
    sequence = list(sequence or [])
    raw_html = portion.get("raw_html", "")
    _enrich_choice_effects(sequence, raw_html)
    _apply_optional_take_choices(sequence, raw_html)
    sequence = _drop_choice_remove_duplicates(sequence)
    sequence = _normalize_sequence_targets(sequence)
    sequence = _dedupe_stat_events(sequence)
    sequence = _reorder_combat_outcomes(sequence)
    sequence = _drop_combat_outcome_choices(sequence)
    sequence = _drop_mechanic_outcome_choices(sequence)
    if section_id.lower() == "background":
        has_turn_to_one = False
        for event in sequence or []:
            if event.get("kind") == "choice" and str(event.get("targetSection")) == "1":
                has_turn_to_one = True
                break
        if not has_turn_to_one:
            sequence = list(sequence or [])
            sequence.append({
                "kind": "choice",
                "targetSection": "1",
                "choiceText": "Turn to 1",
            })

    candidate_type = classify_type(section_id, portion, text_body)

    section: Dict[str, Any] = {
        "id": section_id,
        "html": html_body,
        "pageStart": page_start,
        "pageEnd": page_end,
        "isGameplaySection": is_gameplay(section_id, portion, candidate_type),
        "type": candidate_type,
    }
    # Omit plain text fields from final gamebook output.

    if section.get("isGameplaySection", False):
        section["sequence"] = sequence

    # Propagate end_game marker (used to suppress no-choice warnings)
    if portion.get("end_game") or portion.get("endGame") or portion.get("is_endgame"):
        section["end_game"] = True
    ending_status = portion.get("ending")
    if ending_status in ("death", "victory", "defeat"):
        section["status"] = ending_status

    # Sequence is the canonical gameplay representation; legacy mechanic fields are omitted.

    provenance = {
        "portion_id": portion.get("portion_id"),
        "orig_portion_id": portion.get("orig_portion_id"),
        "confidence": portion.get("confidence"),
        "continuation_of": portion.get("continuation_of"),
        "continuation_confidence": portion.get("continuation_confidence"),
        "source_images": portion.get("source_images") or [],
        "source_pages": list(range(page_start, page_end + 1)),
        "source_pages_original": list(range(page_start_original, page_end_original + 1)) if isinstance(page_start_original, int) and isinstance(page_end_original, int) else None,
        "macro_section": portion.get("macro_section"),
        "module_id": portion.get("module_id"),
        "run_id": portion.get("run_id"),
    }
    # Omit raw/clean text in provenance for final gamebook output.
    section["provenance"] = provenance
    return section_id, section


def _collect_targets_from_sequence(sequence: List[Dict[str, Any]]) -> List[str]:
    targets: List[str] = []
    for event in sequence or []:
        kind = event.get("kind")
        if kind == "choice":
            if event.get("targetSection"):
                targets.append(str(event["targetSection"]))
        elif kind == "stat_check":
            for outcome_key in ("pass", "fail"):
                outcome = event.get(outcome_key) or {}
                if outcome.get("targetSection"):
                    targets.append(str(outcome["targetSection"]))
        elif kind == "stat_change":
            outcome = event.get("else") or {}
            if outcome.get("targetSection"):
                targets.append(str(outcome["targetSection"]))
        elif kind == "test_luck":
            for outcome_key in ("lucky", "unlucky"):
                outcome = event.get(outcome_key) or {}
                if outcome.get("targetSection"):
                    targets.append(str(outcome["targetSection"]))
        elif kind in {"item_check", "state_check"}:
            for outcome_key in ("has", "missing"):
                outcome = event.get(outcome_key) or {}
                if outcome.get("targetSection"):
                    targets.append(str(outcome["targetSection"]))
        elif kind == "combat":
            outcomes = event.get("outcomes") or {}
            for outcome_key in ("win", "lose", "escape"):
                outcome = outcomes.get(outcome_key) or {}
                if outcome.get("targetSection"):
                    targets.append(str(outcome["targetSection"]))
        elif kind == "death":
            outcome = event.get("outcome") or {}
            if outcome.get("targetSection"):
                targets.append(str(outcome["targetSection"]))
        else:
            if event.get("targetSection"):
                targets.append(str(event["targetSection"]))
    return targets


def collect_targets(section: Dict[str, Any]) -> List[str]:
    return _collect_targets_from_sequence(section.get("sequence") or [])


def main():
    parser = argparse.ArgumentParser(description="Build Fighting Fantasy Engine gamebook JSON from enriched portions.")
    parser.add_argument("--portions", required=True, help="Path to portions_enriched.jsonl")
    parser.add_argument("--out", required=True, help="Output gamebook JSON path")
    parser.add_argument("--combat-styles", dest="combat_styles", help="Optional combat styles JSON (frontmatter-derived)")
    parser.add_argument("--section-count", dest="section_count_file", help="Section range JSON (optional)")
    parser.add_argument("--title", required=True, help="Gamebook title")
    parser.add_argument("--author", help="Gamebook author")
    parser.add_argument("--start-section", "--start_section", default="1", dest="start_section", help="Starting section id")
    parser.add_argument("--format-version", "--format_version", default="1.0.0", dest="format_version", help="Format version string")
    parser.add_argument("--allow-stubs", action="store_true", dest="allow_stubs",
                        help="Permit stub backfill for missing targets (default: fail if stubs needed)")
    parser.add_argument("--expected-range", "--expected_range", default="1-400", dest="expected_range",
                        help="Expected section id range (e.g., 1-400). Targets outside are ignored.")
    parser.add_argument("--emit-text", "--emit_text", dest="emit_text", action="store_true",
                        help="Include plain text in section outputs (default: true)")
    parser.add_argument("--drop-text", "--drop_text", dest="emit_text", action="store_false",
                        help="Omit plain text from section outputs")
    parser.set_defaults(emit_text=True)
    parser.add_argument("--emit-provenance-text", "--emit_provenance_text", dest="emit_provenance_text",
                        action="store_true", help="Include raw/clean text in provenance (default: true)")
    parser.add_argument("--drop-provenance-text", "--drop_provenance_text", dest="emit_provenance_text",
                        action="store_false", help="Omit raw/clean text from provenance")
    parser.set_defaults(emit_provenance_text=True)
    parser.add_argument("--validator-version", "--validator_version", dest="validator_version",
                        help="Validator version stamp (defaults to bundled Node validator version)")
    parser.add_argument("--unresolved-missing", "--unresolved_missing", dest="unresolved_missing",
                        help="Optional path to unresolved_missing.json (sections verified missing from source).")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    parser.add_argument("--pages", help="(ignored; driver compatibility)")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("build_ff_engine", "running", current=0, total=None, message="Loading enriched portions", module_id="build_ff_engine_v1")

    # Parse expected range for filtering targets/stubs.
    try:
        r0, r1 = args.expected_range.split("-", 1)
        min_expected = int(r0.strip())
        max_expected = int(r1.strip())
    except Exception:
        min_expected, max_expected = 1, 400

    section_count_override = None
    if args.section_count_file:
        try:
            with open(args.section_count_file, "r", encoding="utf-8") as f:
                section_data = json.load(f)
            section_count_override = int(section_data["max_section"])
            max_expected = min(max_expected, section_count_override)
        except Exception:
            section_count_override = None

    # Load unresolved-missing allowlist (explicit artifact). If present, we can allow stubs
    # for these missing IDs without requiring --allow-stubs.
    unresolved_allow: set[str] = set()
    unresolved_path = args.unresolved_missing
    if not unresolved_path:
        unresolved_path = os.path.join(os.path.dirname(os.path.abspath(args.out)), "unresolved_missing.json")
    try:
        if unresolved_path and os.path.exists(unresolved_path):
            with open(unresolved_path, "r", encoding="utf-8") as f:
                unresolved_allow = {str(x) for x in json.load(f)}
    except Exception:
        unresolved_allow = set()

    portions = list(read_jsonl(args.portions))

    sections: Dict[str, Any] = {}
    for idx, portion in enumerate(portions, start=1):
        # Skip error records
        if "error" in portion:
            continue

        section_id, section = build_section(portion, args.emit_text, args.emit_provenance_text)
        if section_count_override is not None and str(section_id).isdigit():
            if int(section_id) > section_count_override:
                continue
        sections[section_id] = section
        if idx % 20 == 0:
            logger.log("build_ff_engine", "running", current=idx, total=len(portions),
                       message=f"Assembled {idx}/{len(portions)} sections", module_id="build_ff_engine_v1")

    # Backfill any missing target sections with stubs to satisfy validator
    all_targets: List[str] = []
    for sec in sections.values():
        all_targets.extend(collect_targets(sec))
    # Ignore targets outside expected range (often OCR/AI noise in provenance targets).
    missing = {
        t for t in all_targets
        if t.isdigit()
        and min_expected <= int(t) <= max_expected
        and t not in sections
    }
    stub_targets = sorted(missing, key=lambda x: int(x))
    stub_count = len(stub_targets)

    allow_stubs_effective = args.allow_stubs or (stub_targets and all(t in unresolved_allow for t in stub_targets))

    if stub_count and not allow_stubs_effective:
        # Explicit failure message for observability
        missing_ids_preview = ", ".join(stub_targets[:10])
        if stub_count > 10:
            missing_ids_preview += f" (and {stub_count - 10} more)"
        
        error_msg = (
            f"\n❌ BUILD FAILED: {stub_count} sections require stub backfill\n\n"
            f"Missing section IDs: {missing_ids_preview}\n\n"
            f"Root cause: Pipeline detected section boundaries but extraction failed, "
            f"or boundaries are missing entirely for these sections.\n\n"
            f"Next steps:\n"
            f"  1. Check boundary detection: Are these sections in section_boundaries_merged.jsonl?\n"
            f"  2. Check extraction: Did portionize_ai_extract_v1 fail on these boundaries?\n"
            f"  3. For debugging: Use --allow-stubs to build with placeholders and inspect validation_report.json\n"
            f"  4. To fix: Improve boundary detection (Priority 1) or extraction quality (Priority 2)\n"
        )
        
        logger.log("build_ff_engine", "failed", current=len(portions), total=len(portions),
                   message=f"Stub backfill required ({stub_count}); failing per policy", module_id="build_ff_engine_v1")
        raise SystemExit(error_msg)

    for mid in sorted(missing, key=lambda x: int(x) if str(x).isdigit() else x):
        reason = "backfilled missing target"
        if mid in unresolved_allow:
            reason = "verified_missing_from_source"
        stub_section = {
            "id": mid,
            "html": "",
            "isGameplaySection": True,
            "type": "section",
            "provenance": {"stub": True, "reason": reason},
        }
        sections[mid] = stub_section

    start_section = str(args.start_section)
    if "background" in sections:
        start_section = "background"
    if start_section not in sections and sections:
        # prefer numeric "1" if present, else first section id
        if "1" in sections:
            start_section = "1"
        else:
            start_section = sorted(sections.keys())[0]

    validator_version = args.validator_version or _read_validator_version()
    numeric_ids = [int(sid) for sid in sections.keys() if str(sid).isdigit()]
    section_count = max(numeric_ids) if numeric_ids else len(sections)
    if args.section_count_file:
        try:
            with open(args.section_count_file, "r", encoding="utf-8") as f:
                section_data = json.load(f)
            if isinstance(section_data, dict) and isinstance(section_data.get("max_section"), int):
                section_count = section_data["max_section"]
        except Exception:
            pass
    combat_styles_input = None
    if args.combat_styles:
        try:
            with open(args.combat_styles, "r", encoding="utf-8") as f:
                combat_styles_input = json.load(f)
        except Exception:
            combat_styles_input = None
    styles_in_use = collect_combat_styles(sections)
    combat_styles = None
    if combat_styles_input and isinstance(combat_styles_input, dict):
        style_map = combat_styles_input.get("styles") if isinstance(combat_styles_input.get("styles"), dict) else None
        if isinstance(style_map, dict):
            combat_styles = {k: v for k, v in style_map.items() if k in styles_in_use or v.get("default")}
    if not combat_styles:
        combat_styles = resolve_combat_styles(styles_in_use)
    metadata = {
        "title": args.title,
        "author": args.author,
        "startSection": start_section,
        "formatVersion": args.format_version,
        "sectionCount": section_count,
        **({"validatorVersion": validator_version} if validator_version else {}),
    }
    if combat_styles:
        metadata["combatStyles"] = combat_styles

    gamebook = {
        "metadata": metadata,
        "sections": sections,
        "provenance": {
            "stub_targets": stub_targets[:20],
            "stub_count": stub_count,
            "stubs_allowed": bool(allow_stubs_effective),
            "expected_range": args.expected_range,
            "unresolved_missing": sorted(
                [s for s in unresolved_allow if s.isdigit()],
                key=lambda x: int(x),
            )
            if unresolved_allow
            else [],
        },
    }

    save_json(args.out, gamebook)
    msg = f"Wrote {len(sections)} sections → {args.out}"
    if stub_count:
        msg += f" (stubs added: {stub_count})"
    logger.log("build_ff_engine", "done", current=len(portions), total=len(portions),
               message=msg, artifact=args.out,
               module_id="build_ff_engine_v1", schema_version="ff_engine_gamebook_v1",
               extra={"summary_metrics": {"sections_count": len(sections), "stubs_count": stub_count}})
    print(f"Wrote gamebook with {len(sections)} sections to {args.out}")


if __name__ == "__main__":
    main()
