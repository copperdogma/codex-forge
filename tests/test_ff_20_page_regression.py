import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
import hashlib
from collections import Counter, defaultdict


REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = REPO_ROOT / "testdata" / "ff-20-pages"
EXPECTED_GOLDENS = {
    "pagelines_final.jsonl": "Final OCR/line output",
    "pagelines_reconstructed.jsonl": "Reconstructed text after merges",
    "elements_core.jsonl": "Element extraction output with metadata",
    "section_boundaries_scan.jsonl": "Detected section boundaries",
    "ocr_quality_report.json": "Quality metrics for OCR/columns",
}
BASELINE_RUN_ID = "ff-canonical-full-20-test"
BASELINE_RUN_DIR = REPO_ROOT / "output" / "runs" / "ff-canonical"
RECIPE_PATH = REPO_ROOT / "configs" / "recipes" / "legacy" / "recipe-ff-canonical.yaml"

def _skip_if_baseline_run_dir_not_canonical_20_pages():
    """
    `output/` is git-ignored and frequently reused locally.
    Only enforce baseline-vs-golden comparisons when the baseline run directory
    clearly corresponds to the canonical 20-page baseline described in
    `testdata/ff-20-pages/README.md`.
    """
    snap = BASELINE_RUN_DIR / "snapshots" / "recipe.yaml"
    if not snap.exists():
        raise unittest.SkipTest(f"Baseline run snapshots missing: {snap}")
    text = snap.read_text(encoding="utf-8", errors="replace")
    # Conservative string checks avoid depending on YAML parsers in tests.
    if f"run_id: {BASELINE_RUN_ID}" not in text:
        raise unittest.SkipTest(
            f"Baseline run dir does not match expected run_id '{BASELINE_RUN_ID}': {snap}"
        )
    # Ensure intake stage is configured for pages 1-20 (spread-aware outputs are expected in goldens).
    if "start: 1" not in text or "end: 20" not in text:
        raise unittest.SkipTest(f"Baseline run dir is not configured for pages 1-20: {snap}")


def _skip_if_missing_golden():
    missing = [name for name in EXPECTED_GOLDENS if not (GOLDEN_DIR / name).exists()]
    if missing:
        raise unittest.SkipTest(
            f"Golden fixtures missing: {', '.join(missing)}. "
            f"Generate from run_id '{BASELINE_RUN_ID}' and copy into {GOLDEN_DIR}."
        )


class FF20PageRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not GOLDEN_DIR.exists():
            raise unittest.SkipTest(
                f"Golden directory absent: {GOLDEN_DIR}. "
                f"Create it and populate artifacts from run_id '{BASELINE_RUN_ID}'."
            )
        _skip_if_missing_golden()

    def test_golden_files_present_and_nonempty(self):
        for filename in EXPECTED_GOLDENS:
            path = GOLDEN_DIR / filename
            self.assertTrue(path.exists(), f"Missing golden file: {filename}")
            self.assertGreater(path.stat().st_size, 0, f"Golden file empty: {filename}")

    def test_golden_json_and_jsonl_parseable(self):
        for filename in EXPECTED_GOLDENS:
            path = GOLDEN_DIR / filename
            if filename.endswith(".jsonl"):
                with path.open("r", encoding="utf-8") as f:
                    # Parse first two lines to catch structural errors without loading entire file
                    for _ in range(2):
                        line = f.readline()
                        if not line:
                            break
                        json.loads(line)
            elif filename.endswith(".json"):
                json.loads(path.read_text(encoding="utf-8"))

    def test_baseline_counts_match_golden_counts(self):
        """
        Lightweight regression guard: compares counts from the canonical baseline
        run directory to the checked-in golden fixtures. This avoids re-running
        OCR/LLM work in CI but still catches accidental drift in stored artifacts.
        """
        if not BASELINE_RUN_DIR.exists():
            raise unittest.SkipTest(f"Baseline run dir missing: {BASELINE_RUN_DIR}")
        _skip_if_baseline_run_dir_not_canonical_20_pages()

        produced = {
            "pagelines_final.jsonl": BASELINE_RUN_DIR / "pagelines_final.jsonl",
            "pagelines_reconstructed.jsonl": BASELINE_RUN_DIR / "pagelines_reconstructed.jsonl",
            "elements_core.jsonl": BASELINE_RUN_DIR / "elements_core.jsonl",
            "section_boundaries_scan.jsonl": BASELINE_RUN_DIR / "section_boundaries_scan.jsonl",
            "ocr_quality_report.json": BASELINE_RUN_DIR / "ocr_ensemble" / "ocr_quality_report.json",
        }

        for name, path in produced.items():
            self.assertTrue(path.exists(), f"Missing pipeline artifact: {name}")

        def jsonl_count(path: Path) -> int:
            with path.open("r", encoding="utf-8") as f:
                return sum(1 for _ in f if _.strip())

        count_checks = {
            "pagelines_final.jsonl": jsonl_count,
            "pagelines_reconstructed.jsonl": jsonl_count,
            "elements_core.jsonl": jsonl_count,
            "section_boundaries_scan.jsonl": jsonl_count,
            "ocr_quality_report.json": lambda p: len(json.loads(p.read_text(encoding="utf-8"))),
        }

        for name, fn in count_checks.items():
            produced_count = fn(produced[name])
            golden_count = fn(GOLDEN_DIR / name)
            self.assertEqual(
                produced_count,
                golden_count,
                f"Count mismatch for {name}: produced={produced_count}, golden={golden_count}",
            )

    def test_schema_and_metrics_health(self):
        """Validate key schema rows and sanity-check quality metrics."""
        validator = REPO_ROOT / "validate_artifact.py"
        for fname in ("pagelines_final.jsonl", "pagelines_reconstructed.jsonl"):
            proc = subprocess.run(
                ["python", str(validator), "--schema", "pagelines_v1", "--file", str(GOLDEN_DIR / fname)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, f"{fname} schema validation failed:\n{proc.stdout}")

        # elements_core schema spot-check (first 20 rows)
        proc = subprocess.run(
            ["python", str(validator), "--schema", "element_core_v1", "--file", str(GOLDEN_DIR / "elements_core.jsonl")],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"elements_core schema validation failed:\n{proc.stdout}")

        with (GOLDEN_DIR / "section_boundaries_scan.jsonl").open("r", encoding="utf-8") as f:
            boundaries = [json.loads(line) for line in f if line.strip()]
        section_ids = {b["section_id"] for b in boundaries}
        self.assertTrue({"1", "2", "7", "12"}.issubset(section_ids))
        for b in boundaries:
            self.assertIsNotNone(b.get("start_element_id"), "Boundary missing start_element_id")

        quality = json.loads((GOLDEN_DIR / "ocr_quality_report.json").read_text(encoding="utf-8"))
        rates = [item.get("disagree_rate", 0) for item in quality]
        high = [r for r in rates if r > 0.85]
        self.assertLessEqual(max(rates), 1.05, f"Max disagree_rate too high: {max(rates)}")
        self.assertLessEqual(len(high), 2, f"Too many high-disagreement pages: {len(high)}")
        self.assertEqual(len(quality), 40)

        # Content fingerprint spot-check on reconstructed pagelines for stability
        def fingerprints(path: Path, images=None):
            fps = {}
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    image = Path(row.get("image", "")).name
                    if images is not None and image not in images:
                        continue
                    text = "\n".join([l.get("text", "") for l in row.get("lines", [])])
                    fps[image] = hashlib.sha1(text.encode("utf-8")).hexdigest()
            return fps

        sample_images = {"page-016R.png", "page-018L.png", "page-020R.png"}
        golden_fp = fingerprints(GOLDEN_DIR / "pagelines_reconstructed.jsonl", sample_images)
        if BASELINE_RUN_DIR.exists():
            try:
                _skip_if_baseline_run_dir_not_canonical_20_pages()
            except unittest.SkipTest:
                baseline_fp = None
            else:
                baseline_fp = fingerprints(BASELINE_RUN_DIR / "pagelines_reconstructed.jsonl", sample_images)
        else:
            baseline_fp = None
        if baseline_fp is not None:
            self.assertEqual(golden_fp, baseline_fp, f"Fingerprint mismatch: {golden_fp} vs {baseline_fp}")

        # Element seq monotonicity and kind distribution
        kinds = Counter()
        last_seq = -1
        with (GOLDEN_DIR / "elements_core.jsonl").open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                kinds[row["kind"]] += 1
                self.assertGreaterEqual(row["seq"], last_seq, "Element seq not monotonic increasing")
                last_seq = row["seq"]
        self.assertGreater(kinds["text"], 0, "No text elements found")
        self.assertLess(kinds["image"] + kinds["table"], kinds["text"] * 2, "Non-text elements unexpectedly high")

        # Diff-friendly per-page hash for all pages; report first mismatch
        golden_all = fingerprints(GOLDEN_DIR / "pagelines_reconstructed.jsonl")
        if BASELINE_RUN_DIR.exists():
            try:
                _skip_if_baseline_run_dir_not_canonical_20_pages()
            except unittest.SkipTest:
                baseline_all = None
            else:
                baseline_all = fingerprints(BASELINE_RUN_DIR / "pagelines_reconstructed.jsonl")
        else:
            baseline_all = None
        diffs = [img for img in golden_all if baseline_all is not None and golden_all.get(img) != baseline_all.get(img)]
        if diffs:
            first = diffs[0]
            def lines_for(image_name, path):
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        row = json.loads(line)
                        if Path(row.get("image", "")).name == image_name:
                            return [l.get("text", "") for l in row.get("lines", [])][:5]
                return []
            def first_line_diff(g_lines, b_lines):
                limit = min(len(g_lines), len(b_lines))
                for idx in range(limit):
                    if g_lines[idx] != b_lines[idx]:
                        return idx, g_lines[idx], b_lines[idx]
                if len(g_lines) != len(b_lines):
                    return limit, "<golden ends>" if len(g_lines) <= len(b_lines) else g_lines[limit], "<baseline ends>" if len(b_lines) <= len(g_lines) else b_lines[limit]
                return None
            g_lines = lines_for(first, GOLDEN_DIR / "pagelines_reconstructed.jsonl")
            b_lines = lines_for(first, BASELINE_RUN_DIR / "pagelines_reconstructed.jsonl") if baseline_all is not None else []
            diff_info = first_line_diff(g_lines, b_lines)
            diff_msg = ""
            if diff_info:
                idx, g_line, b_line = diff_info
                diff_msg = f" First differing line #{idx}: golden='{g_line}' baseline='{b_line}'."
            self.fail(
                f"Per-page text drift detected for {first}: "
                f"golden hash {golden_all[first]} vs baseline {baseline_all.get(first) if baseline_all is not None else None}. "
                f"Golden first lines: {g_lines}. Baseline first lines: {b_lines}.{diff_msg}"
            )

    def test_optional_full_pipeline_run_against_golden_counts(self):
        """
        Slow path guarded by env var FF20_RUN_PIPELINE=1.
        Runs the canonical recipe into a temp dir and compares counts to goldens.
        """
        if os.getenv("FF20_RUN_PIPELINE") != "1":
            raise unittest.SkipTest("Set FF20_RUN_PIPELINE=1 to enable full pipeline regression run.")
        if not RECIPE_PATH.exists():
            raise unittest.SkipTest(f"Recipe missing: {RECIPE_PATH}")
        if not (REPO_ROOT / "input" / "06 deathtrap dungeon.pdf").exists():
            raise unittest.SkipTest("Input PDF missing.")

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            cmd = [
                "python",
                "driver.py",
                "--recipe",
                str(RECIPE_PATH),
                "--run-id",
                "ff-20-regression-temp",
                "--output-dir",
                str(run_dir),
                "--skip-done",
            ]
            proc = subprocess.run(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self.assertEqual(proc.returncode, 0, f"Pipeline run failed:\n{proc.stdout}")

            produced = {
                "pagelines_final.jsonl": run_dir / "pagelines_final.jsonl",
                "pagelines_reconstructed.jsonl": run_dir / "pagelines_reconstructed.jsonl",
                "elements_core.jsonl": run_dir / "elements_core.jsonl",
                "section_boundaries_scan.jsonl": run_dir / "section_boundaries_scan.jsonl",
                "ocr_quality_report.json": run_dir / "ocr_ensemble" / "ocr_quality_report.json",
            }
            for name, path in produced.items():
                self.assertTrue(path.exists(), f"Missing artifact from fresh run: {name}")

            def jsonl_count(path: Path) -> int:
                with path.open("r", encoding="utf-8") as f:
                    return sum(1 for _ in f if _.strip())

            count_checks = {
                "pagelines_final.jsonl": jsonl_count,
                "pagelines_reconstructed.jsonl": jsonl_count,
                "elements_core.jsonl": jsonl_count,
                "section_boundaries_scan.jsonl": jsonl_count,
                "ocr_quality_report.json": lambda p: len(json.loads(p.read_text(encoding="utf-8"))),
            }
            for name, fn in count_checks.items():
                produced_count = fn(produced[name])
                golden_count = fn(GOLDEN_DIR / name)
                self.assertEqual(
                    produced_count,
                    golden_count,
                    f"Fresh run count mismatch for {name}: produced={produced_count}, golden={golden_count}",
                )

    def test_quality_guards(self):
        """Targeted assertions for columns, forbidden OCR strings, and fragmentation."""
        # Baseline comparisons are optional because `output/` is git-ignored and may be reused locally.
        baseline_ok = False
        if BASELINE_RUN_DIR.exists():
            try:
                _skip_if_baseline_run_dir_not_canonical_20_pages()
            except unittest.SkipTest:
                baseline_ok = False
            else:
                baseline_ok = True

        # Columns: assert consistency between golden and baseline; enforce no split on known single-column pages
        no_column_images = {"page-011R.png", "page-018L.png"}
        def spans_by_image(path: Path):
            spans = {}
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    image = Path(row.get("image", "")).name
                    spans[image] = len(row.get("column_spans") or [])
            return spans

        golden_spans = spans_by_image(GOLDEN_DIR / "pagelines_final.jsonl")
        if baseline_ok:
            baseline_spans = spans_by_image(BASELINE_RUN_DIR / "pagelines_final.jsonl")
            self.assertEqual(golden_spans, baseline_spans, "Column span layouts drifted from golden")
            # Guard specific single-column expectation only if golden already single-column
            for img in no_column_images:
                if golden_spans.get(img) is not None:
                    self.assertEqual(golden_spans.get(img), baseline_spans.get(img), f"Column split drift on {img}")

        # Fragmentation guard
        with (GOLDEN_DIR / "pagelines_final.jsonl").open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                image = Path(row.get("image", "")).name
                frag = row.get("quality_metrics", {}).get("fragmentation_details", {}).get("fragmentation_ratio", 0)
                self.assertLess(frag, 0.5, f"High fragmentation on {image}: {frag}")

        # Forbidden OCR strings: ensure no increase vs baseline
        bad_tokens = {"sxrLL", "otk", "ha them", "decic", "hirn", "craw!", "alittle"}

        def token_counts(path: Path):
            counts = Counter()
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    text = "\n".join(l.get("text", "") for l in row.get("lines", []))
                    lower = text.lower()
                    for token in bad_tokens:
                        if token.lower() in lower:
                            counts[token] += 1
            return counts

        golden_counts = token_counts(GOLDEN_DIR / "pagelines_reconstructed.jsonl")
        if baseline_ok:
            produced_counts = token_counts(BASELINE_RUN_DIR / "pagelines_reconstructed.jsonl")
            for token in bad_tokens:
                self.assertLessEqual(
                    produced_counts[token],
                    golden_counts[token],
                    f"Forbidden token '{token}' increased: produced {produced_counts[token]} > golden {golden_counts[token]}",
                )

        # Long-line jumble guard: produced lines should not exceed golden max length
        def longest_line(path: Path):
            max_len = 0
            max_img = None
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    for t in (l.get("text", "") for l in row.get("lines", [])):
                        if len(t) > max_len:
                            max_len = len(t)
                            max_img = Path(row.get("image", "")).name
            return max_len, max_img

        golden_max, golden_img = longest_line(GOLDEN_DIR / "pagelines_reconstructed.jsonl")
        if baseline_ok:
            produced_max, produced_img = longest_line(BASELINE_RUN_DIR / "pagelines_reconstructed.jsonl")
            self.assertLessEqual(
                produced_max,
                golden_max,
                f"Longest line grew: produced {produced_max} on {produced_img} vs golden {golden_max} on {golden_img}",
            )

        # Hyphen handling: ensure 'twenty metre' does not appear (or increase)
        def token_count(path: Path, token: str):
            c = 0
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    text = "\n".join(l.get("text", "") for l in row.get("lines", []))
                    c += text.lower().count(token)
            return c

        golden_twenty = token_count(GOLDEN_DIR / "pagelines_reconstructed.jsonl", "twenty metre")
        self.assertEqual(golden_twenty, 0, "Golden contains 'twenty metre' which should be absent")
        if baseline_ok:
            produced_twenty = token_count(BASELINE_RUN_DIR / "pagelines_reconstructed.jsonl", "twenty metre")
            self.assertEqual(produced_twenty, golden_twenty, "'twenty metre' count drifted")

        # Choice counts: ensure total and per-page 'turn to' counts remain stable
        def choice_counts(path: Path):
            total = 0
            per_page = {}
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    img = Path(row.get("image", "")).name
                    text = "\n".join(l.get("text", "") for l in row.get("lines", []))
                    count = text.lower().count("turn to")
                    if count:
                        per_page[img] = per_page.get(img, 0) + count
                        total += count
            return total, per_page

        g_total, g_per = choice_counts(GOLDEN_DIR / "pagelines_reconstructed.jsonl")
        if baseline_ok:
            p_total, p_per = choice_counts(BASELINE_RUN_DIR / "pagelines_reconstructed.jsonl")
            self.assertEqual(p_total, g_total, f"Total choices changed: produced {p_total} vs golden {g_total}")
            self.assertEqual(p_per, g_per, f"Per-page choice counts changed: produced {p_per} vs golden {g_per}")


if __name__ == "__main__":
    unittest.main()
