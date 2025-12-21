from modules.extract.ocr_ai_gpt51_v1.main import sanitize_html


def test_sanitize_html_allows_only_whitelisted_tags():
    raw = (
        '<div>Bad<div><script>alert(1)</script>'
        '<p class="running-head">6-8</p>'
        '<p class="page-number">17</p>'
        '<p class="other">Text</p>'
        '<span>Ignored</span>'
        '<h2>6</h2>'
        '<table><tr><td>Cell</td></tr></table>'
        '<img alt="Illustration">'
        '</div>'
    )
    clean = sanitize_html(raw)

    assert '<div>' not in clean
    assert '<script>' not in clean
    assert '<span>' not in clean
    assert '<p class="running-head">6-8</p>' in clean
    assert '<p class="page-number">17</p>' in clean
    # non-allowed class is stripped to plain <p>
    assert '<p>Text</p>' in clean
    assert '<h2>6</h2>' in clean
    assert '<table>' in clean
    assert '<td>Cell</td>' in clean
    assert '<img alt="Illustration">' in clean
