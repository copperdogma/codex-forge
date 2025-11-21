import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DriverIntegrationTests(unittest.TestCase):
    def test_mock_dag_with_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_dir = tmp_path / "input"
            input_dir.mkdir(parents=True, exist_ok=True)
            sample = input_dir / "sample.md"
            sample.write_text("A tiny sample page for integration test.", encoding="utf-8")

            recipe_path = tmp_path / "recipe.yaml"
            recipe = {
                "run_id": "test-dag-integration",
                "input": {"text_glob": str(input_dir / "*.md")},
                "output_dir": str(tmp_path / "run"),
                "outputs": {
                    "portionize_coarse": "window_hypotheses_coarse.jsonl",
                    "portionize_fine": "window_hypotheses_fine.jsonl",
                    "hyp_merge": "adapter_out.jsonl",
                    "consensus_merge": "portions_locked_merged.jsonl",
                },
                "stages": [
                    {"id": "extract_text", "stage": "extract", "module": "extract_text_v1",
                     "params": {"start_page": 1}},
                    {"id": "clean_pages", "stage": "clean", "module": "clean_llm_v1", "needs": ["extract_text"]},
                    {"id": "portionize_coarse", "stage": "portionize", "module": "portionize_sliding_v1",
                     "needs": ["clean_pages"]},
                    {"id": "portionize_fine", "stage": "portionize", "module": "portionize_sliding_v1",
                     "needs": ["clean_pages"]},
                    {"id": "hyp_merge", "stage": "adapter", "module": "merge_portion_hyp_v1",
                     "needs": ["portionize_coarse", "portionize_fine"]},
                    {"id": "consensus_merge", "stage": "consensus", "module": "consensus_vote_v1",
                     "needs": ["hyp_merge"]},
                ],
            }
            recipe_path.write_text(json.dumps(recipe), encoding="utf-8")

            cmd = [
                sys.executable, "driver.py",
                "--recipe", str(recipe_path),
                "--mock",
                "--skip-done",
                "--registry", "modules",
            ]
            result = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parents[1]))
            self.assertEqual(result.returncode, 0)

            # Verify artifacts exist
            run_dir = tmp_path / "run"
            self.assertTrue((run_dir / "adapter_out.jsonl").exists())
            self.assertTrue((run_dir / "portions_locked_merged.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
