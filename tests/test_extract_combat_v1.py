from modules.enrich.extract_combat_v1.main import extract_combat_regex


def test_combat_escape_and_special_rules():
    text = (
        "A BEAST attacks! BEAST SKILL 7 STAMINA 8. "
        "If you escape by running west, turn to 12. "
        "Reduce your SKILL by 2 during this combat."
    )
    combats = extract_combat_regex(text)
    assert len(combats) == 1
    combat = combats[0]
    assert combat.escape_section == "12"
    assert combat.special_rules is not None
