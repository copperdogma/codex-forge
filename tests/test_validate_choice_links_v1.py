from modules.validate.validate_choice_links_v1.main import _extract_anchor_targets, _has_placeholder_targets


def test_extract_anchor_targets_dedupes():
    html = '<p><a href="#38">Turn to 38</a> then <a href="#38">38</a> and <a href="#111">111</a></p>'
    targets = _extract_anchor_targets(html)
    assert targets == ["38", "111"]


def test_placeholder_targets_detected():
    html = "<p>Turn to 1XX to proceed.</p>"
    assert _has_placeholder_targets(html) is True

