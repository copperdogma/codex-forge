import json
import os
import sys
import tempfile
import unittest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from driver import build_plan, validate_plan_schemas, stamp_artifact
from driver import cleanup_artifact


class DriverPlanTests(unittest.TestCase):
    def setUp(self):
        # minimal registry stubs
        self.registry = {
            "m_extract": {"module_id": "m_extract", "stage": "extract", "entrypoint": "extract.py",
                          "output_schema": "s_out"},
            "m_clean": {"module_id": "m_clean", "stage": "clean", "entrypoint": "clean.py",
                        "input_schema": "s_out", "output_schema": "s_clean"},
            "m_portion": {"module_id": "m_portion", "stage": "portionize", "entrypoint": "portion.py",
                          "input_schema": "s_clean", "output_schema": "s_portion"},
            "m_merge": {"module_id": "m_merge", "stage": "adapter", "entrypoint": "merge.py",
                        "input_schema": "s_portion", "output_schema": "s_portion"},
            "m_consensus": {"module_id": "m_consensus", "stage": "consensus", "entrypoint": "consensus.py",
                            "input_schema": "s_portion", "output_schema": "locked"},
            "m_param": {"module_id": "m_param", "stage": "extract", "entrypoint": "param.py",
                        "param_schema": {"properties": {"start": {"type": "integer", "minimum": 1},
                                                        "lang": {"type": "string"}},
                                         "required": ["start"]}},
        }

    def test_cycle_detection(self):
        recipe = {
            "stages": [
                {"id": "a", "stage": "extract", "module": "m_extract", "needs": ["b"]},
                {"id": "b", "stage": "clean", "module": "m_clean", "needs": ["a"]},
            ]
        }
        with self.assertRaises(SystemExit):
            build_plan(recipe, self.registry)

    def test_param_validation_unknown_param(self):
        recipe = {
            "stages": [
                {"id": "a", "stage": "extract", "module": "m_param", "params": {"bogus": 1}},
            ]
        }
        with self.assertRaises(SystemExit):
            build_plan(recipe, self.registry)

    def test_param_validation_type_mismatch(self):
        recipe = {
            "stages": [
                {"id": "a", "stage": "extract", "module": "m_param", "params": {"start": "one"}},
            ]
        }
        with self.assertRaises(SystemExit):
            build_plan(recipe, self.registry)

    def test_stage_out_overrides_outputs_map(self):
        recipe = {
            "outputs": {"a": "from_outputs.jsonl"},
            "stages": [
                {"id": "a", "stage": "portionize", "module": "m_portion", "out": "from_stage.jsonl"},
            ]
        }
        plan = build_plan(recipe, self.registry)
        self.assertEqual(plan["nodes"]["a"]["artifact_name"], "from_stage.jsonl")

    def test_outputs_map_used_when_no_stage_out(self):
        recipe = {
            "outputs": {"a": "from_outputs.jsonl"},
            "stages": [
                {"id": "a", "stage": "portionize", "module": "m_portion"},
            ]
        }
        plan = build_plan(recipe, self.registry)
        self.assertEqual(plan["nodes"]["a"]["artifact_name"], "from_outputs.jsonl")

    def test_schema_mismatch(self):
        recipe = {
            "stages": [
                {"id": "a", "stage": "extract", "module": "m_extract"},
                {"id": "b", "stage": "clean", "module": "m_clean", "needs": ["a"]},
                {"id": "c", "stage": "portionize", "module": "m_portion", "needs": ["a"]},  # wrong dep schema
            ]
        }
        plan = build_plan(recipe, self.registry)
        with self.assertRaises(SystemExit):
            validate_plan_schemas(plan)

    def test_schema_match_passes(self):
        recipe = {
            "stages": [
                {"id": "a", "stage": "extract", "module": "m_extract"},
                {"id": "b", "stage": "clean", "module": "m_clean", "needs": ["a"]},
                {"id": "c", "stage": "portionize", "module": "m_portion", "needs": ["b"]},
            ]
        }
        plan = build_plan(recipe, self.registry)
        validate_plan_schemas(plan)  # should not raise

    def test_duplicate_ids_rejected(self):
        recipe = {
            "stages": [
                {"id": "a", "stage": "extract", "module": "m_extract"},
                {"id": "a", "stage": "clean", "module": "m_clean", "needs": ["a"]},
            ]
        }
        with self.assertRaises(SystemExit):
            build_plan(recipe, self.registry)

    def test_adapter_allows_multi_input_consensus(self):
        recipe = {
            "stages": [
                {"id": "a", "stage": "extract", "module": "m_extract"},
                {"id": "b", "stage": "clean", "module": "m_clean", "needs": ["a"]},
                {"id": "p1", "stage": "portionize", "module": "m_portion", "needs": ["b"]},
                {"id": "p2", "stage": "portionize", "module": "m_portion", "needs": ["b"]},
                {"id": "merge", "stage": "adapter", "module": "m_merge", "needs": ["p1", "p2"]},
                {"id": "cons", "stage": "consensus", "module": "m_consensus", "needs": ["merge"]},
            ]
        }
        plan = build_plan(recipe, self.registry)
        validate_plan_schemas(plan)  # should not raise

    def test_stamp_artifact_backfills_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "locked.jsonl")
            rows = [{
                "portion_id": "P001",
                "page_start": 1,
                "page_end": 1,
                "confidence": 0.5,
                "source_images": [],
            }]
            with open(path, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")

            stamp_artifact(path, "locked_portion_v1", "mod_a", "run_a")

            with open(path, "r", encoding="utf-8") as f:
                stamped = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(len(stamped), 1)
            row = stamped[0]
            self.assertEqual(row["module_id"], "mod_a")
            self.assertEqual(row["run_id"], "run_a")
            self.assertEqual(row["schema_version"], "locked_portion_v1")
            self.assertIn("created_at", row)

    def test_cleanup_artifact_removes_on_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write("old\n")
            self.assertTrue(os.path.exists(path))
            cleanup_artifact(path, force=True)
            self.assertFalse(os.path.exists(path))
            # no-op when file missing
            cleanup_artifact(path, force=True)


if __name__ == "__main__":
    unittest.main()
