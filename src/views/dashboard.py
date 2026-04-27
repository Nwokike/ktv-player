import flet as ft
from core.state import state
from core.theme import AppColors
from components.ui.glass_container import GlassContainer
from components.ui.shimmer_loader import ShimmerList
from database.manager import db_manager

class DashboardView(ft.Container):
    def __init__(self, on_play: callable):
        super().__init__()
        self.on_play = on_play
        self.expand = True
        self.padding = 20
        self.bgcolor = "background"
        
        # State
        self.selected_tab = 0
        self.search_query = ""
        self.add_type = "playlist"
        
        # Refs
        self.page_ref = None
        self.new_name = ft.Ref[ft.TextField]()
        self.new_url = ft.Ref[ft.TextField]()
        
        # Dialog
        self.dialog = self.build_dialog()

    def build_dialog(self):
        return ft.AlertDialog(
            title=ft.Text("Add Custom Content"),
            content=ft.Column([
                ft.SegmentedButton(
                    selected={self.add_type},
                    allow_empty_selection=False,
                    on_change=self.handle_add_type_change,
                    segments=[
                        ft.Segment(value="playlist", label=ft.Text("Playlist"), icon=ft.Icon(ft.Icons.PLAYLIST_ADD)),
                        ft.Segment(value="channel", label=ft.Text("Single Channel"), icon=ft.Icon(ft.Icons.TV)),
                    ],
                ),
                ft.TextField(ref=self.new_name, label="Name", placeholder="e.g. My Channel"),
                ft.TextField(ref=self.new_url, label="URL", placeholder="https://...m3u8"),
            ], tight=True, spacing=15, width=400),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_dialog),
                ft.Button("Add", on_click=self.handle_add, bgcolor=AppColors.PRIMARY, color="white"),
            ],
        )

    def handle_add_type_change(self, e):
        self.add_type = list(e.selection)[0]
        self.update()

    def close_dialog(self, _):
        self.dialog.open = False
        self.page.update()

    async def handle_add(self, _):
        name = self.new_name.current.value
        url = self.new_url.current.value
        if name and url:
            if self.add_type == "playlist":
                await db_manager.add_playlist(name, url)
            else:
                await db_manager.add_custom_channel(name, url)
            
            self.dialog.open = False
            self.new_name.current.value = ""
            self.new_url.current.value = ""
            
            # Refresh channels
            from services.iptv_service import iptv_service
            state.is_loading = True
            self.page.update()
            state.channels = await iptv_service.load_all_sources()
            state.is_loading = False
            self.page.update()

    def handle_tab_change(self, e):
        self.selected_tab = int(e.data)
        self.update()

    def get_grouped_data(self):
        groups = {}
        if self.selected_tab == 0:
            for c in state.channels:
                country = c.get('group', 'General')
                if country not in groups: groups[country] = []
                groups[country].append(c)
        elif self.selected_tab == 1:
            for c in state.channels:
                cat = c.get('group', 'General')
                if cat not in groups: groups[cat] = []
                groups[cat].append(c)
        return groups

    def build_custom_tab(self):
        community_sources = [
            {"name": "Nigeria (Community)", "code": "ng"},
            {"name": "USA (Community)", "code": "us"},
            {"name": "UK (Community)", "code": "gb"},
            {"name": "Global Index", "url": "https://iptv-org.github.io/iptv/index.m3u"},
        ]

        async def import_source(source):
            url = source.get("url") or f"https://iptv-org.github.io/iptv/streams/{source['code']}.m3u"
            await db_manager.add_playlist(source["name"], url)
            from services.iptv_service import iptv_service
            state.channels = await iptv_service.load_all_sources()
            self.page.update()

        return ft.Column([
            ft.ListTile(
                leading=ft.Icon(ft.Icons.ADD_LINK, color=AppColors.PRIMARY),
                title=ft.Text("Add Custom Playlist or Channel"),
                subtitle=ft.Text("Import external M3U playlists or individual stream URLs"),
                on_click=lambda _: self.page.show_dialog(self.dialog)
            ),
            ft.Divider(height=30),
            ft.Text("Quick Import from Community Sources", weight=ft.FontWeight.BOLD, size=16),
            ft.Text("Reliable legal streams from the iptv-org community", size=12, italic=True),
            ft.Row([
                ft.Chip(
                    label=ft.Text(s["name"]),
                    on_click=lambda _, s=s: self.page.run_task(import_source, s),
                    leading=ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, size=16),
                ) for s in community_sources
            ], wrap=True, spacing=10),
            ft.Divider(height=30),
            ft.Text("Your Added Sources", weight=ft.FontWeight.BOLD, size=16),
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    def build(self):
        grouped_data = self.get_grouped_data()
        group_names = sorted(grouped_data.keys())
        if state.user_country in group_names:
            group_names.remove(state.user_country)
            group_names.insert(0, state.user_country)

        # Header
        header = ft.Row([
            ft.Text("KTV Player", style=ft.TextThemeStyle.HEADLINE_MEDIUM, weight=ft.FontWeight.BOLD),
            ft.IconButton(ft.Icons.SEARCH_ROUNDED, on_click=lambda _: None),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        # Tabs
        tabs = ft.Tabs(
            selected_index=self.selected_tab,
            on_change=self.handle_tab_change,
            tabs=[
                ft.Tab(text="Countries", icon=ft.Icons.PUBLIC),
                ft.Tab(text="Categories", icon=ft.Icons.CATEGORY),
                ft.Tab(text="Custom", icon=ft.Icons.PLAYLIST_ADD),
            ],
        )

        # Content
        if self.selected_tab < 2:
            content = ft.Column(
                [
                    ft.ExpansionTile(
                        title=ft.Text(name),
                        initially_expanded=(name == state.user_country or len(group_names) == 1),
                        controls=[
                            ft.ListTile(
                                leading=ft.Image(src=c.get('logo'), width=30, height=30, fit="contain", 
                                               error_content=ft.Icon(ft.Icons.TV)),
                                title=ft.Text(c.get('name', 'Unknown')),
                                trailing=ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED),
                                on_click=lambda _, url=c.get('url'): self.on_play(url)
                            ) for c in channels
                        ]
                    ) for name, channels in [(n, grouped_data[n]) for n in group_names if grouped_data[n]]
                ] if state.channels and not state.is_loading else (
                    [ShimmerList(count=5)] if state.is_loading else [
                        ft.Container(
                            content=ft.Column([
                                ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED, size=50, color="on_surface_variant"),
                                ft.Text("No channels found. Try adding a custom playlist in the 'Custom' tab.", 
                                       text_align=ft.TextAlign.CENTER, color="on_surface_variant")
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=40,
                            alignment=ft.Alignment(0, 0)
                        )
                    ]
                ),
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            )
        else:
            content = self.build_custom_tab()

        # Footer
        footer = ft.Container(
            content=ft.Column([
                ft.Text("Looking for more? Discover community playlists on GitHub", size=12, italic=True),
                ft.FilledButton(
                    "Discover Community Channels",
                    icon=ft.Icons.EXPLORE,
                    on_click=lambda _: None, # logic here
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=10,
            alignment=ft.Alignment(0, 0)
        ) if self.selected_tab < 2 else ft.Container()

        self.content = ft.Column([header, tabs, content, ft.Divider(height=1) if self.selected_tab < 2 else ft.Container(), footer], spacing=10, expand=True)
