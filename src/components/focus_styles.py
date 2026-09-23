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


def attach_focus_pop(control, *, scale: float = 1.04):
    """Give a focusable card a subtle scale lift while it is focused.

    The FOCUSED border from `card_button_style` is the primary focus cue;
    this adds the small depth pop that makes a D-pad selection unmistakable
    at 10-foot distance. `update()` is guarded because cards are also built
    headless (unit tests, pre-mount) where no page exists yet.

    Args:
        control: the focusable control (e.g. the card's FilledButton).
        scale: scale to apply while focused.

    Returns:
        The same control, with `on_focus`/`on_blur` attached.
    """

    def _on_focus(e):
        control.scale = scale
        try:
            control.update()
        except Exception:
            pass

    def _on_blur(e):
        control.scale = 1.0
        try:
            control.update()
        except Exception:
            pass

    control.on_focus = _on_focus
    control.on_blur = _on_blur
    return control


__all__ = ["attach_focus_pop", "card_button_style"]
