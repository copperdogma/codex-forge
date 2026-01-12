"""Tests for detect_boundaries_html_loop_v1 page-number marker handling."""
import re
import pytest

from modules.portionize.detect_boundaries_html_loop_v1.main import _code_repair_html


def test_page_number_marker_with_existing_h2_not_converted():
    """Page-number markers should NOT be converted to h2 when there's already an h2 with that number."""
    html = """<p class="page-number">168</p>
<p>Some text</p>
<h2>168</h2>
<p>More text</p>"""
    
    repaired, changed = _code_repair_html(html, [168])
    
    # Page-number marker should remain (not converted to h2)
    assert '<p class="page-number">168</p>' in repaired or 'page-number' in repaired
    # h2 should remain
    assert '<h2>168</h2>' in repaired
    # Should not create duplicate h2
    h2_count = len(re.findall(r'<h2>\s*168\s*</h2>', repaired, re.IGNORECASE))
    assert h2_count == 1, f"Expected 1 h2>168</h2>, found {h2_count}"


def test_page_number_marker_without_h2_not_converted():
    """Page-number markers should NOT be converted to h2 even when there's no h2 (they're page numbers, not headers)."""
    html = """<p class="page-number">168</p>
<p>Some text</p>"""
    
    repaired, changed = _code_repair_html(html, [168])
    
    # Page-number marker should remain (not converted to h2)
    assert '<p class="page-number">168</p>' in repaired or 'page-number' in repaired
    # Should NOT create h2 from page-number marker
    assert '<h2>168</h2>' not in repaired


def test_plain_p_tag_with_number_is_converted():
    """Plain <p> tags with section numbers (not page-number markers) should still be converted."""
    html = """<p>168</p>
<p>Some text</p>"""
    
    repaired, changed = _code_repair_html(html, [168])
    
    # Plain <p> tag should be converted to h2 (if no existing h2)
    assert '<h2>168</h2>' in repaired
    assert changed is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
