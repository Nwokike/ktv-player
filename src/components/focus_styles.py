"""Shared focus-aware styling helpers for card-like tiles.

The ONLY focus cue is declarative: the FOCUSED border/overlay that
``card_button_style`` declares per ``ControlState``. Do NOT add
on_focus/on_blur handlers that mutate ``control.scale``: cards are the
body of a ``@ft.component``, so Flet freezes them after render and every
prop write raises "Frozen controls cannot be updated" (that exact bug
shipped in 2.3.0). A scale animation alone is also pointless — nothing
sets ``scale``, so there is nothing to animate.
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




__all__ = ["card_button_style"]
