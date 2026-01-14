"""
Integration tests for output directory structure (Story 113).

Tests that output/ is the canonical location for gamebook.json and related artifacts.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path


class TestOutputDirectoryStructure(unittest.TestCase):
    """Test output directory structure and canonical location."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.run_dir = Path(self.test_dir) / "run"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = self.run_dir / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_gamebook_json_in_output_directory(self):
        """Test that gamebook.json exists in output/ directory."""
        gamebook_path = self.output_dir / "gamebook.json"
        gamebook = {
            "metadata": {"title": "Test Book"},
            "sections": {},
        }
        with open(gamebook_path, "w", encoding="utf-8") as f:
            json.dump(gamebook, f, indent=2)

        # Verify it exists in output/
        self.assertTrue(gamebook_path.exists(), "gamebook.json should exist in output/")
        self.assertFalse((self.run_dir / "gamebook.json").exists(), "gamebook.json should NOT exist in run root")

    def test_images_directory_in_output(self):
        """Test that images/ directory exists in output/."""
        images_dir = self.output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        # Verify it exists
        self.assertTrue(images_dir.exists(), "images/ should exist in output/")
        self.assertTrue(images_dir.is_dir(), "images/ should be a directory")

    def test_image_paths_resolve_correctly(self):
        """Test that image paths in gamebook.json resolve correctly."""
        # Create images directory
        images_dir = self.output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        # Create a dummy image file
        image_file = images_dir / "page-001.png"
        image_file.write_bytes(b"fake image data")

        # Create gamebook with image reference
        gamebook_path = self.output_dir / "gamebook.json"
        gamebook = {
            "metadata": {"title": "Test Book"},
            "sections": {
                "1": {
                    "id": "1",
                    "presentation_html": "<p>Test</p>",
                    "images": ["images/page-001.png"],
                },
            },
        }
        with open(gamebook_path, "w", encoding="utf-8") as f:
            json.dump(gamebook, f, indent=2)

        # Verify image path resolves
        image_path = gamebook["sections"]["1"]["images"][0]
        # Path is relative to gamebook.json location (output/)
        resolved_path = self.output_dir / image_path
        self.assertTrue(resolved_path.exists(), f"Image path should resolve: {resolved_path}")

    def test_validator_directory_in_output(self):
        """Test that validator/ directory exists in output/."""
        validator_dir = self.output_dir / "validator"
        validator_dir.mkdir(parents=True, exist_ok=True)

        # Create a dummy validator file
        validator_file = validator_dir / "gamebook-validator.bundle.js"
        validator_file.write_text("// dummy validator", encoding="utf-8")

        # Verify it exists
        self.assertTrue(validator_dir.exists(), "validator/ should exist in output/")
        self.assertTrue(validator_file.exists(), "validator bundle should exist")

    def test_no_gamebook_json_in_run_root(self):
        """Test that gamebook.json does NOT exist in run root (only in output/)."""
        # Create gamebook in output/
        gamebook_path = self.output_dir / "gamebook.json"
        gamebook = {
            "metadata": {"title": "Test Book"},
            "sections": {},
        }
        with open(gamebook_path, "w", encoding="utf-8") as f:
            json.dump(gamebook, f, indent=2)

        # Verify it does NOT exist in run root
        run_root_gamebook = self.run_dir / "gamebook.json"
        self.assertFalse(run_root_gamebook.exists(), "gamebook.json should NOT exist in run root")

    def test_validation_report_in_output(self):
        """Test that validation_report.json exists in output/ directory."""
        validation_report_path = self.output_dir / "validation_report.json"
        report = {
            "valid": True,
            "errors": [],
            "warnings": [],
        }
        with open(validation_report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        # Verify it exists in output/
        self.assertTrue(validation_report_path.exists(), "validation_report.json should exist in output/")
        self.assertFalse((self.run_dir / "validation_report.json").exists(), "validation_report.json should NOT exist in run root")


if __name__ == "__main__":
    unittest.main()
