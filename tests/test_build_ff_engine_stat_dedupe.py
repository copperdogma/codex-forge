from modules.export.build_ff_engine_v1.main import build_section, make_sequence


def test_stat_change_dedupe():
    portion = {
        "stat_modifications": [
            {"stat": "stamina", "amount": -2, "scope": "section"},
            {"stat": "stamina", "amount": -2, "scope": "section"},
            {"stat": "luck", "amount": -1, "scope": "section"},
            {"stat": "luck", "amount": -1, "scope": "section"},
        ],
        "stat_checks": [],
        "choices": [{"target": "10", "text": "Turn to 10"}],
        "raw_html": "",
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    stat_changes = [e for e in seq if e.get("kind") == "stat_change"]
    assert len(stat_changes) == 2


def test_stat_change_dedupe_on_prebuilt_sequence():
    portion = {
        "section_id": "1",
        "portion_id": "1",
        "page_start": 1,
        "page_end": 1,
        "page_start_original": 1,
        "page_end_original": 1,
        "raw_text": "",
        "raw_html": "",
        "sequence": [
            {"kind": "stat_change", "stat": "luck", "amount": -2, "scope": "section"},
            {"kind": "stat_change", "stat": "luck", "amount": -2, "scope": "section"},
            {"kind": "choice", "targetSection": "10", "choiceText": "Turn to 10"},
        ],
    }
    _, section = build_section(portion, emit_text=False, emit_provenance_text=False)
    stat_changes = [e for e in section.get("sequence", []) if e.get("kind") == "stat_change"]
    assert len(stat_changes) == 1
