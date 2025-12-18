import pytest


from modules.extract.extract_ocr_ensemble_v1.main import (
    fuse_characters,
    repair_turn_to_phrases,
    _choose_fused_line,
)


def test_repair_turn_to_phrases_fixes_tum_to_number_preserves_case():
    lines = [
        "Tum to 16",
        "If you win, tum to 364.",
        "TURN TO 12",
        "I'll tum",  # should not change (no numeric target)
        "Return to 12",  # should not change
    ]
    out, repairs = repair_turn_to_phrases(lines)
    assert out[0] == "Turn to 16"
    assert out[1] == "If you win, turn to 364."
    assert out[2] == "TURN TO 12"
    assert out[3] == "I'll tum"
    assert out[4] == "Return to 12"
    assert len(repairs) == 2
    assert repairs[0]["reason"] == "turn_to_phrase_repair"


def test_repair_turn_to_phrases_fixes_t0_to_to_when_followed_by_number():
    lines = [
        "Turn t0 157",
        "turn tO 66",
        "turn to 66",  # should not change
    ]
    out, repairs = repair_turn_to_phrases(lines)
    assert out[0] == "Turn to 157"
    assert out[1] == "turn to 66"
    assert out[2] == "turn to 66"
    assert len(repairs) == 2


def test_fuse_characters_dictionary_tiebreak_fixes_skilI_to_skill():
    assert fuse_characters("skilI", "skill", enable_dict_tiebreak=True) == "skill"


def test_fuse_characters_dictionary_tiebreak_does_not_break_titlecase_proper_noun():
    # Avoid "Iain" -> "lain" style regressions.
    assert fuse_characters("Iain", "lain", enable_dict_tiebreak=True) == "Iain"


def test_choose_fused_line_never_returns_non_string_source():
    row = {
        "tesseract": {"text": "Turn to 250", "conf": 0.95},
        "apple": {"text": "Turn to 250", "conf": 1.0},
        "pdftext": {"text": "Turn to 250", "conf": None},
    }
    txt, src, dist = _choose_fused_line(
        row,
        distance_drop=0.35,
        enable_char_fusion=True,
        enable_spell_weighted_voting=True,
    )
    assert isinstance(src, str)
    assert txt == "Turn to 250"
    assert 0.0 <= dist <= 1.0
