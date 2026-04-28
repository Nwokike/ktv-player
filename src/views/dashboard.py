import flet as ft
import asyncio
from core.state import state
from core.theme import AppColors
from components.ui.shimmer_loader import ShimmerList
from components.ui.glass_container import GlassContainer
from database.manager import db_manager

def build_dashboard_view(page: ft.Page, on_play: callable) -> ft.View:
    """Builds the dashboard view with TV-optimized grid layout and real-time search."""
    
    view_state = {
        "selected_tab": 0,
        "search_query": "",
        "add_type": "playlist",
        "search_task": None # Keeps track of the active search for debouncing
    }

    new_name = ft.Ref[ft.TextField]()
    new_url = ft.Ref[ft.TextField]()

    countries_content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
    categories_content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
    custom_content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

    def close_dialog(e_page):
        e_page.pop_dialog()

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
            
            close_dialog(e.page)
            new_name.current.value = ""
            new_url.current.value = ""
            
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

    def create_channel_card(c):
        return GlassContainer(
            content=ft.Column([
                ft.Image(
                    src=c.get('logo'),
                    width=90,
                    height=90,
                    fit=ft.BoxFit.CONTAIN,
                    border_radius=25,
                    error_content=ft.Icon(ft.Icons.TV, size=40)
                ),
                ft.Text(
                    c.get('name', 'Unknown'),
                    size=11,
                    weight=ft.FontWeight.W_400,
                    text_align=ft.TextAlign.CENTER,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
            padding=12,
            border_radius=25,
            on_click=lambda e, url=c.get('url'): e.page.run_task(on_play, url),
        )

    def build_grid(channels):
        """Helper to build the GridView for a specific category."""
        return ft.GridView(
            controls=[create_channel_card(c) for c in channels],
            runs_count=3,
            max_extent=160,
            spacing=15,
            run_spacing=15,
            padding=15,
        )

    def handle_expansion(e, channels):
        """Dynamic Expansion: Only builds network images and grids when the user actually opens the tile."""
        # e.data is "true" if expanding, "false" if collapsing
        if str(e.data).lower() == "true":
            # Only build the UI if it hasn't been built yet
            if not e.control.controls:
                e.control.controls = [build_grid(channels)]
                e.control.update()

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

            async def import_source(source, e_page):
                url = source.get("url") or f"https://iptv-org.github.io/iptv/countries/{source['code']}.m3u"
                await db_manager.add_playlist(source["name"], url)
                if hasattr(e_page, "load_channels"):
                    await e_page.load_channels()

            target.controls.append(
                ft.Column([
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.ADD_LINK, color=AppColors.PRIMARY),
                        title=ft.Text("Add Custom Playlist or Channel"),
                        subtitle=ft.Text("Import external M3U playlists or individual stream URLs"),
                        on_click=lambda e: e.page.show_dialog(add_dialog)
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
            groups = {}
            query = view_state["search_query"].lower()
            MAX_SEARCH_RESULTS = 50
            results_count = 0
            
            for c in state.channels:
                name_match = query in c.get('name', '').lower()
                
                original_group = c.get('group', 'General')
                parts = [p.strip() for p in original_group.split(';')]
                
                if tab_index == 0: 
                    display_group = parts[0] if c.get('country_code') else "Global"
                else: 
                    display_group = parts[-1] if len(parts) > 1 else (parts[0] if not c.get('country_code') else "General")

                if query and not name_match and query not in display_group.lower():
                    continue
                
                if query:
                    results_count += 1
                    if results_count > MAX_SEARCH_RESULTS: break

                if display_group not in groups: groups[display_group] = []
                groups[display_group].append(c)
            
            group_names = sorted(groups.keys())
            if tab_index == 0 and state.user_country in group_names:
                group_names.remove(state.user_country)
                group_names.insert(0, state.user_country)

            for name in group_names:
                channels = groups[name]
                
                # Expand automatically if it's the user's home country, or if they searched and there are few results
                should_expand = (tab_index == 0 and name == state.user_country) or (query != "" and results_count < 10)
                
                target.controls.append(
                    ft.ExpansionTile(
                        title=ft.Text(f"{name} ({len(channels)})", weight=ft.FontWeight.BOLD),
                        expanded=should_expand,
                        on_change=lambda e, ch=channels: handle_expansion(e, ch),
                        # If it should expand immediately, build it. Otherwise, leave it empty to save memory and data.
                        controls=[build_grid(channels)] if should_expand else []
                    )
                )

    tab_view_container = ft.TabBarView(
        controls=[countries_content, categories_content, custom_content],
        expand=True
    )

    def handle_tab_change(e):
        view_state["selected_tab"] = int(e.data)
        # Only render the content when the tab is actually clicked
        update_tab_content(view_state["selected_tab"])
        e.page.update()

    tab_bar = ft.TabBar(
        tabs=[
            ft.Tab(label="Countries", icon=ft.Icons.PUBLIC),
            ft.Tab(label="Categories", icon=ft.Icons.CATEGORY),
            ft.Tab(label="Custom", icon=ft.Icons.PLAYLIST_ADD),
        ]
    )

    tabs_wrapper = ft.Tabs(
        length=3,
        selected_index=view_state["selected_tab"],
        content=ft.Column([
            tab_bar,
            tab_view_container
        ], expand=True, spacing=0),
        expand=True,
        on_change=handle_tab_change
    )

    async def execute_search(query: str):
        view_state["search_query"] = query
        update_tab_content(view_state["selected_tab"])
        page.update()

    def on_search_change(e):
        """Search debouncer: Waits 400ms after the user stops typing before rebuilding the UI."""
        if view_state["search_task"] and not view_state["search_task"].done():
            view_state["search_task"].cancel()

        query = e.data
        
        async def delayed_search():
            await asyncio.sleep(0.4) 
            await execute_search(query)
            
        view_state["search_task"] = page.run_task(delayed_search)

    search_bar = ft.SearchBar(
        view_elevation=4,
        divider_color=ft.Colors.OUTLINE,
        on_change=on_search_change,
        bar_hint_text="Search channels...",
        bar_leading=ft.Icon(ft.Icons.SEARCH_ROUNDED),
        expand=True,
    )

    # LAZY RENDER: We removed `update_tab_content(1)` and `(2)` from here.
    # It now only renders Tab 0 on launch, halving load times.
    update_tab_content(0)

    header = ft.Row([
        ft.Image(src="/icon.png", width=40, height=40, border_radius=12),
        search_bar,
        ft.IconButton(
            icon=ft.Icons.LIGHT_MODE if page.theme_mode == ft.ThemeMode.DARK else ft.Icons.DARK_MODE,
            on_click=lambda _: setattr(page, "theme_mode", 
                                     ft.ThemeMode.LIGHT if page.theme_mode == ft.ThemeMode.DARK else ft.ThemeMode.DARK) or page.update()
        )
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=20)

    main_col = ft.Column([
        header,
        tabs_wrapper,
    ], spacing=15, expand=True)

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
