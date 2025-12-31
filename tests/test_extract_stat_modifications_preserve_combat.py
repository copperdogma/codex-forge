from schemas import EnrichedPortion
from modules.enrich.extract_stat_modifications_v1.main import _preserve_combat_special_rules


def test_preserve_combat_special_rules_from_raw_row():
    raw_row = {
        "portion_id": "1",
        "page_start": 1,
        "page_end": 1,
        "combat": [
            {
                "enemy": "DWARF",
                "skill": 8,
                "stamina": 6,
                "win_section": "28",
                "special_rules": "reduce your Attack Strength by 2",
            }
        ],
    }
    portion = EnrichedPortion(**raw_row)
    portion.combat[0].special_rules = None
    _preserve_combat_special_rules(portion, raw_row)
    assert portion.combat[0].special_rules == "reduce your Attack Strength by 2"
