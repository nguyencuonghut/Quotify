import pytest
from app.utils.sanitizer import sanitize_html

def test_sanitize_html_keeps_safe_tags():
    raw = "<p>Hello <b>world</b>, this is <strong>bold</strong>, <i>italic</i>, and <em>emphasized</em>.</p>"
    cleaned = sanitize_html(raw)
    assert cleaned == raw

def test_sanitize_html_keeps_lists_and_br():
    raw = "<ul><li>Item 1</li><li>Item 2</li></ul><ol><li>One</li></ol><br>"
    cleaned = sanitize_html(raw)
    assert cleaned == raw

def test_sanitize_html_keeps_safe_links():
    raw = '<p><a href="https://example.com" target="_blank">Click here</a></p>'
    cleaned = sanitize_html(raw)
    assert "https://example.com" in cleaned
    assert "Click here" in cleaned

def test_sanitize_html_removes_dangerous_tags():
    raw = "<p>Normal text <script>alert('XSS')</script> and <iframe src='hack'></iframe></p>"
    cleaned = sanitize_html(raw)
    assert "Normal text" in cleaned
    assert "<script>" not in cleaned
    assert "alert('XSS')" not in cleaned
    assert "<iframe>" not in cleaned

def test_sanitize_html_removes_dangerous_attributes():
    raw = '<p onclick="executehack()" style="color: red;">No inline events</p>'
    cleaned = sanitize_html(raw)
    assert "No inline events" in cleaned
    assert "onclick" not in cleaned
    assert "style=" not in cleaned

def test_sanitize_html_strips_javascript_protocol_links():
    raw = '<a href="javascript:alert(\'hack\')">Dangerous Link</a>'
    cleaned = sanitize_html(raw)
    # The href should either be stripped of the javascript protocol or completely removed
    assert "javascript:" not in cleaned

def test_sanitize_html_removes_unallowed_tags():
    # Images and styles are not allowed in allowlist V1
    raw = '<p><img src="x.jpg" onerror="alert(1)"> <style>body {background: red;}</style> test</p>'
    cleaned = sanitize_html(raw)
    assert "test" in cleaned
    assert "<img>" not in cleaned
    assert "<style>" not in cleaned

def test_sanitize_html_limits_payload_size():
    # Max size allowed is 20 KB (20,480 bytes/characters)
    huge_input = "<p>" + ("a" * 20480) + "</p>"
    with pytest.raises(ValueError, match="Payload size exceeds maximum allowed limit"):
        sanitize_html(huge_input)
