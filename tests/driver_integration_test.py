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
                     "needs": ["clean_pages"], "out": "win_coarse.jsonl"},
                    {"id": "portionize_fine", "stage": "portionize", "module": "portionize_sliding_v1",
                     "needs": ["clean_pages"], "out": "win_fine.jsonl"},
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
            self.assertTrue((run_dir / "win_coarse.jsonl").exists())
            self.assertTrue((run_dir / "win_fine.jsonl").exists())

    def test_param_validation_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            recipe_path = tmp_path / "recipe_bad.yaml"
            recipe = {
                "run_id": "bad-params",
                "input": {"text_glob": str(tmp_path / "*.md")},
                "output_dir": str(tmp_path / "run"),
                "stages": [
                    {"id": "extract_text", "stage": "extract", "module": "extract_text_v1"},
                    {"id": "clean_pages", "stage": "clean", "module": "clean_llm_v1", "needs": ["extract_text"],
                     "params": {"min_conf": "high"}},  # invalid type
                ],
            }
            recipe_path.write_text(json.dumps(recipe), encoding="utf-8")

            cmd = [
                sys.executable, "driver.py",
                "--recipe", str(recipe_path),
                "--dry-run",
                "--registry", "modules",
            ]
            result = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parents[1]))
            self.assertNotEqual(result.returncode, 0)

    def test_resume_honors_stage_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_dir = tmp_path / "input"
            input_dir.mkdir(parents=True, exist_ok=True)
            sample = input_dir / "sample.md"
            sample.write_text("Resume check sample.", encoding="utf-8")

            recipe_path = tmp_path / "recipe.yaml"
            recipe = {
                "run_id": "resume-out-test",
                "input": {"text_glob": str(input_dir / "*.md")},
                "output_dir": str(tmp_path / "run"),
                "stages": [
                    {"id": "extract_text", "stage": "extract", "module": "extract_text_v1"},
                    {"id": "clean_pages", "stage": "clean", "module": "clean_llm_v1", "needs": ["extract_text"],
                     "out": "clean_custom.jsonl"},
                ],
            }
            recipe_path.write_text(json.dumps(recipe), encoding="utf-8")

            base_cmd = [
                sys.executable, "driver.py",
                "--recipe", str(recipe_path),
                "--mock",
                "--registry", "modules",
            ]
            first = subprocess.run(base_cmd + ["--skip-done"], cwd=str(Path(__file__).resolve().parents[1]))
            self.assertEqual(first.returncode, 0)
            clean_path = tmp_path / "run" / "clean_custom.jsonl"
            self.assertTrue(clean_path.exists())
            first_mtime = clean_path.stat().st_mtime

            second = subprocess.run(base_cmd + ["--skip-done"], cwd=str(Path(__file__).resolve().parents[1]))
            self.assertEqual(second.returncode, 0)
            second_mtime = clean_path.stat().st_mtime
            self.assertEqual(first_mtime, second_mtime)

    def test_multi_stage_custom_outputs_propagate(self):
        """
        Smoke: ensure custom out on upstream stages propagates through downstream inputs across >2 hops.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_dir = tmp_path / "input"
            input_dir.mkdir(parents=True, exist_ok=True)
            sample = input_dir / "sample.md"
            sample.write_text("Propagation sample.", encoding="utf-8")

            recipe_path = tmp_path / "recipe.yaml"
            recipe = {
                "run_id": "multi-out-smoke",
                "input": {"text_glob": str(input_dir / "*.md")},
                "output_dir": str(tmp_path / "run"),
                "stages": [
                    {"id": "extract_text", "stage": "extract", "module": "extract_text_v1"},
                    {"id": "clean_pages", "stage": "clean", "module": "clean_llm_v1", "needs": ["extract_text"],
                     "out": "clean_custom.jsonl"},
                    {"id": "portionize_main", "stage": "portionize", "module": "portionize_sliding_v1",
                     "needs": ["clean_pages"], "out": "hyp_custom.jsonl"},
                    {"id": "consensus_main", "stage": "consensus", "module": "consensus_vote_v1",
                     "needs": ["portionize_main"], "out": "locked_custom.jsonl"},
                ],
            }
            recipe_path.write_text(json.dumps(recipe), encoding="utf-8")

            cmd = [
                sys.executable, "driver.py",
                "--recipe", str(recipe_path),
                "--mock",
                "--registry", "modules",
                "--skip-done",
            ]
            result = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parents[1]))
            self.assertEqual(result.returncode, 0)

            run_dir = tmp_path / "run"
            self.assertTrue((run_dir / "clean_custom.jsonl").exists())
            self.assertTrue((run_dir / "hyp_custom.jsonl").exists())
            self.assertTrue((run_dir / "locked_custom.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
