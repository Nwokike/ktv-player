import contextlib

import flet as ft

from core.theme import AppColors

PAGE_SIZE = 24

_groups_cache = {"tab_0": {}, "tab_1": {}, "tab_2": {}, "channels_hash": None}


def _compute_channels_hash(channels):
    return sum(hash(c.get("url", "")) for c in channels) % 10000000


def _build_groups_cache(channels, tab_index):
    cache_key = f"tab_{tab_index}"
    ch_hash = _compute_channels_hash(channels)

    if _groups_cache["channels_hash"] == ch_hash and _groups_cache[cache_key]:
        return _groups_cache[cache_key]

    groups = {}
    for c in channels:
        is_custom = c.get("is_custom", False)
        if tab_index == 2 and not is_custom:
            continue
        if tab_index in (0, 1) and is_custom:
            continue

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
        else:
            display_group = original_group

        if tab_index == 1 and display_group.lower() == "general":
            continue

        if display_group not in groups:
            groups[display_group] = []
        groups[display_group].append(c)

    _groups_cache[cache_key] = groups
    _groups_cache["channels_hash"] = ch_hash
    return groups


def _invalidate_groups_cache():
    _groups_cache["tab_0"] = {}
    _groups_cache["tab_1"] = {}
    _groups_cache["tab_2"] = {}
    _groups_cache["channels_hash"] = None


def style_focusable(control, focused):
    if focused:
        control.bgcolor = ft.Colors.with_opacity(0.1, AppColors.PRIMARY)
        control.border = ft.Border.all(2, AppColors.PRIMARY)
    else:
        control.bgcolor = None
        control.border = ft.Border.all(1, AppColors.GREY_DIM)
    with contextlib.suppress(Exception):
        control.update()


def build_nav_btn(icon, label, tile, channels, offset, page_obj, on_play, ad_service, liveliness, is_next=True):
    btn = ft.Container(
        content=ft.Row(
            [
                ft.Icon(icon, color=AppColors.PRIMARY),
                ft.Text(label, color=AppColors.PRIMARY, weight=ft.FontWeight.W_500),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
        ),
        padding=15,
        border_radius=10,
        border=ft.Border.all(1.5, AppColors.PRIMARY),
        ink=True,
        on_click=lambda e, t=tile, ch=channels, off=offset: show_page(
            t, ch, off, page_obj, on_play, ad_service, liveliness
        ),
    )
    btn.tab_index = 0
    btn.animate = ft.Animation(150, ft.AnimationCurve.EASE_OUT)
    btn.on_focus = lambda e: style_focusable(e.control, True)
    btn.on_blur = lambda e: style_focusable(e.control, False)
    return btn


def show_page(tile, channels, offset, page_obj, on_play, ad_service, liveliness):
    from components.ui.channel_grid import build_channel_grid
    from core.constants import LBL_SHOW_NEXT, LBL_SHOW_PREVIOUS, LBL_SHOWING_RANGE

    total = len(channels)
    end = min(offset + PAGE_SIZE, total)

    tile.controls.clear()

    if offset > 0:
        prev_offset = max(0, offset - PAGE_SIZE)
        prev_label = LBL_SHOW_PREVIOUS.format(
            count=offset - prev_offset,
            start=prev_offset + 1,
            end=offset,
        )
        tile.controls.append(
            build_nav_btn(
                ft.Icons.EXPAND_LESS, prev_label, tile, channels, prev_offset,
                page_obj, on_play, ad_service, liveliness, is_next=False,
            )
        )

    tile.controls.append(
        ft.Container(
            content=ft.Text(
                LBL_SHOWING_RANGE.format(start=offset + 1, end=end, total=total),
                size=11, color=AppColors.GREY_DIM, italic=True,
                text_align=ft.TextAlign.CENTER, width=float("inf"),
            ),
            padding=ft.Padding(0, 5, 0, 5),
        ),
    )

    grid = build_channel_grid(
        channels, offset, PAGE_SIZE,
        on_play=on_play, page_obj=page_obj, ad_service=ad_service,
    )
    tile.controls.append(grid)

    if end < total:
        remaining = total - end
        show_count = min(PAGE_SIZE, remaining)
        next_label = LBL_SHOW_NEXT.format(count=show_count, remaining=remaining)
        tile.controls.append(
            build_nav_btn(
                ft.Icons.EXPAND_MORE, next_label, tile, channels, end,
                page_obj, on_play, ad_service, liveliness, is_next=True,
            )
        )

    tile.update()

    cards_data = liveliness.collect_cards_data(grid)
    if cards_data:
        page_obj.run_task(liveliness.fire_batch, cards_data, tile)


def collapse_other_tiles(current_tile, active_tiles):
    for t in active_tiles:
        if t is not current_tile and t.expanded:
            t.expanded = False
            t.controls.clear()
            with contextlib.suppress(Exception):
                t.update()


def handle_expansion(e, channels, active_tiles, page_obj, on_play, ad_service, liveliness):
    if str(e.data).lower() == "true":
        collapse_other_tiles(e.control, active_tiles)
        if not e.control.controls:
            show_page(e.control, channels, 0, page_obj, on_play, ad_service, liveliness)
    else:
        e.control.controls.clear()
        with contextlib.suppress(Exception):
            e.control.update()


def on_tile_focus(control, focused):
    if focused:
        control.collapsed_bgcolor = ft.Colors.with_opacity(0.15, AppColors.PRIMARY)
        control.bgcolor = ft.Colors.with_opacity(0.15, AppColors.PRIMARY)
    else:
        control.collapsed_bgcolor = ft.Colors.TRANSPARENT
        control.bgcolor = ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE)
    with contextlib.suppress(Exception):
        control.update()


def build_channel_groups(target, tab_index, page_obj, on_play, ad_service, liveliness, view_state, active_tiles):
    from components.ui.channel_grid import build_channel_grid
    from core.constants import LBL_SHOW_NEXT, LBL_SHOWING_RANGE
    from core.state import state

    query = view_state["search_query"].lower()
    MAX_SEARCH_RESULTS = 50

    if query:
        groups = {}
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
            else:
                display_group = original_group

            if tab_index == 1 and display_group.lower() == "general":
                continue

            if not name_match and query not in display_group.lower():
                continue

            results_count += 1
            if results_count > MAX_SEARCH_RESULTS:
                break

            if display_group not in groups:
                groups[display_group] = []
            groups[display_group].append(c)
    else:
        groups = _build_groups_cache(state.channels, tab_index)
        results_count = sum(len(v) for v in groups.values())

    group_names = sorted(groups.keys())
    if (
        tab_index == 0
        and state.user_country in group_names
        and state.user_country != "Other"
    ):
        group_names.remove(state.user_country)
        group_names.insert(0, state.user_country)

    active_tiles.clear()

    if query and not group_names:
        target.controls.append(
            ft.Column(
                [
                    ft.Container(height=60),
                    ft.Icon(ft.Icons.SEARCH_OFF, size=64, color=AppColors.GREY_DIM),
                    ft.Container(height=12),
                    ft.Text(
                        "No results found",
                        size=16,
                        color=AppColors.GREY_DIM,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        f"No channels match \"{query}\"",
                        size=12,
                        color=AppColors.GREY_DIM,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        return

    for name in group_names:
        channels = groups[name]
        should_expand = (tab_index == 0 and name == state.user_country) or (
            query != "" and results_count < 10
        )

        tile_controls = []
        if should_expand:
            grid = build_channel_grid(
                channels, 0, PAGE_SIZE,
                on_play=on_play, page_obj=page_obj, ad_service=ad_service,
            )
            total = len(channels)
            end = min(PAGE_SIZE, total)

            tile_controls.append(
                ft.Container(
                    content=ft.Text(
                        LBL_SHOWING_RANGE.format(start=1, end=end, total=total),
                        size=11, color=AppColors.GREY_DIM, italic=True,
                        text_align=ft.TextAlign.CENTER, width=float("inf"),
                    ),
                    padding=ft.Padding(0, 5, 0, 5),
                ),
            )
            tile_controls.append(grid)

            if total > PAGE_SIZE:
                remaining = total - end
                show_count = min(PAGE_SIZE, remaining)
                next_label = LBL_SHOW_NEXT.format(count=show_count, remaining=remaining)
                nav_btn = build_nav_btn(
                    ft.Icons.EXPAND_MORE, next_label, None, channels, end,
                    page_obj, on_play, ad_service, liveliness,
                )
                nav_btn._needs_tile_ref = True
                tile_controls.append(nav_btn)

            cards_data = liveliness.collect_cards_data(grid)
            if cards_data:
                page_obj.run_task(liveliness.fire_batch, cards_data)

        exp_tile = ft.ExpansionTile(
            title=ft.Text(f"{name} ({len(channels)})", weight=ft.FontWeight.BOLD),
            expanded=should_expand,
            on_change=lambda e, ch=channels: handle_expansion(
                e, ch, active_tiles, page_obj, on_play, ad_service, liveliness,
            ),
            controls=tile_controls,
            collapsed_bgcolor=ft.Colors.TRANSPARENT,
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
        )

        exp_tile.on_focus = lambda e: on_tile_focus(e.control, True)
        exp_tile.on_blur = lambda e: on_tile_focus(e.control, False)

        if should_expand:
            for ctrl in tile_controls:
                if hasattr(ctrl, '_needs_tile_ref'):
                    ctrl.on_click = lambda e, t=exp_tile, ch=channels, off=min(PAGE_SIZE, len(channels)): show_page(
                        t, ch, off, page_obj, on_play, ad_service, liveliness,
                    )

        active_tiles.append(exp_tile)
        target.controls.append(exp_tile)
