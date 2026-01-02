import json
import os
import pytest


def _load_gamebook():
    explicit = os.getenv("CF_GAMEBOOK_PATH")
    if explicit and os.path.exists(explicit):
        with open(explicit) as f:
            return json.load(f)
    run_id = os.getenv("CF_RUN_ID", "ff-ai-ocr-gpt51-pristine-fast-full-vnext-20260101f")
    candidate = os.path.join("output", "runs", run_id, "gamebook.json")
    if not os.path.exists(candidate):
        pytest.skip(f"gamebook.json not found at {candidate}; set CF_GAMEBOOK_PATH or CF_RUN_ID to run integration checks")
    with open(candidate) as f:
        return json.load(f)


def _combat_event(section):
    for event in section.get("sequence", []):
        if event.get("kind") == "combat":
            return event
    return None


def _has_test_luck(section):
    return any(event.get("kind") == "test_luck" for event in section.get("sequence", []))


def test_combat_outcomes_for_known_sections():
    gb = _load_gamebook()
    sections = gb["sections"]

    sec_143 = sections["143"]
    combat_143 = _combat_event(sec_143)
    assert combat_143["outcomes"]["win"] == {"targetSection": "163"}
    assert combat_143["outcomes"]["lose"] == {"targetSection": "2"}
    assert any(t.get("kind") == "enemy_attack_strength_total" and t.get("value") == 22 for t in combat_143.get("triggers", []))
    assert len(combat_143.get("enemies", [])) == 2

    sec_166 = sections["166"]
    combat_166 = _combat_event(sec_166)
    assert combat_166["mode"] == "sequential"
    assert combat_166["outcomes"]["win"] == {"targetSection": "11"}
    assert any(r.get("kind") == "fight_singly" for r in combat_166.get("rules", []))
    assert {"kind": "stat_change", "stat": "skill", "amount": -3, "scope": "combat", "reason": "combat penalty"} in combat_166.get("modifiers", [])

    sec_172 = sections["172"]
    combat_172 = _combat_event(sec_172)
    assert combat_172["outcomes"]["win"] == {"targetSection": "278"}
    assert any(t.get("kind") == "player_round_win" and t.get("count") == 2 and t.get("outcome") == {"targetSection": "278"}
               for t in combat_172.get("triggers", []))

    sec_225 = sections["225"]
    combat_225 = _combat_event(sec_225)
    assert combat_225["outcomes"]["win"] == {"terminal": {"kind": "continue"}}
    assert any(t.get("kind") == "player_round_win" and t.get("count") == 1 for t in combat_225.get("triggers", []))
    assert _has_test_luck(sec_225)

    sec_236 = sections["236"]
    combat_236 = _combat_event(sec_236)
    assert combat_236["outcomes"]["win"] == {"targetSection": "314"}
    assert any(t.get("kind") == "player_round_win" and t.get("count") == 1 and t.get("outcome") == {"targetSection": "314"}
               for t in combat_236.get("triggers", []))

    sec_294 = sections["294"]
    combat_294 = _combat_event(sec_294)
    assert combat_294["outcomes"]["win"] == {"terminal": {"kind": "continue"}}
    assert any(t.get("kind") == "player_round_win" and t.get("count") == 1 for t in combat_294.get("triggers", []))
    assert {"kind": "stat_change", "stat": "skill", "amount": -2, "scope": "combat", "reason": "combat penalty"} in combat_294.get("modifiers", [])
    assert _has_test_luck(sec_294)

    sec_327 = sections["327"]
    combat_327 = _combat_event(sec_327)
    assert combat_327["outcomes"]["win"] == {"targetSection": "92"}
    assert combat_327["outcomes"]["lose"] == {"targetSection": "8"}
    assert any(t.get("kind") == "enemy_round_win" and t.get("outcome") == {"targetSection": "8"}
               for t in combat_327.get("triggers", []))


def test_section_143_split_target_mechanics():
    gb = _load_gamebook()
    sec_143 = gb["sections"]["143"]
    combat = _combat_event(sec_143)
    assert combat["mode"] == "split-target"
    enemy_names = [e.get("enemy") for e in combat.get("enemies", [])]
    assert len(enemy_names) == 2
    assert all("pincer" in (name or "").lower() for name in enemy_names)
    rule_kinds = {r.get("kind") for r in combat.get("rules", [])}
    assert {"both_attack_each_round", "choose_target_each_round", "secondary_enemy_defense_only", "secondary_target_no_damage"} <= rule_kinds
    assert any(t.get("kind") == "enemy_attack_strength_total" and t.get("value") == 22 for t in combat.get("triggers", []))
