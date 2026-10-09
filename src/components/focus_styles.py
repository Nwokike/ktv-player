"""Shared focus-aware styling helpers for card-like tiles.

Cards mount through declarative ``@ft.component`` trees, so focus cues
must be declarative too: the FOCUSED border/overlay in
``card_button_style`` plus an implicit ``animate_scale`` on the card
itself. There is deliberately no ``attach_focus_pop`` in this module —
mutating ``control.scale`` in on_focus/on_blur handlers never visibly
applied (mounted declarative controls are frozen), so the old helper
was deleted and its two call sites now pass ``animate_scale`` instead.
"""

from __future__ import annotations

import flet as ft


def card_button_style(
    *,
    padding: ft.PaddingValue | None = None,
    radius: float = 16,
    overlay_alpha: float = 0.25,
) -> ft.ButtonStyle:
    """ButtonStyle for transparent cards with D-pad focus highlight.

    Args:
        padding: inner padding of the card (defaults to 12 all around).
        radius: corner radius in logical px.
        overlay_alpha: ripple alpha for the FOCUSED state (0-1); HOVERED
            uses half, PRESSED uses full for unmistakable touch feedback.

    Raises:
        ValueError: if ``overlay_alpha`` is outside 0-1 or ``radius`` is
            negative.
    """
    if not 0 <= overlay_alpha <= 1:
        raise ValueError(f"overlay_alpha must be 0-1, got {overlay_alpha!r}")
    if radius < 0:
        raise ValueError(f"radius must be >= 0, got {radius!r}")

    from core.theme import AppColors

    return ft.ButtonStyle(
        padding=padding if padding is not None else ft.Padding.all(12),
        shape=ft.RoundedRectangleBorder(radius=radius),
        bgcolor=ft.Colors.TRANSPARENT,
        color=ft.Colors.ON_SURFACE,
        side={
            ft.ControlState.FOCUSED: ft.BorderSide(2.5, AppColors.PRIMARY),
            ft.ControlState.HOVERED: ft.BorderSide(2.0, AppColors.PRIMARY_LIGHT),
            ft.ControlState.PRESSED: ft.BorderSide(2.5, AppColors.PRIMARY),
            ft.ControlState.DISABLED: ft.BorderSide(
                1.0,
                ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
            ),
            ft.ControlState.DEFAULT: ft.BorderSide(
                1.0,
                ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE),
            ),
        },
        overlay_color={
            ft.ControlState.FOCUSED: ft.Colors.with_opacity(
                overlay_alpha, ft.Colors.PRIMARY
            ),
            ft.ControlState.HOVERED: ft.Colors.with_opacity(
                overlay_alpha / 2, ft.Colors.PRIMARY
            ),
            ft.ControlState.PRESSED: ft.Colors.with_opacity(
                overlay_alpha, ft.Colors.PRIMARY
            ),
            ft.ControlState.DEFAULT: ft.Colors.TRANSPARENT,
        },
        elevation=0,
    )


def card_focus_scale(scale: float = 1.04) -> ft.Animation:
    """Implicit scale animation for focusable cards.

    Assign to the card control's ``animate_scale`` (e.g. the
    ``FilledButton`` in ChannelCard/VideoCard) and set ``control.scale``
    in on_focus/on_blur as before — the animation declaration makes the
    change interpolate instead of snapping. Declarative, so it survives
    the frozen-control restriction that killed ``attach_focus_pop``.
    """
    if scale <= 0:
        raise ValueError(f"scale must be positive, got {scale!r}")
    return ft.Animation(duration=150, curve=ft.AnimationCurve.EASE_OUT)


__all__ = ["card_button_style", "card_focus_scale"]
