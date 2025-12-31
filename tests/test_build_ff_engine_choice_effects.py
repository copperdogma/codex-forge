from modules.export.build_ff_engine_v1.main import make_sequence, build_section


def test_choice_effects_add_item():
    portion = {
        "choices": [
            {"target": "12", "text": "If you take the rope, turn to 12."}
        ],
        "raw_html": "",
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") == [{"kind": "item", "action": "add", "name": "rope"}]


def test_choice_effects_remove_item():
    portion = {
        "choices": [
            {"target": "99", "text": "Eat the bread and turn to 99."}
        ],
        "raw_html": "",
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") == [{"kind": "item", "action": "remove", "name": "bread"}]


def test_choice_effects_ignore_liquid():
    portion = {
        "choices": [
            {"target": "158", "text": "Turn to 158"}
        ],
        "raw_html": "If you wish to drink some of the liquid, turn to <a href=\"#158\"> 158 </a>.",
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") is None


def test_choice_effects_clean_drink_water():
    portion = {
        "choices": [
            {"target": "330", "text": "Turn to 330"}
        ],
        "raw_html": "Eat the rice and drink the water - turn to <a href=\"#330\"> 330 </a>.",
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") == [
        {"kind": "item", "action": "remove", "name": "rice"},
        {"kind": "item", "action": "remove", "name": "water"},
    ]


def test_choice_effects_from_html_context():
    portion = {
        "choices": [
            {"target": "399", "text": "Turn to 399"}
        ],
        "raw_html": "If you wish to eat the bread, turn to <a href=\"#399\"> 399 </a>.",
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") == [{"kind": "item", "action": "remove", "name": "bread"}]


def test_choice_effects_avoid_take_on_shape():
    portion = {
        "choices": [
            {"target": "188", "text": "Turn to 188"}
        ],
        "raw_html": ("You find a glass phial. This liquid will make your body take on the shape of any nearby being. "
                     "Turn to <a href=\"#188\"> 188 </a>."),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") is None


def test_choice_effects_drop_later_phrase():
    portion = {
        "choices": [
            {"target": "140", "text": "Turn to 140"}
        ],
        "raw_html": ("Hoping that it may be of use later, you put it in your backpack. "
                     "If you now wish to prise out the right eye, turn to <a href=\"#140\"> 140 </a>."),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") is None


def test_choice_effects_ignore_accept_offer():
    portion = {
        "choices": [
            {"target": "63", "text": "Accept the Barbarian's offer? Turn to 63."}
        ],
        "raw_html": "",
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") is None


def test_choice_effects_ignore_take_part():
    portion = {
        "choices": [
            {"target": "343", "text": "Turn to 343"}
        ],
        "raw_html": "If you are willing to take part in the Run of the Arrow, turn to <a href=\"#343\"> 343 </a>.",
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") is None


def test_choice_effects_clean_necklace_yourself():
    portion = {
        "choices": [
            {"target": "123", "text": "Turn to 123"}
        ],
        "raw_html": "If you wish to wear the necklace yourself, turn to <a href=\"#123\"> 123 </a>.",
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") == [{"kind": "item", "action": "add", "name": "necklace"}]


def test_choice_effects_paragraph_scoped():
    portion = {
        "choices": [
            {"target": "367", "text": "Turn to 367"},
            {"target": "38", "text": "Turn to 38"},
            {"target": "169", "text": "Turn to 169"},
        ],
        "raw_html": (
            "<p>Talk to him? <a href=\"#367\"> Turn to 367 </a></p>"
            "<p>Take the bread and water off his tray? <a href=\"#38\"> Turn to 38 </a></p>"
            "<p>Offer him some of your provisions (if you have any left)? <a href=\"#169\"> Turn to 169 </a></p>"
        ),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
        "section_id": "1",
        "portion_id": "1",
        "page_start": 1,
        "page_end": 1,
        "page_start_original": 1,
        "page_end_original": 1,
        "raw_text": "",
    }
    _, section = build_section(portion, emit_text=False, emit_provenance_text=False)
    seq = section.get("sequence") or []
    choice_367 = next(e for e in seq if e.get("kind") == "choice" and e.get("targetSection") == "367")
    choice_38 = next(e for e in seq if e.get("kind") == "choice" and e.get("targetSection") == "38")
    choice_169 = next(e for e in seq if e.get("kind") == "choice" and e.get("targetSection") == "169")
    assert choice_367.get("effects") is None
    assert choice_169.get("effects") is None
    assert choice_38.get("effects") == [
        {"kind": "item", "action": "add", "name": "bread"},
        {"kind": "item", "action": "add", "name": "water"},
    ]


def test_optional_take_keeps_container_finds():
    portion = {
        "sequence": [
            {"kind": "item", "action": "add", "name": "unleavened bread"},
            {"kind": "item", "action": "add", "name": "mirror"},
            {"kind": "item", "action": "add", "name": "bone charm in the shape of a monkey"},
            {"kind": "choice", "targetSection": "399", "choiceText": "Turn to 399"},
            {"kind": "choice", "targetSection": "192", "choiceText": "Turn to 192"},
        ],
        "raw_html": (
            "<p>Inside you find some unleavened bread, a mirror and a bone charm in the shape of a monkey. "
            "If you wish to eat the bread, turn to <a href=\"#399\"> 399 </a>. "
            "If you would rather just take the mirror and charm and return, turn to <a href=\"#192\"> 192 </a>.</p>"
        ),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
        "section_id": "1",
        "portion_id": "1",
        "page_start": 1,
        "page_end": 1,
        "page_start_original": 1,
        "page_end_original": 1,
        "raw_text": "",
    }
    _, section = build_section(portion, emit_text=False, emit_provenance_text=False)
    seq = section.get("sequence") or []
    added = [e.get("name") for e in seq if e.get("kind") == "item" and e.get("action") == "add"]
    assert "mirror" in [a.lower() for a in added]
    assert any("bone charm" in a.lower() for a in added)
    choice_192 = next(e for e in seq if e.get("kind") == "choice" and e.get("targetSection") == "192")
    assert choice_192.get("effects") is None


def test_choice_effects_ignore_running_jump():
    portion = {
        "choices": [
            {"target": "285", "text": "Turn to 285"}
        ],
        "raw_html": (
            "You step back to take a running jump. If you are still alive, turn to "
            "<a href=\"#285\"> 285 </a>."
        ),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") is None


def test_choice_effects_ignore_grab_throat():
    portion = {
        "choices": [
            {"target": "275", "text": "Turn to 275"}
        ],
        "raw_html": (
            "You drop the jug and grab your throat in agony. If you are still alive, "
            "turn to <a href=\"#275\"> 275 </a>."
        ),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") is None


def test_choice_effects_ignore_gulps_water():
    portion = {
        "choices": [
            {"target": "110", "text": "Turn to 110"}
        ],
        "raw_html": (
            "You take great gulps of the cool water as fast as you can. "
            "Turn to <a href=\"#110\"> 110 </a>."
        ),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") is None


def test_choice_effects_ignore_take_gift():
    portion = {
        "choices": [
            {"target": "344", "text": "Turn to 344"}
        ],
        "raw_html": (
            "Take this gift to help you. It will grant you one wish. "
            "Turn to <a href=\"#344\"> 344 </a>."
        ),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") is None


def test_choice_effects_taking_with_you():
    portion = {
        "choices": [
            {"target": "74", "text": "Turn to 74"}
        ],
        "raw_html": "Close the door and continue west, taking the wooden balls with you? Turn to <a href=\"#74\"> 74 </a>.",
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") == [{"kind": "item", "action": "add", "name": "wooden balls"}]


def test_optional_take_moves_item_to_choice():
    portion = {
        "choices": [
            {"target": "208", "text": "Turn to 208"},
            {"target": "326", "text": "Turn to 326"},
        ],
        "raw_html": ("On the opposite wall there are two iron hooks, on one of which hangs a coil of rope. "
                     "If you wish to open the door, jump over the pit and take the rope, turn to <a href=\"#208\"> 208 </a>. "
                     "If you would rather continue north, turn to <a href=\"#326\"> 326 </a>."),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [{"action": "add", "name": "Rope"}],
        "combat": [],
        "deathConditions": [],
    }
    portion = {
        **portion,
        "section_id": "1",
        "portion_id": "1",
        "page_start": 1,
        "page_end": 1,
        "page_start_original": 1,
        "page_end_original": 1,
        "raw_text": "",
    }
    _, section = build_section(portion, emit_text=False, emit_provenance_text=False)
    seq = section.get("sequence") or []
    assert not any(e.get("kind") == "item" and e.get("action") == "add" and e.get("name") == "Rope" for e in seq)
    choice = next(e for e in seq if e.get("kind") == "choice" and e.get("targetSection") == "208")
    assert choice.get("effects") is None
    other = next(e for e in seq if e.get("kind") == "choice" and e.get("targetSection") == "326")
    assert other.get("effects") is None


def test_optional_take_negative_choice_has_no_effects():
    portion = {
        "choices": [
            {"target": "331", "text": "Turn to 331"},
            {"target": "128", "text": "Turn to 128"},
        ],
        "raw_html": ("If you wish to take the parchment, turn to <a href=\"#331\"> 331 </a>. "
                     "If you do not wish to take the parchment, turn to <a href=\"#128\"> 128 </a>."),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    portion = {
        **portion,
        "section_id": "1",
        "portion_id": "1",
        "page_start": 1,
        "page_end": 1,
        "page_start_original": 1,
        "page_end_original": 1,
        "raw_text": "",
    }
    _, section = build_section(portion, emit_text=False, emit_provenance_text=False)
    seq = section.get("sequence") or []
    for ev in seq:
        if ev.get("kind") == "choice":
            assert ev.get("effects") is None


def test_optional_take_with_you_not_effect():
    portion = {
        "choices": [
            {"target": "305", "text": "Turn to 305"},
        ],
        "raw_html": ("You find nothing except an old bone, which you may take with you if you wish. "
                     "Turn to <a href=\"#305\"> 305 </a>."),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") is None


def test_choice_effects_keep_walking_no_item():
    portion = {
        "choices": [
            {"target": "292", "text": "Turn to 292"},
        ],
        "raw_html": ("If you wish to stop and lift it up, turn to <a href=\"#120\"> 120 </a>. "
                     "If you prefer to keep walking, turn to <a href=\"#292\"> 292 </a>."),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") is None


def test_choice_effects_if_you_have_suppresses_effects():
    portion = {
        "choices": [
            {"target": "385", "text": "Turn to 385"},
        ],
        "raw_html": ("Drink a Doppelganger Potion (if you have one)? "
                     "Turn to <a href=\"#385\"> 385 </a>."),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") is None


def test_optional_take_multiple_items_keeps_effects():
    portion = {
        "choices": [
            {"target": "192", "text": "Turn to 192"},
        ],
        "raw_html": ("If you would rather just take the mirror and charm and return to the tunnel, "
                     "turn to <a href=\"#192\"> 192 </a>."),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") == [
        {"kind": "item", "action": "add", "name": "mirror"},
        {"kind": "item", "action": "add", "name": "charm"},
    ]


def test_choice_effects_from_table_row():
    portion = {
        "choices": [
            {"target": "397", "text": "Turn to 397"},
        ],
        "raw_html": ("<table><tr><td>Drink the liquid?</td>"
                     "<td>Turn to <a href=\"#397\"> 397 </a></td></tr></table>"),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") is None


def test_choice_effects_rub_liquid():
    portion = {
        "choices": [
            {"target": "75", "text": "Turn to 75"},
        ],
        "raw_html": ("<table><tr><td>Rub the liquid into your wounds?</td>"
                     "<td>Turn to <a href=\"#75\"> 75 </a></td></tr></table>"),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") is None


def test_choice_remove_drops_global_remove():
    portion = {
        "choices": [
            {"target": "330", "text": "Turn to 330"},
        ],
        "raw_html": ("If you wish to eat the rice and drink the water, "
                     "turn to <a href=\"#330\"> 330 </a>."),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
        "inventory": {
            "items_used": [
                {"item": "Rice", "quantity": 1},
                {"item": "Water", "quantity": 1},
            ]
        },
    }
    portion = {
        **portion,
        "section_id": "1",
        "portion_id": "1",
        "page_start": 1,
        "page_end": 1,
        "page_start_original": 1,
        "page_end_original": 1,
        "raw_text": "",
    }
    _, section = build_section(portion, emit_text=False, emit_provenance_text=False)
    seq = section.get("sequence") or []
    assert not any(e.get("kind") == "item" and e.get("action") == "remove" for e in seq)
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") == [
        {"kind": "item", "action": "remove", "name": "rice"},
        {"kind": "item", "action": "remove", "name": "water"},
    ]


def test_choice_effects_taking_just_adds_item():
    portion = {
        "choices": [
            {"target": "127", "text": "Turn to 127"},
        ],
        "raw_html": ("Leave the hall, taking just the diamond with you - "
                     "<a href=\"#127\"> turn to 127 </a>."),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") == [{"kind": "item", "action": "add", "name": "diamond"}]


def test_choice_effects_split_multi_anchor_sentence():
    portion = {
        "choices": [
            {"target": "330", "text": "Turn to 330"},
            {"target": "127", "text": "Turn to 127"},
        ],
        "raw_html": ("If you have not done so already, you may either eat the rice and drink the water - "
                     "<a href=\"#330\"> turn to 330 </a> - or leave the hall, taking just the diamond with you - "
                     "<a href=\"#127\"> turn to 127 </a>."),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
        "inventory": {
            "items_used": [
                {"item": "Rice", "quantity": 1},
                {"item": "Water", "quantity": 1},
            ]
        },
    }
    portion = {
        **portion,
        "section_id": "1",
        "portion_id": "1",
        "page_start": 1,
        "page_end": 1,
        "page_start_original": 1,
        "page_end_original": 1,
        "raw_text": "",
    }
    _, section = build_section(portion, emit_text=False, emit_provenance_text=False)
    seq = section.get("sequence") or []
    choice_330 = next(e for e in seq if e.get("kind") == "choice" and e.get("targetSection") == "330")
    choice_127 = next(e for e in seq if e.get("kind") == "choice" and e.get("targetSection") == "127")
    assert choice_330.get("effects") == [
        {"kind": "item", "action": "remove", "name": "rice"},
        {"kind": "item", "action": "remove", "name": "water"},
    ]
    assert choice_127.get("effects") == [{"kind": "item", "action": "add", "name": "diamond"}]


def test_choice_effects_ignore_fountain():
    portion = {
        "choices": [
            {"target": "173", "text": "Turn to 173"},
        ],
        "raw_html": ("You may either drink from the other fountain - "
                     "<a href=\"#173\"> 173 </a>."),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") is None


def test_choice_effects_strip_of_the():
    portion = {
        "choices": [
            {"target": "269", "text": "Turn to 269"},
        ],
        "raw_html": ("Rub some of the ointment into your wounds - "
                     "<a href=\"#269\"> 269 </a>."),
        "stat_modifications": [],
        "stat_checks": [],
        "items": [],
        "combat": [],
        "deathConditions": [],
    }
    seq = make_sequence(portion, "1")
    choice = next(e for e in seq if e.get("kind") == "choice")
    assert choice.get("effects") == [{"kind": "item", "action": "remove", "name": "ointment"}]
