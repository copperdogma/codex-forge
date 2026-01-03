#!/usr/bin/env python3
"""
Unit tests for validate_choice_completeness_v1 target coverage.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.validate.validate_choice_completeness_v1.main import validate_section_choices


def test_turn_to_links_covered_by_combat_outcome():
    section = {
        "presentation_html": "<p>Fight. <a href=\"#12\">turn to 12</a></p>",
        "turn_to_links": ["12"],
        "sequence": [
            {"kind": "combat", "outcomes": {"win": {"targetSection": "12"}}}
        ],
        "choices": [],
    }

    is_valid, details = validate_section_choices("1", section)
    assert is_valid is True
    assert details["missing_in_claims"] == []
    assert details["claimed_targets"] == [12]
    assert details["text_references"] == [12]


def test_turn_to_links_missing_in_claims():
    section = {
        "presentation_html": "<p><a href=\"#99\">turn to 99</a></p>",
        "turn_to_links": ["99"],
        "sequence": [],
        "choices": [],
    }

    is_valid, details = validate_section_choices("2", section)
    assert is_valid is False
    assert details["missing_in_claims"] == [99]


def test_text_fallback_when_turn_to_links_missing():
    section = {
        "presentation_html": "<p>Turn to 42.</p>",
        "sequence": [{"kind": "choice", "targetSection": "42"}],
        "choices": [],
    }

    is_valid, details = validate_section_choices("3", section)
    assert is_valid is True
    assert details["link_source"] == "text"
    assert details["missing_in_claims"] == []


if __name__ == "__main__":
    test_turn_to_links_covered_by_combat_outcome()
    test_turn_to_links_missing_in_claims()
    test_text_fallback_when_turn_to_links_missing()
    print("✅ All validate_choice_completeness tests passed!")
