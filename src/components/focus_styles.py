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

    The FOCUSED border from `card_button_style` is the primary (and always
    visible) focus cue; this adds a small depth pop on top where the
    control tree allows mutation.

    Best-effort by design: Flet 1.0 freezes declarative component trees,
    where property assignment raises "Frozen controls cannot be updated",
    and headless tests build cards with no page. The pop is a silent
    no-op in those contexts; the border/overlay still guides the D-pad.

    Args:
        control: the focusable control (e.g. the card's FilledButton).
        scale: scale to apply while focused.

    Returns:
        The same control, with `on_focus`/`on_blur` attached.
    """

    def _on_focus(e):
        try:
            control.scale = scale
            control.update()
        except Exception:
            pass

    def _on_blur(e):
        try:
            control.scale = 1.0
            control.update()
        except Exception:
            pass

    control.on_focus = _on_focus
    control.on_blur = _on_blur
    return control


__all__ = ["attach_focus_pop", "card_button_style"]
