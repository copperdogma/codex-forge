from modules.transform.extract_combat_styles_frontmatter_v1 import main as styles_mod


def test_fallback_parses_standard_and_vehicle_from_synthetic_frontmatter():
    text = """
    Combat Rules:
    Standard combat uses SKILL for attack strength and STAMINA for damage.
    Vehicle combat uses FIREPOWER against enemy firepower, and armour takes damage.
    Escaping is only possible when explicitly offered.
    """
    styles = styles_mod._fallback_styles_from_text(text)
    assert "standard" in styles
    assert "vehicle" in styles
    assert styles["standard"]["primaryStat"] == "skill"
    assert styles["standard"]["healthStat"] == "stamina"
    assert styles["vehicle"]["primaryStat"] == "firepower"
    assert styles["vehicle"]["healthStat"] == "armour"


def test_fallback_parses_robot_from_synthetic_frontmatter():
    text = """
    Robot combat: add your COMBAT BONUS and SPEED BONUS to your attack strength.
    Armour is reduced when you are hit.
    """
    styles = styles_mod._fallback_styles_from_text(text)
    assert "robot" in styles
    assert styles["robot"]["primaryStat"] == "skill"
    assert styles["robot"]["healthStat"] == "armour"
