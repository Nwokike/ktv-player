"""Cinematic theme: brand colors plus dark/light detection and surfaces.

Dark/light selection is driven by ``page.theme_mode`` with the device
``platform_brightness`` as the SYSTEM fallback; the ``ft.Theme`` objects
below are handed to ``page.theme`` / ``page.dark_theme`` at boot (see
``main.py``) so Flutter itself picks the right one. Note that Flet 1.0.1's
``ColorScheme`` has no ``brightness`` field — mode selection lives on the
``Theme`` pair, not on the scheme.

``SECONDARY`` intentionally aliases the brand accent (``PRIMARY_DARK``):
Chips and secondary roles use the same accent by design, documented here
so the duplicate value is not "fixed" into a divergence.
"""

import flet as ft

# Fallback assumed when the page is unreachable (off-session render, unit
# tests without a page). Dark matches the cinematic-first default theme.
_FALLBACK_DARK = True


class AppColors:
    PRIMARY = "#0EA5E9"
    PRIMARY_LIGHT = "#38BDF8"
    PRIMARY_DARK = "#0284C7"
    # Intentional accent alias of PRIMARY_DARK (see module docstring).
    SECONDARY = "#0284C7"
    SUCCESS = "#22C55E"
    WARNING = "#F59E0B"
    ERROR = "#EF4444"

    # --- Dark Mode Colors (Cinematic Dark Theme) ---
    DARK_BG = "#0A0E14"
    DARK_SURFACE = "#0F1520"
    DARK_SURFACE_VARIANT = "#162030"
    DARK_TEXT = "#F0F7FF"
    DARK_TEXT_DIM = "#A7C4E2"
    DARK_TEXT_MUTED = "#6B8AB5"

    # --- Light Mode Colors ---
    LIGHT_BG = "#F0F7FF"
    LIGHT_SURFACE = "#FFFFFF"
    LIGHT_SURFACE_VARIANT = "#ECF5FF"
    LIGHT_TEXT = "#021828"

    # Changed from #64748B to #334155 to make "ash" text much darker and legible
    LIGHT_TEXT_DIM = "#334155"

    # Changed from #94A3B8 to #64748B so muted text doesn't vanish into the background
    LIGHT_TEXT_MUTED = "#64748B"

    # General terminal colors
    TERMINAL_BG = "#0D0D0D"
    TERMINAL_TEXT = "#A6E22E"

    WHITE = ft.Colors.WHITE
    BLACK = ft.Colors.BLACK
    TRANSPARENT = ft.Colors.TRANSPARENT

    @staticmethod
    def is_dark(page: ft.Page | None) -> bool:
        """True when the app currently renders the dark theme.

        Explicit LIGHT/DARK wins; SYSTEM (or unset) follows the device.
        When the page is missing or unreadable, falls back to
        ``_FALLBACK_DARK`` — the same default ``grey_dim`` uses, so the two
        can never disagree about which theme is active.
        """
        if page is None:
            return _FALLBACK_DARK
        if page.theme_mode == ft.ThemeMode.LIGHT:
            return False
        if page.theme_mode == ft.ThemeMode.DARK:
            return True
        try:
            return page.platform_brightness == ft.Brightness.DARK
        except (RuntimeError, AttributeError):
            return _FALLBACK_DARK

    # Back-compat alias: callers should use the public ``is_dark``.
    _is_dark = is_dark

    @staticmethod
    def get_surface(page: ft.Page | None) -> str:
        return (
            AppColors.DARK_SURFACE
            if AppColors.is_dark(page)
            else AppColors.LIGHT_SURFACE
        )

    @staticmethod
    def get_card_bg(page: ft.Page | None) -> str:
        """Card background — identical to ``get_surface`` by design."""
        return AppColors.get_surface(page)

    @staticmethod
    def get_border_color(page: ft.Page | None) -> str:
        # Increased light mode border opacity slightly from 0.12 to 0.15 for better definition
        dark = AppColors.is_dark(page)
        return ft.Colors.with_opacity(
            0.12 if dark else 0.15,
            ft.Colors.WHITE if dark else ft.Colors.BLACK,
        )

    @staticmethod
    def grey_dim(page: ft.Page | None = None) -> str:
        """Return a grey color that adapts to dark/light theme.

        With no page, resolves ``ft.context.page``; when that is also
        unavailable, assumes the ``_FALLBACK_DARK`` default — the same
        fallback ``is_dark`` uses, so the two helpers never disagree.
        """
        try:
            if page is None:
                from flet import context

                page = context.page
            if AppColors.is_dark(page):
                return "#AAAAAA"  # lighter grey on dark backgrounds
            return "#555555"  # Changed from #888888 to #555555 for better light mode contrast
        except (RuntimeError, AttributeError):
            return "#AAAAAA" if _FALLBACK_DARK else "#555555"


class AppTheme:
    @staticmethod
    def get_dark_theme() -> ft.Theme:
        return ft.Theme(
            color_scheme_seed=AppColors.PRIMARY,
            color_scheme=ft.ColorScheme(
                primary=AppColors.PRIMARY,
                secondary=AppColors.SECONDARY,
                surface=AppColors.DARK_BG,
                on_surface=AppColors.DARK_TEXT,
                on_surface_variant=AppColors.DARK_TEXT_DIM,
                error=AppColors.ERROR,
                on_primary=ft.Colors.WHITE,
                # Measured WCAG on the #0284C7 accent: white = 4.10:1
                # (passes 3:1 large-text/UI, below 4.5:1 normal text);
                # black = 5.13:1 (passes AA fully). White is deliberate
                # brand consistency with the light scheme's FABs/Chips,
                # accepting the large-text target for normal text on the
                # accent.
                on_secondary=ft.Colors.WHITE,
                outline=AppColors.DARK_TEXT_MUTED,
                surface_tint=AppColors.TRANSPARENT,
            ),
            scaffold_bgcolor=AppColors.DARK_BG,
            dialog_theme=ft.DialogTheme(bgcolor=AppColors.DARK_SURFACE),
            card_theme=ft.CardTheme(
                color=AppColors.DARK_SURFACE,
                elevation=2.0,
                shape=ft.RoundedRectangleBorder(radius=16),
            ),
            navigation_bar_theme=ft.NavigationBarTheme(
                bgcolor=AppColors.DARK_SURFACE,
                indicator_color=AppColors.PRIMARY,
                elevation=4.0,
                label_behavior=ft.NavigationBarLabelBehavior.ONLY_SHOW_SELECTED,
            ),
            appbar_theme=ft.AppBarTheme(bgcolor=AppColors.DARK_SURFACE),
            search_bar_theme=ft.SearchBarTheme(
                bgcolor=AppColors.DARK_SURFACE_VARIANT,
                elevation=1.0,
            ),
            page_transitions=ft.PageTransitionsTheme(
                android=ft.PageTransitionTheme.FADE_UPWARDS,
                ios=ft.PageTransitionTheme.CUPERTINO,
                # Desktop shells default to ZOOM in Flet; stated explicitly
                # so every platform's transition is a conscious choice.
                windows=ft.PageTransitionTheme.ZOOM,
                macos=ft.PageTransitionTheme.ZOOM,
                linux=ft.PageTransitionTheme.ZOOM,
            ),
            focus_color=AppColors.PRIMARY,
            # COMFORTABLE (spacious) is deliberate: this is a 10-foot TV UI
            # first, and larger hit areas beat information density here.
            visual_density=ft.VisualDensity.COMFORTABLE,
            use_material3=True,
        )

    @staticmethod
    def get_light_theme() -> ft.Theme:
        return ft.Theme(
            color_scheme_seed=AppColors.PRIMARY,
            color_scheme=ft.ColorScheme(
                primary=AppColors.PRIMARY,
                secondary=AppColors.SECONDARY,
                surface=AppColors.LIGHT_BG,
                on_surface=AppColors.LIGHT_TEXT,
                on_surface_variant=AppColors.LIGHT_TEXT_DIM,
                error=AppColors.ERROR,
                on_primary=ft.Colors.WHITE,
                # White on the #0284C7 accent (see dark theme note).
                on_secondary=ft.Colors.WHITE,
                surface_tint=AppColors.TRANSPARENT,
            ),
            scaffold_bgcolor=AppColors.LIGHT_BG,
            dialog_theme=ft.DialogTheme(bgcolor=AppColors.LIGHT_SURFACE),
            card_theme=ft.CardTheme(
                color=AppColors.LIGHT_SURFACE,
                elevation=2.0,
                shape=ft.RoundedRectangleBorder(radius=16),
            ),
            navigation_bar_theme=ft.NavigationBarTheme(
                bgcolor=AppColors.LIGHT_SURFACE,
                indicator_color=AppColors.PRIMARY_LIGHT,
                elevation=4.0,
                label_behavior=ft.NavigationBarLabelBehavior.ONLY_SHOW_SELECTED,
            ),
            appbar_theme=ft.AppBarTheme(bgcolor=AppColors.LIGHT_SURFACE),
            search_bar_theme=ft.SearchBarTheme(
                bgcolor=AppColors.LIGHT_SURFACE_VARIANT,
                elevation=1.0,
            ),
            page_transitions=ft.PageTransitionsTheme(
                android=ft.PageTransitionTheme.FADE_UPWARDS,
                ios=ft.PageTransitionTheme.CUPERTINO,
                windows=ft.PageTransitionTheme.ZOOM,
                macos=ft.PageTransitionTheme.ZOOM,
                linux=ft.PageTransitionTheme.ZOOM,
            ),
            focus_color=AppColors.PRIMARY,
            # COMFORTABLE (spacious) is deliberate — see dark theme note.
            visual_density=ft.VisualDensity.COMFORTABLE,
            use_material3=True,
        )
