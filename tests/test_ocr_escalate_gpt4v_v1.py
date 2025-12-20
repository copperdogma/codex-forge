import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_prefers_upstream_escalation_reasons():
    from modules.adapter.ocr_escalate_gpt4v_v1.main import page_escalation_reasons

    q = {
        "page": "009L",
        "needs_escalation": False,
        "escalation_reasons": ["dictionary_oov"],
        "quality_score": 0.01,
    }
    assert page_escalation_reasons(q, threshold=0.8) == ["dictionary_oov"]


def test_fallback_reasons_derived_from_legacy_scores():
    from modules.adapter.ocr_escalate_gpt4v_v1.main import page_escalation_reasons

    q = {
        "page": "011R",
        "needs_escalation": False,
        "disagree_rate": 0.3,
        "disagreement_score": 0.1,
        "quality_score": 0.0,
        "quality_metrics": {
            "corruption_score": 0.6,
            "missing_content_score": 0.0,
            "dictionary_score": 0.0,
            "char_confusion_score": 0.0,
        },
    }
    reasons = page_escalation_reasons(q, threshold=0.8)
    assert "high_disagree_rate" in reasons
    assert "high_corruption" in reasons


def test_candidate_sort_prefers_worse_dictionary_when_quality_ties():
    from modules.adapter.ocr_escalate_gpt4v_v1.main import candidate_sort_key

    a = {
        "page": "001L",
        "quality_score": 0.2,
        "disagreement_score": 0.2,
        "quality_metrics": {"dictionary_score": 0.2, "char_confusion_score": 0.0, "corruption_score": 0.0, "missing_content_score": 0.0},
    }
    b = {
        "page": "002L",
        "quality_score": 0.2,
        "disagreement_score": 0.2,
        "quality_metrics": {"dictionary_score": 0.6, "char_confusion_score": 0.0, "corruption_score": 0.0, "missing_content_score": 0.0},
    }
    assert candidate_sort_key(b) > candidate_sort_key(a)


def test_candidate_sort_can_promote_dictionary_over_slightly_higher_disagreement():
    from modules.adapter.ocr_escalate_gpt4v_v1.main import candidate_sort_key

    # Page A: slightly worse disagreement, but no content-quality indicators.
    a = {
        "page": "010R",
        "quality_score": 0.0,
        "disagreement_score": 0.86,
        "quality_metrics": {"dictionary_score": 0.0, "char_confusion_score": 0.0, "corruption_score": 0.0, "missing_content_score": 0.0},
    }
    # Page B: slightly better disagreement, but clear dictionary signal.
    b = {
        "page": "009L",
        "quality_score": 0.0,
        "disagreement_score": 0.84,
        "quality_metrics": {"dictionary_score": 0.8, "char_confusion_score": 0.0, "corruption_score": 0.0, "missing_content_score": 0.0},
    }
    assert candidate_sort_key(b) > candidate_sort_key(a)


def test_update_quality_row_dry_run_does_not_clear_needs_escalation():
    from modules.adapter.ocr_escalate_gpt4v_v1.main import update_quality_row

    q = {"page": "009L", "needs_escalation": True, "escalation_reasons": ["dictionary_oov"]}
    out = update_quality_row(q, would_escalate=True, reasons=["dictionary_oov"], dry_run=True)
    assert out["needs_escalation"] is True
    assert out["would_escalate"] is True
    assert out["would_escalate_reasons"] == ["dictionary_oov"]


def test_should_escalate_skips_blank_half_spread(tmp_path: Path):
    from modules.adapter.ocr_escalate_gpt4v_v1.main import should_escalate_page_key

    left = tmp_path / "page-001.json"
    right = tmp_path / "page-002.json"
    left.write_text(json.dumps({"lines": [], "page_number": 1, "original_page_number": 1, "spread_side": "L"}), encoding="utf-8")
    right.write_text(
        json.dumps({
            "lines": [{"text": "This is a longer page with substantial text." * 20}],
            "page_number": 2,
            "original_page_number": 1,
            "spread_side": "R",
        }),
        encoding="utf-8",
    )

    index = {"1": str(left), "2": str(right)}
    pages_cache = {}
    ok, reason = should_escalate_page_key(
        "1",
        ["missing_content"],
        index=index,
        pages_cache=pages_cache,
        min_other_side_chars=200,
        min_chars_to_escalate_short_missing=120,
    )
    assert ok is False
    assert reason == "skip_blank_half_spread"


def test_should_escalate_skips_short_missing_content(tmp_path: Path):
    from modules.adapter.ocr_escalate_gpt4v_v1.main import should_escalate_page_key

    page = tmp_path / "page-002.json"
    page.write_text(json.dumps({"lines": [{"text": "NOW TURN OVER"}]}), encoding="utf-8")

    index = {"2": str(page)}
    pages_cache = {}
    ok, reason = should_escalate_page_key(
        "2",
        ["missing_content"],
        index=index,
        pages_cache=pages_cache,
        min_other_side_chars=200,
        min_chars_to_escalate_short_missing=120,
    )
    assert ok is False
    assert reason == "skip_short_missing_content"
