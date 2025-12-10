"""Tests for OCR quality check functions in extract_ocr_ensemble_v1."""
import sys
from pathlib import Path

# Add modules to path for imports
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest


def get_quality_functions():
    """Import the quality functions from the OCR module."""
    from modules.extract.extract_ocr_ensemble_v1.main import (
        detect_form_page,
        detect_sentence_fragmentation,
        check_column_split_quality,
    )
    return detect_form_page, detect_sentence_fragmentation, check_column_split_quality


class TestDetectFormPage:
    """Tests for detect_form_page function."""

    def test_empty_lines_returns_not_form(self):
        detect_form_page, _, _ = get_quality_functions()
        result = detect_form_page([])
        assert result["is_form"] is False
        assert result["confidence"] == 0.0

    def test_adventure_sheet_detected_as_form(self):
        """Adventure Sheet pages should be detected as forms."""
        detect_form_page, _, _ = get_quality_functions()
        # Simulated Adventure Sheet content from page 011R
        lines = [
            "MONSTER ENCOI",
            "",
            "Cif = Shal) =",
            "",
            "Stanpitiwd =",
            "",
            "Sting =",
            "",
            "shill =",
            "Staniny =",
            "",
            "Sil} =",
            "",
            "Sian =",
            "",
            "Skil! =",
            "Swunnd =",
            "",
            "Skill =",
            "",
            "INTER BOXES",
            "",
            "Skul =",
            "",
            "Sona =",
        ]
        result = detect_form_page(lines)
        assert result["is_form"] is True, f"Adventure Sheet should be detected as form: {result}"
        assert result["confidence"] >= 0.5

    def test_prose_text_not_form(self):
        """Normal prose text should not be detected as a form."""
        detect_form_page, _, _ = get_quality_functions()
        lines = [
            "Down in the dark, twisting labyrinth of Fang, unknown",
            "horrors await you. Devised by the devilish mind of Baron",
            "Sukumvit, the labyrinth is riddled with fiendish traps and",
            "bloodthirsty monsters, which will test your skills almost",
            "beyond the limit of endurance. Countless adventurers",
            "before you have taken up the challenge of the Trial of",
            "Champions and walked through the carved mouth of the",
            "labyrinth, never to be seen again. Do YOU dare enter?",
        ]
        result = detect_form_page(lines)
        assert result["is_form"] is False, f"Prose should not be detected as form: {result}"

    def test_form_keywords_detected(self):
        """Form keywords like SKILL, STAMINA, LUCK should be detected."""
        detect_form_page, _, _ = get_quality_functions()
        lines = [
            "ADVENTURE SHEET",
            "SKILL",
            "Initial Skill =",
            "STAMINA",
            "Stamina =",
            "LUCK",
            "Luck =",
            "ITEMS OF EQUIPMENT CARRIED",
        ]
        result = detect_form_page(lines)
        assert "form_keywords" in str(result["reasons"]), f"Form keywords should be detected: {result}"

    def test_high_equals_ratio_detected(self):
        """High density of '=' characters should trigger form detection."""
        detect_form_page, _, _ = get_quality_functions()
        lines = [
            "Skill =",
            "Stamina =",
            "Luck =",
            "Gold =",
            "Items =",
        ]
        result = detect_form_page(lines)
        assert "equals_pattern" in str(result["reasons"]), f"Equals pattern should be detected: {result}"


class TestDetectSentenceFragmentation:
    """Tests for detect_sentence_fragmentation function."""

    def test_empty_text_returns_not_fragmented(self):
        _, detect_sentence_fragmentation, _ = get_quality_functions()
        result = detect_sentence_fragmentation("")
        assert result["is_fragmented"] is False
        assert result["confidence"] == 0.0

    def test_fragmented_column_text_detected(self):
        """Page 008L style fragmented text should be detected."""
        _, detect_sentence_fragmentation, _ = get_quality_functions()
        # Simulated fragmented column output from page 008L
        fragmented_text = """1-6. This sequenc
score of either °
fighting has been

On some pages you
running away from ;
badly for you. How
creature automatical
(subtract 2 STAMINA
price of cowardice. I
this wound in the no:
only Escape if that op
on the page.

Fighting Mo

If you come across
particular encounter
will tell you how to
you will treat them <
you will fight each o1"""

        result = detect_sentence_fragmentation(fragmented_text)
        assert result["is_fragmented"] is True, f"Fragmented text should be detected: {result}"
        assert result["confidence"] >= 0.4

    def test_complete_prose_not_fragmented(self):
        """Complete prose text should not be marked as fragmented."""
        _, detect_sentence_fragmentation, _ = get_quality_functions()
        complete_text = """able. But beware! Using luck is a risky business and
if you are unlucky, the results could be disastrous.

The procedure for using your luck is as follows: roll
two dice. If the number rolled is equal to or less than
your current LUCK score, you have been lucky and
the result will go in your favour. If the number
rolled is higher than your current LUCK score, you
have been unlucky and you will be penalized."""

        result = detect_sentence_fragmentation(complete_text)
        assert result["is_fragmented"] is False, f"Complete text should not be fragmented: {result}"

    def test_lines_ending_with_short_incomplete_words(self):
        """Lines ending with short non-common words should trigger detection."""
        _, detect_sentence_fragmentation, _ = get_quality_functions()
        # Text with lines ending in incomplete words
        fragmented_text = """This is the begi
of a fragmented te
that splits wor
across line boundari"""

        result = detect_sentence_fragmentation(fragmented_text)
        assert result["is_fragmented"] is True, f"Incomplete endings should be detected: {result}"


class TestCheckColumnSplitQuality:
    """Tests for check_column_split_quality function."""

    def test_single_column_always_passes(self):
        _, _, check_column_split_quality = get_quality_functions()
        # Single column span should always pass
        is_good, reason = check_column_split_quality(None, [(0.0, 1.0)])
        assert is_good is True
        assert reason is None

    def test_form_page_in_columns_rejected(self):
        """Form-like content split into columns should be rejected."""
        _, _, check_column_split_quality = get_quality_functions()
        # Simulated Adventure Sheet content split into columns
        tesseract_cols = [
            "MONSTER ENCOI\n\nCif = Shal) =\n\nStanpitiwd =\n\nSting =\n\nshill =\nStaniny =\n",
            "INTER BOXES\n\nSkul =\n\nSona =\n\nSkat =\n\nStamina =\n"
        ]
        spans = [(0.0, 0.5), (0.5, 1.0)]

        is_good, reason = check_column_split_quality(None, spans, tesseract_cols=tesseract_cols)
        assert is_good is False, f"Form page should be rejected: {reason}"
        assert "form_page_detected" in reason

    def test_fragmented_columns_rejected(self):
        """Columns with fragmented text should be rejected."""
        _, _, check_column_split_quality = get_quality_functions()
        # Simulated fragmented column text from page 008L
        tesseract_cols = [
            "1-6. This sequenc\nscore of either °\nfighting has been\n\nOn some pages you\nrunning away from ;\nbadly for you. How\ncreature automatical\n",
            "e continues until the sTAMINA\nyou or the creature you are\nreduced to zero (death).\n\nEscaping\n"
        ]
        spans = [(0.0, 0.5), (0.5, 1.0)]

        is_good, reason = check_column_split_quality(None, spans, tesseract_cols=tesseract_cols)
        assert is_good is False, f"Fragmented columns should be rejected: {reason}"

    def test_good_column_split_passes(self):
        """Well-formed column text should pass the quality check."""
        _, _, check_column_split_quality = get_quality_functions()
        # Simulated good two-column layout
        tesseract_cols = [
            "The first column has complete sentences.\nThis is well-formed prose text.\nIt continues naturally.\n",
            "The second column also has complete text.\nSentences are properly formed.\nNo fragmentation here.\n"
        ]
        spans = [(0.0, 0.5), (0.5, 1.0)]

        is_good, reason = check_column_split_quality(None, spans, tesseract_cols=tesseract_cols)
        assert is_good is True, f"Good columns should pass: {reason}"


class TestIntegration:
    """Integration tests using real test data patterns."""

    def test_page_008l_pattern_rejected(self):
        """The specific fragmentation pattern from page 008L should be rejected."""
        _, _, check_column_split_quality = get_quality_functions()

        # Actual fragmented text pattern from page 008L
        col1 = """1-6. This sequenc
score of either °
fighting has been

On some pages you
running away from ;
badly for you. How
creature automatical
(subtract 2 STAMINA
price of cowardice. I
this wound in the no:
only Escape if that op
on the page.

Fighting Mo

If you come across
particular encounter
will tell you how to
you will treat them <
you will fight each o1

At various times du
battles or when you «
you could either be
these are given on tk
call on your luck ton

12
"""
        col2 = """e continues until the sTAMINA
you or the creature you are
reduced to zero (death).

Escaping

1 may be given the option of
a battle should things be going
ever, if you do run away, the
ly gets in one wound on you
points) as you flee. Such is the
Jote that you may use LUCK on
rmal way (see below). You may
tion is specifically given to you

re Than One Creature

more than one creature in a
, the instructions on that page
handle the battle. Sometimes
is a single monster; sometimes
ye in turn.

Luck

ring your adventure, either in
ome across situations in which
lucky or unlucky (details of
e pages themselves), you may
1ake the outcome more favour-
"""

        tesseract_cols = [col1, col2]
        spans = [(0.0, 0.44), (0.44, 1.0)]

        is_good, reason = check_column_split_quality(None, spans, tesseract_cols=tesseract_cols)
        assert is_good is False, f"Page 008L pattern should be rejected: {reason}"

    def test_page_011r_adventure_sheet_rejected(self):
        """The Adventure Sheet pattern from page 011R should be rejected."""
        _, _, check_column_split_quality = get_quality_functions()

        col1 = """MONSTER ENCOI

Cif = Shal) =

Stanpitiwd =

Sting =

shill =
Staniny =

Sil} =

Sian =

Skil! =
Swunnd =

Skill =

Sinn =

Suit

Shniniie =

"""
        col2 = """INTER BOXES

Skul =

Sona =

Skat =

Stamina =
"""

        tesseract_cols = [col1, col2]
        spans = [(0.0, 0.49), (0.49, 1.0)]

        is_good, reason = check_column_split_quality(None, spans, tesseract_cols=tesseract_cols)
        assert is_good is False, f"Page 011R pattern should be rejected: {reason}"
        assert "form_page_detected" in reason or "fragmented" in reason.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
