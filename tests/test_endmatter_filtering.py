#!/usr/bin/env python3
"""
Unit tests for endmatter pattern detection in portionize_html_extract_v1.
Tests generic patterns (not book-specific) that should work across FF books.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.portionize.portionize_html_extract_v1.main import (
    _is_endmatter_running_head,
    _is_book_title_header,
    _is_author_name_line,
)


def test_endmatter_running_head_detection():
    """Test detection of running heads that indicate endmatter."""
    # Positive cases - should detect as endmatter
    assert _is_endmatter_running_head({
        "block_type": "p",
        "attrs": {"class": "running-head"},
        "text": "More Fighting Fantasy in Puffins"
    })

    assert _is_endmatter_running_head({
        "block_type": "p",
        "attrs": {"class": "running-head"},
        "text": "Also available in this series"
    })

    assert _is_endmatter_running_head({
        "block_type": "p",
        "attrs": {"class": "running-head"},
        "text": "Coming Soon from Puffin"
    })

    assert _is_endmatter_running_head({
        "block_type": "p",
        "attrs": {"class": "running-head"},
        "text": "Further Adventures"
    })

    # Negative cases - should NOT detect as endmatter
    assert not _is_endmatter_running_head({
        "block_type": "p",
        "attrs": {"class": "running-head"},
        "text": "40-42"  # Normal section range running head
    })

    assert not _is_endmatter_running_head({
        "block_type": "p",
        "attrs": {},
        "text": "More Fighting Fantasy"  # Not a running-head class
    })

    assert not _is_endmatter_running_head({
        "block_type": "h2",
        "attrs": {"class": "running-head"},
        "text": "More Fighting Fantasy"  # Wrong block type
    })


def test_book_title_header_detection():
    """Test detection of book title headers (numbered list format)."""
    # Positive cases - should detect as book title
    assert _is_book_title_header({
        "block_type": "h2",
        "text": "1. THE WARLOCK OF FIRETOP MOUNTAIN"
    })

    assert _is_book_title_header({
        "block_type": "h1",
        "text": "12. SPACE ASSASSIN"
    })

    assert _is_book_title_header({
        "block_type": "h2",
        "text": "5. THE CITADEL OF CHAOS"
    })

    # Negative cases - should NOT detect as book title
    assert not _is_book_title_header({
        "block_type": "h2",
        "text": "400"  # Gameplay section number
    })

    assert not _is_book_title_header({
        "block_type": "h2",
        "text": "1. This is not all caps"  # Not all caps
    })

    assert not _is_book_title_header({
        "block_type": "p",
        "text": "1. THE BOOK TITLE"  # Wrong block type
    })

    assert not _is_book_title_header({
        "block_type": "h2",
        "text": "123. TOO LARGE NUMBER"  # Number too large for book list
    })


def test_author_name_line_detection():
    """Test detection of author name patterns."""
    # Positive cases - should detect as author name
    assert _is_author_name_line({
        "block_type": "p",
        "text": "Steve Jackson and Ian Livingstone"
    })

    assert _is_author_name_line({
        "block_type": "p",
        "text": "Ian Livingstone"
    })

    assert _is_author_name_line({
        "block_type": "p",
        "text": "By Andrew Chapman"
    })

    # Negative cases - should NOT detect as author name
    assert not _is_author_name_line({
        "block_type": "p",
        "text": "This is a longer paragraph with multiple sentences. It should not be detected as an author name because it's too long and contains more than just a simple name pattern."
    })

    assert not _is_author_name_line({
        "block_type": "p",
        "text": "all lowercase text"  # Not proper case
    })

    assert not _is_author_name_line({
        "block_type": "p",
        "text": "ALL CAPS TEXT"  # All caps
    })

    assert not _is_author_name_line({
        "block_type": "h2",
        "text": "Steve Jackson"  # Wrong block type
    })

    assert not _is_author_name_line({
        "block_type": "p",
        "text": ""  # Empty text
    })


def test_combined_endmatter_scenario():
    """Test a realistic endmatter sequence (section 400 example)."""
    blocks = [
        {
            "block_type": "h2",
            "text": "400"
        },
        {
            "block_type": "p",
            "text": "Congratulations! You have defeated the Baron and escaped the Deathtrap Dungeon."
        },
        {
            "block_type": "p",
            "attrs": {"class": "running-head"},
            "text": "More Fighting Fantasy in Puffins"
        },
        {
            "block_type": "h2",
            "text": "1. THE WARLOCK OF FIRETOP MOUNTAIN"
        },
        {
            "block_type": "p",
            "text": "Steve Jackson and Ian Livingstone"
        },
    ]

    # The gameplay content (blocks 0-1) should not be detected as endmatter
    assert not _is_endmatter_running_head(blocks[0])
    assert not _is_book_title_header(blocks[0])
    assert not _is_author_name_line(blocks[0])

    assert not _is_endmatter_running_head(blocks[1])
    assert not _is_book_title_header(blocks[1])
    assert not _is_author_name_line(blocks[1])

    # The endmatter content (blocks 2-4) should be detected
    assert _is_endmatter_running_head(blocks[2])
    assert _is_book_title_header(blocks[3])
    assert _is_author_name_line(blocks[4])


if __name__ == "__main__":
    # Run all tests
    test_endmatter_running_head_detection()
    test_book_title_header_detection()
    test_author_name_line_detection()
    test_combined_endmatter_scenario()

    print("✅ All endmatter filtering tests passed!")
