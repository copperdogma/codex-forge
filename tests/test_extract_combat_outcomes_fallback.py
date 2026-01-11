from modules.enrich.extract_combat_v1.main import _merge_fallback_outcomes
from modules.enrich.extract_combat_v1.main import _normalize_outcome_ref
from modules.enrich.extract_combat_v1.main import _coerce_conditional_outcomes
from modules.enrich.extract_combat_v1.main import _detect_outcomes


def test_conditional_outcomes_prefers_fallback():
    outcomes = {
        "win": {
            "conditions": [
                {"condition": "If you have armour left", "targetSection": "354"},
                {"condition": "If armour reduced to zero", "targetSection": "6"},
            ]
        }
    }
    fallback = {
        "win": {"targetSection": "354"},
        "lose": {"targetSection": "6"},
    }
    merged = _merge_fallback_outcomes(outcomes, fallback)
    assert merged == fallback


def test_terminal_outcome_filters_invalid_kind():
    bad = _normalize_outcome_ref({"terminal": {"kind": "not allowed"}})
    assert bad is None


def test_coerce_conditional_outcomes_from_armour_conditions():
    outcomes = {
        "win": {
            "conditional": [
                {"condition": "If you have some ARMOUR points left", "targetSection": "354"},
                {"condition": "If your ARMOUR is reduced to zero", "targetSection": "6"},
            ]
        }
    }
    coerced = _coerce_conditional_outcomes(outcomes)
    assert coerced == {
        "win": {"targetSection": "354"},
        "lose": {"targetSection": "6"},
    }


def test_detect_outcomes_armour_reduced_to_zero():
    text = (
        "If you defeat the beast and have some armour left, turn to 120. "
        "If your armour is reduced to zero, turn to 9."
    )
    win, lose, escape = _detect_outcomes(text)
    assert win == "120"
    assert lose == "9"
    assert escape is None
