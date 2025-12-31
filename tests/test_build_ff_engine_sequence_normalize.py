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
    assert seq[1].get("kind") == "choice"
    assert seq[2].get("kind") == "choice"
