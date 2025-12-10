import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


class DriverIntegrationTests(unittest.TestCase):

    def test_snapshots_written_and_manifest_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_dir = tmp_path / "input"
            input_dir.mkdir(parents=True, exist_ok=True)
            sample = input_dir / "sample.md"
            sample.write_text("Snapshot sample.", encoding="utf-8")

            run_id = f"snapshot-smoke-{int(time.time() * 1000)}"
            recipe_path = tmp_path / "recipe.yaml"
            recipe = {
                "run_id": run_id,
                "input": {"text_glob": str(input_dir / "*.md")},
                "output_dir": str(tmp_path / "run"),
                "stages": [
                    {"id": "extract_text", "stage": "extract", "module": "extract_text_v1"},
                    {"id": "clean_pages", "stage": "clean", "module": "clean_llm_v1", "needs": ["extract_text"]},
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
            snap_dir = run_dir / "snapshots"
            self.assertTrue((snap_dir / "recipe.yaml").is_file())
            self.assertTrue((snap_dir / "plan.json").is_file())
            self.assertTrue((snap_dir / "registry.json").is_file())

            manifest_path = Path(__file__).resolve().parents[1] / "output" / "run_manifest.jsonl"
            self.assertTrue(manifest_path.exists())
            with open(manifest_path, "r", encoding="utf-8") as f:
                entries = [json.loads(line) for line in f if line.strip()]
            target = next((e for e in entries if e.get("run_id") == run_id), None)
            self.assertIsNotNone(target)
            self.assertIn("snapshots", target)
            for key in ("recipe", "plan", "registry"):
                self.assertIn(key, target["snapshots"])

    def test_settings_snapshot_and_relpaths_outside_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            settings_path = tmp_path / "settings.custom.yaml"
            settings_path.write_text("paths:\n  tesseract_cmd: /usr/bin/tesseract\n", encoding="utf-8")

            input_dir = tmp_path / "input"
            input_dir.mkdir(parents=True, exist_ok=True)
            sample = input_dir / "sample.md"
            sample.write_text("Settings snapshot sample.", encoding="utf-8")

            run_id = f"snapshot-settings-{int(time.time() * 1000)}"
            recipe_path = tmp_path / "recipe.yaml"
            recipe = {
                "run_id": run_id,
                "input": {"text_glob": str(input_dir / "*.md")},
                "output_dir": str(tmp_path / "run"),
                "settings": str(settings_path),
                "stages": [
                    {"id": "extract_text", "stage": "extract", "module": "extract_text_v1"},
                    {"id": "clean_pages", "stage": "clean", "module": "clean_llm_v1", "needs": ["extract_text"]},
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
            repo_root = Path(__file__).resolve().parents[1]
            result = subprocess.run(cmd, cwd=str(repo_root))
            self.assertEqual(result.returncode, 0)

            run_dir = tmp_path / "run"
            snap_dir = run_dir / "snapshots"
            settings_copy = snap_dir / "settings.yaml"
            self.assertTrue(settings_copy.is_file())
            self.assertIn("tesseract_cmd", settings_copy.read_text(encoding="utf-8"))

            manifest_path = repo_root / "output" / "run_manifest.jsonl"
            self.assertTrue(manifest_path.exists())
            with open(manifest_path, "r", encoding="utf-8") as f:
                entries = [json.loads(line) for line in f if line.strip()]
            target = next((e for e in entries if e.get("run_id") == run_id), None)
            self.assertIsNotNone(target)
            settings_rel = target["snapshots"].get("settings")
            self.assertIsNotNone(settings_rel)
            # Relpath should not be absolute and should resolve to the copied settings
            self.assertFalse(os.path.isabs(settings_rel))
            resolved_settings = repo_root / settings_rel
            self.assertTrue(resolved_settings.is_file())

    def test_pricing_and_instrumentation_snapshots_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pricing_path = tmp_path / "pricing.yaml"
            pricing_path.write_text(
                "default:\n  prompt_per_1k: 0.1\n  completion_per_1k: 0.2\ncurrency: USD\n",
                encoding="utf-8",
            )

            input_dir = tmp_path / "input"
            input_dir.mkdir(parents=True, exist_ok=True)
            (input_dir / "sample.md").write_text("Instrumentation snapshot sample.", encoding="utf-8")

            run_id = f"snapshot-instrument-{int(time.time() * 1000)}"
            recipe_path = tmp_path / "recipe.yaml"
            recipe = {
                "run_id": run_id,
                "name": "pricing-instrument-snap",
                "input": {"text_glob": str(input_dir / "*.md")},
                "output_dir": str(tmp_path / "run"),
                "instrumentation": {"enabled": True, "price_table": str(pricing_path)},
                "stages": [
                    {"id": "extract_text", "stage": "extract", "module": "extract_text_v1"},
                    {"id": "clean_pages", "stage": "clean", "module": "clean_llm_v1", "needs": ["extract_text"]},
                ],
            }
            recipe_path.write_text(json.dumps(recipe), encoding="utf-8")

            cmd = [
                sys.executable,
                "driver.py",
                "--recipe",
                str(recipe_path),
                "--mock",
                "--registry",
                "modules",
                "--skip-done",
                "--instrument",
                "--price-table",
                str(pricing_path),
            ]
            repo_root = Path(__file__).resolve().parents[1]
            result = subprocess.run(cmd, cwd=str(repo_root))
            self.assertEqual(result.returncode, 0)

            run_dir = tmp_path / "run"
            snap_dir = run_dir / "snapshots"
            pricing_copy = snap_dir / "pricing.yaml"
            instr_copy = snap_dir / "instrumentation.json"
            self.assertTrue(pricing_copy.is_file())
            self.assertTrue(instr_copy.is_file())

            manifest_path = repo_root / "output" / "run_manifest.jsonl"
            self.assertTrue(manifest_path.exists())
            with open(manifest_path, "r", encoding="utf-8") as f:
                entries = [json.loads(line) for line in f if line.strip()]
            target = next((e for e in entries if e.get("run_id") == run_id), None)
            self.assertIsNotNone(target)
            snaps = target.get("snapshots", {})
            self.assertIn("pricing", snaps)
            self.assertIn("instrumentation", snaps)
            self.assertFalse(os.path.isabs(snaps["pricing"]))
            self.assertFalse(os.path.isabs(snaps["instrumentation"]))

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


if __name__ == "__main__":
    unittest.main()
