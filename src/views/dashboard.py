import flet as ft
from core.state import state
from core.theme import AppColors
from components.ui.glass_container import GlassContainer
from components.ui.shimmer_loader import ShimmerList

@ft.component
def DashboardView(on_play: callable):
    # Tab state
    selected_tab, set_selected_tab = ft.use_state(0) # 0 for Countries, 1 for Categories
    search_query, set_search_query = ft.use_state("")
    
    def handle_search(e):
        set_search_query(e.data)

    # Grouping logic
    def get_grouped_data():
        groups = {}
        if selected_tab == 0:
            # Group by Country
            for c in state.channels:
                country = c.get('group', 'General')
                if country not in groups: groups[country] = []
                groups[country].append(c)
        elif selected_tab == 1:
            # Group by Category/Genre
            # Most channels have a category in their group name if not a country
            for c in state.channels:
                cat = c.get('group', 'General')
                if cat not in groups: groups[cat] = []
                groups[cat].append(c)
        else:
            # Custom Playlists (will be handled by Custom tab logic)
            groups = {"My Playlists": []}
            
        return groups

    grouped_data = get_grouped_data()
    
    # Sort groups: User's country first
    group_names = sorted(grouped_data.keys())
    if state.user_country in group_names:
        group_names.remove(state.user_country)
        group_names.insert(0, state.user_country)
    
    # Custom Playlist/Channel Dialog
    add_type, set_add_type = ft.use_state("playlist") # "playlist" or "channel"
    new_name = ft.Ref[ft.TextField]()
    new_url = ft.Ref[ft.TextField]()
    
    async def handle_add(_):
        name = new_name.current.value
        url = new_url.current.value
        if name and url:
            if add_type == "playlist":
                await db_manager.add_playlist(name, url)
            else:
                await db_manager.add_custom_channel(name, url)
            
            dialog.open = False
            # Clear fields
            new_name.current.value = ""
            new_url.current.value = ""
            
            page = page_ref.current
            page.update()
            await load_channels()
    
    dialog = ft.AlertDialog(
        title=ft.Text("Add Custom Content"),
        content=ft.Column([
            ft.SegmentedButton(
                selected={add_type},
                allow_empty_selection=False,
                on_change=lambda e: set_add_type(list(e.selection)[0]),
                segments=[
                    ft.Segment(value="playlist", label=ft.Text("Playlist"), icon=ft.Icon(ft.icons.PLAYLIST_ADD)),
                    ft.Segment(value="channel", label=ft.Text("Single Channel"), icon=ft.Icon(ft.icons.TV)),
                ],
            ),
            ft.TextField(ref=new_name, label="Name", placeholder="e.g. My Channel"),
            ft.TextField(ref=new_url, label="URL", placeholder="https://...m3u8"),
        ], tight=True, spacing=15, width=400),
        actions=[
            ft.TextButton("Cancel", on_click=lambda _: setattr(dialog, "open", False)),
            ft.ElevatedButton("Add", on_click=handle_add, bgcolor=AppColors.PRIMARY, color="white"),
        ],
    )

    page_ref = ft.Ref[ft.Page]()

    def build_custom_tab():
        community_sources = [
            {"name": "Nigeria (Community)", "code": "ng"},
            {"name": "USA (Community)", "code": "us"},
            {"name": "UK (Community)", "code": "gb"},
            {"name": "Global Index", "url": "https://iptv-org.github.io/iptv/index.m3u"},
        ]

        async def import_source(source):
            url = source.get("url") or f"https://iptv-org.github.io/iptv/streams/{source['code']}.m3u"
            await db_manager.add_playlist(source["name"], url)
            await load_channels()

        return ft.Column([
            ft.ListTile(
                leading=ft.Icon(ft.icons.ADD_LINK, color=AppColors.PRIMARY),
                title=ft.Text("Add Custom Playlist or Channel"),
                subtitle=ft.Text("Import external M3U playlists or individual stream URLs"),
                on_click=lambda _: page_ref.current.show_dialog(dialog)
            ),
            ft.Divider(height=30),
            ft.Text("Quick Import from Community Sources", weight=ft.FontWeight.BOLD, size=16),
            ft.Text("Reliable legal streams from the iptv-org community", size=12, italic=True),
            ft.Row([
                ft.Chip(
                    label=ft.Text(s["name"]),
                    on_click=lambda _, s=s: import_source(s),
                    leading=ft.Icon(ft.icons.DOWNLOAD_ROUNDED, size=16),
                ) for s in community_sources
            ], wrap=True, spacing=10),
            ft.Divider(height=30),
            ft.Text("Your Added Sources", weight=ft.FontWeight.BOLD, size=16),
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    def open_external_discovery(_):
        import webbrowser
        webbrowser.open("https://github.com/iptv-org/iptv")

    def on_mount(e):
        page_ref.current = e.page

    return ft.Container(
        on_mount=on_mount,
        content=ft.Column([
            # Header
            ft.Row([
                ft.Text("KTV Player", style=ft.TextThemeStyle.HEADLINE_MEDIUM, weight=ft.FontWeight.BOLD),
                ft.IconButton(ft.icons.SEARCH_ROUNDED, on_click=lambda _: None),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            # Tab Selector
            ft.Tabs(
                selected_index=selected_tab,
                on_change=lambda e: set_selected_tab(int(e.data)),
                tabs=[
                    ft.Tab(text="Countries", icon=ft.icons.PUBLIC),
                    ft.Tab(text="Categories", icon=ft.icons.CATEGORY),
                    ft.Tab(text="Custom", icon=ft.icons.PLAYLIST_ADD),
                ],
            ),
            
            # Channel List
            ft.Column(
                [
                    ft.ExpansionTile(
                        title=ft.Text(name),
                        initially_expanded=(name == state.user_country or len(group_names) == 1),
                        controls=[
                            ft.ListTile(
                                leading=ft.Image(src=c.get('logo'), width=30, height=30, fit=ft.ImageFit.CONTAIN, 
                                               error_content=ft.Icon(ft.icons.TV)),
                                title=ft.Text(c.get('name', 'Unknown')),
                                trailing=ft.Icon(ft.icons.PLAY_ARROW_ROUNDED),
                                on_click=lambda _, url=c.get('url'): on_play(url)
                            ) for c in channels if search_query.lower() in c.get('name', '').lower()
                        ]
                    ) for name, channels in [(n, grouped_data[n]) for n in group_names if grouped_data[n]]
                ] if not state.is_loading else [ShimmerList(count=5)],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ) if selected_tab < 2 else build_custom_tab(),
            
            # Discovery Button (only on Countries/Categories)
            ft.Divider(height=1) if selected_tab < 2 else ft.Container(),
            ft.Container(
                content=ft.Column([
                    ft.Text("Looking for more? Discover community playlists on GitHub", size=12, italic=True),
                    ft.FilledButton(
                        "Discover Community Channels",
                        icon=ft.icons.EXPLORE,
                        on_click=open_external_discovery,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=10,
                alignment=ft.alignment.center
            ) if selected_tab < 2 else ft.Container()
        ], spacing=10, expand=True),
        padding=20,
        expand=True,
    )
