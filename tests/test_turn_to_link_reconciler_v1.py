import json
import os
import sys
import tempfile

import modules.adapter.turn_to_link_reconciler_v1.main as reconciler


def test_reconciler_reports_unclaimed_links():
    with tempfile.TemporaryDirectory() as tmpdir:
        links_path = os.path.join(tmpdir, "links.jsonl")
        claims_path = os.path.join(tmpdir, "claims.jsonl")
        out_path = os.path.join(tmpdir, "unclaimed.jsonl")

        links_row = {
            "schema_version": "turn_to_links_v1",
            "section_id": "1",
            "links": ["10", "20"],
        }
        with open(links_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(links_row) + "\n")

        claim_row = {
            "schema_version": "turn_to_link_claims_v1",
            "section_id": "1",
            "target": "10",
            "claim_type": "choice",
        }
        with open(claims_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(claim_row) + "\n")

        argv = [
            "prog",
            "--links",
            links_path,
            "--claims",
            claims_path,
            "--out",
            out_path,
        ]
        sys_argv = sys.argv
        try:
            sys.argv = argv
            reconciler.main()
        finally:
            sys.argv = sys_argv

        with open(out_path, "r", encoding="utf-8") as f:
            report = json.loads(f.readline())
        assert report["summary"]["unclaimed_total"] == 1
        assert report["issues"][0]["target"] == "20"
