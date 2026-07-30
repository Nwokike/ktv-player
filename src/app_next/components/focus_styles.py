"""Shared Focus-aware styling helpers for card-like tiles."""

from flet import ButtonStyle, Colors, Padding, PaddingValue, RoundedRectangleBorder

# Module-level sentinel so the helper doesn't call Padding.all(12) once per
# argument-default evaluation (ruff B008) — re-used across all card callers
# that don't override `padding`.
_DEFAULT_CARD_PADDING: PaddingValue = Padding.all(12)


def card_button_style(
    *,
    padding: PaddingValue = _DEFAULT_CARD_PADDING,
    radius: float = 16,
    overlay_alpha: float = 0.25,
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
        color=Colors.ON_SURFACE,
        overlay_color=Colors.with_opacity(overlay_alpha, Colors.ON_SURFACE),
        elevation=0,
    )


__all__ = ["card_button_style"]
