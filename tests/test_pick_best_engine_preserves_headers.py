import json

from modules.adapter.pick_best_engine_v1.main import build_chosen_lines


def test_build_chosen_lines_preserves_numeric_headers_across_engines():
    """
    Regression test:

    When extract_ocr_ensemble_v1 synthesizes standalone numeric section headers
    (e.g. '6', '7', '8') in page_data['lines'], but the chosen engine's
    engines_raw text only contains a fused decoration like '6-8', we must
    preserve those standalone numeric header lines when constructing
    pagelines_final.jsonl. Otherwise section starts silently disappear and
    boundary detection/portionize will never see them.

    This test simulates the Deathtrap Dungeon page 17R pattern where:
    - page_data['lines'] contains '6-8', '6', '7', '8' plus body text lines
    - engines_raw['apple'] contains '6-8' and body text but not the standalone digits
    """

    page_data = {
        "module_id": "extract_ocr_ensemble_v1",
        "page": 17,
        "engines_raw": {
            # Note: no standalone '6', '7', '8' lines here by design.
            "apple": "6-8\nBody for 6\nDeath at 7\nDeath at 8\n",
        },
        "lines": [
            {"text": "6-8", "source": "apple"},
            # Standalone numeric headers synthesized upstream; sources may be missing or generic.
            {"text": "6", "source": "synthetic"},
            {"text": "Body for 6", "source": "apple"},
            {"text": "7", "source": "synthetic"},
            {"text": "Death at 7", "source": "apple"},
            {"text": "8", "source": "synthetic"},
            {"text": "Death at 8", "source": "apple"},
        ],
    }

    chosen = build_chosen_lines(page_data, "apple")

    texts = [ln.get("text", "").strip() for ln in chosen]

    # We must preserve all three standalone numeric headers.
    assert "6" in texts
    assert "7" in texts
    assert "8" in texts

    # And we should keep the associated body lines from the chosen engine.
    assert "Body for 6" in texts
    assert "Death at 7" in texts
    assert "Death at 8" in texts



