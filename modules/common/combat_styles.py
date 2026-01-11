from typing import Any, Dict, Iterable, Set


COMBAT_STYLE_DEFS: Dict[str, Dict[str, Any]] = {
    "standard": {
        "id": "standard",
        "name": "Standard Combat",
        "primaryStat": "skill",
        "healthStat": "stamina",
        "default": True,
        "attackStrength": {
            "attacker": "2d6 + SKILL",
            "defender": "2d6 + ENEMY_SKILL",
        },
        "damage": {
            "stat": "stamina",
            "amount": 2,
        },
        "endCondition": {
            "stat": "stamina",
            "threshold": 0,
        },
        "escape": {
            "requires": "page_option",
            "damage": {"stat": "stamina", "amount": 2},
        },
        "notes": [
            "Luck can modify damage on a wound.",
        ],
        "keywords": [
            "combat",
            "attack strength",
            "skill",
            "stamina",
        ],
    },
    "hand": {
        "id": "hand",
        "name": "Hand Fighting",
        "primaryStat": "skill",
        "healthStat": "stamina",
        "attackStrength": {
            "attacker": "2d6 + SKILL",
            "defender": "2d6 + ENEMY_SKILL",
        },
        "damage": {
            "stat": "stamina",
            "amount": "weapon-dependent (bare hands: 1; weapons vary)",
        },
        "endCondition": {
            "stat": "stamina",
            "threshold": 0,
        },
        "notes": [
            "Hand Fighting: deduct injury from STAMINA. Bare hands usually -1; weapons vary (book rules).",
        ],
        "keywords": [
            "hand",
            "hand fighting",
            "bare hands",
        ],
    },
    "shooting": {
        "id": "shooting",
        "name": "Shooting",
        "primaryStat": "skill",
        "healthStat": "stamina",
        "attackStrength": {
            "attacker": "2d6 + SKILL",
            "defender": "2d6 + ENEMY_SKILL",
        },
        "damage": {
            "stat": "stamina",
            "amount": "1d6",
        },
        "endCondition": {
            "stat": "stamina",
            "threshold": 0,
        },
        "keywords": [
            "shooting",
            "shoot",
            "gun",
        ],
    },
    "robot": {
        "id": "robot",
        "name": "Robot Combat",
        "primaryStat": "skill",
        "healthStat": "armour",
        "attackStrength": {
            "attacker": "2d6 + SKILL + COMBAT_BONUS + SPEED_BONUS",
            "defender": "2d6 + ENEMY_SKILL + SPEED_BONUS",
        },
        "damage": {
            "stat": "armour",
            "amount": 2,
        },
        "endCondition": {
            "stat": "armour",
            "threshold": 0,
        },
        "escape": {
            "requires": "faster_robot_and_page_option",
            "damage": {"stat": "armour", "amount": 2},
        },
        "notes": [
            "If your robot is destroyed, you are not necessarily dead.",
        ],
        "keywords": [
            "robot",
            "armour",
            "combat bonus",
            "speed",
        ],
    },
    "vehicle": {
        "id": "vehicle",
        "name": "Vehicle Combat",
        "primaryStat": "firepower",
        "healthStat": "armour",
        "attackStrength": {
            "attacker": "2d6 + FIREPOWER",
            "defender": "2d6 + ENEMY_FIREPOWER",
        },
        "damage": {
            "stat": "armour",
            "amount": "1d6",
        },
        "endCondition": {
            "stat": "armour",
            "threshold": 0,
        },
        "special": [
            "Rocket launch: auto-hit, target destroyed.",
        ],
        "keywords": [
            "vehicle",
            "firepower",
            "armour",
            "road",
        ],
    },
}


def collect_combat_styles(sections: Dict[str, Dict[str, Any]]) -> Set[str]:
    styles: Set[str] = set()
    has_combat_without_style = False
    for section in sections.values():
        for event in section.get("sequence") or []:
            if not isinstance(event, dict):
                continue
            if event.get("kind") != "combat":
                continue
            style = event.get("style")
            if style:
                styles.add(str(style))
            else:
                has_combat_without_style = True
    if has_combat_without_style:
        styles.add("standard")
    return styles


def resolve_combat_styles(styles_in_use: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    resolved: Dict[str, Dict[str, Any]] = {}
    for style in styles_in_use:
        key = str(style)
        if key in COMBAT_STYLE_DEFS:
            resolved[key] = COMBAT_STYLE_DEFS[key]
    return resolved
