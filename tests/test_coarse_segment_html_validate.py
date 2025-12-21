from modules.portionize.coarse_segment_html_v1.main import validate_ranges


def test_validate_ranges_accepts_contiguous_ranges():
    result = {
        "frontmatter_pages": [1, 10],
        "gameplay_pages": [11, 200],
        "endmatter_pages": [201, 220],
        "notes": "ok",
    }
    ok, errors = validate_ranges(result, total_pages=220)
    assert ok is True
    assert errors == []


def test_validate_ranges_rejects_missing_fields():
    result = {
        "frontmatter_pages": [1, 10],
        "notes": "missing gameplay",
    }
    ok, errors = validate_ranges(result, total_pages=220)
    assert ok is False
    assert any("Missing field: gameplay_pages" in e for e in errors)
