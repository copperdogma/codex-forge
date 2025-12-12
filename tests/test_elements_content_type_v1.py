import sys
import tempfile
from pathlib import Path

from modules.common.utils import save_jsonl, read_jsonl
from modules.adapter.elements_content_type_v1.main import main as ct_main


def run_tagging(rows, disabled=False, extra_args=None):
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "elements_core.jsonl"
        out = Path(d) / "elements_core_typed.jsonl"
        dbg = Path(d) / "debug.jsonl"
        save_jsonl(inp, rows)
        argv = [
            "prog",
            "--inputs",
            str(inp),
            "--out",
            str(out),
            "--debug-out",
            str(dbg),
        ]
        if disabled:
            argv.append("--disabled")
        if extra_args:
            argv.extend(extra_args)
        sys.argv = argv
        ct_main()
        return list(read_jsonl(out)), list(read_jsonl(dbg))


def test_content_types_basic_heuristics():
    rows = [
        {"id": "p1-0000", "seq": 0, "page": 1, "kind": "text", "text": "42", "layout": {"h_align": "center", "y": 0.2}},
        {"id": "p1-0001", "seq": 1, "page": 1, "kind": "text", "text": "INTRODUCTION .... 7", "layout": None},
        {"id": "p1-0002", "seq": 2, "page": 1, "kind": "text", "text": "- Take 1 Provision.", "layout": None},
        {"id": "p1-0003", "seq": 3, "page": 1, "kind": "text", "text": "SKILL  STAMINA", "layout": None},
        {"id": "p1-0004", "seq": 4, "page": 1, "kind": "text", "text": "HOW TO PLAY", "layout": {"h_align": "center", "y": 0.15}},
        {"id": "p1-0005", "seq": 5, "page": 1, "kind": "text", "text": "STAMINA =", "layout": None},
        {"id": "p1-0006", "seq": 6, "page": 1, "kind": "text", "text": "2 + 2 = 4", "layout": None},
        {"id": "p1-0007", "seq": 7, "page": 1, "kind": "text", "text": "You step into the corridor.", "layout": None},
        {"id": "p1-0008", "seq": 8, "page": 1, "kind": "image", "text": "", "layout": None},
        {"id": "p1-0009", "seq": 9, "page": 1, "kind": "table", "text": "A  1  2", "layout": None},
    ]
    out_rows, dbg_rows = run_tagging(rows)
    by_seq = {r["seq"]: r for r in out_rows}

    assert by_seq[0]["content_type"] == "Section-header"
    assert by_seq[0]["content_subtype"]["number"] == 42

    assert by_seq[1]["content_type"] == "List-item"
    assert by_seq[2]["content_type"] == "List-item"
    assert by_seq[3]["content_type"] == "Table"

    assert by_seq[4]["content_type"] in {"Title", "Section-header"}
    assert by_seq[5]["content_type"] == "Text"
    assert by_seq[5]["content_subtype"]["form_field"] is True
    kv = by_seq[5]["content_subtype"]["key_value"]
    assert kv["pairs"] == [{"key": "STAMINA", "value": None}]
    assert by_seq[6]["content_type"] == "Formula"
    assert by_seq[7]["content_type"] == "Text"
    assert by_seq[8]["content_type"] == "Picture"
    assert by_seq[9]["content_type"] == "Table"

    assert dbg_rows and dbg_rows[0]["page"] == 1
    assert "label_counts" in dbg_rows[0]


def test_disabled_is_passthrough():
    rows = [
        {"id": "p1-0000", "seq": 0, "page": 1, "kind": "text", "text": "Hello", "layout": None},
    ]
    out_rows, dbg_rows = run_tagging(rows, disabled=True)
    assert out_rows == rows
    assert dbg_rows and dbg_rows[0].get("disabled") is True


def test_combat_stat_block_is_not_table():
    rows = [
        {
            "id": "p1-0000",
            "seq": 0,
            "page": 1,
            "kind": "text",
            "text": "If you win, turn to 364.  MANTICORE      SKILL 11      STAMINA 11",
            "layout": None,
        },
    ]
    out_rows, _ = run_tagging(rows)
    assert out_rows[0]["content_type"] == "Text"
    assert out_rows[0]["content_subtype"]["combat_stats"] is True
    kv = out_rows[0]["content_subtype"]["key_value"]
    assert kv["entity"] == "MANTICORE"
    assert {"key": "SKILL", "value": 11} in kv["pairs"]
    assert {"key": "STAMINA", "value": 11} in kv["pairs"]


def test_layout_role_mapping_beats_heuristics():
    rows = [
        {"id": "p1-0000", "seq": 0, "page": 1, "kind": "text", "text": "random", "layout": None, "layout_role": "LAYOUT_HEADER"},
    ]
    out_rows, _ = run_tagging(rows)
    assert out_rows[0]["content_type"] == "Page-header"
    assert out_rows[0]["content_type_confidence"] == 0.95
    assert out_rows[0]["content_subtype"]["source_role"] == "LAYOUT_HEADER"


def test_repetition_based_header_and_page_numbers():
    rows = []
    for p in (1, 2, 3):
        rows.extend(
            [
                {"id": f"p{p}-0000", "seq": p * 100 + 0, "page": p, "kind": "text", "text": "BOOK TITLE", "layout": {"h_align": "center", "y": 0.03}},
                {"id": f"p{p}-0001", "seq": p * 100 + 1, "page": p, "kind": "text", "text": "Body text here.", "layout": {"h_align": "left", "y": 0.35}},
                {"id": f"p{p}-0002", "seq": p * 100 + 2, "page": p, "kind": "text", "text": str(p), "layout": {"h_align": "center", "y": 0.95}},
            ]
        )
    out_rows, _ = run_tagging(rows)
    by_id = {r["id"]: r for r in out_rows}
    for p in (1, 2, 3):
        assert by_id[f"p{p}-0000"]["content_type"] == "Page-header"
        assert by_id[f"p{p}-0002"]["content_type"] == "Page-footer"
        assert by_id[f"p{p}-0002"]["content_subtype"]["page_number"] == p


def test_top_of_page_title_nudge_does_not_require_repeats():
    rows = [
        {"id": "p1-0000", "seq": 0, "page": 1, "kind": "text", "text": "Unique Page Title", "layout": {"h_align": "left", "y": 0.03}},
        {"id": "p1-0001", "seq": 1, "page": 1, "kind": "text", "text": "Body", "layout": {"h_align": "left", "y": 0.35}},
        {"id": "p2-0000", "seq": 2, "page": 2, "kind": "text", "text": "Another Unique Title", "layout": {"h_align": "left", "y": 0.03}},
        {"id": "p2-0001", "seq": 3, "page": 2, "kind": "text", "text": "More body", "layout": {"h_align": "left", "y": 0.35}},
    ]
    out_rows, _ = run_tagging(rows)
    by_id = {r["id"]: r for r in out_rows}
    assert by_id["p1-0000"]["content_type"] == "Title"
    assert by_id["p2-0000"]["content_type"] == "Title"


def test_unknown_kv_keys_rejected_by_default():
    rows = [
        {"id": "p1-0000", "seq": 0, "page": 1, "kind": "text", "text": "Stanpitiwd =", "layout": None},
    ]
    out_rows, _ = run_tagging(rows)
    assert out_rows[0]["content_type"] == "Text"
    assert out_rows[0]["content_subtype"]["form_field"] is True
    assert "key_value" not in out_rows[0]["content_subtype"]

    out_rows2, _ = run_tagging(rows, extra_args=["--allow-unknown-kv-keys"])
    assert out_rows2[0]["content_subtype"]["key_value"]["pairs"][0]["key"] == "STANPITIWD"


def test_noisy_form_field_is_not_title():
    rows = [
        {"id": "p1-0000", "seq": 0, "page": 1, "kind": "text", "text": "Shit =", "layout": {"h_align": "center", "y": 0.5}},
    ]
    out_rows, _ = run_tagging(rows)
    assert out_rows[0]["content_type"] == "Text"
    assert out_rows[0]["content_subtype"]["form_field"] is True
    assert "key_value" not in out_rows[0]["content_subtype"]


def test_page_range_header_is_page_header():
    rows = [
        {"id": "p1-0000", "seq": 0, "page": 1, "kind": "text", "text": "6-8", "layout": {"h_align": "right", "y": 0.03}},
        {"id": "p1-0001", "seq": 1, "page": 1, "kind": "text", "text": "Body", "layout": {"h_align": "left", "y": 0.35}},
    ]
    out_rows, _ = run_tagging(rows)
    by_id = {r["id"]: r for r in out_rows}
    assert by_id["p1-0000"]["content_type"] == "Page-header"


def test_fixture_repetition_header_and_page_numbers():
    fixture = Path(__file__).parent / "fixtures" / "elements_core_headers_3pg.jsonl"
    rows = list(read_jsonl(fixture))
    out_rows, _ = run_tagging(rows)
    by_id = {r["id"]: r for r in out_rows}
    assert by_id["p1-0000"]["content_type"] == "Page-header"
    assert by_id["p2-0000"]["content_type"] == "Page-header"
    assert by_id["p3-0000"]["content_type"] == "Page-header"
    assert by_id["p1-0002"]["content_type"] == "Page-footer"
    assert by_id["p2-0002"]["content_type"] == "Page-footer"
    assert by_id["p3-0002"]["content_type"] == "Page-footer"


def test_fixture_content_types_rubric_v1():
    fixture = Path(__file__).parent / "fixtures" / "elements_core_content_types_rubric_v1.jsonl"
    rows = list(read_jsonl(fixture))
    out_rows, _ = run_tagging(rows)
    by_id = {r["id"]: r for r in out_rows}

    assert by_id["p1-0000"]["content_type"] == "Title"
    assert by_id["p1-0001"]["content_type"] == "Page-header"
    assert by_id["p1-0002"]["content_type"] == "Title"
    assert by_id["p1-0003"]["content_type"] == "List-item"
    assert by_id["p1-0004"]["content_type"] == "Section-header"

    assert by_id["p1-0005"]["content_type"] == "Text"
    assert by_id["p1-0005"]["content_subtype"]["combat_stats"] is True
    kv = by_id["p1-0005"]["content_subtype"]["key_value"]
    assert kv["entity"] == "MANTICORE"
    assert {"key": "SKILL", "value": 11} in kv["pairs"]
    assert {"key": "STAMINA", "value": 11} in kv["pairs"]

    assert by_id["p1-0006"]["content_type"] == "Text"
    assert by_id["p1-0006"]["content_subtype"]["form_field"] is True
    assert by_id["p1-0006"]["content_subtype"]["key_value"]["pairs"] == [{"key": "STAMINA", "value": None}]

    assert by_id["p1-0007"]["content_type"] == "Text"
    assert by_id["p1-0007"]["content_subtype"]["form_field"] is True
    assert "key_value" not in by_id["p1-0007"]["content_subtype"]

    assert by_id["p1-0008"]["content_type"] == "Section-header"
    assert by_id["p1-0008"]["content_subtype"]["number"] == 42

    assert by_id["p1-0009"]["content_type"] == "Page-footer"
    assert by_id["p1-0009"]["content_subtype"]["page_number"] == 9
