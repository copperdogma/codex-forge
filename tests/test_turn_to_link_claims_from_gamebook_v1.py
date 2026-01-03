import json
import os
import sys
import tempfile

import modules.adapter.turn_to_link_claims_from_gamebook_v1.main as claims


def test_claims_from_gamebook_targets():
    with tempfile.TemporaryDirectory() as tmpdir:
        gamebook_path = os.path.join(tmpdir, "gamebook.json")
        out_path = os.path.join(tmpdir, "claims.jsonl")
        gamebook = {
            "sections": {
                "1": {
                    "sequence": [
                        {"kind": "choice", "targetSection": "10"},
                        {"kind": "combat", "outcomes": {"win": {"targetSection": "20"}}},
                    ]
                }
            }
        }
        with open(gamebook_path, "w", encoding="utf-8") as f:
            json.dump(gamebook, f)

        argv = ["prog", "--input", gamebook_path, "--out", out_path]
        sys_argv = sys.argv
        try:
            sys.argv = argv
            claims.main()
        finally:
            sys.argv = sys_argv

        with open(out_path, "r", encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        targets = {row["target"] for row in rows}
        assert targets == {"10", "20"}
