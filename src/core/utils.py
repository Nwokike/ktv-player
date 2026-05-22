"""Shared utility functions."""


def escape_html(text: str) -> str:
    """Escape HTML special characters.

    Primarily for defense-in-depth when user-generated names pass through
    systems that may render HTML. In Flet (Flutter) context this is not
    needed for ft.Text, but is applied for consistency and safety.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
