"""Tests for core utility functions."""

import pytest

from src.core.utils import escape_html


class TestEscapeHtml:
    def test_no_special_chars(self):
        assert escape_html("hello world") == "hello world"

    def test_ampersand(self):
        assert escape_html("AT&T") == "AT&amp;T"

    def test_less_than(self):
        assert escape_html("5 < 10") == "5 &lt; 10"

    def test_greater_than(self):
        assert escape_html("10 > 5") == "10 &gt; 5"

    def test_double_quote(self):
        assert escape_html('say "hello"') == "say &quot;hello&quot;"

    def test_single_quote(self):
        assert escape_html("it's") == "it&#x27;s"

    def test_all_special(self):
        result = escape_html('<a href="test">AT&T</a>')
        assert result == "&lt;a href=&quot;test&quot;&gt;AT&amp;T&lt;/a&gt;"

    def test_empty_string(self):
        assert escape_html("") == ""

    def test_unicode(self):
        assert escape_html("café") == "café"

    def test_already_escaped_ampersand(self):
        assert escape_html("&amp;") == "&amp;amp;"

    def test_multiple_quotes_and_brackets(self):
        result = escape_html('"<script>alert(1)</script>"')
        assert result == "&quot;&lt;script&gt;alert(1)&lt;/script&gt;&quot;"
