from modules.enrich.extract_combat_v1 import main as extract_combat
from modules.common.combat_styles import collect_combat_styles, resolve_combat_styles


def test_infer_vehicle_style_from_stats():
    enemies = [extract_combat.CombatEnemy(enemy="Road Raider", firepower=9, armour=12)]
    style = extract_combat._infer_combat_style("Vehicle Combat between cars.", enemies)
    assert style == "vehicle"


def test_infer_robot_style_from_stats():
    enemies = [extract_combat.CombatEnemy(enemy="Robot Guard", skill=8, armour=10, speed="Fast")]
    style = extract_combat._infer_combat_style("Robot combat rules apply.", enemies)
    assert style == "robot"


def test_infer_shooting_style_from_text():
    enemies = [extract_combat.CombatEnemy(enemy="Bandit", skill=6, stamina=5)]
    style = extract_combat._infer_combat_style("You draw your gun and shoot.", enemies)
    assert style == "shooting"


def test_infer_hand_style_from_text():
    enemies = [extract_combat.CombatEnemy(enemy="Thug", skill=6, stamina=5)]
    style = extract_combat._infer_combat_style("Hand-to-hand fighting begins.", enemies)
    assert style == "hand"


def test_collect_combat_styles_from_sections():
    sections = {
        "1": {"sequence": [{"kind": "combat", "style": "robot", "enemies": []}]},
        "2": {"sequence": [{"kind": "combat", "enemies": []}]},
    }
    styles = collect_combat_styles(sections)
    resolved = resolve_combat_styles(styles)
    assert "robot" in resolved
    assert "standard" in resolved
