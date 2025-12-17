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


def test_build_chosen_lines_extracts_standalone_headers_from_other_engines():
    """
    Regression test for the case where standalone numeric headers exist in engines_raw
    but are NOT in the lines array (extract_ocr_ensemble_v1 didn't synthesize them).
    
    Scenario:
    - page_data['lines'] only contains body text (no standalone headers)
    - engines_raw['apple'] has "6-8" (range only, chosen engine)
    - engines_raw['tesseract'] has "6", "7", "8" (standalone headers)
    - We should extract standalone headers from tesseract even though apple is chosen
    """
    
    page_data = {
        "module_id": "extract_ocr_ensemble_v1",
        "page": 17,
        "engines_raw": {
            "apple": "6-8\nBody for 6\nDeath at 7\nDeath at 8\n",
            "tesseract": "6\n7\n8\nBody for 6\nDeath at 7\nDeath at 8\n",
        },
        "lines": [
            {"text": "6-8", "source": "apple"},
            {"text": "Body for 6", "source": "apple"},
            {"text": "Death at 7", "source": "apple"},
            {"text": "Death at 8", "source": "apple"},
            # Note: standalone "6", "7", "8" are NOT in lines array
        ],
    }
    
    chosen = build_chosen_lines(page_data, "apple")
    
    texts = [ln.get("text", "").strip() for ln in chosen]
    
    # We must extract standalone numeric headers from tesseract engines_raw
    assert "6" in texts, f"Section 6 missing from: {texts}"
    assert "7" in texts, f"Section 7 missing from: {texts}"
    assert "8" in texts, f"Section 8 missing from: {texts}"
    
    # And we should keep body text from chosen engine
    assert "Body for 6" in texts
    assert "Death at 7" in texts
    assert "Death at 8" in texts

