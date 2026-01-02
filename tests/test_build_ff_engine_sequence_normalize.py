from modules.export.build_ff_engine_v1.main import build_section


def test_normalize_sequence_targets_drops_invalid_pass():
    portion = {
        "section_id": "16",
        "portion_id": "16",
        "page_start": 1,
        "page_end": 1,
        "page_start_original": 1,
        "page_end_original": 1,
        "raw_text": "",
        "raw_html": "",
        "sequence": [
            {
                "kind": "stat_check",
                "stat": "stamina",
                "pass": {"targetSection": "retry instructions (narrative continuation, no exact section)"},
                "fail": {"targetSection": "12"},
            }
        ],
    }
    _, section = build_section(portion, emit_text=False, emit_provenance_text=False)
    seq = section.get("sequence") or []
    stat = seq[0]
    assert "pass" not in stat
    assert stat.get("fail") == {"targetSection": "12"}


def test_combat_outcome_choices_reordered_after_combat():
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
            {"kind": "choice", "targetSection": "76", "choiceText": "Turn to 76"},
            {"kind": "combat", "enemies": [{"enemy": "Grub", "skill": 7, "stamina": 11}],
             "outcomes": {"win": {"targetSection": "76"}, "escape": {"targetSection": "117"}}},
            {"kind": "choice", "targetSection": "117", "choiceText": "Turn to 117"},
        ],
    }
    _, section = build_section(portion, emit_text=False, emit_provenance_text=False)
    seq = section.get("sequence") or []
    assert seq[0].get("kind") == "combat"
    assert len(seq) == 1


def test_normalize_sequence_targets_accepts_continue_terminal():
    portion = {
        "section_id": "2",
        "portion_id": "2",
        "page_start": 1,
        "page_end": 1,
        "page_start_original": 1,
        "page_end_original": 1,
        "raw_text": "",
        "raw_html": "",
        "sequence": [
            {
                "kind": "combat",
                "enemies": [{"enemy": "BEAST", "skill": 7, "stamina": 8}],
                "outcomes": {"win": {"targetSection": "continue"}},
            },
        ],
    }
    _, section = build_section(portion, emit_text=False, emit_provenance_text=False)
    seq = section.get("sequence") or []
    combat = seq[0]
    assert combat.get("outcomes", {}).get("win") == {"terminal": {"kind": "continue", "message": "continue"}}


def test_drop_duplicate_choice_for_combat_outcome():
    portion = {
        "section_id": "10",
        "portion_id": "10",
        "page_start": 1,
        "page_end": 1,
        "page_start_original": 1,
        "page_end_original": 1,
        "raw_text": "",
        "raw_html": "",
        "sequence": [
            {
                "kind": "combat",
                "enemies": [{"enemy": "BEAST", "skill": 7, "stamina": 8}],
                "outcomes": {"win": {"targetSection": "76"}},
            },
            {"kind": "choice", "targetSection": "76", "choiceText": "Turn to 76"},
            {"kind": "choice", "targetSection": "99", "choiceText": "If you flee, turn to 99"},
        ],
    }
    _, section = build_section(portion, emit_text=False, emit_provenance_text=False)
    seq = section.get("sequence") or []
    choices = [e for e in seq if e.get("kind") == "choice"]
    targets = [c.get("targetSection") for c in choices]
    assert "76" not in targets
    assert "99" in targets


def test_drop_duplicate_choices_for_test_luck():
    portion = {
        "section_id": "5",
        "portion_id": "5",
        "page_start": 1,
        "page_end": 1,
        "page_start_original": 1,
        "page_end_original": 1,
        "raw_text": "",
        "raw_html": "",
        "sequence": [
            {"kind": "test_luck", "lucky": {"targetSection": "185"}, "unlucky": {"targetSection": "395"}},
            {"kind": "choice", "targetSection": "185", "choiceText": "Turn to 185"},
            {"kind": "choice", "targetSection": "395", "choiceText": "Turn to 395"},
            {"kind": "choice", "targetSection": "7", "choiceText": "Go back to 7"},
        ],
    }
    _, section = build_section(portion, emit_text=False, emit_provenance_text=False)
    seq = section.get("sequence") or []
    choices = [e for e in seq if e.get("kind") == "choice"]
    targets = [c.get("targetSection") for c in choices]
    assert "185" not in targets
    assert "395" not in targets
    assert "7" in targets


def test_drop_duplicate_choices_for_stat_check():
    portion = {
        "section_id": "6",
        "portion_id": "6",
        "page_start": 1,
        "page_end": 1,
        "page_start_original": 1,
        "page_end_original": 1,
        "raw_text": "",
        "raw_html": "",
        "sequence": [
            {"kind": "stat_check", "stat": "SKILL", "pass": {"targetSection": "10"}, "fail": {"targetSection": "11"}},
            {"kind": "choice", "targetSection": "10", "choiceText": "Turn to 10"},
            {"kind": "choice", "targetSection": "11", "choiceText": "Turn to 11"},
            {"kind": "choice", "targetSection": "12", "choiceText": "Search the room"},
        ],
    }
    _, section = build_section(portion, emit_text=False, emit_provenance_text=False)
    seq = section.get("sequence") or []
    choices = [e for e in seq if e.get("kind") == "choice"]
    targets = [c.get("targetSection") for c in choices]
    assert "10" not in targets
    assert "11" not in targets
    assert "12" in targets
