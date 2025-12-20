from modules.common.page_numbers import validate_sequential_page_numbers


def test_page_number_sequencing_ok():
    rows = [{"page_number": 1}, {"page_number": 2}, {"page_number": 3}]
    ok, missing = validate_sequential_page_numbers(rows)
    assert ok is True
    assert missing == []


def test_page_number_sequencing_detects_gap():
    rows = [{"page_number": 1}, {"page_number": 3}]
    ok, missing = validate_sequential_page_numbers(rows)
    assert ok is False
    assert missing == [2]


def test_page_number_sequencing_allows_gaps():
    rows = [{"page_number": 1}, {"page_number": 3}]
    ok, missing = validate_sequential_page_numbers(rows, allow_gaps=True)
    assert ok is True
    assert missing == []
