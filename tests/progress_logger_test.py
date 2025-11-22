import json
import os
import tempfile
import unittest

from modules.common.utils import (
    ProgressLogger,
    PROGRESS_STATUS_VALUES,
)


class ProgressLoggerTests(unittest.TestCase):
    def test_appends_without_clobbering_existing_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            progress_path = os.path.join(tmp, "events.jsonl")
            state_path = os.path.join(tmp, "state.json")

            baseline = {"existing": True}
            with open(progress_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(baseline) + "\n")

            logger = ProgressLogger(state_path=state_path, progress_path=progress_path, run_id="t-run")
            event = logger.log("extract", "running", current=1, total=2, message="first page",
                               artifact="/tmp/out.jsonl", module_id="mod", schema_version="s_v1")

            with open(progress_path, "r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]

            self.assertEqual(lines[0], baseline)
            self.assertEqual(lines[1]["stage"], "extract")
            self.assertEqual(lines[1]["status"], "running")
            self.assertAlmostEqual(lines[1]["percent"], 50.0)
            self.assertEqual(len(lines), 2)

            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            stage_state = state["stages"]["extract"]
            self.assertEqual(stage_state["status"], "running")
            self.assertEqual(stage_state["progress"]["current"], 1)
            self.assertEqual(stage_state["progress"]["total"], 2)

    def test_rejects_invalid_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            progress_path = os.path.join(tmp, "events.jsonl")
            state_path = os.path.join(tmp, "state.json")
            logger = ProgressLogger(state_path=state_path, progress_path=progress_path, run_id="t-run")
            with self.assertRaises(ValueError):
                logger.log("extract", "bogus", current=1, total=1)
            self.assertIn("running", PROGRESS_STATUS_VALUES)


if __name__ == "__main__":
    unittest.main()
