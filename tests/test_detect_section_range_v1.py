from modules.transform.detect_section_range_v1.main import compute_section_range


def test_compute_section_range_ignores_non_numeric():
    portions = [
        {"section_id": "1"},
        {"section_id": "10"},
        {"section_id": "background"},
        {"section_id": "S003"},
        {"portion_id": 7},
    ]
    result = compute_section_range(portions)
    assert result["min_section"] == 1
    assert result["max_section"] == 10
    assert result["numeric_section_count"] == 2


def test_compute_section_range_conflict_from_refs():
    portions = [
        {"section_id": "1", "choices": [{"target": "99"}]},
        {"section_id": "10"},
    ]
    result = compute_section_range(portions)
    assert result["max_section"] == 10
    assert result["max_ref_section"] == 99
    assert result["confidence"] in {"low", "conflict"}
    assert "refs_exceed_headers" in result["flags"]


def test_compute_section_range_uses_turn_to_links():
    portions = [
        {"section_id": "1", "turn_to_links": ["7", "12"]},
        {"section_id": "5"},
    ]
    result = compute_section_range(portions)
    assert result["max_section"] == 5
    assert result["max_ref_section"] == 12


def test_compute_section_range_prefers_backscan_when_headers_exceed():
    portions = [
        {"section_id": "1"},
        {"section_id": "10"},
        {"section_id": "11"},
    ]
    pages = [{"html": "<h2>10</h2>"}]
    result = compute_section_range(portions, pages)
    assert result["max_section"] == 10
    assert "headers_exceed_backscan" in result["flags"]
