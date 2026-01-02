from modules.enrich.sequence_order_v1.main import build_sequence_from_portion


def test_sequence_dedupes_items():
    portion = {
        "choices": [{"target": "10", "text": "Turn to 10"}],
        "stat_modifications": [],
        "stat_checks": [],
        "inventory": {
            "items_gained": [{"item": "Rope", "quantity": 1}],
            "items_lost": [],
            "items_used": [],
            "inventory_checks": [],
        },
        "items": [{"action": "add", "name": "Rope"}],
        "raw_html": "<p>You find a rope. Turn to <a href=\"#10\">10</a>.</p>",
    }
    seq = build_sequence_from_portion(portion, "1")
    items = [e for e in seq if e.get("kind") == "item" and e.get("action") == "add"]
    assert len(items) == 1


def test_sequence_dedupes_test_luck():
    portion = {
        "choices": [{"target": "5", "text": "Turn to 5"}, {"target": "6", "text": "Turn to 6"}],
        "test_luck": [
            {"lucky_section": "5", "unlucky_section": "6"},
            {"lucky_section": "5", "unlucky_section": "6"},
        ],
        "raw_html": "<p>Test your Luck. If you are Lucky, turn to <a href=\"#5\">5</a>. "
                    "If you are Unlucky, turn to <a href=\"#6\">6</a>.</p>",
    }
    seq = build_sequence_from_portion(portion, "2")
    luck = [e for e in seq if e.get("kind") == "test_luck"]
    assert len(luck) == 1


def test_sequence_preserves_stat_check_after_stat_change():
    portion = {
        "choices": [{"target": "10", "text": "Turn to 10"}, {"target": "11", "text": "Turn to 11"}],
        "stat_modifications": [{"stat": "stamina", "amount": -2, "scope": "section"}],
        "stat_checks": [{
            "stat": "SKILL",
            "dice_roll": "2d6",
            "pass_section": "10",
            "fail_section": "11",
            "pass_condition": "total <= SKILL",
            "fail_condition": "total > SKILL",
        }],
        "raw_html": "<p>Lose 2 STAMINA. Roll two dice. If the total is the same as or "
                    "less than your SKILL, turn to <a href=\"#10\">10</a>. If the total is "
                    "greater than your SKILL, turn to <a href=\"#11\">11</a>.</p>",
    }
    seq = build_sequence_from_portion(portion, "3")
    kinds = [e.get("kind") for e in seq]
    assert kinds.index("stat_change") < kinds.index("stat_check")


def test_sequence_drops_survival_damage_check():
    portion = {
        "stat_modifications": [{"stat": "stamina", "amount": "-(1d6+1)", "scope": "section"}],
        "stat_checks": [{
            "stat": "STAMINA",
            "dice_roll": "1d6",
            "pass_section": "continue if alive",
            "fail_section": "death (no section number)",
            "pass_condition": "STAMINA - (roll + 1) > 0",
            "fail_condition": "STAMINA - (roll + 1) <= 0",
        }],
        "choices": [{"target": "10", "text": "Turn to 10"}],
        "raw_html": "<p>Roll one die, add 1, reduce STAMINA by total. If you're still alive, "
                    "turn to <a href=\"#10\">10</a>.</p>",
    }
    seq = build_sequence_from_portion(portion, "9")
    kinds = [e.get("kind") for e in seq]
    assert "stat_change" in kinds
    assert "stat_check" not in kinds


def test_sequence_drops_survival_damage_check_with_implied_death_text():
    portion = {
        "stat_modifications": [{"stat": "stamina", "amount": "-(1d6+1)", "scope": "section"}],
        "stat_checks": [{
            "stat": "STAMINA",
            "dice_roll": "1d6",
            "pass_section": "continue if alive",
            "fail_section": "implied death if STAMINA <= 0",
            "pass_condition": "STAMINA - (roll + 1) > 0",
            "fail_condition": "STAMINA - (roll + 1) <= 0",
        }],
        "choices": [{"target": "10", "text": "Turn to 10"}],
        "raw_html": "<p>Roll one die, add 1, reduce STAMINA by total. If you're still alive, "
                    "turn to <a href=\"#10\">10</a>.</p>",
    }
    seq = build_sequence_from_portion(portion, "9")
    kinds = [e.get("kind") for e in seq]
    assert "stat_change" in kinds
    assert "stat_check" not in kinds


def test_sequence_includes_combat_rules():
    portion = {
        "combat": [{
            "enemies": [{"enemy": "BEAST", "skill": 7, "stamina": 8}],
            "rules": [{"kind": "note", "text": "Reduce your SKILL by 2 during this combat"}],
            "outcomes": {"win": {"targetSection": "9"}},
        }],
        "raw_html": "<p>Fight the BEAST.</p>",
    }
    seq = build_sequence_from_portion(portion, "4")
    combat = next(e for e in seq if e.get("kind") == "combat")
    assert not combat.get("rules")


def test_sequence_orders_combat_before_test_luck():
    portion = {
        "combat": [{
            "enemies": [{"enemy": "BEAST", "skill": 7, "stamina": 8}],
            "outcomes": {"win": {"targetSection": "9"}},
        }],
        "test_luck": [{"lucky_section": "9", "unlucky_section": "10"}],
        "choices": [{"target": "9", "text": "Turn to 9"}, {"target": "10", "text": "Turn to 10"}],
        "raw_html": "<p>Fight the BEAST. As soon as you win, Test your Luck. "
                    "If you are Lucky, turn to <a href=\"#9\">9</a>. "
                    "If you are Unlucky, turn to <a href=\"#10\">10</a>.</p>",
    }
    seq = build_sequence_from_portion(portion, "5")
    kinds = [e.get("kind") for e in seq]
    assert kinds.index("combat") < kinds.index("test_luck")


def test_sequence_combat_win_continue_outcome():
    portion = {
        "combat": [{
            "enemies": [{"enemy": "BLOODBEAST", "skill": 12, "stamina": 10}],
            "outcomes": {"win": {"targetSection": "continue"}},
        }],
        "test_luck": [{"lucky_section": "97", "unlucky_section": "21"}],
        "raw_html": "<p>As soon as you win your first Attack Round, Test your Luck.</p>",
    }
    seq = build_sequence_from_portion(portion, "225")
    combat = next(e for e in seq if e.get("kind") == "combat")
    assert combat.get("outcomes", {}).get("win") == {"terminal": {"kind": "continue", "message": "continue"}}


def test_sequence_orders_damage_before_combat():
    portion = {
        "stat_modifications": [{"stat": "stamina", "amount": -2, "scope": "section"}],
        "combat": [{"enemies": [{"enemy": "IVY", "skill": 9, "stamina": 9}], "outcomes": {"win": {"targetSection": "201"}}}],
        "choices": [{"target": "201", "text": "Turn to 201"}],
        "raw_html": "<p>You are hit. Lose 2 STAMINA points. If you are still alive, you fight back. "
                    "IVY SKILL 9 STAMINA 9. If you win, turn to <a href=\"#201\">201</a>.</p>",
    }
    seq = build_sequence_from_portion(portion, "7")
    kinds = [e.get("kind") for e in seq]
    assert kinds.index("stat_change") < kinds.index("combat")


def test_sequence_orders_numeric_quantity_items():
    portion = {
        "choices": [{"target": "10", "text": "Turn to 10"}, {"target": "11", "text": "Turn to 11"}],
        "items": [
            {"action": "add", "name": "Wooden Mallet"},
            {"action": "add", "name": "10 Iron Spikes"},
        ],
        "raw_html": ("<p>The cupboard contains a wooden mallet and ten iron spikes. "
                     "If you wish to open the west door, turn to <a href=\"#10\">10</a>. "
                     "If you wish to open the north door, turn to <a href=\"#11\">11</a>.</p>"),
    }
    seq = build_sequence_from_portion(portion, "6")
    kinds = [e.get("kind") for e in seq]
    first_choice = kinds.index("choice")
    assert all(i < first_choice for i, k in enumerate(kinds) if k == "item")


def test_sequence_skips_item_remove_when_checked():
    portion = {
        "inventory": {
            "items_gained": [],
            "items_lost": [],
            "items_used": [{"item": "Potion", "quantity": 1}],
            "inventory_checks": [{"item": "Potion", "condition": "if you have", "target_section": "9"}],
        },
        "choices": [{"target": "9", "text": "Turn to 9"}],
        "raw_html": "<p>If you have a potion, turn to <a href=\"#9\">9</a>.</p>",
    }
    seq = build_sequence_from_portion(portion, "6")
    removes = [e for e in seq if e.get("kind") == "item" and e.get("action") == "remove"]
    assert removes == []


def test_sequence_merges_item_check_missing():
    portion = {
        "inventory": {
            "items_gained": [],
            "items_lost": [],
            "items_used": [],
            "inventory_checks": [
                {"item": "hollow wooden tube", "condition": "if you have", "target_section": "10"},
                {"item": "hollow wooden tube", "condition": "if you do not have", "target_section": "335"},
            ],
        },
        "raw_html": "<p>Have you got a hollow wooden tube? If you have, turn to <a href=\"#10\">10</a>. "
                    "If you have not, turn to <a href=\"#335\">335</a>.</p>",
    }
    seq = build_sequence_from_portion(portion, "7")
    item_checks = [e for e in seq if e.get("kind") == "item_check"]
    assert len(item_checks) == 1
    ev = item_checks[0]
    assert ev.get("has", {}).get("targetSection") == "10"
    assert ev.get("missing", {}).get("targetSection") == "335"


def test_sequence_merges_generic_key_missing():
    portion = {
        "inventory": {
            "items_gained": [],
            "items_lost": [],
            "items_used": [],
            "inventory_checks": [
                {"item": "iron key", "condition": "if you have", "target_section": "86"},
                {"item": "key", "condition": "if you do not have", "target_section": "276"},
            ],
        },
        "raw_html": "<p>If you have an iron key, turn to <a href=\"#86\">86</a>. "
                    "If you do not have a key, turn to <a href=\"#276\">276</a>.</p>",
    }
    seq = build_sequence_from_portion(portion, "8")
    item_checks = [e for e in seq if e.get("kind") == "item_check"]
    assert len(item_checks) == 1
    ev = item_checks[0]
    assert ev.get("itemName") == "iron key"
    assert ev.get("has", {}).get("targetSection") == "86"
    assert ev.get("missing", {}).get("targetSection") == "276"


def test_sequence_emits_state_check_for_read_seen_found():
    portion = {
        "inventory": {
            "items_gained": [],
            "items_lost": [],
            "items_used": [],
            "inventory_checks": [
                {"item": "read the poem written on the parchment", "condition": "if you have", "target_section": "10"},
                {"item": "seen the spirit girl", "condition": "if you do not have", "target_section": "20"},
                {"item": "found a diamond", "condition": "if you have", "target_section": "30"},
            ],
        },
        "raw_html": "<p>If you have read the poem, turn to 10. If you have not, turn to 20.</p>",
    }
    seq = build_sequence_from_portion(portion, "11")
    states = [e for e in seq if e.get("kind") == "state_check"]
    assert len(states) == 2
    assert any("read the poem" in e.get("conditionText", "") for e in states)
    assert any("seen the spirit girl" in e.get("conditionText", "") for e in states)
    item_checks = [e for e in seq if e.get("kind") == "item_check"]
    assert any(e.get("itemName") == "diamond" for e in item_checks)


def test_sequence_emits_state_check_for_compound_items():
    portion = {
        "inventory": {
            "items_gained": [],
            "items_lost": [],
            "items_used": [],
            "inventory_checks": [
                {"item": "coil of rope and a grappling iron", "condition": "if you have", "target_section": "129"},
            ],
        },
        "raw_html": "<p>If you have a coil of rope and a grappling iron, turn to 129.</p>",
    }
    seq = build_sequence_from_portion(portion, "12")
    item_check = next(e for e in seq if e.get("kind") == "item_check")
    assert item_check.get("itemsAll") == ["coil of rope", "grappling iron"]


def test_sequence_adds_custom_dice_check():
    portion = {
        "choices": [{"target": "152", "text": "Turn to 152"}, {"target": "121", "text": "Turn to 121"}],
        "raw_html": "<p>Roll two dice. If the total is less than eight, turn to "
                    "<a href=\"#152\">152</a>. If the total is eight or higher, "
                    "turn to <a href=\"#121\">121</a>.</p>",
    }
    seq = build_sequence_from_portion(portion, "9")
    custom = [e for e in seq if e.get("kind") == "custom"]
    assert len(custom) == 1
    data = custom[0]["data"]
    assert data["type"] == "dice_check"
    assert data["diceRoll"] == "2d6"
    assert data["pass"]["targetSection"] == "152"
    assert data["fail"]["targetSection"] == "121"


def test_sequence_skips_stat_check_with_zero_targets():
    portion = {
        "stat_checks": [{
            "stat": "STAMINA",
            "dice_roll": "1d6",
            "pass_section": 0,
            "fail_section": 0,
            "pass_condition": "STAMINA - (roll + 1) > 0",
            "fail_condition": "STAMINA - (roll + 1) <= 0",
        }],
        "raw_html": "<p>Roll one die and reduce your STAMINA.</p>",
    }
    seq = build_sequence_from_portion(portion, "10")
    assert all(e.get("kind") != "stat_check" for e in seq)


def test_sequence_orders_choices_without_anchors():
    portion = {
        "choices": [
            {"target": "132", "text": "Turn to 132"},
            {"target": "16", "text": "Turn to 16"},
            {"target": "249", "text": "Turn to 249"},
            {"target": "392", "text": "Turn to 392"},
            {"target": "177", "text": "Turn to 177"},
            {"target": "287", "text": "Turn to 287"},
        ],
        "raw_html": (
            "<table>"
            "<tr><td>A</td><td>B</td><td>C</td><td>Turn to 16</td></tr>"
            "<tr><td>Emerald</td><td>Diamond</td><td>Sapphire</td><td>Turn to 392</td></tr>"
            "<tr><td>Diamond</td><td>Sapphire</td><td>Emerald</td><td>Turn to 177</td></tr>"
            "<tr><td>Sapphire</td><td>Emerald</td><td>Diamond</td><td>Turn to 287</td></tr>"
            "<tr><td>Emerald</td><td>Sapphire</td><td>Diamond</td><td>Turn to 132</td></tr>"
            "<tr><td>Diamond</td><td>Emerald</td><td>Sapphire</td><td>Turn to 249</td></tr>"
            "</table>"
        ),
    }
    seq = build_sequence_from_portion(portion, "16")
    targets = [e.get("targetSection") for e in seq if e.get("kind") == "choice"]
    assert targets == ["16", "392", "177", "287", "132", "249"]


def test_sequence_builds_conditional_item_stat_change():
    portion = {
        "choices": [{"target": "36", "text": "Turn to 36"}],
        "stat_modifications": [{"stat": "skill", "amount": -1, "scope": "section"}],
        "inventory": {
            "items_gained": [],
            "items_lost": [{"item": "shield", "quantity": 1}],
            "items_used": [],
            "inventory_checks": [],
        },
        "raw_html": ("Dropping your shield if you have one (lose 1 SKILL point), "
                     "you turn to <a href=\"#36\"> 36 </a>."),
    }
    seq = build_sequence_from_portion(portion, "217")
    conditionals = [e for e in seq if e.get("kind") == "conditional"]
    assert len(conditionals) == 1
    conditional = conditionals[0]
    assert conditional.get("condition", {}).get("itemName") == "shield"
    then_kinds = [e.get("kind") for e in conditional.get("then", [])]
    assert "item" in then_kinds
    assert "stat_change" in then_kinds
    assert not any(e.get("kind") == "item" and e.get("action") == "remove" for e in seq if e is not conditional)
    assert not any(e.get("kind") == "stat_change" for e in seq if e is not conditional)
