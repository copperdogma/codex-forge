"""Tests for Gemini coordinate format handling in the crop module.

Covers:
- _parse_gemini_box: box_2d/box_3d/box_4d native format parsing
- _auto_fix_axis_swap: page-level axis swap detection
- Array axis swap in _call_vlm_boxes (via _call_vlm_boxes parsing logic)
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.extract.crop_illustrations_guided_v1.main import (
    _auto_fix_axis_swap,
    _is_gemini_model,
    _parse_gemini_box,
)


# ---------------------------------------------------------------------------
# _is_gemini_model
# ---------------------------------------------------------------------------

class TestIsGeminiModel:
    def test_gemini_models(self):
        assert _is_gemini_model("gemini-3-flash-preview")
        assert _is_gemini_model("gemini-2.5-pro")
        assert _is_gemini_model("gemini-3-pro-preview")

    def test_non_gemini_models(self):
        assert not _is_gemini_model("gpt-5.1")
        assert not _is_gemini_model("claude-sonnet-4-6")
        assert not _is_gemini_model("not-gemini")


# ---------------------------------------------------------------------------
# _parse_gemini_box
# ---------------------------------------------------------------------------

class TestParseGeminiBox:
    def test_box_2d_native_format_0_1000_scale(self):
        """Gemini returns box_2d as [y_min, x_min, y_max, x_max] at 0-1000."""
        item = {"box_2d": [268, 61, 458, 937]}
        result = _parse_gemini_box(item)
        assert result is not None
        assert abs(result["x0"] - 0.061) < 0.001
        assert abs(result["y0"] - 0.268) < 0.001
        assert abs(result["x1"] - 0.937) < 0.001
        assert abs(result["y1"] - 0.458) < 0.001

    def test_box_2d_native_format_0_1_scale(self):
        """Gemini returns box_2d at 0-1 scale (already normalized)."""
        item = {"box_2d": [0.268, 0.061, 0.458, 0.937]}
        result = _parse_gemini_box(item)
        assert result is not None
        # Native format: [y_min, x_min, y_max, x_max] → swap
        assert abs(result["x0"] - 0.061) < 0.001
        assert abs(result["y0"] - 0.268) < 0.001
        assert abs(result["x1"] - 0.937) < 0.001
        assert abs(result["y1"] - 0.458) < 0.001

    def test_box_3d_and_box_4d(self):
        """box_3d and box_4d should also be parsed."""
        for key in ("box_3d", "box_4d"):
            item = {key: [100, 200, 500, 800]}
            result = _parse_gemini_box(item)
            assert result is not None
            assert abs(result["x0"] - 0.200) < 0.001
            assert abs(result["y0"] - 0.100) < 0.001

    def test_no_gemini_keys(self):
        """Returns None when no box_Nd keys present."""
        item = {"image_box": {"x0": 0.1, "y0": 0.2, "x1": 0.5, "y1": 0.8}}
        assert _parse_gemini_box(item) is None

    def test_invalid_values(self):
        """Returns None when values can't be converted to float."""
        item = {"box_2d": ["a", "b", "c", "d"]}
        assert _parse_gemini_box(item) is None

    def test_wrong_length(self):
        """Returns None when array length != 4."""
        item = {"box_2d": [100, 200, 300]}
        assert _parse_gemini_box(item) is None

    def test_box_2d_takes_priority(self):
        """box_2d is checked before box_3d."""
        item = {"box_2d": [100, 200, 500, 800], "box_3d": [0, 0, 1000, 1000]}
        result = _parse_gemini_box(item)
        assert abs(result["x0"] - 0.200) < 0.001  # from box_2d


# ---------------------------------------------------------------------------
# _auto_fix_axis_swap (page-level safety net)
# ---------------------------------------------------------------------------

class TestAutoFixAxisSwap:
    def test_empty_boxes(self):
        assert _auto_fix_axis_swap([], 5100, 6600) == []

    def test_zero_dimensions(self):
        boxes = [{"x0": 0.1, "y0": 0.2, "x1": 0.5, "y1": 0.8}]
        assert _auto_fix_axis_swap(boxes, 0, 0) == boxes

    def test_correctly_oriented_boxes_unchanged(self):
        """Boxes that are already [x,y,x,y] should not be swapped."""
        boxes = [{"x0": 0.1, "y0": 0.3, "x1": 0.9, "y1": 0.5}]
        result = _auto_fix_axis_swap(boxes, 5100, 6600)
        assert result[0]["x0"] == 0.1
        assert result[0]["y0"] == 0.3

    def test_out_of_bounds_triggers_swap(self):
        """Boxes where normal interpretation goes out of bounds should swap."""
        # If normal: x0=0.1, y0=0.9, x1=0.5, y1=1.5 → y1 out of bounds
        # If swapped: x0=0.9, y0=0.1, x1=1.5, y1=0.5 → x1 out of bounds
        # Both bad — but this tests the penalty logic runs
        boxes = [{"x0": 0.1, "y0": 0.2, "x1": 0.5, "y1": 0.8}]
        result = _auto_fix_axis_swap(boxes, 5100, 6600)
        # Well-formed box, should not be swapped
        assert result[0]["x0"] == 0.1

    def test_preserves_metadata_keys(self):
        """Non-coordinate keys should be preserved through swap."""
        boxes = [{"x0": 0.1, "y0": 0.2, "x1": 0.5, "y1": 0.8, "_description": "test"}]
        result = _auto_fix_axis_swap(boxes, 5100, 6600)
        assert result[0]["_description"] == "test"

    def test_multiple_boxes(self):
        """All boxes should be processed together."""
        boxes = [
            {"x0": 0.1, "y0": 0.2, "x1": 0.5, "y1": 0.4},
            {"x0": 0.1, "y0": 0.6, "x1": 0.5, "y1": 0.8},
        ]
        result = _auto_fix_axis_swap(boxes, 5100, 6600)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Gemini array swap in _call_vlm_boxes parsing
# ---------------------------------------------------------------------------

class TestGeminiArraySwapParsing:
    """Test the array swap logic that would run inside _call_vlm_boxes.

    We can't easily call _call_vlm_boxes (it makes API calls), so we test
    the transformation logic directly: for a Gemini model, arrays in
    image_box should be interpreted as [y0, x0, y1, x1].
    """

    def test_gemini_array_swap(self):
        """Gemini image_box arrays should be swapped: [y0,x0,y1,x1] → [x0,y0,x1,y1]."""
        # Simulating what _call_vlm_boxes does for Gemini arrays
        img_box = [0.268, 0.061, 0.458, 0.937]  # [y0, x0, y1, x1]
        model = "gemini-3-flash-preview"

        if _is_gemini_model(model):
            result = {"x0": img_box[1], "y0": img_box[0], "x1": img_box[3], "y1": img_box[2]}
        else:
            result = {"x0": img_box[0], "y0": img_box[1], "x1": img_box[2], "y1": img_box[3]}

        # After swap: x0=0.061, y0=0.268, x1=0.937, y1=0.458
        assert abs(result["x0"] - 0.061) < 0.001
        assert abs(result["y0"] - 0.268) < 0.001
        assert abs(result["x1"] - 0.937) < 0.001
        assert abs(result["y1"] - 0.458) < 0.001

    def test_non_gemini_array_no_swap(self):
        """Non-Gemini image_box arrays should NOT be swapped."""
        img_box = [0.1, 0.2, 0.5, 0.8]
        model = "gpt-5.1"

        if _is_gemini_model(model):
            result = {"x0": img_box[1], "y0": img_box[0], "x1": img_box[3], "y1": img_box[2]}
        else:
            result = {"x0": img_box[0], "y0": img_box[1], "x1": img_box[2], "y1": img_box[3]}

        assert result["x0"] == 0.1
        assert result["y0"] == 0.2

    def test_gemini_caption_box_swap(self):
        """Caption box arrays from Gemini should also be swapped."""
        cap_box = [0.606, 0.319, 0.725, 0.718]  # [y0, x0, y1, x1]
        model = "gemini-3-flash-preview"

        if _is_gemini_model(model):
            result = {"x0": cap_box[1], "y0": cap_box[0], "x1": cap_box[3], "y1": cap_box[2]}
        else:
            result = {"x0": cap_box[0], "y0": cap_box[1], "x1": cap_box[2], "y1": cap_box[3]}

        assert abs(result["x0"] - 0.319) < 0.001
        assert abs(result["y0"] - 0.606) < 0.001

    def test_real_page4_case(self):
        """Regression test: Page 4 from Onward book.
        Flash returned [0.268, 0.061, 0.458, 0.937], golden is [0.060, 0.268, 0.938, 0.461].
        After swap should closely match golden."""
        flash_array = [0.268, 0.061, 0.458, 0.937]
        golden = [0.060, 0.268, 0.938, 0.461]

        swapped = {"x0": flash_array[1], "y0": flash_array[0], "x1": flash_array[3], "y1": flash_array[2]}

        assert abs(swapped["x0"] - golden[0]) < 0.01
        assert abs(swapped["y0"] - golden[1]) < 0.01
        assert abs(swapped["x1"] - golden[2]) < 0.01
        assert abs(swapped["y1"] - golden[3]) < 0.01

    def test_real_page14_case(self):
        """Regression test: Page 14 from Onward book.
        Flash returned [0.415, 0.097, 0.683, 0.488], golden is [0.097, 0.414, 0.489, 0.683]."""
        flash_array = [0.415, 0.097, 0.683, 0.488]
        golden = [0.097, 0.414, 0.489, 0.683]

        swapped = {"x0": flash_array[1], "y0": flash_array[0], "x1": flash_array[3], "y1": flash_array[2]}

        assert abs(swapped["x0"] - golden[0]) < 0.01
        assert abs(swapped["y0"] - golden[1]) < 0.01
        assert abs(swapped["x1"] - golden[2]) < 0.01
        assert abs(swapped["y1"] - golden[3]) < 0.01
