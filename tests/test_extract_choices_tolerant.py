from modules.extract.extract_choices_v1.main import extract_choice_patterns


def test_extract_choices_tolerates_tum_t0_and_digit_confusions():
    text = "If you win, Tum t0 1S7. Otherwise, turn tO 66."
    cands = extract_choice_patterns(text, min_section=1, max_section=400)
    targets = sorted({c.target for c in cands})
    assert targets == [66, 157]


def test_extract_choices_does_not_match_unrelated_tum():
    text = "I'll tum around now. This is not an instruction."
    cands = extract_choice_patterns(text, min_section=1, max_section=400)
    assert cands == []

