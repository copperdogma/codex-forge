from modules.enrich.extract_state_refs_v1.main import _extract_state_refs


def _find_state_value(state_values, key, value):
    return any(v.get("key") == key and v.get("value") == value for v in state_values)


def _find_state_check(state_checks, key, template_target=None, missing_target=None, choice_text_contains=None):
    for check in state_checks:
        if check.get("key") != key:
            continue
        if template_target is not None and check.get("template_target") != template_target:
            continue
        if missing_target is not None and check.get("missing_target") != missing_target:
            continue
        if choice_text_contains:
            choice_text = check.get("choice_text") or ""
            if choice_text_contains not in choice_text:
                continue
        return True
    return False


def test_map_reference_value_extraction():
    text = (
        "The map reference is 2X. Make a note of this number. "
        "Substitute it for XX when you are given the option to visit the City of the Guardians."
    )
    values, checks = _extract_state_refs(text)
    assert _find_state_value(values, "map_reference_city_of_the_guardians", "2X")
    assert values


def test_placeholder_turn_to_extraction():
    text = (
        "The City of the Guardians? Turn to 1XX. "
        "Note that you may not go to the City of the Guardians unless you know the numbers."
    )
    values, checks = _extract_state_refs(text)
    assert _find_state_check(
        checks,
        "map_reference_city_of_the_guardians",
        template_target="1{state}",
        choice_text_contains="City of the Guardians",
    )


def test_map_reference_state_check_with_missing_target():
    text = (
        "If you have read a military volume on the City of the Guardians, "
        "turn to the map reference you were given there. "
        "If you have not read this volume, turn to 218."
    )
    values, checks = _extract_state_refs(text)
    assert _find_state_check(
        checks,
        "map_reference_city_of_the_guardians",
        template_target="{state}",
        missing_target="218",
    )


def test_countersign_state_extraction():
    text = (
        "'Eighty-eight!' you bark at the Karosseans. 'Seven!' they reply to you. "
        "Aha! You have learned the countersign to their password! "
        "If you know the countersign, turn to that number. If not, turn to 50."
    )
    values, checks = _extract_state_refs(text)
    assert _find_state_value(values, "countersign_eighty_eight", "7")
    assert _find_state_check(
        checks,
        "countersign_eighty_eight",
        template_target="{state}",
        missing_target="50",
    )


def test_flask_letter_count_state():
    text = (
        "You have a flask of Blue Potion. "
        "If you have a flask of liquid in your possession, count the letters in both words of its name, "
        "multiply that number by 10, and turn to that reference. If you have no flask, turn to 166."
    )
    values, checks = _extract_state_refs(text)
    assert _find_state_value(values, "flask_letter_count", "10")
    assert _find_state_check(
        checks,
        "flask_letter_count",
        template_target="{state}0",
        missing_target="166",
    )


def test_reference_number_state():
    text = (
        "The reference number of the book is 111. Make a note of this and turn to 224. "
        "If you know something that might help you now, turn to the reference number that came with that information. "
        "Otherwise, turn to 228."
    )
    values, checks = _extract_state_refs(text)
    assert _find_state_value(values, "reference_number", "111")
    assert _find_state_check(
        checks,
        "reference_number",
        template_target="{state}",
        missing_target="228",
    )


def test_model_number_state():
    text = (
        "You sit down in the seat. Instantly, you find yourself at the controls of a sleek fighter - the experimental Wasp 200! "
        "If you know the Wasp Fighter's model number, turn to that reference number. If not, turn to 23."
    )
    values, checks = _extract_state_refs(text)
    assert _find_state_value(values, "model_number_wasp_fighter", "200")
    assert _find_state_check(
        checks,
        "model_number_wasp_fighter",
        template_target="{state}",
        missing_target="23",
    )
