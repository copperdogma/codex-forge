from modules.extract.extract_choices_relaxed_v1.main import _looks_like_anchor_variant


def test_anchor_variant_same_length_one_digit():
    anchors = {108, 290}
    assert _looks_like_anchor_variant(106, anchors) is True
    assert _looks_like_anchor_variant(108, anchors) is True


def test_anchor_variant_truncated():
    anchors = {290}
    assert _looks_like_anchor_variant(29, anchors) is True
    assert _looks_like_anchor_variant(290, anchors) is True


def test_anchor_variant_far():
    anchors = {290}
    assert _looks_like_anchor_variant(311, anchors) is False
