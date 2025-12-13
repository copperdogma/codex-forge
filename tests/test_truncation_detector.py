from modules.validator.truncation_detector_v1.main import detect_truncated_lines


def test_detects_truncation():
    lines = ["This sentence is complete.", "A fragment without punctuation"]
    warnings = detect_truncated_lines(lines, min_len=10)
    assert warnings == ["A fragment without punctuation"]


def test_ignored_short_line():
    lines = ["Short" ]
    warnings = detect_truncated_lines(lines, min_len=10)
    assert warnings == []
