from pathlib import Path

import pytest

from modules.portionize.detect_boundaries_html_loop_v1.main import _is_blank_image, _is_blank_page


def _write_image(path: Path, color: int) -> None:
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"PIL not available: {exc}")
    img = Image.new("L", (200, 200), color=color)
    img.save(path)


def test_blank_image_detection(tmp_path: Path) -> None:
    white = tmp_path / "white.png"
    dark = tmp_path / "dark.png"
    _write_image(white, 255)
    _write_image(dark, 0)

    assert _is_blank_image(str(white), 0.98) is True
    assert _is_blank_image(str(dark), 0.98) is False


def test_blank_page_detection(tmp_path: Path) -> None:
    white = tmp_path / "white.png"
    _write_image(white, 255)
    page = {
        "ocr_empty": True,
        "raw_html": "",
        "html": "",
        "image": str(white),
    }
    assert _is_blank_page(page, 0.98) is True

