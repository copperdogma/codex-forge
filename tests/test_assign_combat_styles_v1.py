from modules.transform.assign_combat_styles_v1.main import _pick_style


def test_pick_style_prefers_shooting_combat_phrase():
    styles = {
        "standard": {"id": "standard", "primaryStat": "skill", "healthStat": "stamina", "default": True},
        "shooting": {"id": "shooting", "primaryStat": "skill", "healthStat": "stamina"},
    }
    text = "During this Shooting Combat, both outlaws fire first."
    assert _pick_style(styles, "skill", "stamina", text) == "shooting"

