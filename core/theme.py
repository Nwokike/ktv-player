import flet as ft

class AppColors:
    # Deep, premium dark mode palette
    BACKGROUND = "#0F111A"
    SURFACE = "#1A1D2D"
    PRIMARY = "#7C4DFF"  # Deep Purple Accent
    SECONDARY = "#00E5FF"  # Cyan Accent
    ERROR = "#FF5252"
    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#8E94A5"
    
    # Glassmorphism tokens
    GLASS_BG = ft.Colors.with_opacity(0.1, "#FFFFFF")
    GLASS_BORDER = ft.Colors.with_opacity(0.2, "#FFFFFF")
    SHIMMER_BASE = "#1E2132"
    SHIMMER_HIGHLIGHT = "#2D324A"

class AppTheme:
    @staticmethod
    def get_theme() -> ft.Theme:
        return ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=AppColors.PRIMARY,
                secondary=AppColors.SECONDARY,
                surface=AppColors.SURFACE,
                error=AppColors.ERROR,
                on_primary=ft.Colors.WHITE,
                on_secondary=ft.Colors.BLACK,
                on_surface=AppColors.TEXT_PRIMARY,
            ),
            text_theme=ft.TextTheme(
                headline_large=ft.TextStyle(size=32, weight=ft.FontWeight.BOLD, color=AppColors.TEXT_PRIMARY),
                body_large=ft.TextStyle(size=16, color=AppColors.TEXT_PRIMARY),
                body_medium=ft.TextStyle(size=14, color=AppColors.TEXT_SECONDARY),
            ),
            visual_density=ft.VisualDensity.COMFORTABLE,
        )
