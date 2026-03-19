"""Tests for build_chapter_html_v1 — HTML5 structure, image integration, navigation."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup

from modules.build.build_chapter_html_v1.main import (
    _attach_images,
    _is_likely_caption,
    _html5_wrap,
    _add_table_scope,
    _build_nav,
    _merge_contiguous_genealogy_tables,
    _normalize_heading_breaks,
    _refine_chapter_segments,
    _strip_headers_and_numbers,
    _stitch_page_breaks,
    _titles_related,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PAGE_HTML = '<p>Some text.</p><img alt="Photo"><p>More text.</p>'
SAMPLE_PAGE_HTML_MULTI = '<p>Text.</p><img alt="A"><img alt="B"><p>End.</p>'
SAMPLE_PAGE_HTML_NO_IMG = '<p>Just text, no images here.</p>'
SAMPLE_PAGE_HTML_COUNTED = '<img alt="Two photographs" data-count="2"><p>More text.</p>'
SAMPLE_PAGE_HTML_SWAPPED = (
    "<p>The ten pound bags were dyed into different colors which were then cut "
    "into squares and made into</p>"
    "<img alt=\"Photo of Leonidas and Josephine L'Heureux seated together\">"
    "<p><em>Leonidas and Josephine (second wife) L'Heureux.</em></p>"
    "<img alt=\"Oval portrait of Laetitia L'Heureux\">"
    "<p><em>Mrs. Leonidas L'Heureux (Laetitia - first wife).</em></p>"
    "<p>colorful bedspreads.</p>"
)


def _crop(filename: str, alt: str = "", image_description: str = "",
          caption_text: str = None) -> dict:
    """Helper to build a minimal crop record."""
    return {
        "filename": filename,
        "alt": alt,
        "image_description": image_description,
        "caption_text": caption_text,
        "bbox": {"x0": 0, "y0": 0, "x1": 100, "y1": 100},
        "source_page": 1,
    }


# ---------------------------------------------------------------------------
# T4: Rich alt text
# ---------------------------------------------------------------------------

class TestRichAltText:
    def test_prefers_image_description_over_alt(self):
        crops = [_crop("img.jpg", alt="Photo", image_description="Portrait of a man in uniform")]
        result = _attach_images(SAMPLE_PAGE_HTML, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        img = soup.find("img")
        assert img["alt"] == "Portrait of a man in uniform"

    def test_falls_back_to_alt_when_no_description(self):
        crops = [_crop("img.jpg", alt="Photo", image_description="")]
        result = _attach_images(SAMPLE_PAGE_HTML, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        img = soup.find("img")
        assert img["alt"] == "Photo"

    def test_empty_alt_when_nothing_available(self):
        crops = [_crop("img.jpg")]
        result = _attach_images(SAMPLE_PAGE_HTML, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        img = soup.find("img")
        assert img["alt"] == ""


# ---------------------------------------------------------------------------
# T5: <figure>/<figcaption> wrapping
# ---------------------------------------------------------------------------

class TestFigureWrapping:
    def test_img_wrapped_in_figure(self):
        crops = [_crop("img.jpg")]
        result = _attach_images(SAMPLE_PAGE_HTML, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        figures = soup.find_all("figure")
        assert len(figures) == 1
        assert figures[0].find("img") is not None

    def test_figcaption_when_caption_text_present(self):
        crops = [_crop("img.jpg", caption_text="Arthur L'Heureux, circa 1942")]
        result = _attach_images(SAMPLE_PAGE_HTML, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        figcaption = soup.find("figcaption")
        assert figcaption is not None
        assert figcaption.string == "Arthur L'Heureux, circa 1942"

    def test_no_figcaption_when_no_caption(self):
        crops = [_crop("img.jpg")]
        result = _attach_images(SAMPLE_PAGE_HTML, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        assert soup.find("figcaption") is None

    def test_multiple_images_each_get_figure(self):
        crops = [_crop("a.jpg", caption_text="Cap A"), _crop("b.jpg")]
        result = _attach_images(SAMPLE_PAGE_HTML_MULTI, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        figures = soup.find_all("figure")
        assert len(figures) == 2
        # First has caption, second doesn't
        captions = soup.find_all("figcaption")
        assert len(captions) == 1
        assert captions[0].string == "Cap A"


# ---------------------------------------------------------------------------
# Caption heuristic detection (Story 009)
# ---------------------------------------------------------------------------

class TestCaptionHeuristic:
    """Test _is_likely_caption for identifying caption text near images."""

    def test_name_with_date(self):
        assert _is_likely_caption("Moise and Sophie L'Heureux about 1910")

    def test_anniversary_caption(self):
        assert _is_likely_caption("Henry and Alma Alain on their 50th wedding anniversary in 1957.")

    def test_family_name(self):
        assert _is_likely_caption("Moise and Sophie's Family")

    def test_row_label(self):
        assert _is_likely_caption("Back Row: George, Marie Louise, Father Cochin")

    def test_circa(self):
        assert _is_likely_caption("Arthur L'Heureux, circa 1942")

    def test_left_to_right(self):
        assert _is_likely_caption("Left to right: Arthur, Marie, Sophie")

    def test_generic_prose_rejected(self):
        assert not _is_likely_caption("More text.")

    def test_narrative_opener_rejected(self):
        assert not _is_likely_caption("The family moved west in the spring of that year.")

    def test_long_text_rejected(self):
        assert not _is_likely_caption("This is a very long paragraph that goes on and on "
                                      "and on with many many words exceeding the caption limit "
                                      "which should not be treated as a caption")

    def test_empty_string(self):
        assert not _is_likely_caption("")

    def test_single_lowercase_word(self):
        assert not _is_likely_caption("hello")


class TestCaptionAbsorption:
    """Test that _attach_images absorbs adjacent caption <p> tags."""

    def test_absorbs_caption_with_date(self):
        html = '<img alt="Photo"><p>Moise and Sophie about 1910</p><p>Regular paragraph.</p>'
        crops = [_crop("img.jpg")]
        result = _attach_images(html, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        figcaption = soup.find("figcaption")
        assert figcaption is not None
        assert "1910" in figcaption.get_text()
        # Regular paragraph should NOT be absorbed
        remaining_p = soup.find_all("p")
        assert any("Regular paragraph" in p.get_text() for p in remaining_p)

    def test_does_not_absorb_narrative(self):
        html = '<img alt="Photo"><p>The family moved west after the war.</p>'
        crops = [_crop("img.jpg")]
        result = _attach_images(html, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        assert soup.find("figcaption") is None

    def test_crop_caption_takes_priority(self):
        """When crop pipeline provides caption_text, use it over heuristic."""
        html = '<img alt="Photo"><p>Moise L\'Heureux 1910</p>'
        crops = [_crop("img.jpg", caption_text="VLM-provided caption")]
        result = _attach_images(html, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        figcaption = soup.find("figcaption")
        assert figcaption is not None
        assert figcaption.string == "VLM-provided caption"

    def test_existing_figure_preserved(self):
        """New OCR format: <figure> already wraps <img>. Don't double-wrap."""
        html = '<figure><img alt="Photo"><figcaption>Existing caption</figcaption></figure>'
        crops = [_crop("img.jpg")]
        result = _attach_images(html, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        figures = soup.find_all("figure")
        assert len(figures) == 1
        figcaption = soup.find("figcaption")
        assert figcaption is not None
        assert "Existing caption" in figcaption.get_text()

    def test_existing_figure_gets_crop_caption(self):
        """<figure> without <figcaption> gets caption from crop pipeline."""
        html = '<figure><img alt="Photo"></figure>'
        crops = [_crop("img.jpg", caption_text="From crop pipeline")]
        result = _attach_images(html, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        figcaption = soup.find("figcaption")
        assert figcaption is not None
        assert figcaption.string == "From crop pipeline"


# ---------------------------------------------------------------------------
# T3: Robust image matching
# ---------------------------------------------------------------------------

class TestImageMatching:
    def test_more_tags_than_crops(self):
        """Extra <img> tags should be left alone, not crash."""
        crops = [_crop("img.jpg")]
        result = _attach_images(SAMPLE_PAGE_HTML_MULTI, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        imgs = soup.find_all("img")
        assert len(imgs) == 2
        assert imgs[0].get("src") == "images/img.jpg"
        assert imgs[1].get("src") is None  # unmatched

    def test_more_crops_than_tags(self):
        """Extra crops should be ignored, not crash."""
        crops = [_crop("a.jpg"), _crop("b.jpg"), _crop("c.jpg")]
        result = _attach_images(SAMPLE_PAGE_HTML, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        imgs = soup.find_all("img")
        assert len(imgs) == 1
        assert imgs[0].get("src") == "images/a.jpg"

    def test_no_crops_returns_html_unchanged(self):
        result = _attach_images(SAMPLE_PAGE_HTML, [], "images")
        assert result == SAMPLE_PAGE_HTML

    def test_no_html_returns_empty(self):
        result = _attach_images("", [_crop("img.jpg")], "images")
        assert result == ""

    def test_sets_src_and_data_attribute(self):
        crops = [_crop("photo.jpg")]
        result = _attach_images(SAMPLE_PAGE_HTML, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        img = soup.find("img")
        assert img["src"] == "images/photo.jpg"
        assert img["data-crop-filename"] == "photo.jpg"

    def test_expands_data_count_placeholders(self):
        crops = [_crop("a.jpg"), _crop("b.jpg")]
        result = _attach_images(SAMPLE_PAGE_HTML_COUNTED, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        imgs = soup.find_all("img")
        assert len(imgs) == 2
        assert imgs[0]["src"] == "images/a.jpg"
        assert imgs[1]["src"] == "images/b.jpg"

    def test_matches_crops_by_descriptor_not_manifest_order(self):
        crops = [
            _crop(
                "single.jpg",
                alt="Photo of Leonidas and Josephine L'Heureux seated together",
                image_description="Oval portrait of Laetitia L'Heureux",
            ),
            _crop(
                "couple.jpg",
                alt="Oval portrait of Laetitia L'Heureux",
                image_description="Photo of Leonidas and Josephine L'Heureux seated together",
            ),
        ]
        result = _attach_images(SAMPLE_PAGE_HTML_SWAPPED, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        figures = soup.find_all("figure")
        assert len(figures) == 2
        assert figures[0].find("img")["src"] == "images/couple.jpg"
        assert "Leonidas and Josephine" in figures[0].find("figcaption").get_text()
        assert figures[1].find("img")["src"] == "images/single.jpg"
        assert "Laetitia" in figures[1].find("figcaption").get_text()


class TestFigurePlacementNormalization:
    def test_stitches_sentence_split_by_figure_run(self):
        crops = [
            _crop(
                "single.jpg",
                alt="Photo of Leonidas and Josephine L'Heureux seated together",
                image_description="Oval portrait of Laetitia L'Heureux",
            ),
            _crop(
                "couple.jpg",
                alt="Oval portrait of Laetitia L'Heureux",
                image_description="Photo of Leonidas and Josephine L'Heureux seated together",
            ),
        ]
        result = _attach_images(SAMPLE_PAGE_HTML_SWAPPED, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        paragraphs = soup.find_all("p")
        assert paragraphs[0].get_text(" ", strip=True) == (
            "The ten pound bags were dyed into different colors which were then "
            "cut into squares and made into colorful bedspreads."
        )
        assert len(paragraphs) == 1

    def test_keeps_figure_between_complete_paragraphs(self):
        crops = [_crop("photo.jpg")]
        result = _attach_images(SAMPLE_PAGE_HTML, crops, "images")
        soup = BeautifulSoup(result, "html.parser")
        paragraphs = soup.find_all("p")
        assert len(paragraphs) == 2
        assert paragraphs[0].get_text(" ", strip=True) == "Some text."
        assert paragraphs[1].get_text(" ", strip=True) == "More text."


# ---------------------------------------------------------------------------
# T6: HTML5 document wrapper
# ---------------------------------------------------------------------------

class TestHtml5Wrapper:
    def test_has_doctype(self):
        html = _html5_wrap("<p>Hello</p>", "Test Page")
        assert html.startswith("<!DOCTYPE html>")

    def test_has_charset_and_viewport(self):
        html = _html5_wrap("<p>Hello</p>", "Test Page")
        assert '<meta charset="utf-8">' in html
        assert 'name="viewport"' in html

    def test_has_title(self):
        html = _html5_wrap("<p>Hello</p>", "My Chapter")
        assert "<title>My Chapter</title>" in html

    def test_escapes_title(self):
        html = _html5_wrap("<p>Hello</p>", "A & B <script>")
        assert "A &amp; B &lt;script&gt;" in html

    def test_has_embedded_css(self):
        html = _html5_wrap("<p>Hello</p>", "Test")
        assert "<style>" in html
        assert "max-width" in html

    def test_wraps_in_article(self):
        html = _html5_wrap("<p>Content</p>", "Test")
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("article") is not None
        assert soup.find("article").find("p") is not None

    def test_includes_nav(self):
        nav = _build_nav("prev.html", "Prev", "next.html", "Next")
        html = _html5_wrap("<p>Body</p>", "Test", nav_html_top=nav)
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("nav") is not None

    def test_no_external_urls(self):
        """Output must be self-contained — no http:// or https:// in CSS or HTML."""
        html = _html5_wrap("<p>Hello</p>", "Test")
        assert "http://" not in html
        assert "https://" not in html


# ---------------------------------------------------------------------------
# T8: Navigation
# ---------------------------------------------------------------------------

class TestNavigation:
    def test_prev_and_next(self):
        nav = _build_nav("ch1.html", "Ch 1", "ch3.html", "Ch 3")
        assert 'href="ch1.html"' in nav
        assert 'href="ch3.html"' in nav
        assert 'href="index.html"' in nav

    def test_no_prev(self):
        nav = _build_nav(None, None, "ch2.html", "Ch 2")
        assert "nav-placeholder" in nav
        assert 'href="ch2.html"' in nav

    def test_no_next(self):
        nav = _build_nav("ch1.html", "Ch 1", None, None)
        assert 'href="ch1.html"' in nav
        assert "nav-placeholder" in nav

    def test_bottom_nav_class(self):
        nav = _build_nav("a.html", "A", "b.html", "B", is_bottom=True)
        assert "bottom" in nav


# ---------------------------------------------------------------------------
# T10: Table scope attributes
# ---------------------------------------------------------------------------

class TestTableScope:
    def test_adds_scope_col_to_header_row(self):
        html = "<table><tr><th>Name</th><th>Age</th></tr><tr><td>A</td><td>1</td></tr></table>"
        result = _add_table_scope(html)
        soup = BeautifulSoup(result, "html.parser")
        ths = soup.find_all("th")
        assert all(th.get("scope") == "col" for th in ths)

    def test_adds_scope_row_to_first_col(self):
        html = "<table><tr><th>H1</th><th>H2</th></tr><tr><th>Row1</th><td>Val</td></tr></table>"
        result = _add_table_scope(html)
        soup = BeautifulSoup(result, "html.parser")
        body_th = soup.find_all("tr")[1].find("th")
        assert body_th.get("scope") == "row"

    def test_no_tables_returns_unchanged(self):
        html = "<p>No tables here</p>"
        assert _add_table_scope(html) == html

    def test_preserves_existing_scope(self):
        html = '<table><tr><th scope="colgroup">X</th></tr></table>'
        result = _add_table_scope(html)
        soup = BeautifulSoup(result, "html.parser")
        th = soup.find("th")
        assert th.get("scope") == "colgroup"


# ---------------------------------------------------------------------------
# Strip headers
# ---------------------------------------------------------------------------

class TestStripHeaders:
    def test_removes_page_numbers(self):
        html = '<p>Text</p><span class="page-number">42</span>'
        result = _strip_headers_and_numbers(html)
        assert "42" not in result
        assert "Text" in result

    def test_removes_running_heads(self):
        html = '<div class="running-head">CHAPTER 1</div><p>Body</p>'
        result = _strip_headers_and_numbers(html)
        assert "CHAPTER 1" not in result
        assert "Body" in result

    def test_empty_html(self):
        assert _strip_headers_and_numbers("") == ""


# ---------------------------------------------------------------------------
# Structure refinement
# ---------------------------------------------------------------------------

class TestStructureRefinement:
    def test_normalizes_cosmetic_heading_breaks(self):
        html = "<h1>JOSEPHINE<br>(L'HEUREUX ) ALAIN</h1>"
        result = _normalize_heading_breaks(html)
        assert "<br" not in result
        assert "JOSEPHINE (L'HEUREUX ) ALAIN" in result

    def test_title_matching_does_not_confuse_single_letter_last_name_tokens(self):
        assert _titles_related("Wilfrid L'Heureux", "Wilfred")
        assert not _titles_related("LEONIDAS L'HEUREUX", "ARTHUR L'HEUREUX")

    def test_refines_coarse_span_into_multiple_owner_segments(self):
        pages = [
            {
                "html": "<h1>JOSEPHINE (L'HEUREUX ) ALAIN</h1><p>Josephine text.</p>",
                "page_number": 48,
                "printed_page_number": 48,
                "owner_heading": "JOSEPHINE (L'HEUREUX ) ALAIN",
            },
            {
                "html": "<h1>Josephine L'Heureux Alain</h1><p>More Josephine.</p>",
                "page_number": 49,
                "printed_page_number": 49,
                "owner_heading": "Josephine L'Heureux Alain",
            },
            {
                "html": "<h1>PAUL L'HEUREUX</h1><p>Paul text.</p>",
                "page_number": 50,
                "printed_page_number": 50,
                "owner_heading": "PAUL L'HEUREUX",
            },
        ]
        segments = _refine_chapter_segments("Leonidas", 37, pages, ["Leonidas", "Josephine", "Paul", "George"])
        assert [segment["title"] for segment in segments] == [
            "JOSEPHINE (L'HEUREUX ) ALAIN",
            "PAUL L'HEUREUX",
        ]
        assert segments[0]["page_start"] == 48
        assert segments[0]["page_end"] == 49
        assert segments[1]["page_start"] == 50

    def test_marks_leading_pages_for_carry_back_when_stale_span_reaches_new_owner(self):
        pages = [
            {
                "html": "<p>Blank spacer page.</p>",
                "page_number": 107,
                "printed_page_number": 98,
                "owner_heading": None,
            },
            {
                "html": "<h1>PIERRE L'HEUREUX</h1><p>Pierre text.</p>",
                "page_number": 108,
                "printed_page_number": 99,
                "owner_heading": "PIERRE L'HEUREUX",
            },
        ]
        segments = _refine_chapter_segments(
            "Wilfred",
            98,
            pages,
            ["Wilfred", "Pierre", "Antoine"],
            stale_portion=True,
        )
        assert len(segments) == 2
        assert segments[0]["carry_back"] is True
        assert segments[0]["title"] == "Wilfred"
        assert segments[0]["page_start"] == 98
        assert segments[0]["page_end"] == 98
        assert segments[1]["title"] == "PIERRE L'HEUREUX"
        assert segments[1]["page_start"] == 99
        assert segments[1]["page_end"] == 99

    def test_accepts_minor_title_spelling_drift(self):
        pages = [
            {
                "html": "<h1>Wilfrid L'Heureux</h1><p>Wilfrid text.</p>",
                "page_number": 102,
                "printed_page_number": 93,
                "owner_heading": "Wilfrid L'Heureux",
            },
        ]
        segments = _refine_chapter_segments("Wilfred", 93, pages, ["Wilfred", "Pierre", "Antoine"])
        assert len(segments) == 1
        assert segments[0]["title"] == "Wilfrid L'Heureux"

    def test_carry_backs_entire_stale_anonymous_span(self):
        pages = [
            {
                "html": "<table><tr><td>Tail rows.</td></tr></table>",
                "page_number": 98,
                "printed_page_number": 89,
                "owner_heading": None,
            },
        ]
        segments = _refine_chapter_segments(
            "Roseanna",
            89,
            pages,
            ["Roseanna", "Antoinette", "Emilie"],
            stale_portion=True,
        )
        assert len(segments) == 1
        assert segments[0]["carry_back"] is True
        assert segments[0]["title"] == "Roseanna"
        assert segments[0]["page_start"] == 89
        assert segments[0]["page_end"] == 89

    def test_carry_backs_prefix_when_first_heading_matches_previous_chapter(self):
        pages = [
            {
                "html": "<h1>George L'Heureux</h1><p>George genealogy starts.</p>",
                "page_number": 62,
                "printed_page_number": 53,
                "owner_heading": "George L'Heureux",
            },
            {
                "html": "<table><tr><td>George continuation.</td></tr></table>",
                "page_number": 63,
                "printed_page_number": 54,
                "owner_heading": None,
            },
            {
                "html": "<h1>JOE (JOSEPH) L'HEUREUX</h1><p>Joe intro.</p>",
                "page_number": 66,
                "printed_page_number": 57,
                "owner_heading": "JOE (JOSEPH) L'HEUREUX",
            },
        ]
        segments = _refine_chapter_segments(
            "Paul",
            53,
            pages,
            ["Paul", "George", "Joe"],
            previous_title="GEORGE L'HEUREUX",
        )
        assert len(segments) == 2
        assert segments[0]["carry_back"] is True
        assert segments[0]["title"] == "GEORGE L'HEUREUX"
        assert segments[0]["page_start"] == 53
        assert segments[0]["page_end"] == 54
        assert segments[1]["title"] == "JOE (JOSEPH) L'HEUREUX"
        assert segments[1]["page_start"] == 57

    def test_previous_title_does_not_swallow_late_new_owner_after_anonymous_prefix(self):
        pages = [
            {
                "html": "<table><tr><td>Arthur genealogy tail.</td></tr></table>",
                "page_number": 35,
                "printed_page_number": 26,
                "owner_heading": None,
            },
            {
                "html": "<table><tr><td>More Arthur genealogy.</td></tr></table>",
                "page_number": 36,
                "printed_page_number": 27,
                "owner_heading": None,
            },
            {
                "html": "<h1>LEONIDAS L'HEUREUX</h1><p>Leonidas intro.</p>",
                "page_number": 38,
                "printed_page_number": 29,
                "owner_heading": "LEONIDAS L'HEUREUX",
            },
        ]
        segments = _refine_chapter_segments(
            "Arthur",
            26,
            pages,
            ["Arthur", "Leonidas", "Josephine"],
            previous_title="ARTHUR L'HEUREUX",
            stale_portion=True,
        )
        assert len(segments) == 2
        assert segments[0]["carry_back"] is True
        assert segments[0]["title"] == "Arthur"
        assert segments[0]["page_start"] == 26
        assert segments[0]["page_end"] == 27
        assert segments[1]["title"] == "LEONIDAS L'HEUREUX"
        assert segments[1]["page_start"] == 29

    def test_carry_backs_entire_portion_when_first_heading_matches_previous_chapter(self):
        pages = [
            {
                "html": "<h1>Marie Louise L'Heureux LaClare</h1><p>Marie-Louise genealogy.</p>",
                "page_number": 80,
                "printed_page_number": 71,
                "owner_heading": "Marie Louise L'Heureux LaClare",
            },
            {
                "html": "<table><tr><td>More genealogy.</td></tr></table>",
                "page_number": 81,
                "printed_page_number": 72,
                "owner_heading": None,
            },
        ]
        segments = _refine_chapter_segments(
            "Mathilda",
            71,
            pages,
            ["Mathilda", "Marie-Louise", "Roseanna"],
            previous_title="MARIE-LOUISE (L'HEUREUX) LaCLARE",
        )
        assert len(segments) == 1
        assert segments[0]["carry_back"] is True
        assert segments[0]["title"] == "MARIE-LOUISE (L'HEUREUX) LaCLARE"
        assert segments[0]["page_start"] == 71
        assert segments[0]["page_end"] == 72

    def test_retitles_from_first_page_heading_even_when_not_in_toc(self):
        pages = [
            {
                "html": "<h1><strong><em>I WISH</em></strong></h1><p>Closing page.</p>",
                "page_number": 118,
                "printed_page_number": 109,
                "owner_heading": "I WISH",
            },
        ]
        segments = _refine_chapter_segments("Antoine", 109, pages, ["Antoine"])
        assert len(segments) == 1
        assert segments[0]["title"] == "I WISH"

    def test_allows_late_non_toc_heading_after_stale_leading_pages(self):
        pages = [
            {
                "html": "<p>109</p>",
                "page_number": 118,
                "printed_page_number": 109,
                "owner_heading": None,
            },
            {
                "html": "<p>110</p>",
                "page_number": 119,
                "printed_page_number": 110,
                "owner_heading": None,
            },
            {
                "html": "<h1><strong><em>I WISH</em></strong></h1><p>Closing page.</p>",
                "page_number": 120,
                "printed_page_number": 111,
                "owner_heading": "I WISH",
            },
        ]
        segments = _refine_chapter_segments(
            "Antoine",
            109,
            pages,
            ["Antoine"],
            stale_portion=True,
        )
        assert len(segments) == 2
        assert segments[0]["carry_back"] is True
        assert segments[0]["page_start"] == 109
        assert segments[0]["page_end"] == 110
        assert segments[1]["title"] == "I WISH"
        assert segments[1]["page_start"] == 111

    def test_does_not_split_on_non_toc_family_heading(self):
        pages = [
            {
                "html": "<h1>ARTHUR L'HEUREUX</h1><p>Arthur text.</p>",
                "page_number": 26,
                "printed_page_number": 26,
                "owner_heading": "ARTHUR L'HEUREUX",
            },
            {
                "html": "<h1>NOEL'S FAMILY</h1><p>Subfamily table.</p>",
                "page_number": 27,
                "printed_page_number": 27,
                "owner_heading": "NOEL'S FAMILY",
            },
        ]
        segments = _refine_chapter_segments("Arthur", 26, pages, ["Arthur", "Leonidas", "Josephine"])
        assert len(segments) == 1
        assert segments[0]["title"] == "ARTHUR L'HEUREUX"

    def test_stitches_page_break_continuations(self):
        result = _stitch_page_breaks([
            "<p>Dad sold the land and put up an addition to</p>",
            "<p>be the store and post office.</p>",
        ])
        soup = BeautifulSoup(result, "html.parser")
        paragraphs = soup.find_all("p")
        assert len(paragraphs) == 1
        assert "addition to be the store and post office." in paragraphs[0].get_text(" ", strip=True)

    def test_keeps_distinct_paragraphs_when_sentence_is_complete(self):
        result = _stitch_page_breaks([
            "<p>Dad sold the land and moved home.</p>",
            "<p>He later opened the store.</p>",
        ])
        soup = BeautifulSoup(result, "html.parser")
        assert len(soup.find_all("p")) == 2

    def test_stitches_page_break_when_figure_run_ends_page(self):
        result = _stitch_page_breaks([
            (
                "<p>In 1931, after his father passed away, George bought his ranch "
                "and used his Twin City tractor and 51</p>"
                "<figure><img alt=\"Mrs. George\"></figure>"
            ),
            "<p>steel wheels. Around 1940, a salesman came by.</p>",
        ])
        soup = BeautifulSoup(result, "html.parser")
        paragraphs = soup.find_all("p")
        assert "Twin City tractor and 51 steel wheels." in paragraphs[0].get_text(" ", strip=True)


class TestGenealogyMerging:
    def test_merge_contiguous_genealogy_tables_preserves_existing_image_attrs(self):
        html = """
        <h1>ALMA</h1>
        <figure data-placement="ocr-inline" data-caption-source="heuristic">
          <img src="images/page-022-000.jpg" alt="Portrait" data-crop-filename="page-022-000.jpg"/>
          <figcaption><strong><em>Henry and Alma Alain on their 50th wedding anniversary in 1957.</em></strong></figcaption>
        </figure>
        <table>
          <thead>
            <tr><th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY/GIRL</th><th>DIED</th></tr>
          </thead>
          <tbody>
            <tr><td>Alma</td><td>July 31, 1883</td><td>Apr. 8, 1907</td><td>Henry Alain</td><td>4 4</td><td>Dec. 15, 1982</td></tr>
          </tbody>
        </table>
        <h2>Alma's Grandchildren</h2>
        <h3>MARY PAULE'S FAMILY</h3>
        <table>
          <tbody>
            <tr><td>Ronald</td><td>Jan. 24, 1933</td><td>July 20, 1963</td><td>Jean Bailey</td><td>1</td><td>1</td></tr>
          </tbody>
        </table>
        """

        result = _merge_contiguous_genealogy_tables(html)
        soup = BeautifulSoup(result, "html.parser")
        figure = soup.find("figure")
        img = soup.find("img")

        assert figure is not None
        assert img is not None
        assert figure["data-placement"] == "ocr-inline"
        assert figure["data-caption-source"] == "heuristic"
        assert img["src"] == "images/page-022-000.jpg"
        assert img["data-crop-filename"] == "page-022-000.jpg"
        assert img["alt"] == "Portrait"

    def test_merge_contiguous_genealogy_tables_splits_flattened_context_headings(self):
        html = """
        <h1>ALMA</h1>
        <table>
          <thead>
            <tr><th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY/GIRL</th><th>DIED</th></tr>
          </thead>
          <tbody>
            <tr><td>Wayne</td><td>Aug. 23, 1946</td><td>Dec., 1966</td><td>Lynn LeBlue</td><td>2</td><td></td></tr>
          </tbody>
        </table>
        <h2>Alma's Grandchildren BERTHA'S FAMILY</h2>
        <table>
          <tbody>
            <tr><td>Norbert</td><td>July 3, 1939</td><td>Apr. 15, 1961</td><td>Shirley Allen</td><td>4</td><td></td></tr>
          </tbody>
        </table>
        <h2>Alma's Great Grandchildren Bertha's Grandchildren NORBERT'S FAMILY</h2>
        <table>
          <tbody>
            <tr><td>Michelle</td><td>Jan. 12, 1962</td></tr>
          </tbody>
        </table>
        """

        result = _merge_contiguous_genealogy_tables(html)
        soup = BeautifulSoup(result, "html.parser")
        subgroup_rows = [
            row.get_text(" ", strip=True)
            for row in soup.find_all("tr", class_="genealogy-subgroup-heading")
        ]

        assert subgroup_rows == [
            "Alma's Grandchildren",
            "BERTHA'S FAMILY",
            "Alma's Great Grandchildren",
            "Bertha's Grandchildren",
            "NORBERT'S FAMILY",
        ]

    def test_merge_contiguous_genealogy_tables_collapses_heading_table_runs(self):
        html = """
        <h1>ALMA</h1>
        <p>Intro paragraph.</p>
        <table>
          <thead>
            <tr><th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY/GIRL</th><th>DIED</th></tr>
          </thead>
          <tbody>
            <tr><td>Alma</td><td>July 31, 1883</td><td>Apr. 8, 1907</td><td>Henry Alain</td><td>4 4</td><td>Dec. 15, 1982</td></tr>
          </tbody>
        </table>
        <h2>Alma's Grandchildren</h2>
        <h3>MARY PAULE'S FAMILY</h3>
        <table>
          <tbody>
            <tr><td>Ronald</td><td>Jan. 24, 1933</td><td>July 20, 1963</td><td>Jean Bailey</td><td>1</td><td>1</td></tr>
          </tbody>
        </table>
        <p><strong>Alma's Great Grandchildren<br/>Mary Paule's Grandchildren<br/>RONALD'S FAMILY</strong></p>
        <table>
          <tbody>
            <tr><td>Kari Lou</td><td>Oct. 30, 1964</td></tr>
          </tbody>
        </table>
        <table>
          <tbody>
            <tr><td>TOTAL DESCENDANTS</td><td>83</td></tr>
            <tr><td>LIVING</td><td>78</td></tr>
            <tr><td>DECEASED</td><td>5</td></tr>
          </tbody>
        </table>
        """

        result = _merge_contiguous_genealogy_tables(html)
        soup = BeautifulSoup(result, "html.parser")
        tables = soup.find_all("table")

        assert len(tables) == 2
        assert [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])] == ["ALMA"]

        main_rows = tables[0].find("tbody").find_all("tr", recursive=False)
        subgroup_rows = [
            row.get_text(" ", strip=True)
            for row in main_rows
            if "genealogy-subgroup-heading" in (row.get("class") or [])
        ]
        assert subgroup_rows == [
            "Alma's Grandchildren",
            "MARY PAULE'S FAMILY",
            "Alma's Great Grandchildren",
            "Mary Paule's Grandchildren",
            "RONALD'S FAMILY",
        ]
        assert "Kari Lou" in tables[0].get_text(" ", strip=True)
        assert "TOTAL DESCENDANTS" in tables[1].get_text(" ", strip=True)

    def test_merge_contiguous_genealogy_tables_converts_name_list_paragraphs(self):
        html = """
        <h1>ARTHUR</h1>
        <table>
          <thead>
            <tr><th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY/GIRL</th><th>DIED</th></tr>
          </thead>
          <tbody>
            <tr><td>Noel</td><td>Jan. 1, 1940</td><td></td><td></td><td>2 1</td><td></td></tr>
          </tbody>
        </table>
        <h2>ULRIC'S FAMILY</h2>
        <p>Claire<br/>Duffy<br/>Robin</p>
        <h2>RENE'S FAMILY</h2>
        <table>
          <tbody>
            <tr><td>Barbara Jean</td><td>Sept. 28, 1949</td></tr>
          </tbody>
        </table>
        """

        result = _merge_contiguous_genealogy_tables(html)
        soup = BeautifulSoup(result, "html.parser")
        tables = soup.find_all("table")

        assert len(tables) == 1
        assert not any("Claire" in paragraph.get_text(" ", strip=True) for paragraph in soup.find_all("p"))
        subgroup_rows = [
            row.get_text(" ", strip=True)
            for row in tables[0].find("tbody").find_all("tr", recursive=False)
            if "genealogy-subgroup-heading" in (row.get("class") or [])
        ]
        assert "ULRIC'S FAMILY" in subgroup_rows
        assert "RENE'S FAMILY" in subgroup_rows

    def test_merge_contiguous_genealogy_tables_stitches_direct_adjacent_continuations(self):
        html = """
        <h1>ARTHUR</h1>
        <table>
          <thead>
            <tr><th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY</th><th>GIRL</th><th>DIED</th></tr>
          </thead>
          <tbody>
            <tr><td>Alice</td><td>Jan. 1, 1930</td><td></td><td></td><td>1</td><td>0</td><td></td></tr>
          </tbody>
        </table>
        <table>
          <thead>
            <tr><th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY</th><th>GIRL</th><th>DIED</th></tr>
          </thead>
          <tbody>
            <tr><td>Bob</td><td>Feb. 2, 1932</td><td></td><td></td><td>0</td><td>1</td><td></td></tr>
          </tbody>
        </table>
        <table>
          <tbody>
            <tr><td>TOTAL DESCENDANTS</td><td>2</td></tr>
          </tbody>
        </table>
        """

        result = _merge_contiguous_genealogy_tables(html)
        soup = BeautifulSoup(result, "html.parser")
        tables = soup.find_all("table")

        assert len(tables) == 2
        main_rows = tables[0].find("tbody").find_all("tr", recursive=False)
        assert [row.get_text(" ", strip=True) for row in main_rows] == [
            "Alice Jan. 1, 1930 1 0",
            "Bob Feb. 2, 1932 0 1",
        ]
        assert "TOTAL DESCENDANTS" in tables[1].get_text(" ", strip=True)

    def test_merge_contiguous_genealogy_tables_rewrites_left_column_heading_rows(self):
        html = """
        <table>
          <thead>
            <tr><th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY</th><th>GIRL</th><th>DIED</th></tr>
          </thead>
          <tbody>
            <tr><td>Alice</td><td>Jan. 1, 1930</td><td></td><td></td><td>1</td><td>0</td><td></td></tr>
            <tr><th><strong>Leonidas’ Great Great Grandchildren<br/>Alma’s Great Grandchildren<br/>Dolly’s Grandchildren<br/>SHARON’S FAMILY</strong></th><td></td><td></td><td></td><td></td><td></td><td></td></tr>
            <tr><td>Blaine</td><td>Aug. 16, 1971</td><td></td><td></td><td></td><td></td><td></td></tr>
          </tbody>
        </table>
        """

        result = _merge_contiguous_genealogy_tables(html)
        soup = BeautifulSoup(result, "html.parser")
        rows = soup.find("tbody").find_all("tr", recursive=False)

        assert [row.get_text(" ", strip=True) for row in rows[1:5]] == [
            "Leonidas’ Great Great Grandchildren",
            "Alma’s Great Grandchildren",
            "Dolly’s Grandchildren",
            "SHARON’S FAMILY",
        ]
        for row in rows[1:5]:
            assert "genealogy-subgroup-heading" in (row.get("class") or [])
            cells = row.find_all(["th", "td"], recursive=False)
            assert len(cells) == 1
            assert cells[0].get("colspan") == "7"

    def test_merge_contiguous_genealogy_tables_splits_flattened_generation_context_rows(self):
        html = """
        <table>
          <thead>
            <tr><th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY</th><th>GIRL</th><th>DIED</th></tr>
          </thead>
          <tbody>
            <tr><th>Leonidas’ Great Great Grandchildren Alma’s Great Grandchildren Dolly’s Grandchildren SHARON’S FAMILY</th><td></td><td></td><td></td><td></td><td></td><td></td></tr>
            <tr><td>Blaine</td><td>Aug. 16, 1971</td><td></td><td></td><td></td><td></td><td></td></tr>
          </tbody>
        </table>
        """

        result = _merge_contiguous_genealogy_tables(html)
        soup = BeautifulSoup(result, "html.parser")
        rows = soup.find("tbody").find_all("tr", recursive=False)

        assert [row.get_text(" ", strip=True) for row in rows[:4]] == [
            "Leonidas’ Great Great Grandchildren",
            "Alma’s Great Grandchildren",
            "Dolly’s Grandchildren",
            "SHARON’S FAMILY",
        ]
        assert rows[4].get_text(" ", strip=True) == "Blaine Aug. 16, 1971"

    def test_merge_contiguous_genealogy_tables_moves_death_value_out_of_girl_column(self):
        html = """
        <table>
          <thead>
            <tr><th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY</th><th>GIRL</th><th>DIED</th></tr>
          </thead>
          <tbody>
            <tr><td>Richard</td><td>, 1951</td><td></td><td></td><td></td><td>, 1956</td><td></td></tr>
          </tbody>
        </table>
        """

        result = _merge_contiguous_genealogy_tables(html)
        soup = BeautifulSoup(result, "html.parser")
        cells = soup.find("tbody").find("tr").find_all("td", recursive=False)
        assert [cell.get_text(" ", strip=True) for cell in cells] == [
            "Richard",
            ", 1951",
            "",
            "",
            "",
            "",
            ", 1956",
        ]

    def test_merge_contiguous_genealogy_tables_drops_repeated_body_header_rows(self):
        html = """
        <table>
          <thead>
            <tr><th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY</th><th>GIRL</th><th>DIED</th></tr>
          </thead>
          <tbody>
            <tr><td>Reginald</td><td>Apr. 3, 1953</td><td>June 29, 1974</td><td>Judy O'Keefe</td><td>2</td><td></td><td></td></tr>
          </tbody>
        </table>
        <table>
          <tbody>
            <tr><td><strong>Arthur's Great Grandchildren<br/>Alphonse's Grandchildren<br/>ROGER'S FAMILY</strong></td></tr>
            <tr><th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY/GIRL</th><th>DIED</th><td></td></tr>
            <tr><td>Danial</td><td>Mar. 3, 1973</td><td></td><td></td><td></td><td></td><td></td></tr>
            <tr><td>Diane</td><td>July 19, 1976</td><td></td><td></td><td></td><td></td><td></td></tr>
          </tbody>
        </table>
        """

        result = _merge_contiguous_genealogy_tables(html)
        soup = BeautifulSoup(result, "html.parser")
        tables = soup.find_all("table")

        assert len(tables) == 1
        assert result.count("BOY/GIRL") == 0
        assert result.count("BOY</th><th>GIRL") == 1

        repeated_headers = [
            row
            for row in tables[0].find("tbody").find_all("tr", recursive=False)
            if [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"], recursive=False)][:6]
            == ["NAME", "BORN", "MARRIED", "SPOUSE", "BOY/GIRL", "DIED"]
        ]
        assert repeated_headers == []

        subgroup_rows = [
            row.get_text(" ", strip=True)
            for row in tables[0].find("tbody").find_all("tr", class_="genealogy-subgroup-heading", recursive=False)
        ]
        assert subgroup_rows == [
            "Arthur's Great Grandchildren",
            "Alphonse's Grandchildren",
            "ROGER'S FAMILY",
        ]
        assert "Danial" in tables[0].get_text(" ", strip=True)
        assert "Diane" in tables[0].get_text(" ", strip=True)


# ---------------------------------------------------------------------------
# Integration: full pipeline via CLI
# ---------------------------------------------------------------------------

class TestCLIIntegration:
    """Run the module as a subprocess with fixture data and validate output."""

    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        # Create fake pipeline_state.json so _resolve_run_dir works
        (self.tmpdir / "pipeline_state.json").write_text("{}")

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_jsonl(self, path: Path, rows: list):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")

    def test_produces_valid_html5_output(self):
        pages_path = self.tmpdir / "pages.jsonl"
        portions_path = self.tmpdir / "portions.jsonl"
        out_path = self.tmpdir / "manifest.jsonl"
        html_dir = self.tmpdir / "html"

        self._write_jsonl(pages_path, [
            {"page_number": 1, "printed_page_number": 1, "html": "<p>Page one content.</p>"},
            {"page_number": 2, "printed_page_number": 2, "html": '<p>Page two.</p><img alt="Photo">'},
        ])
        self._write_jsonl(portions_path, [
            {"title": "Introduction", "page_start": 1, "page_end": 2},
        ])

        # Create a minimal illustration manifest
        illust_dir = self.tmpdir / "illustrations"
        illust_images_dir = illust_dir / "images"
        illust_images_dir.mkdir(parents=True)
        # Create a tiny fake image
        (illust_images_dir / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0")
        illust_path = illust_dir / "illustration_manifest.jsonl"
        self._write_jsonl(illust_path, [
            {
                "source_page": 2,
                "filename": "photo.jpg",
                "alt": "Photo",
                "image_description": "A family portrait from 1920",
                "caption_text": "The L'Heureux family",
                "bbox": {"x0": 100, "y0": 200, "x1": 400, "y1": 500},
            },
        ])

        cmd = [
            sys.executable, "-m", "modules.build.build_chapter_html_v1.main",
            "--pages", str(pages_path),
            "--portions", str(portions_path),
            "--out", str(out_path),
            "--output-dir", str(html_dir),
            "--illustration-manifest", str(illust_path),
            "--book-title", "Test Book",
            "--book-author", "Test Author",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent))
        assert result.returncode == 0, f"STDERR: {result.stderr}"

        # Validate index.html
        index_html = (html_dir / "index.html").read_text()
        assert "<!DOCTYPE html>" in index_html
        assert "Test Book" in index_html
        assert "Test Author" in index_html
        assert "Contents" in index_html

        # Validate chapter HTML
        chapter = (html_dir / "chapter-001.html").read_text()
        soup = BeautifulSoup(chapter, "html.parser")

        # HTML5 structure
        assert "<!DOCTYPE html>" in chapter
        assert soup.find("meta", attrs={"charset": "utf-8"}) is not None

        # Navigation
        navs = soup.find_all("nav")
        assert len(navs) >= 1
        assert any("index.html" in str(n) for n in navs)

        content_blocks = soup.find("article").find_all(["h1", "p", "figure"], recursive=False)
        assert content_blocks
        assert all(block.get("id", "").startswith("blk-chapter-001-") for block in content_blocks)

        # Image with figure/figcaption
        figure = soup.find("figure")
        assert figure is not None, "Expected <figure> wrapping for image"
        img = figure.find("img")
        assert img is not None
        assert img["alt"] == "A family portrait from 1920"  # VLM description
        figcaption = figure.find("figcaption")
        assert figcaption is not None
        assert figcaption.string == "The L'Heureux family"

        # Image file was copied
        assert (html_dir / "images" / "photo.jpg").exists()

        # Self-contained: no external URLs
        assert "http://" not in chapter
        assert "https://" not in chapter

        # Manifest output
        manifest = [json.loads(line) for line in out_path.read_text().strip().split("\n")]
        assert len(manifest) >= 1
        assert manifest[0]["kind"] == "chapter"
        assert manifest[0]["title"] == "Introduction"

        bundle_manifest = json.loads((html_dir / "manifest.json").read_text())
        assert bundle_manifest["schema_version"] == "doc_web_bundle_manifest_v1"
        assert bundle_manifest["entries"][0]["entry_id"] == "chapter-001"
        assert bundle_manifest["reading_order"] == ["chapter-001"]
        assert bundle_manifest["provenance_path"] == "provenance/blocks.jsonl"

        provenance_rows = [
            json.loads(line)
            for line in (html_dir / "provenance" / "blocks.jsonl").read_text().strip().split("\n")
        ]
        assert provenance_rows
        assert provenance_rows[0]["entry_id"] == "chapter-001"
        assert provenance_rows[0]["block_id"].startswith("blk-chapter-001-")
        assert provenance_rows[0]["source_element_ids"]

    def test_overwrites_stale_published_image_on_rerun(self):
        pages_path = self.tmpdir / "pages.jsonl"
        portions_path = self.tmpdir / "portions.jsonl"
        out_path = self.tmpdir / "manifest.jsonl"
        html_dir = self.tmpdir / "html"

        self._write_jsonl(pages_path, [
            {"page_number": 1, "printed_page_number": 1, "html": '<p>Page one.</p><img alt="Photo">'},
        ])
        self._write_jsonl(portions_path, [
            {"title": "Introduction", "page_start": 1, "page_end": 1},
        ])

        illust_dir = self.tmpdir / "illustrations"
        illust_images_dir = illust_dir / "images"
        illust_images_dir.mkdir(parents=True)
        source_bytes = b"fresh-image-bytes"
        stale_bytes = b"stale-image-bytes"
        (illust_images_dir / "photo.jpg").write_bytes(source_bytes)
        illust_path = illust_dir / "illustration_manifest.jsonl"
        self._write_jsonl(illust_path, [
            {
                "source_page": 1,
                "filename": "photo.jpg",
                "alt": "Photo",
                "image_description": "Fresh image",
                "caption_text": None,
                "bbox": {"x0": 100, "y0": 200, "x1": 400, "y1": 500},
            },
        ])

        (html_dir / "images").mkdir(parents=True)
        (html_dir / "images" / "photo.jpg").write_bytes(stale_bytes)

        cmd = [
            sys.executable, "-m", "modules.build.build_chapter_html_v1.main",
            "--pages", str(pages_path),
            "--portions", str(portions_path),
            "--out", str(out_path),
            "--output-dir", str(html_dir),
            "--illustration-manifest", str(illust_path),
            "--book-title", "Test Book",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent))
        assert result.returncode == 0, f"STDERR: {result.stderr}"

        assert (html_dir / "images" / "photo.jpg").read_bytes() == source_bytes

    def test_merges_stale_duplicate_tail_into_previous_chapter(self):
        pages_path = self.tmpdir / "pages.jsonl"
        portions_path = self.tmpdir / "portions.jsonl"
        out_path = self.tmpdir / "manifest.jsonl"
        html_dir = self.tmpdir / "html"

        self._write_jsonl(pages_path, [
            {"page_number": 1, "printed_page_number": 1, "html": "<h1>ALMA</h1><p>Alma intro.</p>"},
            {"page_number": 2, "printed_page_number": 2, "html": "<table><tr><td>Arthur tail rows.</td></tr></table>"},
            {"page_number": 3, "printed_page_number": 3, "html": "<h1>ARTHUR</h1><p>Arthur intro.</p>"},
            {"page_number": 4, "printed_page_number": 4, "html": "<p>More Arthur.</p>"},
        ])
        self._write_jsonl(portions_path, [
            {"title": "Veterans", "page_start": 1, "page_end": 1},
            {"title": "Alma", "page_start": 2, "page_end": 3},
            {"title": "Arthur", "page_start": 4, "page_end": 4},
        ])

        cmd = [
            sys.executable, "-m", "modules.build.build_chapter_html_v1.main",
            "--pages", str(pages_path),
            "--portions", str(portions_path),
            "--out", str(out_path),
            "--output-dir", str(html_dir),
            "--book-title", "Test Book",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent))
        assert result.returncode == 0, f"STDERR: {result.stderr}"

        manifest = [json.loads(line) for line in out_path.read_text().strip().split("\n")]
        chapters = [row for row in manifest if row["kind"] == "chapter"]
        assert len(chapters) == 2
        assert chapters[0]["title"] == "ALMA"
        assert chapters[0]["page_start"] == 1
        assert chapters[0]["page_end"] == 2
        assert chapters[0]["source_portion_titles"] == ["Veterans", "Alma"]
        assert chapters[1]["title"] == "ARTHUR"
        assert chapters[1]["page_start"] == 3
        assert chapters[1]["page_end"] == 4
        assert chapters[1]["source_portion_titles"] == ["Alma", "Arthur"]

        chapter_one = (html_dir / "chapter-001.html").read_text()
        chapter_two = (html_dir / "chapter-002.html").read_text()
        assert "Arthur tail rows." in chapter_one
        assert "Arthur intro." in chapter_two

    def test_cli_merges_contiguous_genealogy_tables_when_enabled(self):
        pages_path = self.tmpdir / "pages.jsonl"
        portions_path = self.tmpdir / "portions.jsonl"
        out_path = self.tmpdir / "manifest.jsonl"
        html_dir = self.tmpdir / "html"

        self._write_jsonl(pages_path, [
            {
                "page_number": 1,
                "printed_page_number": 1,
                "html": (
                    "<h1>ALMA</h1>"
                    "<table><thead><tr><th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY/GIRL</th><th>DIED</th></tr></thead>"
                    "<tbody><tr><td>Alma</td><td>July 31, 1883</td><td>Apr. 8, 1907</td><td>Henry Alain</td><td>4 4</td><td>Dec. 15, 1982</td></tr></tbody></table>"
                ),
            },
            {
                "page_number": 2,
                "printed_page_number": 2,
                "html": (
                    "<h2>Alma's Grandchildren</h2><h3>MARY PAULE'S FAMILY</h3>"
                    "<table><tbody><tr><td>Ronald</td><td>Jan. 24, 1933</td><td>July 20, 1963</td><td>Jean Bailey</td><td>1</td><td>1</td></tr></tbody></table>"
                    "<p><strong>Alma's Great Grandchildren<br/>Mary Paule's Grandchildren<br/>RONALD'S FAMILY</strong></p>"
                    "<table><tbody><tr><td>Kari Lou</td><td>Oct. 30, 1964</td></tr></tbody></table>"
                ),
            },
        ])
        self._write_jsonl(portions_path, [
            {"title": "Alma", "page_start": 1, "page_end": 2},
        ])

        cmd = [
            sys.executable, "-m", "modules.build.build_chapter_html_v1.main",
            "--pages", str(pages_path),
            "--portions", str(portions_path),
            "--out", str(out_path),
            "--output-dir", str(html_dir),
            "--book-title", "Test Book",
            "--merge-contiguous-genealogy-tables",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent))
        assert result.returncode == 0, f"STDERR: {result.stderr}"

        chapter = (html_dir / "chapter-001.html").read_text()
        soup = BeautifulSoup(chapter, "html.parser")
        tables = soup.find("article").find_all("table")
        assert len(tables) == 1
        assert "MARY PAULE'S FAMILY" in tables[0].get_text(" ", strip=True)
        assert "RONALD'S FAMILY" in tables[0].get_text(" ", strip=True)

    def test_cli_keeps_caption_provenance_after_genealogy_merge(self):
        pages_path = self.tmpdir / "pages.jsonl"
        portions_path = self.tmpdir / "portions.jsonl"
        out_path = self.tmpdir / "manifest.jsonl"
        html_dir = self.tmpdir / "html"

        self._write_jsonl(pages_path, [
            {
                "page_number": 20,
                "printed_page_number": 20,
                "html": (
                    "<h1>L’HEUREUX VETERANS OF WORLD WAR I & II</h1>"
                    "<table><thead><tr><th>Family</th><th>Name</th></tr></thead>"
                    "<tbody><tr><td>Arthur</td><td>Alphonse L'Heureux</td></tr></tbody></table>"
                ),
            },
            {
                "page_number": 21,
                "printed_page_number": 21,
                "html": (
                    "<img alt=\"Ranch buildings\">"
                    "<p><em>Aerial photo of ranch buildings</em></p>"
                    "<img alt=\"Ranch house and barn\">"
                    "<p><em>Ranch house and barn</em></p>"
                ),
            },
        ])
        self._write_jsonl(portions_path, [
            {"title": "Veterans", "page_start": 20, "page_end": 21},
        ])

        illust_dir = self.tmpdir / "illustrations"
        illust_images_dir = illust_dir / "images"
        illust_images_dir.mkdir(parents=True)
        (illust_images_dir / "page-021-000.jpg").write_bytes(b"\xff\xd8\xff\xe0")
        (illust_images_dir / "page-021-001.jpg").write_bytes(b"\xff\xd8\xff\xe0")
        illust_path = illust_dir / "illustration_manifest.jsonl"
        self._write_jsonl(illust_path, [
            {
                "source_page": 21,
                "filename": "page-021-000.jpg",
                "alt": "Ranch buildings",
                "image_description": "Aerial view of ranch buildings and surrounding landscape",
                "caption_text": None,
                "bbox": {"x0": 0, "y0": 0, "x1": 100, "y1": 100},
            },
            {
                "source_page": 21,
                "filename": "page-021-001.jpg",
                "alt": "Ranch house and barn",
                "image_description": "Ranch house and barn with cattle in the foreground",
                "caption_text": None,
                "bbox": {"x0": 0, "y0": 0, "x1": 100, "y1": 100},
            },
        ])

        cmd = [
            sys.executable, "-m", "modules.build.build_chapter_html_v1.main",
            "--pages", str(pages_path),
            "--portions", str(portions_path),
            "--out", str(out_path),
            "--output-dir", str(html_dir),
            "--illustration-manifest", str(illust_path),
            "--book-title", "Test Book",
            "--merge-contiguous-genealogy-tables",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent))
        assert result.returncode == 0, f"STDERR: {result.stderr}"

        chapter = (html_dir / "chapter-001.html").read_text()
        soup = BeautifulSoup(chapter, "html.parser")
        paragraphs = [
            paragraph.get_text(" ", strip=True)
            for paragraph in soup.find("article").find_all("p", recursive=False)
        ]
        assert "Aerial photo of ranch buildings" in paragraphs
        assert "Ranch house and barn" in paragraphs

        provenance_rows = [
            json.loads(line)
            for line in (html_dir / "provenance" / "blocks.jsonl").read_text().strip().split("\n")
        ]
        first_caption = next(
            row for row in provenance_rows if row["text_quote"] == "Aerial photo of ranch buildings"
        )
        second_caption = next(
            row for row in provenance_rows if row["text_quote"] == "Ranch house and barn"
        )
        assert first_caption["source_element_ids"] == ["p021-b2"]
        assert second_caption["source_element_ids"] == ["p021-b4"]

    def test_merges_same_family_prefix_into_previous_chapter(self):
        pages_path = self.tmpdir / "pages.jsonl"
        portions_path = self.tmpdir / "portions.jsonl"
        out_path = self.tmpdir / "manifest.jsonl"
        html_dir = self.tmpdir / "html"

        self._write_jsonl(pages_path, [
            {"page_number": 1, "printed_page_number": 1, "html": "<h1>GEORGE L'HEUREUX</h1><p>George intro.</p>"},
            {"page_number": 2, "printed_page_number": 2, "html": "<p>George prose continues.</p>"},
            {"page_number": 3, "printed_page_number": 3, "html": "<h1>George L'Heureux</h1><table><tr><td>George genealogy.</td></tr></table>"},
            {"page_number": 4, "printed_page_number": 4, "html": "<p>More George genealogy.</p>"},
            {"page_number": 5, "printed_page_number": 5, "html": "<h1>JOE (JOSEPH) L'HEUREUX</h1><p>Joe intro.</p>"},
        ])
        self._write_jsonl(portions_path, [
            {"title": "Josephine", "page_start": 1, "page_end": 2},
            {"title": "Paul", "page_start": 3, "page_end": 5},
        ])

        cmd = [
            sys.executable, "-m", "modules.build.build_chapter_html_v1.main",
            "--pages", str(pages_path),
            "--portions", str(portions_path),
            "--out", str(out_path),
            "--output-dir", str(html_dir),
            "--book-title", "Test Book",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent))
        assert result.returncode == 0, f"STDERR: {result.stderr}"

        manifest = [json.loads(line) for line in out_path.read_text().strip().split("\n")]
        chapters = [row for row in manifest if row["kind"] == "chapter"]
        assert len(chapters) == 2
        assert chapters[0]["title"] == "GEORGE L'HEUREUX"
        assert chapters[0]["page_start"] == 1
        assert chapters[0]["page_end"] == 4
        assert chapters[0]["source_portion_titles"] == ["Josephine", "Paul"]
        assert chapters[1]["title"] == "JOE (JOSEPH) L'HEUREUX"
        assert chapters[1]["page_start"] == 5
        assert chapters[1]["page_end"] == 5

    def test_provenance_sidecar_keeps_source_ids_when_paragraphs_stitch_across_pages(self):
        pages_path = self.tmpdir / "pages.jsonl"
        portions_path = self.tmpdir / "portions.jsonl"
        out_path = self.tmpdir / "manifest.jsonl"
        html_dir = self.tmpdir / "html"

        self._write_jsonl(pages_path, [
            {"page_number": 10, "printed_page_number": 1, "html": "<p>The story continues into</p>"},
            {"page_number": 11, "printed_page_number": 2, "html": "<p>the next printed page.</p>"},
        ])
        self._write_jsonl(portions_path, [
            {"title": "Introduction", "page_start": 1, "page_end": 2},
        ])

        cmd = [
            sys.executable, "-m", "modules.build.build_chapter_html_v1.main",
            "--pages", str(pages_path),
            "--portions", str(portions_path),
            "--out", str(out_path),
            "--output-dir", str(html_dir),
            "--book-title", "Test Book",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent))
        assert result.returncode == 0, f"STDERR: {result.stderr}"

        chapter = (html_dir / "chapter-001.html").read_text()
        soup = BeautifulSoup(chapter, "html.parser")
        paragraphs = soup.find("article").find_all("p", recursive=False)
        assert len(paragraphs) == 1
        assert paragraphs[0].get_text(" ", strip=True) == "The story continues into the next printed page."

        provenance_rows = [
            json.loads(line)
            for line in (html_dir / "provenance" / "blocks.jsonl").read_text().strip().split("\n")
        ]
        paragraph_row = next(row for row in provenance_rows if row["block_kind"] == "paragraph")
        assert paragraph_row["source_page_number"] == 10
        assert paragraph_row["source_printed_page_number"] == 1
        assert paragraph_row["source_element_ids"] == ["p010-b1", "p011-b1"]
