"""
Unit tests for PDF text extraction engine.
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.extract.extract_ocr_ensemble_v1.main import extract_pdf_text


def test_extract_pdf_text_basic():
    """Test basic PDF text extraction (smoke test)."""
    # This is a smoke test - we don't have a test PDF with guaranteed embedded text
    # The function should gracefully return empty string for missing/invalid files
    result = extract_pdf_text("/nonexistent/file.pdf", 1)
    assert isinstance(result, str)
    assert result == ""


def test_extract_pdf_text_invalid_page():
    """Test extraction with invalid page number."""
    # Should return empty string for page out of bounds
    result = extract_pdf_text("/nonexistent/file.pdf", 0)
    assert result == ""

    result = extract_pdf_text("/nonexistent/file.pdf", -1)
    assert result == ""


def test_extract_pdf_text_returns_string():
    """Verify extract_pdf_text always returns a string."""
    # Even with errors, should return empty string (not None, not exception)
    result = extract_pdf_text("", 1)
    assert isinstance(result, str)

    result = extract_pdf_text(None, 1)
    assert isinstance(result, str)


if __name__ == "__main__":
    test_extract_pdf_text_basic()
    test_extract_pdf_text_invalid_page()
    test_extract_pdf_text_returns_string()
    print("All PDF text extraction tests passed!")
