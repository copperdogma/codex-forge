import json

from modules.export.apply_edgecase_patches_v1.main import apply_patches


def _gamebook():
    return {
        "metadata": {
            "title": "Example",
            "startSection": "1",
            "formatVersion": "1.0.0",
        },
        "sections": {
            "1": {
                "id": "1",
                "presentation_html": "<p>Example</p>",
                "isGameplaySection": True,
                "type": "section",
                "sequence": [
                    {"kind": "choice", "targetSection": "2", "choiceText": "Turn to 2"}
                ],
            },
            "2": {
                "id": "2",
                "presentation_html": "<p>End</p>",
                "isGameplaySection": True,
                "type": "section",
                "sequence": [],
            },
        },
    }


def test_apply_replace_patch():
    gb = _gamebook()
    patches = [{
        "schema_version": "edgecase_patch_v1",
        "section_id": "1",
        "reason_code": "terminal_outcome_text",
        "path": "/sections/1/sequence/0/choiceText",
        "op": "replace",
        "value": "Run away",
    }]
    patched, report = apply_patches(gb, patches)
    assert patched["sections"]["1"]["sequence"][0]["choiceText"] == "Run away"
    assert report[0]["status"] == "applied"


def test_apply_add_patch():
    gb = _gamebook()
    patches = [{
        "schema_version": "edgecase_patch_v1",
        "section_id": "1",
        "reason_code": "conditional_choice_branch",
        "path": "/sections/1/sequence/1",
        "op": "add",
        "value": {"kind": "choice", "targetSection": "3", "choiceText": "Climb"},
    }]
    patched, report = apply_patches(gb, patches)
    assert len(patched["sections"]["1"]["sequence"]) == 2
    assert report[0]["status"] == "applied"


def test_apply_remove_patch():
    gb = _gamebook()
    patches = [{
        "schema_version": "edgecase_patch_v1",
        "section_id": "1",
        "reason_code": "dual_item_check",
        "path": "/sections/1/sequence/0",
        "op": "remove",
    }]
    patched, report = apply_patches(gb, patches)
    assert patched["sections"]["1"]["sequence"] == []
    assert report[0]["status"] == "applied"


def test_idempotent_patch_skips():
    gb = _gamebook()
    patches = [{
        "schema_version": "edgecase_patch_v1",
        "section_id": "1",
        "reason_code": "terminal_outcome_text",
        "path": "/sections/1/sequence/0/choiceText",
        "op": "replace",
        "value": "Turn to 2",
    }]
    patched, report = apply_patches(gb, patches)
    assert report[0]["status"] == "already_applied"
    assert patched["sections"]["1"]["sequence"][0]["choiceText"] == "Turn to 2"
