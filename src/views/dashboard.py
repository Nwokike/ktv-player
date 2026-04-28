import flet as ft
import asyncio
import base64
from core.state import state
from core.theme import AppColors
from components.ui.shimmer_loader import ShimmerList
from components.ui.glass_container import GlassContainer
from database.manager import db_manager

def build_dashboard_view(page: ft.Page, on_play: callable) -> ft.View:
    view_state = {
        "selected_tab": 0,
        "search_query": "",
        "add_type": "playlist",
        "search_task": None 
    }

    new_name = ft.Ref[ft.TextField]()
    new_url = ft.Ref[ft.TextField]()

    countries_content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
    categories_content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
    custom_content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
    preferences_content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

    def close_dialog(e_page):
        e_page.pop_dialog()

    def handle_type_change(e):
        view_state["add_type"] = list(e.selection)[0]
        e.control.update()

    async def handle_add(e):
        name = new_name.current.value.strip()
        raw_url = new_url.current.value.strip()
        
        if name and raw_url:
            stealth_codes = {
                "#movies": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL21vdmllcy5tM3U=",
                "#sports": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL3Nwb3J0cy5tM3U=",
                "#news": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL25ld3MubTN1",
                "#music": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL211c2ljLm0zdQ==",
                "#kids": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL2tpZHMubTN1",
                "#comedy": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL2NvbWVkeS5tM3U=",
                "#global": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9pbmRleC5tM3U="
            }
            
            shortcode_key = raw_url.lower()
            is_stealth = shortcode_key in stealth_codes
            
            if is_stealth:
                final_url = base64.b64decode(stealth_codes[shortcode_key]).decode('utf-8')
            else:
                final_url = raw_url
            
            state.is_loading = True
            e.page.update()

            close_dialog(e.page)
            new_name.current.value = ""
            new_url.current.value = ""

            if is_stealth or view_state["add_type"] == "playlist":
                await db_manager.add_playlist(name, final_url)
            else:
                await db_manager.add_custom_channel(name, final_url)
            
            if hasattr(e.page, "load_channels"):
                await e.page.load_channels()
                
            e.page.snack_bar = ft.SnackBar(ft.Text(f"{name} added successfully!"))
            e.page.snack_bar.open = True
            e.page.update()

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
            ft.TextField(ref=new_name, label="Name", hint_text="Enter reference name"),
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
        return ft.GridView(
            controls=[create_channel_card(c) for c in channels],
            runs_count=3,
            max_extent=160,
            spacing=15,
            run_spacing=15,
            padding=15,
        )

    def handle_expansion(e, channels):
        if str(e.data).lower() == "true":
            if not e.control.controls:
                e.control.controls = [build_grid(channels)]
                e.control.update()

    def update_tab_content(tab_index: int):
        target = [countries_content, categories_content, custom_content, preferences_content][tab_index]
        target.controls.clear()
        
        if state.is_loading:
            target.controls.append(ShimmerList(count=5))
            return

        if tab_index == 3:
            # --- SETTINGS / PREFERENCES TAB ---
            async def handle_clear_history(e):
                await db_manager.clear_history()
                e.page.snack_bar = ft.SnackBar(ft.Text("Watch history cleared!"), bgcolor=ft.Colors.GREEN)
                e.page.snack_bar.open = True
                e.page.update()

            async def handle_clear_custom(e):
                state.is_loading = True
                e.page.update()
                await db_manager.clear_custom_content()
                if hasattr(e.page, "load_channels"):
                    await e.page.load_channels()
                e.page.snack_bar = ft.SnackBar(ft.Text("Custom library reset!"), bgcolor=ft.Colors.GREEN)
                e.page.snack_bar.open = True
                e.page.update()

            async def handle_country_change(e):
                val = e.control.value
                await db_manager.set_setting("user_country", val)
                state.user_country = val
                e.page.snack_bar = ft.SnackBar(ft.Text(f"Primary country updated to {val}"))
                e.page.snack_bar.open = True
                e.page.update()

            unique_countries = sorted(list(set([c.get('group', '').split(';')[0].strip() for c in state.channels if c.get('country_code')])))
            if not unique_countries:
                unique_countries = ["Global", "Nigeria", "USA", "UK"] 
                
            country_dropdown = ft.Dropdown(
                label="Primary Content Region",
                value=state.user_country if state.user_country in unique_countries else None,
                options=[ft.dropdown.Option(c) for c in unique_countries],
                on_change=handle_country_change,
            )

            target.controls.append(
                ft.Column([
                    ft.Text("Preferences", size=24, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=20),
                    
                    ft.Text("Localization", size=16, weight=ft.FontWeight.W_500, color=AppColors.PRIMARY),
                    ft.Text("Select your home region to prioritize its networks at the top of your dashboard.", size=12, color=ft.Colors.GREY_500),
                    country_dropdown,
                    
                    ft.Container(height=20),
                    
                    ft.Text("Data Management", size=16, weight=ft.FontWeight.W_500, color=AppColors.PRIMARY),
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.HISTORY, color=ft.Colors.RED),
                        title=ft.Text("Clear Watch History"),
                        subtitle=ft.Text("Remove all recently watched streams from memory"),
                        on_click=handle_clear_history
                    ),
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.DELETE_FOREVER, color=ft.Colors.RED),
                        title=ft.Text("Reset Custom Library"),
                        subtitle=ft.Text("Delete all manually added custom URLs and external playlists"),
                        on_click=handle_clear_custom
                    ),
                ], spacing=10, expand=True)
            )

        elif tab_index == 2:
            # --- CUSTOM / OPSEC TAB ---
            target.controls.append(
                ft.Column([
                    ft.Container(
                        content=ft.Column([
                            # BUG FIX: Replaced non-existent SHIELD_OUTLINED with the valid SECURITY icon
                            ft.Icon(ft.Icons.SECURITY, size=50, color=ft.Colors.GREY_500),
                            ft.Text("Personal Media Player", weight=ft.FontWeight.BOLD, size=20),
                            ft.Text(
                                "KTV Player is a clean network utility. It does not contain pre-loaded TV streams. "
                                "Use the button below to connect your own legal M3U playlists or individual stream links.",
                                text_align=ft.TextAlign.CENTER,
                                color=ft.Colors.GREY_500
                            )
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                        padding=ft.padding.only(top=40, bottom=40),
                        alignment=ft.alignment.center
                    ),
                    ft.ElevatedButton(
                        text="Add Custom Configuration",
                        icon=ft.Icons.LINK,
                        on_click=lambda e: e.page.show_dialog(add_dialog),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            padding=20,
                            bgcolor=AppColors.PRIMARY,
                            color=ft.Colors.WHITE
                        ),
                        width=float('inf')
                    )
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
                should_expand = (tab_index == 0 and name == state.user_country) or (query != "" and results_count < 10)
                
                target.controls.append(
                    ft.ExpansionTile(
                        title=ft.Text(f"{name} ({len(channels)})", weight=ft.FontWeight.BOLD),
                        expanded=should_expand,
                        on_change=lambda e, ch=channels: handle_expansion(e, ch),
                        controls=[build_grid(channels)] if should_expand else []
                    )
                )

    tab_view_container = ft.TabBarView(
        controls=[countries_content, categories_content, custom_content, preferences_content],
        expand=True
    )

    def handle_tab_change(e):
        view_state["selected_tab"] = int(e.data)
        update_tab_content(view_state["selected_tab"])
        e.page.update()

    tab_bar = ft.TabBar(
        tabs=[
            ft.Tab(label="Countries", icon=ft.Icons.PUBLIC),
            ft.Tab(label="Categories", icon=ft.Icons.CATEGORY),
            ft.Tab(label="Custom", icon=ft.Icons.PLAYLIST_ADD),
            ft.Tab(label="Settings", icon=ft.Icons.SETTINGS),
        ]
    )

    tabs_wrapper = ft.Tabs(
        length=4,
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
        if view_state["search_task"] and not view_state["search_task"].done():
            view_state["search_task"].cancel()

        query = e.data
        async def delayed_search():
            await asyncio.sleep(0.4) 
            await execute_search(query)
        view_state["search_task"] = page.run_task(delayed_search)

    search_bar = ft.SearchBar(
        view_elevation=4,
        divider_color=ft.Colors.GREY_500,
        on_change=on_search_change,
        bar_hint_text="Search channels...",
        bar_leading=ft.Icon(ft.Icons.SEARCH_ROUNDED),
        expand=True,
    )

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
