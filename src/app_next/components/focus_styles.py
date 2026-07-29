"""Shared Focus-aware styling helpers for card-like tiles.

Cards that are clickable (ChannelCard, RecentlyWatched card, VideoCard) need
to be D-pad-focusable on Android TV / Fire Stick remotes. Flet 0.86.4's
`ft.Container` is NOT focusable — only Material buttons (FilledButton,
TextButton, OutlinedButton, IconButton) carry `autofocus`, `on_focus`,
`on_blur`, and a `focus()` method.

`card_button_style` returns a `ButtonStyle` that preserves the previous
Container-card visuals:
- `padding` set from the existing per-card padding
- `shape=RoundedRectangleBorder(radius=...)` to keep the rounded corners
- `bgcolor=Colors.TRANSPARENT` so the card shows its own background colour
- `overlay_color` restores the ink/ripple that `ink=True` provided

Tests in test_focus_cards.py assert that cards return `FilledButton`
instances with these properties applied. The helper is intentionally tiny
and pure so it can be unit-tested separately.
"""

from flet import ButtonStyle, Colors, Padding, PaddingValue, RoundedRectangleBorder

# Module-level sentinel so the helper doesn't call Padding.all(12) once per
# argument-default evaluation (ruff B008) — re-used across all card callers
# that don't override `padding`.
_DEFAULT_CARD_PADDING: PaddingValue = Padding.all(12)


def card_button_style(
    *,
    padding: PaddingValue = _DEFAULT_CARD_PADDING,
    radius: float = 16,
    overlay_alpha: float = 0.12,
) -> ButtonStyle:
    """Return a ButtonStyle that visually matches a Container-based card.

    Args:
        padding: inner padding of the card (matches the Container's `padding`).
        radius: corner radius (matches the Container's `border_radius`).
        overlay_alpha: ink/ripple alpha (the material focus/tap highlight).
    """
    return ButtonStyle(
        padding=padding,
        shape=RoundedRectangleBorder(radius=radius),
        bgcolor=Colors.TRANSPARENT,
        overlay_color=Colors.with_opacity(overlay_alpha, Colors.ON_SURFACE),
        elevation=0,
    )


__all__ = ["card_button_style"]
