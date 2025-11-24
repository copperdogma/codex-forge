import os


def test_pipeline_visibility_prefers_manifest_path():
    """Regression: ensure dashboard uses manifest path for nested runs."""
    html = os.path.join(os.path.dirname(__file__), "..", "docs", "pipeline-visibility.html")
    with open(html, "r", encoding="utf-8") as f:
        text = f.read()
    assert "meta.path ? `${ROOT}/${meta.path}`" in text
