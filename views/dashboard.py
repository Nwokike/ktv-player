import flet as ft
from core.state import state
from core.theme import AppColors
from components.ui.glass_container import GlassContainer
from components.ui.shimmer_loader import ShimmerList

@ft.component
def DashboardView(on_play: callable):
    # Search and Filter state
    search_query, set_search_query = ft.use_state("")
    
    def handle_search(e):
        set_search_query(e.data)

    # Filtered channels
    filtered_channels = [
        c for c in state.channels 
        if search_query.lower() in c.get('name', '').lower()
    ]

    return ft.Container(
        content=ft.Column([
            # Header
            ft.Row([
                ft.Text("Dashboard", style=ft.TextThemeStyle.HEADLINE_LARGE),
                ft.IconButton(ft.icons.SETTINGS, on_click=lambda _: None),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            # Search Bar
            ft.TextField(
                label="Search Channels...",
                prefix_icon=ft.icons.SEARCH,
                border_radius=15,
                on_change=handle_search,
                bgcolor=AppColors.SURFACE,
            ),
            
            # Recent History (Horizontal)
            ft.Text("Recently Played", style=ft.TextThemeStyle.TITLE_MEDIUM),
            ft.Row(
                [
                    GlassContainer(
                        content=ft.Text(url.split('/')[-1][:10] + "..."),
                        on_click=lambda _, u=url: on_play(u)
                    ) for url in state.history[:5]
                ] if state.history else [ft.Text("No history yet", color=AppColors.TEXT_SECONDARY)],
                scroll=ft.ScrollMode.HIDDEN
            ),

            # Channel List
            ft.Text("Live TV Channels", style=ft.TextThemeStyle.TITLE_MEDIUM),
            ft.Column(
                [
                    ft.ListTile(
                        leading=ft.Icon(ft.icons.TV, color=AppColors.PRIMARY),
                        title=ft.Text(c.get('name', 'Unknown')),
                        subtitle=ft.Text(c.get('category', 'General')),
                        trailing=ft.Icon(ft.icons.PLAY_ARROW_ROUNDED),
                        on_click=lambda _, url=c.get('url'): on_play(url)
                    ) for c in filtered_channels
                ] if not state.is_loading else [ShimmerList(count=10)],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            )
        ], spacing=20, expand=True),
        padding=20,
        expand=True,
    )
