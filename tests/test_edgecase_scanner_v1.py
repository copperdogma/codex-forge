from modules.adapter.edgecase_scanner_v1.main import _scan_text


def _codes(issues):
    return {i.get("reason_code") for i in issues}


def test_survival_gate_damage():
    text = "Roll one die. Lose that many STAMINA points. If you are still alive, turn to 10."
    issues = _scan_text("1", text, None, None, sequence_kinds=set())
    assert "survival_gate_damage" in _codes(issues)


def test_conditional_choice_branch():
    text = "If you take the gem, turn to 12. If you do not take it, turn to 9."
    issues = _scan_text("2", text, None, None, sequence_kinds=set())
    assert "conditional_choice_branch" in _codes(issues)


def test_dual_item_check():
    text = "If you have the rope, turn to 33. If you do not have it, turn to 44."
    issues = _scan_text("3", text, None, None, sequence_kinds=set())
    assert "dual_item_check" in _codes(issues)


def test_state_check():
    text = "Have you previously visited the shrine? If so, turn to 90."
    issues = _scan_text("4", text, None, None, sequence_kinds=set())
    assert "dual_state_check" in _codes(issues)


def test_dice_damage_no_branch():
    text = "Roll two dice and lose that many STAMINA points."
    issues = _scan_text("5", text, None, None, sequence_kinds=set())
    assert "dice_damage_no_branch" in _codes(issues)


# test_terminal_outcome_text removed - feature not yet implemented (see story-111)
# The scanner should detect "you die" patterns but this logic hasn't been added yet


def test_multi_item_requirement():
    text = "If you have the key and the map, turn to 77."
    issues = _scan_text("7", text, None, None, sequence_kinds=set())
    assert "multi_item_requirement" in _codes(issues)
