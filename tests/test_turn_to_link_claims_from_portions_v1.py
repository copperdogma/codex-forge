import json
import os
import sys
import tempfile

import modules.adapter.turn_to_link_claims_from_portions_v1.main as claims


def test_claims_from_portions():
    with tempfile.TemporaryDirectory() as tmpdir:
        portions_path = os.path.join(tmpdir, "portions.jsonl")
        out_path = os.path.join(tmpdir, "claims.jsonl")

        portion = {
            "portion_id": "p1",
            "section_id": "1",
            "turn_to_claims": [{"target": "99", "claim_type": "combat", "module_id": "extract_combat_v1"}],
            "choices": [{"target": "10"}],
            "test_luck": [{"lucky_section": "20", "unlucky_section": "30"}],
            "stat_checks": [{"pass_section": "40", "fail_section": "50"}],
            "inventory": {"inventory_checks": [{"target_section": "60"}]},
            "combat": [{"outcomes": {"win": {"targetSection": "70"}}}],
        }
        with open(portions_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(portion) + "\n")

        argv = ["prog", "--input", portions_path, "--out", out_path]
        sys_argv = sys.argv
        try:
            sys.argv = argv
            claims.main()
        finally:
            sys.argv = sys_argv

        with open(out_path, "r", encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        targets = {row["target"] for row in rows}
        assert targets == {"99"}


def test_claims_fallback_without_explicit():
    with tempfile.TemporaryDirectory() as tmpdir:
        portions_path = os.path.join(tmpdir, "portions.jsonl")
        out_path = os.path.join(tmpdir, "claims.jsonl")

        portion = {
            "portion_id": "p2",
            "section_id": "2",
            "choices": [{"target": "10"}],
            "test_luck": [{"lucky_section": "20", "unlucky_section": "30"}],
            "stat_checks": [{"pass_section": "40", "fail_section": "50"}],
            "inventory": {"inventory_checks": [{"target_section": "60"}]},
            "combat": [{"outcomes": {"win": {"targetSection": "70"}}}],
        }
        with open(portions_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(portion) + "\n")

        argv = ["prog", "--input", portions_path, "--out", out_path]
        sys_argv = sys.argv
        try:
            sys.argv = argv
            claims.main()
        finally:
            sys.argv = sys_argv

        with open(out_path, "r", encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        targets = {row["target"] for row in rows}
        assert targets == {"10", "20", "30", "40", "50", "60", "70"}
