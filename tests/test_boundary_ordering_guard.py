import pytest

from modules.portionize.detect_boundaries_code_first_v1.main import (
    _build_element_sequence,
    detect_ordering_conflicts,
    detect_span_issues,
)


def _elem(eid, seq, text, page=10, content_type=None, side=None):
    return {
        "id": eid,
        "seq": seq,
        "text": text,
        "page": page,
        "page_number": page,
        "metadata": {"spread_side": side} if side else {},
        "content_type": content_type,
    }


def test_ordering_conflicts_per_side():
    elements = [
        _elem("010-0001", 1, "2", content_type="Section-header", side="L"),
        _elem("010-0002", 2, "1", content_type="Section-header", side="L"),
        _elem("010-0003", 3, "3", content_type="Section-header", side="R"),
        _elem("010-0004", 4, "4", content_type="Section-header", side="R"),
    ]
    _, _, _, id_to_seq = _build_element_sequence(elements)

    boundaries = [
        {"section_id": "2", "start_element_id": "010-0001", "start_page": 10, "start_element_metadata": {"spread_side": "L"}},
        {"section_id": "1", "start_element_id": "010-0002", "start_page": 10, "start_element_metadata": {"spread_side": "L"}},
        {"section_id": "3", "start_element_id": "010-0003", "start_page": 10, "start_element_metadata": {"spread_side": "R"}},
        {"section_id": "4", "start_element_id": "010-0004", "start_page": 10, "start_element_metadata": {"spread_side": "R"}},
    ]

    conflicts = detect_ordering_conflicts(boundaries, id_to_seq)
    assert "10L" in conflicts
    assert "10R" not in conflicts


def test_span_issue_inverted_span():
    elements = [
        _elem("010-0001", 1, "2", content_type="Section-header", side="L"),
        _elem("010-0002", 2, "1", content_type="Section-header", side="L"),
        _elem("010-0003", 3, "Some text here", content_type="Text", side="L"),
        _elem("010-0004", 4, "3", content_type="Section-header", side="L"),
        _elem("010-0005", 5, "More text here", content_type="Text", side="L"),
    ]
    elements_sorted, _, id_to_index, _ = _build_element_sequence(elements)

    boundaries = [
        {"section_id": "1", "start_element_id": "010-0002", "start_page": 10, "start_element_metadata": {"spread_side": "L"}},
        {"section_id": "2", "start_element_id": "010-0001", "start_page": 10, "start_element_metadata": {"spread_side": "L"}},
        {"section_id": "3", "start_element_id": "010-0004", "start_page": 10, "start_element_metadata": {"spread_side": "L"}},
    ]

    issues = detect_span_issues(
        boundaries,
        id_to_index=id_to_index,
        elements_sorted=elements_sorted,
        min_words=1,
        min_alpha_ratio=0.0,
        min_alpha_chars=0,
    )
    assert issues["10L"]["reason"] == "inverted_span"


def test_span_issue_empty_text():
    elements = [
        _elem("010-0001", 1, "1", content_type="Section-header", side="L"),
        _elem("010-0002", 2, "2", content_type="Section-header", side="L"),
    ]
    elements_sorted, _, id_to_index, _ = _build_element_sequence(elements)

    boundaries = [
        {"section_id": "1", "start_element_id": "010-0001", "start_page": 10, "start_element_metadata": {"spread_side": "L"}},
        {"section_id": "2", "start_element_id": "010-0002", "start_page": 10, "start_element_metadata": {"spread_side": "L"}},
    ]

    issues = detect_span_issues(
        boundaries,
        id_to_index=id_to_index,
        elements_sorted=elements_sorted,
        min_words=1,
        min_alpha_ratio=0.1,
        min_alpha_chars=1,
    )
    assert issues["10L"]["reason"] == "empty_or_low_text_span"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
