from modules.adapter.repair_candidates_v1.main import select_candidates


def build_pageline(page: int, char_confusion_score: float = 0.0, dictionary_oov_ratio: float = 0.0, reasons=None):
    return {
        "page": page,
        "quality_metrics": {
            "char_confusion_score": char_confusion_score,
            "dictionary_oov_ratio": dictionary_oov_ratio,
        },
        "escalation_reasons": reasons or [],
    }


def build_portion(portion_id: str, start: int, end: int = None):
    return {
        "portion_id": portion_id,
        "page_start": start,
        "page_end": end or start,
        "raw_text": f"Sample text for {portion_id}",
    }


def test_select_candidates_by_char_confusion():
    pagelines = [build_pageline(page=7, char_confusion_score=0.6)]
    portions = [build_portion("P007", 7), build_portion("P008", 8)]
    candidates, stats = select_candidates(
        pagelines,
        portions,
        char_confusion_threshold=0.5,
        dictionary_oov_threshold=0.4,
        include_escalation_reasons=False,
        forced_pages=set(),
        forced_portions=set(),
        max_candidates=None,
    )
    assert len(candidates) == 2
    assert stats["candidate_count"] == 1
    flagged = [c for c in candidates if c["portion_id"] == "P007"]
    assert flagged
    hints = candidates[0]["repair_hints"]
    assert hints["flagged_pages"] == [7]
    assert hints["char_confusion_score"] == 0.6
    assert stats["flagged_pages"] == [7]


def test_select_candidates_forced_portions_pages():
    pagelines = [build_pageline(page=20, char_confusion_score=0.0)]
    portions = [
        build_portion("P100", 20),
        build_portion("P200", 30),
    ]
    candidates, stats = select_candidates(
        pagelines,
        portions,
        char_confusion_threshold=0.5,
        dictionary_oov_threshold=0.5,
        include_escalation_reasons=False,
        forced_pages={20},
        forced_portions={"P200"},
        max_candidates=10,
    )
    assert {c["portion_id"] for c in candidates} == {"P100", "P200"}


def test_select_candidates_respects_max_limit():
    pagelines = [build_pageline(page=i, char_confusion_score=0.6) for i in range(1, 6)]
    portions = [build_portion(f"P{i}", i) for i in range(1, 6)]
    candidates, stats = select_candidates(
        pagelines,
        portions,
        char_confusion_threshold=0.5,
        dictionary_oov_threshold=0.5,
        include_escalation_reasons=False,
        forced_pages=set(),
        forced_portions=set(),
        max_candidates=2,
    )
    assert stats["candidate_count"] == 2
