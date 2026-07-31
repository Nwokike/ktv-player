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
    """Return a ButtonStyle matching transparent card visuals with D-pad focus highlight on edges.

    Args:
        padding: inner padding of the card.
        radius: corner radius.
        overlay_alpha: ink/ripple alpha.
    """
    from flet import BorderSide, ControlState

    from core.theme import AppColors

    return ButtonStyle(
        padding=padding,
        shape=RoundedRectangleBorder(radius=radius),
        bgcolor=Colors.TRANSPARENT,
        color=Colors.ON_SURFACE,
        side={
            ControlState.FOCUSED: BorderSide(2.5, AppColors.PRIMARY),
            ControlState.HOVERED: BorderSide(2.0, AppColors.PRIMARY_LIGHT),
            ControlState.DEFAULT: BorderSide(
                1.0,
                Colors.with_opacity(0.15, Colors.ON_SURFACE),
            ),
        },
        overlay_color={
            ControlState.FOCUSED: Colors.with_opacity(0.2, AppColors.PRIMARY),
            ControlState.HOVERED: Colors.with_opacity(0.1, AppColors.PRIMARY),
            ControlState.DEFAULT: Colors.TRANSPARENT,
        },
        elevation=0,
    )


__all__ = ["card_button_style"]
