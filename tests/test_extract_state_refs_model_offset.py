from modules.enrich.extract_state_refs_v1 import main as extract_state_refs


def _extract(text: str):
    values, checks = extract_state_refs._extract_state_refs(text)
    return values, checks


def test_model_number_value_extracts_generic_and_specific_key():
    text = (
        "You leave in disgust. But, as you do, you notice a plaque by the door. "
        "It reads, in part, 'Cloak of Invisibility' device, Model 3, now being tested."
    )
    values, _ = _extract(text)
    keys = {(v.get("key"), v.get("value")) for v in values}
    assert ("model_number", "3") in keys
    assert ("model_number_cloak_of_invisibility", "3") in keys


def test_model_number_add_offset_check():
    text = (
        "If you know what you might find in this building, add 50 to its model number "
        "and turn to that paragraph."
    )
    _, checks = _extract(text)
    assert any(
        c.get("key") == "model_number"
        and c.get("template_target") == "{state}"
        and c.get("template_op") == "add"
        and c.get("template_value") == "50"
        for c in checks
    )
