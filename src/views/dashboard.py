import flet as ft
import asyncio
import base64
import httpx
from core.state import state
from core.theme import AppColors
from components.ui.glass_container import GlassContainer
from database.manager import db_manager
from services.ad_service import AdService

_liveliness_cache = {}


def build_dashboard_view(page_obj: ft.Page, on_play: callable, ad_service: AdService) -> ft.View:
    view_state = {
        "selected_tab": 0,
        "search_query": "",
        "add_type": "playlist",
        "search_task": None,
    }

    new_name = ft.Ref[ft.TextField]()
    new_url = ft.Ref[ft.TextField]()
    countries_content = ft.ListView(expand=True, spacing=15)
    categories_content = ft.ListView(expand=True, spacing=15)
    custom_content = ft.ListView(expand=True, spacing=15)
    preferences_content = ft.ListView(expand=True, spacing=15)

    check_semaphore = asyncio.Semaphore(8)
    _shared_http_client = None

    def _get_http_client():
        nonlocal _shared_http_client
        if _shared_http_client is None or _shared_http_client.is_closed:
            _shared_http_client = httpx.AsyncClient(
                timeout=3.0,
                follow_redirects=True,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return _shared_http_client

    async def _check_single(url: str) -> tuple[str, bool]:
        cached = _liveliness_cache.get(url)
        if cached is not None:
            return (url, cached)

        async with check_semaphore:
            try:
                client = _get_http_client()
                resp = await client.head(url, timeout=2.0)
                is_live = resp.status_code < 400
                _liveliness_cache[url] = is_live
                return (url, is_live)
            except Exception:
                _liveliness_cache[url] = False
                return (url, False)

    async def _fire_liveliness_batch(cards_data: list):
        BATCH_SIZE = 10
        for i in range(0, len(cards_data), BATCH_SIZE):
            batch = cards_data[i : i + BATCH_SIZE]
            tasks = [_check_single(cd["url"]) for cd in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for cd, result in zip(batch, results):
                if isinstance(result, tuple):
                    _, is_live = result
                    cd["indicator"].bgcolor = AppColors.SUCCESS if is_live else AppColors.ERROR
                else:
                    cd["indicator"].bgcolor = AppColors.ERROR

            try:
                page_obj.update()
            except Exception:
                pass

            if i + BATCH_SIZE < len(cards_data):
                await asyncio.sleep(0.05)

    def close_dialog(e_page_obj):
        e_page_obj.pop_dialog()

    def handle_type_change(e):
        view_state["add_type"] = list(e.control.selected)[0]
        e.control.update()

    async def handle_add(e):
        name = new_name.current.value.strip()
        raw_url = new_url.current.value.strip()

        if name and raw_url:
            close_dialog(page_obj)
            new_name.current.value = ""
            new_url.current.value = ""

            state.is_loading = True
            update_tab_content(view_state["selected_tab"])
            page_obj.update()

            stealth_codes = {
                "#movies": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL21vdmllcy5tM3U=",
                "#sports": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL3Nwb3J0cy5tM3U=",
                "#news": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL25ld3MubTN1",
                "#music": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL211c2ljLm0zdQ==",
                "#kids": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL2tpZHMubTN1",
                "#comedy": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL2NvbWVkeS5tM3U=",
                "#global": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9pbmRleC5tM3U=",
            }
            shortcode_key = raw_url.lower()
            is_stealth = shortcode_key in stealth_codes
            final_url = (
                base64.b64decode(stealth_codes[shortcode_key]).decode("utf-8")
                if is_stealth
                else raw_url
            )

            if is_stealth or view_state["add_type"] == "playlist":
                await db_manager.add_playlist(name, final_url)
            else:
                await db_manager.add_custom_channel(name, final_url)

            if hasattr(page_obj, "load_channels"):
                await page_obj.load_channels()

            state.is_loading = False
            update_tab_content(view_state["selected_tab"])

            page_obj.snack_bar = ft.SnackBar(
                ft.Text(f"{name} added successfully!"), bgcolor=AppColors.SUCCESS
            )
            page_obj.snack_bar.open = True
            page_obj.update()

    add_dialog = ft.AlertDialog(
        title=ft.Text("Add Custom Content"),
        content=ft.Column(
            [
                ft.SegmentedButton(
                    selected=[view_state["add_type"]],
                    allow_empty_selection=False,
                    on_change=handle_type_change,
                    segments=[
                        ft.Segment(
                            value="playlist",
                            label=ft.Text("Playlist"),
                            icon=ft.Icon(ft.Icons.PLAYLIST_ADD),
                        ),
                        ft.Segment(
                            value="channel",
                            label=ft.Text("Single Channel"),
                            icon=ft.Icon(ft.Icons.TV),
                        ),
                    ],
                ),
                ft.TextField(ref=new_name, label="Name", hint_text="Enter reference name"),
                ft.TextField(ref=new_url, label="URL", hint_text="Enter M3U8 or Playlist URL"),
            ],
            tight=True,
            spacing=15,
            width=400,
        ),
        actions=[
            ft.TextButton(content="Cancel", on_click=lambda e: close_dialog(page_obj)),
            ft.FilledButton(
                content="Add",
                on_click=handle_add,
                style=ft.ButtonStyle(bgcolor=AppColors.PRIMARY, color=ft.Colors.WHITE),
            ),
        ],
    )

    def create_channel_card(c):
        url = c.get("url", "")
        cached = _liveliness_cache.get(url)
        initial_color = AppColors.GREY_DIM
        if cached is True:
            initial_color = AppColors.SUCCESS
        elif cached is False:
            initial_color = AppColors.ERROR

        status_indicator = ft.Container(
            width=10, height=10, border_radius=5, bgcolor=initial_color
        )

        card_visual = GlassContainer(
            content=ft.Column(
                [
                    ft.Row([status_indicator], alignment=ft.MainAxisAlignment.END),
                    ft.Image(
                        src=c.get("logo"),
                        width=60,
                        height=60,
                        fit=ft.BoxFit.CONTAIN,
                        border_radius=20,
                        error_content=ft.Icon(ft.Icons.TV, size=30),
                    ),
                    ft.Text(
                        c.get("name", "Unknown"),
                        size=11,
                        weight=ft.FontWeight.W_400,
                        text_align=ft.TextAlign.CENTER,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
            ),
            padding=10,
            border_radius=25,
            focusable=True,
        )

        interactive_card = ft.Container(
            content=card_visual,
            border_radius=25,
            ink=True,
            on_click=lambda e, play_url=url: page_obj.run_task(on_play, play_url),
        )

        interactive_card.data = {"url": url, "indicator": status_indicator}
        return interactive_card

    def build_grid(channels):
        grid = ft.GridView(
            max_extent=130,
            child_aspect_ratio=0.85,
            spacing=12,
            run_spacing=12,
        )

        for c in channels:
            grid.controls.append(create_channel_card(c))

        return grid

    def _collect_cards_data(grid) -> list:
        cards_data = []
        for card in grid.controls:
            if card and getattr(card, "data", None):
                url = card.data.get("url")
                indicator = card.data.get("indicator")
                if url and indicator:
                    cards_data.append({"url": url, "indicator": indicator})
        return cards_data

    def handle_expansion(e, channels):
        if str(e.data).lower() == "true":
            if not e.control.controls:
                grid = build_grid(channels)
                e.control.controls = [grid]
                e.control.update()
                cards_data = _collect_cards_data(grid)
                if cards_data:
                    page_obj.run_task(_fire_liveliness_batch, cards_data)

    def update_tab_content(tab_index: int):
        target = [countries_content, categories_content, custom_content, preferences_content][
            tab_index
        ]
        target.controls.clear()

        if state.is_loading:
            target.controls.append(
                ft.Column(
                    [
                        ft.Container(height=80),
                        ft.ProgressRing(
                            width=60, height=60, stroke_width=6, color=AppColors.PRIMARY
                        ),
                        ft.Container(height=20),
                        ft.Text(
                            "Fetching and validating channels...",
                            color=AppColors.GREY_DIM,
                            size=18,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            "Please wait, massive playlists may take a moment.",
                            color=AppColors.GREY_DIM,
                            size=12,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
            return

        if tab_index == 3:

            async def handle_clear_history(e):
                await db_manager.clear_history()
                page_obj.snack_bar = ft.SnackBar(
                    ft.Text("Watch history cleared!"), bgcolor=AppColors.SUCCESS
                )
                page_obj.snack_bar.open = True
                page_obj.update()

            async def handle_clear_custom(e):
                state.is_loading = True
                update_tab_content(view_state["selected_tab"])
                page_obj.update()

                await db_manager.clear_custom_content()
                if hasattr(page_obj, "load_channels"):
                    await page_obj.load_channels()

                state.is_loading = False
                update_tab_content(view_state["selected_tab"])

                page_obj.snack_bar = ft.SnackBar(
                    ft.Text("Custom library reset!"), bgcolor=AppColors.SUCCESS
                )
                page_obj.snack_bar.open = True
                page_obj.update()

            async def handle_country_change(e):
                val = e.control.value
                await db_manager.set_setting("user_country", val)
                state.user_country = val
                page_obj.snack_bar = ft.SnackBar(ft.Text(f"Primary country updated to {val}"))
                page_obj.snack_bar.open = True
                page_obj.update()

            unique_countries = sorted(
                list(
                    set(
                        [
                            c.get("group", "").split(";")[0].strip()
                            for c in state.channels
                            if c.get("country_code")
                        ]
                    )
                )
            )
            if "Other" not in unique_countries:
                unique_countries.append("Other")
            if not unique_countries or (
                len(unique_countries) == 1 and unique_countries[0] == "Other"
            ):
                unique_countries = ["Global", "Nigeria", "USA", "UK", "Other"]

            country_dropdown = ft.Dropdown(
                label="Primary Content Region",
                value=state.user_country if state.user_country in unique_countries else None,
                options=[ft.dropdown.Option(c) for c in unique_countries],
                on_select=handle_country_change,
            )

            target.controls.append(
                ft.Column(
                    [
                        ft.Text("Preferences", size=24, weight=ft.FontWeight.BOLD),
                        ft.Divider(height=20),
                        ft.Text(
                            "Localization",
                            size=16,
                            weight=ft.FontWeight.W_500,
                            color=AppColors.PRIMARY,
                        ),
                        ft.Text(
                            "Select your home region to prioritize its networks at the top of your dashboard.",
                            size=12,
                            color=AppColors.GREY_DIM,
                        ),
                        country_dropdown,
                        ft.Container(height=20),
                        ft.Text(
                            "Data Management",
                            size=16,
                            weight=ft.FontWeight.W_500,
                            color=AppColors.PRIMARY,
                        ),
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.HISTORY, color=AppColors.WARNING),
                            title=ft.Text("Clear Watch History"),
                            subtitle=ft.Text("Remove all recently watched streams from memory"),
                            on_click=handle_clear_history,
                        ),
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.DELETE_FOREVER, color=AppColors.WARNING),
                            title=ft.Text("Reset Custom Library"),
                            subtitle=ft.Text(
                                "Delete all manually added custom URLs and external playlists"
                            ),
                            on_click=handle_clear_custom,
                        ),
                    ],
                    spacing=10,
                    expand=True,
                )
            )

        else:
            if tab_index == 2:
                target.controls.append(
                    ft.FilledButton(
                        content="Add Custom Configuration",
                        icon=ft.Icons.LINK,
                        on_click=lambda e: page_obj.show_dialog(add_dialog),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            padding=20,
                            bgcolor=AppColors.PRIMARY,
                            color=ft.Colors.WHITE,
                        ),
                        width=float("inf"),
                    )
                )
                target.controls.append(ft.Container(height=10))
                target.controls.append(ad_service.get_standard_banner_ad())
                target.controls.append(ft.Divider(height=20, color=AppColors.GREY_DIM))

            groups = {}
            query = view_state["search_query"].lower()
            MAX_SEARCH_RESULTS = 50
            results_count = 0

            for c in state.channels:
                is_custom = c.get("is_custom", False)
                if tab_index == 2 and not is_custom:
                    continue
                if tab_index in (0, 1) and is_custom:
                    continue

                name_match = query in c.get("name", "").lower()
                original_group = c.get("group", "General")
                parts = [p.strip() for p in original_group.split(";")]

                if tab_index == 0:
                    display_group = parts[0] if c.get("country_code") else "Global"
                elif tab_index == 1:
                    display_group = (
                        parts[-1]
                        if len(parts) > 1
                        else (parts[0] if not c.get("country_code") else "General")
                    )
                elif tab_index == 2:
                    display_group = original_group

                if tab_index == 1 and display_group.lower() == "general":
                    continue

                if query and not name_match and query not in display_group.lower():
                    continue

                if query:
                    results_count += 1
                    if results_count > MAX_SEARCH_RESULTS:
                        break

                if display_group not in groups:
                    groups[display_group] = []
                groups[display_group].append(c)

            group_names = sorted(groups.keys())
            if (
                tab_index == 0
                and state.user_country in group_names
                and state.user_country != "Other"
            ):
                group_names.remove(state.user_country)
                group_names.insert(0, state.user_country)

            ad_counter = 0
            for name in group_names:
                channels = groups[name]
                should_expand = (tab_index == 0 and name == state.user_country) or (
                    query != "" and results_count < 10
                )

                tile_controls = []
                if should_expand:
                    grid = build_grid(channels)
                    tile_controls = [grid]
                    cards_data = _collect_cards_data(grid)
                    if cards_data:
                        page_obj.run_task(_fire_liveliness_batch, cards_data)

                target.controls.append(
                    ft.ExpansionTile(
                        title=ft.Text(f"{name} ({len(channels)})", weight=ft.FontWeight.BOLD),
                        expanded=should_expand,
                        on_change=lambda e, ch=channels: handle_expansion(e, ch),
                        controls=tile_controls,
                    )
                )

                ad_counter += 1
                if ad_counter % 4 == 0:
                    target.controls.append(
                        ft.Container(
                            content=ad_service.get_standard_banner_ad(),
                            alignment=ft.Alignment.CENTER,
                            padding=ft.Padding(0, 5, 0, 5),
                        )
                    )

    tab_view_container = ft.TabBarView(
        controls=[countries_content, categories_content, custom_content, preferences_content],
        expand=True,
    )

    def handle_tab_change(e):
        view_state["selected_tab"] = int(e.data)
        update_tab_content(view_state["selected_tab"])
        page_obj.update()

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
        content=ft.Column([tab_bar, tab_view_container], expand=True, spacing=0),
        expand=True,
        on_change=handle_tab_change,
    )

    def refresh_dashboard():
        update_tab_content(view_state["selected_tab"])
        page_obj.update()

    page_obj.refresh_dashboard = refresh_dashboard

    async def execute_search(query: str):
        view_state["search_query"] = query
        update_tab_content(view_state["selected_tab"])
        page_obj.update()

    def on_search_change(e):
        if view_state["search_task"] and not view_state["search_task"].done():
            view_state["search_task"].cancel()

        query = e.data

        async def delayed_search():
            await asyncio.sleep(0.4)
            await execute_search(query)

        view_state["search_task"] = page_obj.run_task(delayed_search)

    search_bar = ft.SearchBar(
        view_elevation=4,
        divider_color=AppColors.GREY_DIM,
        on_change=on_search_change,
        bar_hint_text="Search channels...",
        bar_leading=ft.Icon(ft.Icons.SEARCH_ROUNDED),
        expand=True,
    )

    update_tab_content(0)

    header = ft.Row(
        [
            ft.Image(src="/icon.png", width=40, height=40, border_radius=12),
            search_bar,
            ft.IconButton(
                icon=ft.Icons.LIGHT_MODE
                if page_obj.theme_mode == ft.ThemeMode.DARK
                else ft.Icons.DARK_MODE,
                on_click=lambda _: (
                    setattr(
                        page_obj,
                        "theme_mode",
                        ft.ThemeMode.LIGHT
                        if page_obj.theme_mode == ft.ThemeMode.DARK
                        else ft.ThemeMode.DARK,
                    ),
                    setattr(state, "theme_mode", page_obj.theme_mode),
                    page_obj.update(),
                ),
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        spacing=20,
    )

    main_col = ft.Column(
        [
            header,
            tabs_wrapper,
        ],
        spacing=15,
        expand=True,
    )

    return ft.View(
        route="/dashboard",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=main_col,
                    expand=True,
                    padding=20,
                    bgcolor=ft.Colors.SURFACE,
                ),
                expand=True,
            ),
            ft.Container(
                content=ad_service.get_anchor_banner_ad(),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding(0, 5, 0, 5),
            )
        ],
        padding=0,
    )
