import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from driver import build_plan, validate_plan_schemas


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


if __name__ == "__main__":
    unittest.main()
