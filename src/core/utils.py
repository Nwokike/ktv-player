"""Shared utility functions."""


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def country_code_to_flag(code: str) -> str:
    """Convert 2-letter ISO country code (e.g. 'US', 'GB', 'NG', 'AL') into Unicode flag emoji."""
    if not code or len(code) != 2 or not code.isalpha():
        return ""
    code = code.upper()
    return chr(127397 + ord(code[0])) + chr(127397 + ord(code[1]))
