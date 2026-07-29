import flet as ft


class AppColors:
    PRIMARY = "#7C4DFF"
    PRIMARY_LIGHT = "#B388FF"
    PRIMARY_DARK = "#651FFF"
    SECONDARY = "#00E5FF"
    SUCCESS = "#4CAF50"
    WARNING = "#F44336"
    ERROR = "#FF5252"

    DARK_BG = "#0D0F1A"
    DARK_SURFACE = "#151828"
    DARK_SURFACE_VARIANT = "#1E2235"
    DARK_TEXT = "#F0F2FF"
    DARK_TEXT_DIM = "#8E94A5"
    DARK_TEXT_MUTED = "#5A6078"

    LIGHT_BG = "#F5F7FB"
    LIGHT_SURFACE = "#FFFFFF"
    LIGHT_SURFACE_VARIANT = "#F0F2F8"
    LIGHT_TEXT = "#1A1D2D"
    LIGHT_TEXT_DIM = "#64748B"
    LIGHT_TEXT_MUTED = "#94A3B8"

    GREY_DIM = "#888888"
    TERMINAL_BG = "#0D0D0D"
    TERMINAL_TEXT = "#A6E22E"

    WHITE = ft.Colors.WHITE
    BLACK = ft.Colors.BLACK
    TRANSPARENT = ft.Colors.TRANSPARENT

    @staticmethod
    def _is_dark(page: ft.Page) -> bool:
        if page.theme_mode == ft.ThemeMode.LIGHT:
            return False
        if page.theme_mode == ft.ThemeMode.DARK:
            return True
        try:
            return page.platform_brightness == ft.Brightness.DARK
        except Exception:
            return True

    @staticmethod
    def get_glass_bg(page: ft.Page):
        return ft.Colors.with_opacity(
            0.08,
            ft.Colors.WHITE if AppColors._is_dark(page) else ft.Colors.BLACK,
        )

    @staticmethod
    def get_bg(page: ft.Page) -> str:
        return AppColors.DARK_BG if AppColors._is_dark(page) else AppColors.LIGHT_BG

    @staticmethod
    def get_surface(page: ft.Page) -> str:
        return (
            AppColors.DARK_SURFACE
            if AppColors._is_dark(page)
            else AppColors.LIGHT_SURFACE
        )

    @staticmethod
    def get_surface_variant(page: ft.Page) -> str:
        return (
            AppColors.DARK_SURFACE_VARIANT
            if AppColors._is_dark(page)
            else AppColors.LIGHT_SURFACE_VARIANT
        )

    @staticmethod
    def get_card_bg(page: ft.Page) -> str:
        return (
            AppColors.DARK_SURFACE
            if AppColors._is_dark(page)
            else AppColors.LIGHT_SURFACE
        )

    @staticmethod
    def get_border_color(page: ft.Page) -> str:
        return ft.Colors.with_opacity(
            0.12,
            ft.Colors.WHITE if AppColors._is_dark(page) else ft.Colors.BLACK,
        )

    @staticmethod
    def get_text(page: ft.Page) -> str:
        return AppColors.DARK_TEXT if AppColors._is_dark(page) else AppColors.LIGHT_TEXT

    @staticmethod
    def get_text_dim(page: ft.Page) -> str:
        return (
            AppColors.DARK_TEXT_DIM
            if AppColors._is_dark(page)
            else AppColors.LIGHT_TEXT_DIM
        )

    @staticmethod
    def grey_dim(page=None) -> str:
        """Return a grey color that adapts to dark/light theme.

        Falls back to ``"#888888"`` when no page context is available.
        """
        try:
            if page is None:
                from flet.controls.context import context

                page = context.page
            if AppColors._is_dark(page):
                return "#AAAAAA"  # lighter grey on dark backgrounds
            return "#888888"  # darker grey on light backgrounds
        except Exception:
            return "#888888"


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
                on_secondary=ft.Colors.BLACK,
                outline=AppColors.DARK_TEXT_MUTED,
                surface_tint=AppColors.TRANSPARENT,
            ),
            card_theme=ft.CardTheme(
                color=AppColors.DARK_SURFACE,
                elevation=2.0,
                shape=ft.RoundedRectangleBorder(radius=16),
            ),
            navigation_bar_theme=ft.NavigationBarTheme(
                bgcolor=AppColors.DARK_SURFACE,
                indicator_color=AppColors.PRIMARY,
                elevation=4.0,
            ),
            search_bar_theme=ft.SearchBarTheme(
                bgcolor=AppColors.DARK_SURFACE_VARIANT,
                elevation=1.0,
            ),
            page_transitions=ft.PageTransitionsTheme(
                android=ft.PageTransitionTheme.FADE_UPWARDS,
                ios=ft.PageTransitionTheme.CUPERTINO,
            ),
            focus_color=AppColors.PRIMARY,
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
                on_secondary=ft.Colors.BLACK,
                outline=AppColors.LIGHT_TEXT_MUTED,
                surface_tint=AppColors.TRANSPARENT,
            ),
            card_theme=ft.CardTheme(
                color=AppColors.LIGHT_SURFACE,
                elevation=2.0,
                shape=ft.RoundedRectangleBorder(radius=16),
            ),
            navigation_bar_theme=ft.NavigationBarTheme(
                bgcolor=AppColors.LIGHT_SURFACE,
                indicator_color=AppColors.PRIMARY_LIGHT,
                elevation=4.0,
            ),
            search_bar_theme=ft.SearchBarTheme(
                bgcolor=AppColors.LIGHT_SURFACE_VARIANT,
                elevation=1.0,
            ),
            page_transitions=ft.PageTransitionsTheme(
                android=ft.PageTransitionTheme.FADE_UPWARDS,
                ios=ft.PageTransitionTheme.CUPERTINO,
            ),
            focus_color=AppColors.PRIMARY,
            visual_density=ft.VisualDensity.COMFORTABLE,
            use_material3=True,
        )
