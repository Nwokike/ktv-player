import flet as ft

class AppColors:
    # Branding
    PRIMARY = "#7C4DFF"
    SECONDARY = "#00E5FF"
    ERROR = "#FF5252"
    
    # Dark Mode
    DARK_BG = "#0F111A"
    DARK_SURFACE = "#1A1D2D"
    DARK_TEXT = "#FFFFFF"
    DARK_TEXT_DIM = "#8E94A5"
    
    # Light Mode
    LIGHT_BG = "#F5F7FA"
    LIGHT_SURFACE = "#FFFFFF"
    LIGHT_TEXT = "#1A1D2D"
    LIGHT_TEXT_DIM = "#64748B"

    # Additional Roles
    TEXT_PRIMARY = ft.Colors.WHITE
    TEXT_SECONDARY = ft.Colors.ON_SURFACE_VARIANT

    @staticmethod
    def get_glass_bg(page: ft.Page):
        return ft.Colors.with_opacity(0.1, ft.Colors.WHITE if page.theme_mode == ft.ThemeMode.DARK else ft.Colors.BLACK)

    @staticmethod
    def get_shimmer_base(page: ft.Page):
        return "#1E2132" if page.theme_mode == ft.ThemeMode.DARK else "#E2E8F0"

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
                outline=AppColors.DARK_TEXT_DIM,
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
                outline=AppColors.LIGHT_TEXT_DIM,
            ),
            visual_density=ft.VisualDensity.COMFORTABLE,
        )

