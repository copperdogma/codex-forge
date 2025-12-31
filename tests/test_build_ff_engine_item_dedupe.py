from modules.export.build_ff_engine_with_issues_v1.main import build_section, make_sequence


def test_item_add_dedupe_prefers_longer_name():
    portion = {
        "items": [{"action": "add", "name": "pearl"}],
        "inventory": {"items_gained": [{"item": "Large Pearl", "quantity": 1}]},
        "stat_modifications": [],
        "stat_checks": [],
        "choices": [],
        "raw_html": "",
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    adds = [e for e in seq if e.get("kind") == "item" and e.get("action") == "add"]
    assert len(adds) == 1
    assert adds[0].get("name") == "Large Pearl"


def test_item_dedupe_applies_to_prebuilt_sequence():
    portion = {
        "section_id": "1",
        "page_start": 1,
        "page_end": 1,
        "raw_html": "",
        "raw_text": "You find a large pearl.",
        "sequence": [
            {"kind": "item", "action": "add", "name": "pearl"},
            {"kind": "item", "action": "add", "name": "Large Pearl"},
        ],
    }
    _, section = build_section(portion, emit_text=False, emit_provenance_text=False)
    adds = [e for e in section.get("sequence", []) if e.get("kind") == "item"]
    assert len(adds) == 1
    assert adds[0].get("name") == "Large Pearl"
