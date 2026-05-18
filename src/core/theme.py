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
    DARK_SURFACE_ELEVATED = "#252A3D"
    DARK_TEXT = "#F0F2FF"
    DARK_TEXT_DIM = "#8E94A5"
    DARK_TEXT_MUTED = "#5A6078"

    LIGHT_BG = "#F5F7FB"
    LIGHT_SURFACE = "#FFFFFF"
    LIGHT_SURFACE_VARIANT = "#F0F2F8"
    LIGHT_SURFACE_ELEVATED = "#FFFFFF"
    LIGHT_TEXT = "#1A1D2D"
    LIGHT_TEXT_DIM = "#64748B"
    LIGHT_TEXT_MUTED = "#94A3B8"

    GREY_DIM = "#888888"
    SPLASH_BG = "#0D0F1A"

    WHITE = ft.Colors.WHITE
    BLACK = ft.Colors.BLACK
    TRANSPARENT = ft.Colors.TRANSPARENT

    TEXT_PRIMARY = ft.Colors.WHITE
    TEXT_SECONDARY = ft.Colors.ON_SURFACE_VARIANT

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
            0.08, ft.Colors.WHITE if AppColors._is_dark(page) else ft.Colors.BLACK
        )

    @staticmethod
    def get_hover_bg(page: ft.Page):
        return ft.Colors.with_opacity(
            0.12, ft.Colors.WHITE if AppColors._is_dark(page) else ft.Colors.BLACK
        )

    @staticmethod
    def get_surface_variant(page: ft.Page):
        if page.theme_mode == ft.ThemeMode.LIGHT:
            return AppColors.LIGHT_SURFACE_VARIANT
        if page.theme_mode == ft.ThemeMode.DARK:
            return AppColors.DARK_SURFACE_VARIANT
        try:
            is_dark = page.platform_brightness == ft.Brightness.DARK
            return AppColors.DARK_SURFACE_VARIANT if is_dark else AppColors.LIGHT_SURFACE_VARIANT
        except Exception:
            return AppColors.DARK_SURFACE_VARIANT

    @staticmethod
    def focus_gradient(is_dark: bool = True):
        if is_dark:
            return ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[
                    ft.Colors.with_opacity(0.15, AppColors.PRIMARY),
                    ft.Colors.with_opacity(0.05, AppColors.SECONDARY),
                ],
            )
        return ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[
                ft.Colors.with_opacity(0.1, AppColors.PRIMARY),
                ft.Colors.with_opacity(0.03, AppColors.SECONDARY),
            ],
        )


class AppTheme:
    @staticmethod
    def get_dark_theme() -> ft.Theme:
        return ft.Theme(
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
            visual_density=ft.VisualDensity.COMFORTABLE,
        )

    @staticmethod
    def get_light_theme() -> ft.Theme:
        return ft.Theme(
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
            visual_density=ft.VisualDensity.COMFORTABLE,
        )
