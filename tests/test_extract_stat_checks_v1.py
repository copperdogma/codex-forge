from modules.enrich.extract_stat_checks_v1.main import extract_stat_checks_regex, ensure_test_luck


def test_roll_vs_skill_check_extracted():
    text = (
        "Roll two dice. If the total is the same as or less than your SKILL, "
        "turn to 10. If the total is greater than your SKILL, turn to 20."
    )
    checks, luck = extract_stat_checks_regex(text)
    assert luck == []
    assert len(checks) == 1
    check = checks[0]
    assert check.stat == "SKILL"
    assert check.pass_section == "10"
    assert check.fail_section == "20"
    assert check.dice_roll == "2d6"


def test_filter_stat_check_without_roll():
    text = "During combat reduce your attack strength by 2. If you win, turn to 10."
    checks, luck = extract_stat_checks_regex(text)
    assert checks == []


def test_ensure_test_luck_recovers_missing():
    text = "Test your Luck. If you are Lucky, turn to 97. If you are Unlucky, turn to 21."
    luck = ensure_test_luck(text, [])
    assert len(luck) == 1
    assert luck[0].lucky_section == "97"
    assert luck[0].unlucky_section == "21"


def test_ensure_test_luck_falls_back_to_two_numbers_near_turn_to():
    text = "Test your Luck. If you are Lucky, turn to 97 21."
    luck = ensure_test_luck(text, [])
    assert len(luck) == 1
    assert luck[0].lucky_section == "97"
    assert luck[0].unlucky_section == "21"
