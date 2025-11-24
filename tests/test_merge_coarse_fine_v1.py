import json
from modules.adapter.merge_coarse_fine_v1.main import merge_portions, attach_continuations


def mk(span, conf=0.6, title=None, typ=None, src="fine"):
    p = {
        "page_start": span[0],
        "page_end": span[1],
        "confidence": conf,
        "title": title,
        "type": typ,
        "source": [src],
    }
    return p


def test_coarse_added_when_uncovered_ratio_met():
    fine = [mk((1, 2))]
    coarse = [mk((1, 4), conf=0.5, src="coarse")]
    merged = merge_portions(fine, coarse, uncovered_thresh=0.5)
    spans = {(p["page_start"], p["page_end"]) for p in merged}
    assert (1, 4) in spans  # 50% of coarse pages (2 of 4) were uncovered


def test_coarse_not_added_when_covered():
    fine = [mk((1, 4))]
    coarse = [mk((1, 4), conf=0.9, src="coarse")]
    merged = merge_portions(fine, coarse, uncovered_thresh=0.5)
    spans = [(p["page_start"], p["page_end"], tuple(sorted(p.get("source", [])))) for p in merged]
    assert spans.count((1, 4, ("fine",))) == 1  # coarse copy should not be added


def test_duplicate_span_collapsed_keeps_highest_conf():
    fine = [mk((1, 2), conf=0.4, src="fine"), mk((1, 2), conf=0.9, src="coarse")]
    merged = merge_portions(fine, [], uncovered_thresh=0.5)
    assert len(merged) == 1
    m = merged[0]
    assert m["confidence"] == 0.9
    assert set(m["source"]) == {"fine", "coarse"}


def test_attach_continuations_gap_and_title_similarity():
    a = mk((1, 1), title="Intro to Dungeon", typ="intro", conf=0.8)
    a["portion_id"] = "P1"
    b = mk((2, 2), title="Intro Dungeon", typ="intro", conf=0.7)
    b["portion_id"] = "P1"
    merged = attach_continuations([a, b], gap=1, title_sim_thresh=0.5)
    assert merged[1].get("continuation_of") == "P1"
    assert merged[1].get("continuation_confidence", 0) >= 0.55
