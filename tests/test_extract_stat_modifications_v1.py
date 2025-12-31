from modules.enrich.extract_stat_modifications_v1.main import extract_stat_modifications_regex, _build_audit_maps


def test_combat_modifier_not_stat_change():
    text = "During each Attack Round you must reduce your Attack Strength by 2 because of your condition."
    mods = extract_stat_modifications_regex(text)
    assert mods == []


def test_roll_dice_each_loss_expression():
    text = "Roll two dice for the number of splinters. Each one reduces your STAMINA by one point."
    mods = extract_stat_modifications_regex(text)
    assert any(m.stat == "stamina" and m.amount == "-(2d6)" for m in mods)


def test_roll_die_per_spike_expression():
    text = "Roll one die. Lose 2 STAMINA points for each spike."
    mods = extract_stat_modifications_regex(text)
    assert any(m.stat == "stamina" and m.amount == "-(1d6*2)" for m in mods)
    assert not any(m.stat == "stamina" and m.amount == -2 for m in mods)


def test_roll_die_add_total_each_loss_expression():
    text = ("Roll one die and add 2 to the total. This is the number of stings you "
            "have suffered and you must reduce your STAMINA by 1 for each sting.")
    mods = extract_stat_modifications_regex(text)
    assert any(m.stat == "stamina" and m.amount == "-(1d6+2)" for m in mods)
    assert not any(m.stat == "stamina" and m.amount == -1 for m in mods)


def test_roll_die_add_number_reduce_by_total():
    text = ("Roll one die, add 1 to the number and reduce your STAMINA by the total. "
            "If you are still alive, turn to 10.")
    mods = extract_stat_modifications_regex(text)
    assert any(m.stat == "stamina" and m.amount == "-(1d6+1)" for m in mods)


def test_roll_die_deduct_number_from_stamina():
    text = "Roll one die and deduct the number from your STAMINA score."
    mods = extract_stat_modifications_regex(text)
    assert any(m.stat == "stamina" and m.amount == "-(1d6)" for m in mods)


def test_combat_duration_modifier_not_stat_change():
    text = "You must fight bare-handed, reducing your SKILL by 4 for the duration of the combat."
    mods = extract_stat_modifications_regex(text)
    assert mods == []


def test_add_to_each_stat_scores():
    text = "Add 1 to each of your SKILL, STAMINA and LUCK scores."
    mods = extract_stat_modifications_regex(text)
    stats = {(m.stat, m.amount) for m in mods}
    assert ("skill", 1) in stats
    assert ("stamina", 1) in stats
    assert ("luck", 1) in stats


def test_audit_maps_skip_missing_item_index():
    removals = [{"section_id": "10", "item_index": None}]
    corrections = [{"section_id": "10", "item_index": None, "data": {"stat": "stamina", "amount": -1}}]
    additions = [{"section_id": "10", "data": {"stat": "luck", "amount": 1}}]
    removals_map, corrections_map, additions_map = _build_audit_maps(removals, corrections, additions)
    assert removals_map == {}
    assert corrections_map == {}
    assert additions_map == {"10": [{"stat": "luck", "amount": 1}]}
