"""Channel group classification and building.

Single source of truth for how channels map to display groups.
"""
import contextlib
import logging

import flet as ft

from core.constants import LBL_SHOW_NEXT, LBL_SHOWING_RANGE, MAX_SEARCH_RESULTS, PAGE_SIZE
from core.state import state
from core.theme import AppColors
from views.tabs.pagination import build_nav_btn, show_page

logger = logging.getLogger(__name__)

# Module-level groups cache
_groups_cache: dict = {"countries": {}, "categories": {}, "custom": {}, "hash": None}


def _invalidate_groups_cache():
    _groups_cache["countries"] = {}
    _groups_cache["categories"] = {}
    _groups_cache["custom"] = {}
    _groups_cache["hash"] = None


def classify_channel(channel: dict, tab_index: int) -> str | None:
    """Classify a single channel into its display group for the given tab.

    tab_index: 0=Countries, 1=Categories, 2=Custom
    Returns the display group name, or None if the channel should be excluded.
    """
    is_custom = channel.get("is_custom", False)
    if tab_index == 2 and not is_custom:
        return None
    if tab_index in (0, 1) and is_custom:
        return None

    original_group = channel.get("group", "General")
    parts = [p.strip() for p in original_group.split(";")]

    if tab_index == 0:  # Countries
        return parts[0] if channel.get("country_code") else "Global"
    elif tab_index == 1:  # Categories
        group = parts[-1] if len(parts) > 1 else (parts[0] if not channel.get("country_code") else "General")
        return None if group.lower() == "general" else group
    else:  # Custom
        return original_group


def _build_groups(channels: list[dict], tab_index: int) -> dict[str, list[dict]]:
    """Build groups dict, using cache when channels haven't changed."""
    cache_keys = {0: "countries", 1: "categories", 2: "custom"}
    cache_key = cache_keys.get(tab_index, "custom")

    if _groups_cache["hash"] == state.channels_hash and _groups_cache[cache_key]:
        return _groups_cache[cache_key]

    groups: dict[str, list[dict]] = {}
    for c in channels:
        display_group = classify_channel(c, tab_index)
        if display_group is None:
            continue
        if display_group not in groups:
            groups[display_group] = []
        groups[display_group].append(c)

    _groups_cache[cache_key] = groups
    _groups_cache["hash"] = state.channels_hash
    return groups


def _search_channels(channels: list[dict], query: str, tab_index: int) -> dict[str, list[dict]]:
    """Filter channels by search query using the same classify_channel logic."""
    groups: dict[str, list[dict]] = {}
    count = 0
    for c in channels:
        display_group = classify_channel(c, tab_index)
        if display_group is None:
            continue

        name_match = query in c.get("name", "").lower()
        if not name_match and query not in display_group.lower():
            continue

        count += 1
        if count > MAX_SEARCH_RESULTS:
            break

        if display_group not in groups:
            groups[display_group] = []
        groups[display_group].append(c)
    return groups


def _on_tile_focus(control, focused):
    if focused:
        control.collapsed_bgcolor = ft.Colors.with_opacity(0.12, AppColors.PRIMARY)
        control.bgcolor = ft.Colors.with_opacity(0.12, AppColors.PRIMARY)
        control.border = ft.Border.all(2, AppColors.PRIMARY)
        control.border_radius = 12
    else:
        control.collapsed_bgcolor = ft.Colors.TRANSPARENT
        control.bgcolor = ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE)
        control.border = ft.Border.all(0, ft.Colors.TRANSPARENT)
        control.border_radius = 0
    with contextlib.suppress(Exception):
        control.update()


def _hint_focus(control, focused):
    if focused:
        control.bgcolor = ft.Colors.with_opacity(0.08, AppColors.PRIMARY)
    else:
        control.bgcolor = None
    with contextlib.suppress(Exception):
        control.update()


def _collapse_other_tiles(current_tile, active_tiles):
    for t in active_tiles:
        if t is not current_tile and t.expanded:
            t.expanded = False
            with contextlib.suppress(Exception):
                t.update()


def _handle_expansion(e, channels, active_tiles, page_obj, on_play, ad_service, liveliness):
    if str(e.data).lower() == "true":
        _collapse_other_tiles(e.control, active_tiles)
        if not e.control.controls:
            show_page(e.control, channels, 0, page_obj, on_play, ad_service, liveliness)
        with contextlib.suppress(Exception):
            e.control.update()


def build_channel_groups(target, tab_index, page_obj, on_play, ad_service, liveliness, view_state, active_tiles):
    """Build expansion tiles for channel groups. Used by Countries, Categories, and Custom tabs."""
    from components.ui.channel_grid import build_channel_grid

    query = view_state["search_query"].lower()

    groups = _search_channels(state.channels, query, tab_index) if query else _build_groups(state.channels, tab_index)

    group_names = sorted(groups.keys())

    # Prioritize user's country in Countries tab
    # "Other" maps to "Global" — users who pick Other get Global expanded
    primary_country = "Global" if state.user_country == "Other" else state.user_country
    if tab_index == 0 and primary_country in group_names:
        group_names.remove(primary_country)
        group_names.insert(0, primary_country)

    active_tiles.clear()
    results_count = sum(len(v) for v in groups.values())

    if query and not group_names:
        target.controls.append(
            ft.Column(
                [
                    ft.Container(height=60),
                    ft.Icon(ft.Icons.SEARCH_OFF, size=64, color=AppColors.GREY_DIM),
                    ft.Container(height=12),
                    ft.Text("No results found", size=16, color=AppColors.GREY_DIM, text_align=ft.TextAlign.CENTER),
                    ft.Text(f'No channels match "{query}"', size=12, color=AppColors.GREY_DIM, text_align=ft.TextAlign.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        return

    for name in group_names:
        channels = groups[name]
        should_expand = bool((tab_index == 0 and name == primary_country) or (query and results_count < 10))

        tile_controls = []
        if should_expand:
            total = len(channels)
            ad_indices = {idx for idx in range(0, min(PAGE_SIZE, total)) if (idx + 1) % 12 == 0 and (idx + 1) < total}
            grid = build_channel_grid(channels, 0, PAGE_SIZE, on_play=on_play, page_obj=page_obj, ad_service=ad_service, ad_indices=ad_indices)

            end = min(PAGE_SIZE, total)
            tile_controls.append(
                ft.Container(
                    content=ft.Text(
                        LBL_SHOWING_RANGE.format(start=1, end=end, total=total),
                        size=11, color=AppColors.GREY_DIM, italic=True,
                        text_align=ft.TextAlign.CENTER, width=float("inf"),
                    ),
                    padding=ft.Padding(0, 5, 0, 5),
                )
            )
            tile_controls.append(grid)

            # D-pad focus anchor: focusable Container OUTSIDE the grid (sibling in Column)
            hint_btn = ft.Container(
                content=ft.Row(
                    [
                        ft.Container(width=8, height=8, border_radius=4, bgcolor=ft.Colors.GREEN),
                        ft.Text("Live", size=10, color=AppColors.GREY_DIM),
                        ft.Container(width=8, height=8, border_radius=4, bgcolor=ft.Colors.RED),
                        ft.Text("Offline — Play green channels", size=10, color=AppColors.GREY_DIM, italic=True),
                    ],
                    spacing=6,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                padding=ft.Padding(8, 4, 8, 4),
                border_radius=8,
                ink=True,
                on_click=lambda e: None,
            )
            hint_btn.tab_index = 998
            hint_btn.on_focus = lambda e: _hint_focus(e.control, True)
            hint_btn.on_blur = lambda e: _hint_focus(e.control, False)
            tile_controls.append(hint_btn)

            if total > PAGE_SIZE:
                remaining = total - end
                show_count = min(PAGE_SIZE, remaining)
                next_label = LBL_SHOW_NEXT.format(count=show_count, remaining=remaining)
                # The nav_btn's on_click gets patched below with the correct tile reference
                nav_btn = build_nav_btn(ft.Icons.EXPAND_MORE, next_label)
                nav_btn._patch_target = True
                tile_controls.append(nav_btn)

            cards_data = liveliness.collect_cards_data(grid)
            if cards_data:
                page_obj.run_task(liveliness.fire_batch, cards_data)

        exp_tile = ft.ExpansionTile(
            title=ft.Text(f"{name} ({len(channels)})", weight=ft.FontWeight.BOLD),
            expanded=should_expand,
            on_change=lambda e, ch=channels: _handle_expansion(e, ch, active_tiles, page_obj, on_play, ad_service, liveliness),
            controls=tile_controls,
            collapsed_bgcolor=ft.Colors.TRANSPARENT,
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
        )

        tile_wrapper = ft.Container(
            content=exp_tile,
            border_radius=12,
        )

        # Patch nav button to reference the correct expansion tile
        if should_expand:
            next_offset = min(PAGE_SIZE, len(channels))
            for ctrl in tile_controls:
                if hasattr(ctrl, "_patch_target"):
                    ctrl.on_click = lambda e, t=exp_tile, ch=channels, off=next_offset: show_page(
                        t, ch, off, page_obj, on_play, ad_service, liveliness,
                    )

        active_tiles.append(exp_tile)
        target.controls.append(tile_wrapper)
