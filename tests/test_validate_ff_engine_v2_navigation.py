#!/usr/bin/env python3
"""
Tests for validate_ff_engine_v2 navigation detection.

Tests that validation correctly identifies sections with navigation,
including conditional events (stat_check, test_luck, etc.) as choices.
"""
import json
import pytest
from modules.validate.validate_ff_engine_v2.main import validate_gamebook


def test_has_direct_choice():
    """Section with direct choice should not be flagged."""
    gamebook = {
        "sections": {
            "1": {
                "isGameplaySection": True,
                "sequence": [
                    {"kind": "choice", "targetSection": "2", "text": "Go to 2"}
                ]
            }
        }
    }
    report = validate_gamebook(gamebook, 1, 1)
    assert "1" not in report.sections_with_no_choices


def test_has_stat_check_navigation():
    """Section with stat_check that has targetSection outcomes should not be flagged."""
    gamebook = {
        "sections": {
            "12": {
                "isGameplaySection": True,
                "sequence": [
                    {
                        "kind": "stat_check",
                        "stat": "SKILL",
                        "pass": {"targetSection": "316"},
                        "fail": {"targetSection": "379"}
                    }
                ]
            }
        }
    }
    report = validate_gamebook(gamebook, 1, 400)
    assert "12" not in report.sections_with_no_choices


def test_has_test_luck_navigation():
    """Section with test_luck that has targetSection outcomes should not be flagged."""
    gamebook = {
        "sections": {
            "50": {
                "isGameplaySection": True,
                "sequence": [
                    {
                        "kind": "test_luck",
                        "lucky": {"targetSection": "100"},
                        "unlucky": {"targetSection": "200"}
                    }
                ]
            }
        }
    }
    report = validate_gamebook(gamebook, 1, 400)
    assert "50" not in report.sections_with_no_choices


def test_has_item_check_navigation():
    """Section with item_check that has targetSection outcomes should not be flagged."""
    gamebook = {
        "sections": {
            "75": {
                "isGameplaySection": True,
                "sequence": [
                    {
                        "kind": "item_check",
                        "itemName": "sword",
                        "has": {"targetSection": "150"},
                        "missing": {"targetSection": "250"}
                    }
                ]
            }
        }
    }
    report = validate_gamebook(gamebook, 1, 400)
    assert "75" not in report.sections_with_no_choices


def test_has_combat_navigation():
    """Section with combat that has targetSection outcomes should not be flagged."""
    gamebook = {
        "sections": {
            "100": {
                "isGameplaySection": True,
                "sequence": [
                    {
                        "kind": "combat",
                        "enemy": "Orc",
                        "outcomes": {
                            "win": {"targetSection": "200"},
                            "lose": {"targetSection": "300"}
                        }
                    }
                ]
            }
        }
    }
    report = validate_gamebook(gamebook, 1, 400)
    assert "100" not in report.sections_with_no_choices


def test_has_stat_change_navigation():
    """Section with stat_change that has else outcome should not be flagged."""
    gamebook = {
        "sections": {
            "25": {
                "isGameplaySection": True,
                "sequence": [
                    {
                        "kind": "stat_change",
                        "stat": "STAMINA",
                        "amount": 2,
                        "else": {"targetSection": "50"}
                    }
                ]
            }
        }
    }
    report = validate_gamebook(gamebook, 1, 400)
    assert "25" not in report.sections_with_no_choices


def test_no_navigation_should_be_flagged():
    """Section with no navigation should be flagged."""
    gamebook = {
        "sections": {
            "1": {
                "isGameplaySection": True,
                "sequence": [
                    {"kind": "text", "content": "You are dead."}
                ]
            }
        }
    }
    report = validate_gamebook(gamebook, 1, 1)
    assert "1" in report.sections_with_no_choices


def test_stat_check_without_targets_should_be_flagged():
    """Section with stat_check but no targetSection outcomes should be flagged."""
    gamebook = {
        "sections": {
            "1": {
                "isGameplaySection": True,
                "sequence": [
                    {
                        "kind": "stat_check",
                        "stat": "SKILL",
                        "pass": {},
                        "fail": {}
                    }
                ]
            }
        }
    }
    report = validate_gamebook(gamebook, 1, 1)
    assert "1" in report.sections_with_no_choices


def test_end_game_section_should_not_be_flagged():
    """Section with end_game flag should not be flagged."""
    gamebook = {
        "sections": {
            "400": {
                "isGameplaySection": True,
                "end_game": True,
                "sequence": []
            }
        }
    }
    report = validate_gamebook(gamebook, 1, 400)
    assert "400" not in report.sections_with_no_choices


def test_stub_section_should_not_be_flagged():
    """Section with stub provenance should not be flagged."""
    gamebook = {
        "sections": {
            "1": {
                "isGameplaySection": True,
                "provenance": {"stub": True},
                "sequence": []
            }
        }
    }
    report = validate_gamebook(gamebook, 1, 1)
    assert "1" not in report.sections_with_no_choices


def test_non_gameplay_section_should_not_be_flagged():
    """Section that is not gameplay should not be flagged."""
    gamebook = {
        "sections": {
            "background": {
                "isGameplaySection": False,
                "sequence": []
            }
        }
    }
    report = validate_gamebook(gamebook, 1, 1)
    assert "background" not in report.sections_with_no_choices


def test_robot_commando_section_12():
    """Real-world test: Robot Commando section 12 should not be flagged."""
    gamebook = {
        "sections": {
            "12": {
                "isGameplaySection": True,
                "sequence": [
                    {
                        "kind": "stat_check",
                        "stat": "SKILL",
                        "diceRoll": "2d6",
                        "passCondition": "total <= SKILL",
                        "failCondition": "total > SKILL",
                        "pass": {"targetSection": "316"},
                        "fail": {"targetSection": "379"}
                    }
                ]
            }
        }
    }
    report = validate_gamebook(gamebook, 1, 400)
    assert "12" not in report.sections_with_no_choices, "Section 12 should not be flagged - it has stat_check navigation"
