#!/usr/bin/env python3
"""
Unit tests for content_type filtering in boundary detection modules.

Tests the content_type-aware filtering and confidence boosting added in story-059.
"""

import sys
from pathlib import Path

# Add modules directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.portionize.detect_gameplay_numbers_v1.main import (
    should_skip_by_content_type,
    get_content_type_confidence_boost,
    extract_numbers_from_ocr_errors,
)
from modules.portionize.portionize_ai_scan_v1.main import should_skip_element


def test_should_skip_by_content_type():
    """Test that Page-header, Page-footer, and List-item are filtered out."""
    # Should skip these types
    assert should_skip_by_content_type({"content_type": "Page-header"}) is True
    assert should_skip_by_content_type({"content_type": "Page-footer"}) is True
    assert should_skip_by_content_type({"content_type": "List-item"}) is True

    # Should NOT skip these types
    assert should_skip_by_content_type({"content_type": "Section-header"}) is False
    assert should_skip_by_content_type({"content_type": "Text"}) is False
    assert should_skip_by_content_type({"content_type": "Title"}) is False

    # Should NOT skip elements without content_type
    assert should_skip_by_content_type({}) is False
    assert should_skip_by_content_type({"text": "42"}) is False


def test_should_skip_element():
    """Test ai_scan pre-filtering (same logic as detect_gameplay_numbers)."""
    # Should skip these types
    assert should_skip_element({"content_type": "Page-header"}) is True
    assert should_skip_element({"content_type": "Page-footer"}) is True
    assert should_skip_element({"content_type": "List-item"}) is True

    # Should NOT skip these types
    assert should_skip_element({"content_type": "Section-header"}) is False
    assert should_skip_element({"content_type": "Text"}) is False
    assert should_skip_element({}) is False


def test_confidence_boost_section_header():
    """Test confidence boost for Section-header content_type."""
    elem = {"content_type": "Section-header"}
    boost, evidence = get_content_type_confidence_boost(elem, section_id=42)

    assert boost == 0.1  # Base boost for Section-header
    assert "content_type=Section-header" in evidence


def test_confidence_boost_section_header_with_matching_number():
    """Test additional boost when content_subtype.number matches section_id."""
    elem = {
        "content_type": "Section-header",
        "content_subtype": {"number": 42}
    }
    boost, evidence = get_content_type_confidence_boost(elem, section_id=42)

    assert boost == 0.2  # 0.1 for Section-header + 0.1 for matching number
    assert "content_type=Section-header" in evidence
    assert "content_subtype.number=42" in evidence


def test_confidence_boost_section_header_with_non_matching_number():
    """Test no additional boost when content_subtype.number doesn't match."""
    elem = {
        "content_type": "Section-header",
        "content_subtype": {"number": 99}
    }
    boost, evidence = get_content_type_confidence_boost(elem, section_id=42)

    assert boost == 0.1  # Only base boost for Section-header
    assert "content_type=Section-header" in evidence
    assert "content_subtype.number=42" not in evidence


def test_confidence_boost_no_content_type():
    """Test no boost when content_type is missing."""
    elem = {"text": "42"}
    boost, evidence = get_content_type_confidence_boost(elem, section_id=42)

    assert boost == 0.0
    assert evidence == []


def test_confidence_boost_text_content_type():
    """Test no boost for regular Text content_type."""
    elem = {"content_type": "Text"}
    boost, evidence = get_content_type_confidence_boost(elem, section_id=42)

    assert boost == 0.0
    assert evidence == []


def test_integration_scenario():
    """Test realistic scenario with multiple content_type signals."""
    # Scenario 1: Strong signal - Section-header with matching number
    elem1 = {
        "id": "016-0001",
        "text": "42",
        "content_type": "Section-header",
        "content_subtype": {"number": 42}
    }
    boost1, evidence1 = get_content_type_confidence_boost(elem1, section_id=42)
    assert boost1 == 0.2
    assert len(evidence1) == 2

    # Scenario 2: Medium signal - Section-header without number
    elem2 = {
        "id": "016-0002",
        "text": "43",
        "content_type": "Section-header"
    }
    boost2, evidence2 = get_content_type_confidence_boost(elem2, section_id=43)
    assert boost2 == 0.1
    assert len(evidence2) == 1

    # Scenario 3: Filtered out - List-item
    elem3 = {
        "id": "016-0003",
        "text": "1",
        "content_type": "List-item"
    }
    assert should_skip_by_content_type(elem3) is True


def test_ocr_extraction_in_4():
    """Test OCR error: 'in 4' → '4'."""
    variants = extract_numbers_from_ocr_errors("in 4")
    assert "in 4" in variants  # Original preserved
    assert "4" in variants  # Extracted number
    assert len([v for v in variants if v == "4"]) == 1  # No duplicates


def test_ocr_extraction_section_42():
    """Test OCR error: 'Section42' → '42'."""
    variants = extract_numbers_from_ocr_errors("Section42")
    assert "Section42" in variants  # Original preserved
    assert "42" in variants  # Extracted number


def test_ocr_extraction_m_4():
    """Test OCR error: 'm 4' → '4' (in → m corruption)."""
    variants = extract_numbers_from_ocr_errors("m 4")
    assert "m 4" in variants
    assert "4" in variants


def test_ocr_extraction_pure_number():
    """Test that pure numbers are passed through unchanged."""
    variants = extract_numbers_from_ocr_errors("42")
    assert variants == ["42"]  # Only original, no extraction needed


def test_ocr_extraction_no_match():
    """Test text with no numbers returns only original."""
    variants = extract_numbers_from_ocr_errors("Hello World")
    assert variants == ["Hello World"]


def test_ocr_extraction_multiple_patterns():
    """Test text that matches multiple patterns."""
    variants = extract_numbers_from_ocr_errors("in 42")
    assert "in 42" in variants
    assert "42" in variants


if __name__ == "__main__":
    # Run tests
    test_should_skip_by_content_type()
    test_should_skip_element()
    test_confidence_boost_section_header()
    test_confidence_boost_section_header_with_matching_number()
    test_confidence_boost_section_header_with_non_matching_number()
    test_confidence_boost_no_content_type()
    test_confidence_boost_text_content_type()
    test_integration_scenario()
    test_ocr_extraction_in_4()
    test_ocr_extraction_section_42()
    test_ocr_extraction_m_4()
    test_ocr_extraction_pure_number()
    test_ocr_extraction_no_match()
    test_ocr_extraction_multiple_patterns()

    print("✅ All content_type filtering and OCR extraction tests passed!")
