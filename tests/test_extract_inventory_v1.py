from modules.enrich.extract_inventory_v1.main import (
    extract_inventory_regex,
    _item_in_choice_prompt,
    _item_only_in_choice_prompt,
    _item_has_explicit_if,
    _keep_removed_item,
    _allow_audit_addition,
)


def test_inventory_check_with_target():
    text = "If you are carrying a pair of stilts, turn to 123. Otherwise, turn to 9."
    inv = extract_inventory_regex(text)
    assert len(inv.inventory_checks) == 1
    check = inv.inventory_checks[0]
    assert check.item == "pair of stilts"
    assert check.target_section == "123"


def test_conditional_use_is_not_consumed():
    text = "If you wish to drink a potion, turn to 10. If you do not, turn to 11."
    inv = extract_inventory_regex(text)
    assert inv.items_used == []


def test_read_message_not_counted_as_use():
    text = "You read the message and then move on."
    inv = extract_inventory_regex(text)
    assert inv.items_used == []


def test_using_other_not_treated_as_item():
    text = "You climb down, using the other to grip your sword."
    inv = extract_inventory_regex(text)
    assert inv.items_used == []


def test_drinkable_water_not_used():
    text = "You crawl along the floor desperately trying to find drinkable water in the pools."
    inv = extract_inventory_regex(text)
    assert inv.items_used == []


def test_pool_not_item():
    text = "You find a pool behind the dead Hobgoblins and take great gulps of the cool water."
    inv = extract_inventory_regex(text)
    assert inv.items_gained == []


def test_goblet_may_be_of_use_cleaned():
    text = "At least the goblet may be of use, so you put it in your backpack."
    inv = extract_inventory_regex(text)
    names = [i.item for i in inv.items_gained]
    assert names == ["goblet"]


def test_lose_grip_not_item_loss():
    text = "The beast slams its body against your arm, and you lose your grip on the rope."
    inv = extract_inventory_regex(text)
    assert inv.items_lost == []


def test_broken_item_not_added():
    text = "Acid has fallen from the broken jug."
    inv = extract_inventory_regex(text)
    assert inv.items_gained == []


def test_take_off_shirt_not_item():
    text = "You take off your shirt and tear it in half."
    inv = extract_inventory_regex(text)
    assert inv.items_gained == []


def test_split_item_list_and_quantity():
    text = "You take two daggers, a mirror and a bone charm."
    inv = extract_inventory_regex(text)
    names = [i.item for i in inv.items_gained]
    assert "daggers" in names
    assert "mirror" in names
    assert "bone charm" in names


def test_truncate_list_on_action_verb():
    text = "You take two daggers and search the backpack."
    inv = extract_inventory_regex(text)
    names = [i.item for i in inv.items_gained]
    assert "daggers" in names
    assert "backpack" not in names


def test_nothing_except_extracts_real_item():
    text = "You find nothing except for an old bone. Turn to 10."
    inv = extract_inventory_regex(text)
    names = [i.item for i in inv.items_gained]
    assert names == ["old bone"]


def test_take_out_of_backpack_not_added():
    text = "You take the bone out of your backpack and throw it down the stairs."
    inv = extract_inventory_regex(text)
    assert inv.items_gained == []
    lost = [i.item for i in inv.items_lost]
    assert "bone" in lost


def test_find_yourself_not_item():
    text = "You climb up and find yourself in a small chamber."
    inv = extract_inventory_regex(text)
    assert inv.items_gained == []


def test_deep_breath_not_item():
    text = "You take a deep breath and dive into the dark pool."
    inv = extract_inventory_regex(text)
    assert inv.items_gained == []


def test_lose_balance_not_item():
    text = "You lose your balance and tumble headlong to the floor."
    inv = extract_inventory_regex(text)
    assert inv.items_lost == []


def test_negative_inventory_check_sets_condition():
    text = "If you do not have a key, turn to 5."
    inv = extract_inventory_regex(text)
    assert len(inv.inventory_checks) == 1
    check = inv.inventory_checks[0]
    assert check.item == "key"
    assert check.condition == "if you do not have"
    assert check.target_section == "5"


def test_have_not_clause_reuses_item():
    text = ("Have you got a hollow wooden tube? If you have, turn to 10. "
            "If you have not, turn to 335.")
    inv = extract_inventory_regex(text)
    checks = inv.inventory_checks
    assert len(checks) == 2
    has = next(c for c in checks if c.condition == "if you have")
    missing = next(c for c in checks if c.condition == "if you do not have")
    assert has.item == "hollow wooden tube"
    assert missing.item == "hollow wooden tube"
    assert has.target_section == "10"
    assert missing.target_section == "335"


def test_have_not_done_so_already_not_item_check():
    text = "If you have not done so already, you may drink from the other fountain."
    inv = extract_inventory_regex(text)
    assert inv.inventory_checks == []


def test_have_not_done_so_already_with_dash_not_item_check():
    text = "If you have not done so already - turn to 41 - or leave the chamber."
    inv = extract_inventory_regex(text)
    assert inv.inventory_checks == []


def test_find_items_not_optional_if_wish():
    text = (
        "Inside you find some unleavened bread, a mirror and a bone charm in the shape of a monkey. "
        "If you wish to eat the bread, turn to 399. "
        "If you would rather just take the mirror and charm and return to the tunnel, turn to 192."
    )
    inv = extract_inventory_regex(text)
    gained = [i.item for i in inv.items_gained]
    assert "unleavened bread" in gained
    assert "mirror" in gained
    assert any("bone charm" in item for item in gained)


def test_item_has_explicit_if_requires_item_after_have():
    text = ("If you have not done so already, you may either eat the rice and drink the water "
            "or leave the hall, taking just the diamond with you.")
    assert _item_has_explicit_if(text, "diamond") is False
    assert _item_has_explicit_if("If you have a lantern, turn to 10.", "lantern") is True


def test_drop_and_grab_throat_only_jug_removed():
    text = "You drop the jug and grab your throat in agony."
    inv = extract_inventory_regex(text)
    names = [i.item for i in inv.items_lost]
    assert names == ["jug"]


def test_find_it_is_not_item():
    text = "As you touch the door handle, you find it is glued to the handle."
    inv = extract_inventory_regex(text)
    assert inv.items_gained == []


def test_take_two_of_her_daggers_cleans_name():
    text = "You take two of her daggers and search her backpack."
    inv = extract_inventory_regex(text)
    names = [i.item for i in inv.items_gained]
    assert "daggers" in names


def test_take_raft_up_river_not_item():
    text = "You take a raft up-river for four days until finally you arrive in Fang."
    inv = extract_inventory_regex(text)
    assert inv.items_gained == []


def test_given_scarf_for_status_not_item():
    text = "You are given a violet scarf to tie around your arm so people recognize your status."
    inv = extract_inventory_regex(text)
    assert inv.items_gained == []


def test_hidden_danger_not_item():
    text = "Although you see no trap, the chest contains a hidden danger."
    inv = extract_inventory_regex(text)
    assert inv.items_gained == []


def test_have_you_drunk_potion_check():
    text = ("Have you drunk a potion found inside a black leather book? If you have, turn to 345. "
            "If you have not drunk it, turn to 372.")
    inv = extract_inventory_regex(text)
    checks = inv.inventory_checks
    assert len(checks) == 2
    has = next(c for c in checks if c.condition == "if you have")
    missing = next(c for c in checks if c.condition == "if you do not have")
    assert has.item.lower() == "potion found inside a black leather book"
    assert missing.item.lower() == "potion found inside a black leather book"
    assert has.target_section == "345"
    assert missing.target_section == "372"


def test_have_not_does_not_create_have_check():
    text = "If you have not seen the spirit girl, turn to 224."
    inv = extract_inventory_regex(text)
    checks = inv.inventory_checks
    assert len(checks) == 1
    assert checks[0].condition == "if you do not have"
    assert checks[0].target_section == "224"


def test_have_you_read_book_details_check():
    text = ("If you have previously read the details about the beast in a leather-bound book, turn to 172. "
            "If you have not read this book, turn to 357.")
    inv = extract_inventory_regex(text)
    checks = inv.inventory_checks
    assert len(checks) == 2
    has = next(c for c in checks if c.condition == "if you have")
    missing = next(c for c in checks if c.condition == "if you do not have")
    assert "book" in has.item.lower()
    assert has.item.lower() == missing.item.lower()
    assert has.target_section == "172"
    assert missing.target_section == "357"


def test_if_you_do_not_infers_missing_check():
    text = "If you have a jug of acid, turn to 303. If you do not, turn to 236."
    inv = extract_inventory_regex(text)
    checks = inv.inventory_checks
    assert len(checks) == 2
    has = next(c for c in checks if c.condition == "if you have")
    missing = next(c for c in checks if c.condition == "if you do not have")
    assert has.item == "jug of acid"
    assert missing.item == "jug of acid"
    assert has.target_section == "303"
    assert missing.target_section == "236"


def test_have_these_items_reuses_name():
    text = ("If you have a coil of rope and a grappling iron, turn to 129. "
            "If you do not have these items, turn to 245.")
    inv = extract_inventory_regex(text)
    checks = inv.inventory_checks
    assert len(checks) == 2
    has = next(c for c in checks if c.condition == "if you have")
    missing = next(c for c in checks if c.condition == "if you do not have")
    assert has.item.lower() == missing.item.lower()
    assert has.target_section == "129"
    assert missing.target_section == "245"


def test_read_this_poem_reuses_name():
    text = ("If you have read the poem written on the skeleton's parchment, turn to 222. "
            "If you have not read this poem, turn to 247.")
    inv = extract_inventory_regex(text)
    checks = inv.inventory_checks
    assert len(checks) == 2
    has = next(c for c in checks if c.condition == "if you have")
    missing = next(c for c in checks if c.condition == "if you do not have")
    assert has.item.lower() == missing.item.lower()
    assert has.target_section == "222"
    assert missing.target_section == "247"


def test_cupboard_contains_items_with_quantity():
    text = "The cupboard contains a wooden mallet and ten iron spikes, which you put in your backpack."
    inv = extract_inventory_regex(text)
    gained = {i.item: i.quantity for i in inv.items_gained}
    assert gained.get("wooden mallet") == 1
    assert gained.get("iron spikes") == 10


def test_which_you_put_removed_from_item_name():
    text = "The chest contains a silver goblet, which you put in your backpack."
    inv = extract_inventory_regex(text)
    names = [i.item for i in inv.items_gained]
    assert "silver goblet" in names
    assert all("which you put" not in n for n in names)


def test_put_it_in_backpack_resolves_previous_item():
    text = ("You prise loose the idol's emerald eye with your blade. "
            "Once it comes free, you put it in your backpack.")
    inv = extract_inventory_regex(text)
    names = [i.item for i in inv.items_gained]
    assert "emerald eye" in names


def test_rope_up_again_cleaned():
    text = "You quickly coil the rope up again and put it in your backpack."
    inv = extract_inventory_regex(text)
    names = [i.item for i in inv.items_gained]
    assert "rope" in names


def test_find_crack_not_item():
    text = "You find an almost invisible crack in the arm, which you start to press and squeeze."
    inv = extract_inventory_regex(text)
    assert inv.items_gained == []


def test_audit_addition_requires_add_verb():
    text = "The mirror shimmers in the wall."
    assert _allow_audit_addition(text, "mirror") is False
    text2 = "You find a mirror on the floor and put it in your backpack."
    assert _allow_audit_addition(text2, "mirror") is True


def test_choice_prompt_not_item_use_or_check():
    text = "Eat the dried meat? Turn to 226. Leave the meat? Turn to 41."
    inv = extract_inventory_regex(text)
    assert inv.items_used == []
    assert inv.inventory_checks == []
    assert _item_in_choice_prompt(text, "dried meat") is True
    assert _item_has_explicit_if(text, "dried meat") is False


def test_choice_prompt_with_narrative_gain():
    text = "You find a rope. If you wish to take the rope, turn to 208."
    inv = extract_inventory_regex(text)
    assert inv.items_gained == []


def test_choice_prompt_keeps_narrative_item():
    text = "You find a loaf of bread in the backpack. If you want to eat the bread, turn to 399."
    inv = extract_inventory_regex(text)
    names = [i.item for i in inv.items_gained]
    assert any("bread" in name for name in names)
    assert _item_only_in_choice_prompt(text, "bread") is False


def test_keep_removed_item_add_guard():
    text = "You find a rope and pick it up before moving on."
    assert _keep_removed_item(text, "rope", "add") is True
    text = "You find a rope. If you wish to take the rope, turn to 208."
    assert _keep_removed_item(text, "rope", "add") is True


def test_choice_only_item_not_added():
    text = "If you want the rope, turn to 208."
    inv = extract_inventory_regex(text)
    assert inv.items_gained == []


def test_optional_if_wish_not_unconditional_gain():
    text = "You find nothing except for an old bone, taking it with you if you wish."
    inv = extract_inventory_regex(text)
    assert inv.items_gained == []


def test_seize_dagger_adds_item():
    text = "You lean over the pit and seize the dagger by the hilt."
    inv = extract_inventory_regex(text)
    names = [i.item for i in inv.items_gained]
    assert "dagger" in names


def test_put_pearl_in_pocket_adds_item():
    text = "After putting the pearl in your pocket, you press on."
    inv = extract_inventory_regex(text)
    names = [i.item for i in inv.items_gained]
    assert "pearl" in names


def test_put_them_in_backpack_extracts_eyes():
    text = ("You recognize the yellow jewelled eyes as topaz. "
            "You pluck them from their sockets and put them in your backpack.")
    inv = extract_inventory_regex(text)
    names = [i.item for i in inv.items_gained]
    assert any("eyes" in name for name in names)
    assert not any(name.lower().startswith("you recognize") for name in names)


def test_choice_prompt_not_item_remove():
    text = "Eat the rice and drink the water - turn to 330."
    inv = extract_inventory_regex(text)
    assert inv.items_lost == []
