import json
import os
import sys
import tempfile
import unittest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from driver import artifact_schema_matches


class ResumeTests(unittest.TestCase):
    def test_artifact_schema_matches_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.jsonl")
            rows = [
                {"schema_version": "clean_page_v1", "foo": 1},
                {"schema_version": "clean_page_v1", "foo": 2},
            ]
            with open(path, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
            self.assertTrue(artifact_schema_matches(path, "clean_page_v1"))

    def test_artifact_schema_matches_negative(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.jsonl")
            rows = [
                {"schema_version": "other_v1", "foo": 1},
            ]
            with open(path, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
            self.assertFalse(artifact_schema_matches(path, "clean_page_v1"))


if __name__ == "__main__":
    unittest.main()
