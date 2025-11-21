import json
import os
import sys
import tempfile
import unittest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from driver import concat_dedupe_jsonl


class MergeTests(unittest.TestCase):
    def test_concat_dedupe_by_portion_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            f1 = os.path.join(tmp, "a.jsonl")
            f2 = os.path.join(tmp, "b.jsonl")
            out = os.path.join(tmp, "out.jsonl")
            rows1 = [
                {"portion_id": "P1", "v": 1},
                {"portion_id": "P2", "v": 2},
            ]
            rows2 = [
                {"portion_id": "P2", "v": 3},  # dup id should drop
                {"portion_id": "P3", "v": 4},
            ]
            with open(f1, "w", encoding="utf-8") as f:
                for r in rows1:
                    f.write(json.dumps(r) + "\n")
            with open(f2, "w", encoding="utf-8") as f:
                for r in rows2:
                    f.write(json.dumps(r) + "\n")

            concat_dedupe_jsonl([f1, f2], out, key_field="portion_id")

            with open(out, "r", encoding="utf-8") as f:
                lines = [json.loads(l) for l in f if l.strip()]
            self.assertEqual([r["portion_id"] for r in lines], ["P1", "P2", "P3"])
            self.assertEqual(len(lines), 3)


if __name__ == "__main__":
    unittest.main()
