import flet as ft
from core.state import state
from core.theme import AppColors
from components.ui.glass_container import GlassContainer
from components.ui.shimmer_loader import ShimmerList
from database.manager import db_manager

def build_dashboard_view(on_play: callable) -> ft.View:
    """Builds the dashboard view."""
    
    # Internal state for the view
    view_state = {
        "selected_tab": 0,
        "search_query": "",
        "add_type": "playlist"
    }

    new_name = ft.Ref[ft.TextField]()
    new_url = ft.Ref[ft.TextField]()

    # Containers for each tab content
    countries_content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
    categories_content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
    custom_content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

    def close_dialog(page):
        page.dialog.open = False
        page.update()

    def handle_type_change(e):
        view_state["add_type"] = list(e.selection)[0]
        e.control.update()

    async def handle_add(e):
        name = new_name.current.value
        url = new_url.current.value
        if name and url:
            if view_state["add_type"] == "playlist":
                await db_manager.add_playlist(name, url)
            else:
                await db_manager.add_custom_channel(name, url)
            
            e.page.dialog.open = False
            new_name.current.value = ""
            new_url.current.value = ""
            e.page.update()
            
            if hasattr(e.page, "load_channels"):
                await e.page.load_channels()

    add_dialog = ft.AlertDialog(
        title=ft.Text("Add Custom Content"),
        content=ft.Column([
            ft.SegmentedButton(
                selected=[view_state["add_type"]],
                allow_empty_selection=False,
                on_change=handle_type_change,
                segments=[
                    ft.Segment(value="playlist", label=ft.Text("Playlist"), icon=ft.Icon(ft.Icons.PLAYLIST_ADD)),
                    ft.Segment(value="channel", label=ft.Text("Single Channel"), icon=ft.Icon(ft.Icons.TV)),
                ],
            ),
            ft.TextField(ref=new_name, label="Name", hint_text="Enter channel or playlist name"),
            ft.TextField(ref=new_url, label="URL", hint_text="Enter M3U8 or Playlist URL"),
        ], tight=True, spacing=15, width=400),
        actions=[
            ft.TextButton("Cancel", on_click=lambda e: close_dialog(e.page)),
            ft.FilledButton("Add", on_click=handle_add, style=ft.ButtonStyle(bgcolor=AppColors.PRIMARY, color="white")),
        ],
    )

    def show_dialog(page):
        page.dialog = add_dialog
        add_dialog.open = True
        page.update()

    def update_tab_content(tab_index: int):
        target = [countries_content, categories_content, custom_content][tab_index]
        target.controls.clear()
        
        if state.is_loading:
            target.controls.append(ShimmerList(count=5))
            return

        if tab_index == 2:
            # Custom Tab
            community_sources = [
                {"name": "Nigeria (Community)", "code": "ng"},
                {"name": "USA (Community)", "code": "us"},
                {"name": "UK (Community)", "code": "gb"},
                {"name": "Global Index", "url": "https://iptv-org.github.io/iptv/index.m3u"},
            ]

            async def import_source(source, page):
                url = source.get("url") or f"https://iptv-org.github.io/iptv/countries/{source['code']}.m3u"
                await db_manager.add_playlist(source["name"], url)
                if hasattr(page, "load_channels"):
                    await page.load_channels()

            target.controls.append(
                ft.Column([
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.ADD_LINK, color=AppColors.PRIMARY),
                        title=ft.Text("Add Custom Playlist or Channel"),
                        subtitle=ft.Text("Import external M3U playlists or individual stream URLs"),
                        on_click=lambda e: show_dialog(e.page)
                    ),
                    ft.Divider(height=30),
                    ft.Text("Quick Import from Community Sources", weight=ft.FontWeight.BOLD, size=16),
                    ft.Row([
                        ft.Chip(
                            label=ft.Text(s["name"]),
                            on_click=lambda e, s=s: e.page.run_task(import_source, s, e.page),
                            leading=ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, size=16),
                        ) for s in community_sources
                    ], wrap=True, spacing=10),
                ], scroll=ft.ScrollMode.AUTO, expand=True)
            )
        else:
            # Grouped Data (Countries or Categories)
            groups = {}
            for c in state.channels:
                key = c.get('group', 'General')
                if key not in groups: groups[key] = []
                groups[key].append(c)
            
            group_names = sorted(groups.keys())
            if tab_index == 0 and state.user_country in group_names:
                group_names.remove(state.user_country)
                group_names.insert(0, state.user_country)

            for name in group_names:
                channels = groups[name]
                filtered_channels = [c for c in channels if view_state["search_query"].lower() in c.get('name', '').lower()]
                if not filtered_channels: continue
                
                target.controls.append(
                    ft.ExpansionTile(
                        title=ft.Text(name),
                        expanded=(tab_index == 0 and name == state.user_country or len(group_names) == 1),
                        controls=[
                            ft.ListTile(
                                leading=ft.Image(src=c.get('logo'), width=30, height=30, fit=ft.BoxFit.CONTAIN, 
                                               error_content=ft.Icon(ft.Icons.TV)),
                                title=ft.Text(c.get('name', 'Unknown')),
                                trailing=ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED),
                                on_click=lambda e, url=c.get('url'): on_play(url)
                            ) for c in filtered_channels
                        ]
                    )
                )

    def handle_tab_change(e):
        view_state["selected_tab"] = int(e.data)
        update_tab_content(view_state["selected_tab"])
        e.page.update()

    # Initial population of all tabs
    update_tab_content(0)
    update_tab_content(1)
    update_tab_content(2)

    tabs_control = ft.Tabs(
        length=3,
        selected_index=view_state["selected_tab"],
        on_change=handle_tab_change,
        content=ft.Column([
            ft.TabBar(
                tabs=[
                    ft.Tab(label="Countries", icon=ft.Icons.PUBLIC),
                    ft.Tab(label="Categories", icon=ft.Icons.CATEGORY),
                    ft.Tab(label="Custom", icon=ft.Icons.PLAYLIST_ADD),
                ],
            ),
            ft.TabBarView(
                controls=[
                    countries_content,
                    categories_content,
                    custom_content
                ],
                expand=True
            )
        ], expand=True)
    )

    main_col = ft.Column([
        ft.Row([
            ft.Image(src="/icon.png", width=40, height=40),
            ft.IconButton(ft.Icons.SEARCH_ROUNDED, on_click=lambda _: None),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        
        tabs_control,
        
        # Discovery Footer
        ft.Container(
            content=ft.Column([
                ft.Text("Looking for more? Discover community playlists on GitHub", size=12, italic=True),
                ft.FilledButton(
                    "Discover Community Channels",
                    icon=ft.Icons.EXPLORE,
                    on_click=lambda e: e.page.launch_url("https://github.com/iptv-org/iptv"),
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=10,
            alignment=ft.Alignment(0, 0),
        )
    ], spacing=10, expand=True)

    return ft.View(
        route="/dashboard",
        controls=[
            ft.Container(
                content=main_col,
                expand=True,
                padding=20,
                bgcolor=ft.Colors.SURFACE,
            )
        ],
        padding=0,
    )
