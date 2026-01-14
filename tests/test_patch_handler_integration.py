"""
Integration tests for patch handler system (Story 123).

Tests patch application via driver.py's apply_before/apply_after logic.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from modules.common.patch_handler import load_patches, apply_patch


class TestPatchHandlerIntegration(unittest.TestCase):
    """Test patch handler integration with driver.py logic."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.run_dir = Path(self.test_dir) / "run"
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_add_link_patch_applies_correctly(self):
        """Test that add_link operation applies correctly to gamebook.json."""
        # Create a minimal gamebook
        gamebook_path = self.run_dir / "gamebook.json"
        gamebook = {
            "metadata": {"title": "Test Book"},
            "sections": {
                "1": {
                    "id": "1",
                    "presentation_html": "<p>Test section</p>",
                    "isGameplaySection": True,
                    "type": "section",
                    "sequence": [],
                },
            },
        }
        with open(gamebook_path, "w", encoding="utf-8") as f:
            json.dump(gamebook, f, indent=2)

        # Create a patch
        patch = {
            "id": "test-add-link",
            "apply_after": "build_ff_engine_with_issues_v1",
            "operation": "add_link",
            "target_file": "gamebook.json",
            "section": "1",
            "link": {
                "kind": "choice",
                "targetSection": "2",
                "choiceText": "Go to section 2",
                "metadata": {
                    "patchApplied": True,
                    "patchId": "test-add-link",
                },
            },
        }

        # Apply patch
        result = apply_patch(patch, str(self.run_dir), "build_ff_engine_with_issues_v1", str(gamebook_path))
        self.assertTrue(result.get("success"), f"Patch application failed: {result.get('error')}")

        # Verify patch was applied
        with open(gamebook_path, "r", encoding="utf-8") as f:
            patched_gamebook = json.load(f)

        sequence = patched_gamebook["sections"]["1"]["sequence"]
        self.assertEqual(len(sequence), 1, "Expected one choice in sequence")
        self.assertEqual(sequence[0]["kind"], "choice")
        self.assertEqual(sequence[0]["targetSection"], "2")
        self.assertEqual(sequence[0]["choiceText"], "Go to section 2")
        self.assertTrue(sequence[0].get("metadata", {}).get("patchApplied"))

    def test_remove_link_patch_applies_correctly(self):
        """Test that remove_link operation applies correctly."""
        # Create gamebook with existing link
        gamebook_path = self.run_dir / "gamebook.json"
        gamebook = {
            "metadata": {"title": "Test Book"},
            "sections": {
                "1": {
                    "id": "1",
                    "presentation_html": "<p>Test section</p>",
                    "isGameplaySection": True,
                    "type": "section",
                    "sequence": [
                        {
                            "kind": "choice",
                            "targetSection": "2",
                            "choiceText": "Remove this",
                        },
                        {
                            "kind": "choice",
                            "targetSection": "3",
                            "choiceText": "Keep this",
                        },
                    ],
                },
            },
        }
        with open(gamebook_path, "w", encoding="utf-8") as f:
            json.dump(gamebook, f, indent=2)

        # Create patch to remove link
        patch = {
            "id": "test-remove-link",
            "apply_after": "build_ff_engine_with_issues_v1",
            "operation": "remove_link",
            "target_file": "gamebook.json",
            "section": "1",
            "link_match": {
                "targetSection": "2",
            },
        }

        # Apply patch
        result = apply_patch(patch, str(self.run_dir), "build_ff_engine_with_issues_v1", str(gamebook_path))
        self.assertTrue(result.get("success"), f"Patch application failed: {result.get('error')}")

        # Verify patch was applied
        with open(gamebook_path, "r", encoding="utf-8") as f:
            patched_gamebook = json.load(f)

        sequence = patched_gamebook["sections"]["1"]["sequence"]
        self.assertEqual(len(sequence), 1, "Expected one choice remaining")
        self.assertEqual(sequence[0]["targetSection"], "3")

    def test_override_field_patch_applies_correctly(self):
        """Test that override_field operation applies correctly."""
        # Create gamebook
        gamebook_path = self.run_dir / "gamebook.json"
        gamebook = {
            "metadata": {"title": "Test Book"},
            "sections": {
                "1": {
                    "id": "1",
                    "presentation_html": "<p>Original</p>",
                    "isGameplaySection": True,
                    "type": "section",
                    "sequence": [],
                },
            },
        }
        with open(gamebook_path, "w", encoding="utf-8") as f:
            json.dump(gamebook, f, indent=2)

        # Create patch to override field
        patch = {
            "id": "test-override",
            "apply_after": "build_ff_engine_with_issues_v1",
            "operation": "override_field",
            "target_file": "gamebook.json",
            "section": "1",
            "field_path": "presentation_html",
            "value": "<p>Overridden</p>",
        }

        # Apply patch
        result = apply_patch(patch, str(self.run_dir), "build_ff_engine_with_issues_v1", str(gamebook_path))
        self.assertTrue(result.get("success"), f"Patch application failed: {result.get('error')}")

        # Verify patch was applied
        with open(gamebook_path, "r", encoding="utf-8") as f:
            patched_gamebook = json.load(f)

        self.assertEqual(patched_gamebook["sections"]["1"]["presentation_html"], "<p>Overridden</p>")

    def test_patch_file_loading(self):
        """Test that patch file loading works correctly."""
        # Create a patch file
        patch_file = self.run_dir / "patch.json"
        patch_data = {
            "book_id": "test-book",
            "schema_version": "patch_v1",
            "patches": [
                {
                    "id": "test-1",
                    "apply_after": "build_ff_engine_with_issues_v1",
                    "operation": "add_link",
                    "target_file": "gamebook.json",
                    "section": "1",
                    "link": {"kind": "choice", "targetSection": "2"},
                },
            ],
        }
        with open(patch_file, "w", encoding="utf-8") as f:
            json.dump(patch_data, f, indent=2)

        # Load patches
        loaded = load_patches(str(patch_file))
        self.assertEqual(loaded["book_id"], "test-book")
        self.assertEqual(len(loaded["patches"]), 1)
        self.assertEqual(loaded["patches"][0]["id"], "test-1")

    def test_patch_validation_requires_apply_before_or_after(self):
        """Test that patches must have either apply_before or apply_after."""
        patch_file = self.run_dir / "patch.json"
        patch_data = {
            "book_id": "test-book",
            "schema_version": "patch_v1",
            "patches": [
                {
                    "id": "test-invalid",
                    "operation": "add_link",
                    "target_file": "gamebook.json",
                    "section": "1",
                    "link": {"kind": "choice", "targetSection": "2"},
                    # Missing apply_before and apply_after
                },
            ],
        }
        with open(patch_file, "w", encoding="utf-8") as f:
            json.dump(patch_data, f, indent=2)

        # Loading should raise ValueError
        with self.assertRaises(ValueError) as cm:
            load_patches(str(patch_file))
        self.assertIn("apply_before", str(cm.exception).lower() or "apply_after", str(cm.exception).lower())


if __name__ == "__main__":
    unittest.main()
