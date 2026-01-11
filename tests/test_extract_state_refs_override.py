from modules.enrich.extract_state_refs_v1.main import _extract_state_refs


def test_map_ref_override_replaces_ambiguous_value():
    text = "The map reference is 2X. Make a note of this number."
    values, _ = _extract_state_refs(text, map_ref_override="22")
    assert any(v.get("key").startswith("map_reference") and v.get("value") == "22" for v in values)
