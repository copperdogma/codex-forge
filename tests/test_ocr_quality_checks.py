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


class TestOutlierDetection:
    """Tests for detect_outlier_engine function."""

    def get_outlier_function(self):
        """Import the outlier detection function from the OCR module."""
        from modules.extract.extract_ocr_ensemble_v1.main import detect_outlier_engine
        return detect_outlier_engine

    def test_single_engine_no_outliers(self):
        """Single engine should produce no outliers."""
        detect_outlier_engine = self.get_outlier_function()
        result = detect_outlier_engine({"tesseract": "Some text here"})
        assert result["outliers"] == []
        assert result["best_pair"] is None

    def test_two_similar_engines_no_outliers(self):
        """Two similar engines should have no outliers."""
        detect_outlier_engine = self.get_outlier_function()
        result = detect_outlier_engine({
            "tesseract": "The quick brown fox jumps over the lazy dog",
            "apple": "The quick brown fox jumps over the lazy dog"
        })
        assert result["outliers"] == []
        assert result["best_pair_distance"] == 0.0

    def test_two_very_different_engines_both_outliers(self):
        """With two very different engines (both exceed threshold), both may be outliers."""
        detect_outlier_engine = self.get_outlier_function()
        result = detect_outlier_engine({
            "tesseract": "The quick brown fox",
            "apple": "Completely different text here"
        })
        # When both engines differ by more than the outlier threshold,
        # and they're the only pair, both may be marked as outliers
        # This is correct behavior - it indicates neither engine should be trusted
        assert result["best_pair"] is not None
        assert result["best_pair_distance"] > 0.5  # They're very different

    def test_three_engines_one_outlier(self):
        """With three engines where one is very different, detect the outlier."""
        detect_outlier_engine = self.get_outlier_function()
        result = detect_outlier_engine({
            "tesseract": "The quick brown fox jumps over the lazy dog",
            "apple": "The quick brown fox jumps over the lazy dog.",  # Very similar
            "easyocr": "GARBAGE OUTPUT COMPLETELY DIFFERENT ZZZZZ"  # Outlier
        })
        assert "easyocr" in result["outliers"], f"Expected easyocr as outlier: {result}"
        assert result["best_pair"] in [("tesseract", "apple"), ("apple", "tesseract")]

    def test_empty_and_error_engines_ignored(self):
        """Empty outputs and error keys should be ignored."""
        detect_outlier_engine = self.get_outlier_function()
        result = detect_outlier_engine({
            "tesseract": "Valid text here",
            "apple": "Valid text here too",
            "easyocr": "",  # Empty - should be ignored
            "easyocr_error": "Some error occurred"  # Error key - should be ignored
        })
        assert "easyocr" not in result.get("avg_distances", {})
        assert result["outliers"] == []


class TestFusionFunctions:
    """Tests for character-level fusion and align_and_vote functions."""

    def get_fusion_functions(self):
        """Import the fusion functions from the OCR module."""
        from modules.extract.extract_ocr_ensemble_v1.main import (
            fuse_characters,
            align_and_vote,
        )
        return fuse_characters, align_and_vote

    def test_fuse_characters_identical(self):
        """Identical strings should return as-is."""
        fuse_characters, _ = self.get_fusion_functions()
        result = fuse_characters("STAMINA", "STAMINA")
        assert result == "STAMINA"

    def test_fuse_characters_case_difference(self):
        """Case differences should prefer uppercase."""
        fuse_characters, _ = self.get_fusion_functions()
        # sTAMINA vs STAMINA should prefer uppercase S
        result = fuse_characters("sTAMINA", "STAMINA")
        assert result == "STAMINA", f"Expected 'STAMINA', got '{result}'"

    def test_fuse_characters_digit_vs_letter(self):
        """Should prefer letter over digit for common OCR confusions."""
        fuse_characters, _ = self.get_fusion_functions()
        # cru5he5 vs crushes - prefer letters
        result = fuse_characters("cru5he5", "crushes")
        assert result == "crushes", f"Expected 'crushes', got '{result}'"

    def test_fuse_characters_empty_inputs(self):
        """Empty inputs should be handled gracefully."""
        fuse_characters, _ = self.get_fusion_functions()
        assert fuse_characters("", "test") == "test"
        assert fuse_characters("test", "") == "test"
        assert fuse_characters("", "") == ""

    def test_fuse_characters_very_different_lengths(self):
        """Very different lengths should pick the longer one."""
        fuse_characters, _ = self.get_fusion_functions()
        result = fuse_characters("short", "this is much longer")
        assert result == "this is much longer"

    def test_align_and_vote_identical_lines(self):
        """Identical line lists should return with 'agree' source."""
        _, align_and_vote = self.get_fusion_functions()
        lines = ["Line one", "Line two", "Line three"]
        fused, sources, distances = align_and_vote(lines, lines)
        assert fused == lines
        assert all(s == "agree" for s in sources)
        assert all(d == 0.0 for d in distances)

    def test_align_and_vote_empty_alt(self):
        """Empty alt lines should return primary lines."""
        _, align_and_vote = self.get_fusion_functions()
        primary = ["Line one", "Line two"]
        fused, sources, distances = align_and_vote(primary, [])
        assert fused == primary
        assert all(s == "primary" for s in sources)

    def test_align_and_vote_character_fusion_triggered(self):
        """Similar lines should trigger character-level fusion."""
        _, align_and_vote = self.get_fusion_functions()
        primary = ["sTAMINA score is 12"]
        alt = ["STAMINA score is 12"]
        fused, sources, distances = align_and_vote(primary, alt, enable_char_fusion=True)
        # Should fuse to prefer uppercase
        assert "STAMINA" in fused[0], f"Expected fused to contain 'STAMINA': {fused}"

    def test_align_and_vote_too_different_uses_primary(self):
        """Very different lines should use primary only."""
        _, align_and_vote = self.get_fusion_functions()
        primary = ["The quick brown fox jumps over the lazy dog"]
        alt = ["Completely unrelated text that is very different"]
        fused, sources, distances = align_and_vote(primary, alt, distance_drop=0.35)
        # Should use primary because they're too different
        assert fused[0] == primary[0]
        assert sources[0] == "primary"

    def test_align_and_vote_high_confidence_prefers_alt(self):
        """High confidence Apple lines should be preferred."""
        _, align_and_vote = self.get_fusion_functions()
        primary = ["STAMIN score is twelve"]  # Tesseract made an error
        alt = ["STAMINA score is twelve"]  # Apple got it right
        # Lines are similar enough (not dropped by distance) but different
        # High confidence should prefer alt
        fused, sources, distances = align_and_vote(
            primary, alt,
            alt_confidences=[0.95]  # High confidence
        )
        # With high confidence, should prefer alt
        assert "STAMINA" in fused[0], f"Expected alt line with high confidence: {fused}"

    def test_align_and_vote_low_confidence_prefers_primary(self):
        """Low confidence Apple lines should not override primary."""
        _, align_and_vote = self.get_fusion_functions()
        primary = ["The correct text here"]
        alt = ["Th corrct txt hre"]  # Garbled Apple output
        # Low confidence should prefer primary
        fused, sources, distances = align_and_vote(
            primary, alt,
            alt_confidences=[0.3]  # Low confidence
        )
        assert fused[0] == primary[0], f"Expected primary with low alt confidence: {fused}"
        assert sources[0] == "primary"

    def test_align_and_vote_three_engine_majority(self):
        """Two engines agreeing should win over a third differing engine."""
        _, align_and_vote = self.get_fusion_functions()
        engines = {
            "tesseract": ["STAMINA score is twelve"],
            "apple": ["STAMINA score is twelve"],
            "easyocr": ["STAMIN score is twelve"],
        }
        fused, sources, distances = align_and_vote(
            engines,
            None,
            confidences_by_engine={"tesseract": [0.7], "apple": [0.9]},
        )
        assert fused[0] == "STAMINA score is twelve"
        assert sources[0] in ("tesseract", "apple")
        assert distances[0] <= 0.2

    def test_align_and_vote_three_engine_confidence_breaks_tie(self):
        """When all three differ, confidence should drive the selection."""
        _, align_and_vote = self.get_fusion_functions()
        engines = {
            "tesseract": ["STAMIN4 score is twelve"],
            "apple": ["STAMINA score is twelve"],
            "easyocr": ["STAMINA score is twelue"],
        }
        fused, sources, _ = align_and_vote(
            engines,
            None,
            confidences_by_engine={"tesseract": [0.4], "apple": [0.95]},
        )
        assert fused[0] == "STAMINA score is twelve"
        assert sources[0] == "apple"


class TestInlineEscalation:
    """Tests for R6: inline vision escalation functions."""

    def get_escalation_functions(self):
        """Import the escalation functions from the OCR module."""
        from modules.extract.extract_ocr_ensemble_v1.main import (
            is_critical_failure,
            encode_image_base64,
        )
        return is_critical_failure, encode_image_base64

    def test_is_critical_failure_high_corruption(self):
        """High corruption should trigger critical failure."""
        is_critical_failure, _ = self.get_escalation_functions()
        metrics = {
            "corruption_score": 0.9,
            "disagree_rate": 0.2,
            "line_count": 20,
            "missing_content_score": 0.1,
        }
        assert is_critical_failure(metrics) is True

    def test_is_critical_failure_high_disagree(self):
        """High disagree rate should trigger critical failure."""
        is_critical_failure, _ = self.get_escalation_functions()
        metrics = {
            "corruption_score": 0.2,
            "disagree_rate": 0.85,
            "line_count": 20,
            "missing_content_score": 0.1,
        }
        assert is_critical_failure(metrics) is True

    def test_is_critical_failure_few_lines_and_missing(self):
        """Very few lines with missing content should trigger critical failure."""
        is_critical_failure, _ = self.get_escalation_functions()
        metrics = {
            "corruption_score": 0.3,
            "disagree_rate": 0.2,
            "line_count": 2,
            "missing_content_score": 0.75,
        }
        assert is_critical_failure(metrics) is True

    def test_is_critical_failure_normal_page(self):
        """Normal quality page should not trigger critical failure."""
        is_critical_failure, _ = self.get_escalation_functions()
        metrics = {
            "corruption_score": 0.1,
            "disagree_rate": 0.1,
            "line_count": 25,
            "missing_content_score": 0.1,
        }
        assert is_critical_failure(metrics) is False

    def test_is_critical_failure_moderate_issues(self):
        """Moderate issues should not trigger critical failure (below threshold)."""
        is_critical_failure, _ = self.get_escalation_functions()
        metrics = {
            "corruption_score": 0.5,  # Below 0.8
            "disagree_rate": 0.5,  # Below 0.8
            "line_count": 15,
            "missing_content_score": 0.3,
        }
        assert is_critical_failure(metrics) is False

    def test_is_critical_failure_custom_thresholds(self):
        """Custom thresholds should be respected."""
        is_critical_failure, _ = self.get_escalation_functions()
        metrics = {
            "corruption_score": 0.6,
            "disagree_rate": 0.5,
            "line_count": 15,
            "missing_content_score": 0.3,
        }
        # With default thresholds (0.8), this should NOT be critical
        assert is_critical_failure(metrics) is False
        # With lower threshold (0.5), this SHOULD be critical
        assert is_critical_failure(metrics, corruption_threshold=0.5) is True

    def test_is_critical_failure_form_page_low_ivr(self):
        """Form pages with very low IVR should trigger critical failure."""
        is_critical_failure, _ = self.get_escalation_functions()
        metrics = {
            "corruption_score": 0.0,  # No corruption detected
            "disagree_rate": 0.55,  # Moderate disagreement
            "line_count": 20,
            "missing_content_score": 0.0,
        }
        # Without form flag and with normal thresholds, not critical
        assert is_critical_failure(metrics) is False
        # With form flag and low IVR, should be critical
        assert is_critical_failure(metrics, is_form_page=True, ivr=0.1) is True
        # Form page with higher IVR, not critical
        assert is_critical_failure(metrics, is_form_page=True, ivr=0.5) is False

    def test_is_critical_failure_form_page_moderate_disagree_low_ivr(self):
        """Form pages with moderate disagreement and low IVR should be critical."""
        is_critical_failure, _ = self.get_escalation_functions()
        metrics = {
            "corruption_score": 0.0,
            "disagree_rate": 0.55,  # Above 0.5
            "line_count": 25,
            "missing_content_score": 0.0,
        }
        # Form with disagree > 0.5 and IVR < 0.4 is critical
        assert is_critical_failure(metrics, is_form_page=True, ivr=0.35) is True
        # Form with disagree > 0.5 but IVR > 0.4 is not critical
        assert is_critical_failure(metrics, is_form_page=True, ivr=0.45) is False

    def test_is_critical_failure_form_page_high_fragmentation(self):
        """Form pages with high fragmentation should be critical."""
        is_critical_failure, _ = self.get_escalation_functions()
        metrics = {
            "corruption_score": 0.0,
            "disagree_rate": 0.2,
            "line_count": 30,
            "missing_content_score": 0.0,
            "fragmentation_score": 0.35,  # High fragmentation
        }
        # Form with high fragmentation and low IVR is critical
        assert is_critical_failure(metrics, is_form_page=True, ivr=0.4) is True
        # Form with high fragmentation but high IVR is not critical
        assert is_critical_failure(metrics, is_form_page=True, ivr=0.6) is False


class TestFragmentFilter:
    """Tests for Task 5.2: filter_fragment_artifacts function."""

    def get_filter_function(self):
        """Import the filter function from the OCR module."""
        from modules.extract.extract_ocr_ensemble_v1.main import filter_fragment_artifacts
        return filter_fragment_artifacts

    def test_filter_trailing_fragments(self):
        """Trailing fragment cluster should be filtered."""
        filter_func = self.get_filter_function()
        # Simulate page 007L pattern with fragments at end
        # Fragments are short word endings from right column edges
        lines = [
            "There is also a LUCK box. Roll one die, add 6 to this",
            "number and enter this total in the LUCK box.",
            "Battles",
            "",
            "10",
            "his",   # fragment (3 chars)
            "LL.",   # fragment (3 chars)
            "ur-",   # fragment (3 chars) - hyphenated word ending
            "ser",   # fragment (3 chars)
            "es.",   # fragment (3 chars)
        ]
        filtered, removed, stats = filter_func(lines)
        assert stats["filtered"] is True
        assert len(removed) == 5  # Should remove 5 fragments
        assert "his" in removed
        assert "10" in filtered  # Page number preserved
        assert "Battles" in filtered  # Header preserved

    def test_preserve_page_numbers(self):
        """Digit-only lines (page numbers) should be preserved."""
        filter_func = self.get_filter_function()
        lines = [
            "Line one",
            "Line two",
            "Line three",
            "10",  # page number - should stay
            "his",
            "er",
            "LL.",
        ]
        filtered, removed, stats = filter_func(lines)
        assert "10" in filtered
        assert "10" not in removed

    def test_preserve_common_short_words(self):
        """Common short words like 'to', 'of', 'in' should not be filtered."""
        filter_func = self.get_filter_function()
        lines = [
            "Line one",
            "Line two",
            "to",   # common word - keep
            "of",   # common word - keep
            "his",  # fragment
            "er",   # fragment
            "LL.",  # fragment
        ]
        filtered, removed, stats = filter_func(lines)
        # Common words should be preserved
        assert "to" in filtered
        assert "of" in filtered

    def test_no_filter_without_cluster(self):
        """Should not filter if fragments aren't clustered at end."""
        filter_func = self.get_filter_function()
        lines = [
            "Line one",
            "er",  # fragment in middle
            "Line two",
            "LL.",  # fragment in middle
            "Line three",
            "Full sentence here",
        ]
        filtered, removed, stats = filter_func(lines)
        assert stats["filtered"] is False
        assert len(removed) == 0
        assert filtered == lines

    def test_too_few_lines_not_filtered(self):
        """Very short line lists should not be filtered."""
        filter_func = self.get_filter_function()
        lines = ["one", "two", "er"]
        filtered, removed, stats = filter_func(lines)
        assert stats["filtered"] is False
        assert stats["reason"] == "too_few_lines"

    def test_empty_lines_preserved(self):
        """Empty lines should be preserved (not treated as fragments)."""
        filter_func = self.get_filter_function()
        lines = [
            "Line one",
            "",
            "Line two",
            "",
            "Line three",
            "his",
            "er",
            "LL.",
        ]
        filtered, removed, stats = filter_func(lines)
        # Empty lines should remain
        assert "" in filtered

class TestSpellGarbleMetrics:
    def test_dictionary_score_flags_suspicious_consonant_oov(self):
        from modules.common.text_quality import spell_garble_metrics

        vocab = {"skill", "stamina", "luck"}
        metrics = spell_garble_metrics(["sxrLL"], vocab=set(vocab))
        assert metrics["dictionary_oov_words"] >= 1
        assert metrics["dictionary_suspicious_oov_words"] >= 1
        assert metrics["dictionary_score"] >= 0.5
        # Alpha-only confusion (x↔k, r↔i) should be detected as a fixable-to-vocab token.
        assert metrics["char_confusion_alpha_fixed_words"] >= 1
        alpha_examples = [w for (w, _n) in metrics["char_confusion_alpha_fixed_examples"]]
        assert any("sxrLL->skill" == e or "sxrLL->skill" in e for e in alpha_examples)

    def test_char_confusion_score_flags_mixed_alnum_tokens(self):
        from modules.common.text_quality import spell_garble_metrics

        vocab = {"you", "are", "following", "start", "to", "peter", "out", "as"}
        metrics = spell_garble_metrics(["y0u 4re f0110win9 5t4rt t0 peter 0ut 45."], vocab=set(vocab))
        assert metrics["char_confusion_mixed_ratio"] > 0.0
        assert metrics["char_confusion_score"] > 0.0
        examples = [w for (w, _n) in metrics["char_confusion_examples"]]
        assert any("y0u" in e or "f0110win9" in e for e in examples)
        # Digit confusion should be detected even for short tokens like y0u/t0 when they map to vocab words.
        assert metrics["char_confusion_digit_fixed_words"] >= 1
        digit_examples = [w for (w, _n) in metrics["char_confusion_digit_fixed_examples"]]
        assert any("y0u->you" in e or "t0->to" in e for e in digit_examples)

    def test_enhanced_quality_metrics_exposes_spell_fields(self):
        from modules.extract.extract_ocr_ensemble_v1.main import compute_enhanced_quality_metrics

        q = compute_enhanced_quality_metrics(["sxrLL"], {}, disagreement=0.0, disagree_rate=0.0)
        assert "dictionary_score" in q
        assert "char_confusion_score" in q

    def test_escalation_reasons_include_dictionary_oov(self):
        from modules.extract.extract_ocr_ensemble_v1.main import (
            compute_enhanced_quality_metrics,
            compute_escalation_reasons,
        )

        q = compute_enhanced_quality_metrics(["sxrLL"], {}, disagreement=0.0, disagree_rate=0.0)
        reasons = compute_escalation_reasons(
            disagreement=0.0,
            disagree_rate=0.0,
            quality_metrics=q,
            line_count=1,
            avg_len=5.0,
            escalation_threshold=1.0,
        )
        assert "dictionary_oov" in reasons

    def test_escalation_reasons_include_char_confusion(self):
        from modules.extract.extract_ocr_ensemble_v1.main import (
            compute_enhanced_quality_metrics,
            compute_escalation_reasons,
        )

        q = compute_enhanced_quality_metrics(
            ["y0u 4re f0110win9 5t4rt t0 peter 0ut 45."],
            {},
            disagreement=0.0,
            disagree_rate=0.0,
        )
        reasons = compute_escalation_reasons(
            disagreement=0.0,
            disagree_rate=0.0,
            quality_metrics=q,
            line_count=1,
            avg_len=10.0,
            escalation_threshold=1.0,
        )
        assert "char_confusion" in reasons


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
