"""HomeScreen — main browsing screen compositing header + carousel + filters + grid.

Reads observable AppState via use_context. Memoizes channel maps and
filtered results. Owns the "Add Custom Content" dialog state and the
favorites toggle flow. Delegates to sub-components.
"""

import logging

import flet as ft
from flet.controls.control import Control

from app_next.components.add_custom_content_dialog import AddCustomContentDialog
from app_next.components.channel_grid import ChannelGrid
from app_next.components.empty_state import EmptyState
from app_next.components.filter_bar import FilterBar
from app_next.components.header import Header
from app_next.components.loading_state import LoadingState
from app_next.components.recently_watched import RecentlyWatched
from app_next.hooks.apply_filters import _default_filters, apply_filters
from app_next.state.app_state import AppStateCtx
from app_next.state.controller_ctx import ControllerMethodsCtx
from app_next.utils.channels import (
    build_channels_map,
    build_favorites_set,
    extract_categories,
    extract_countries,
)
from app_next.utils.favorites import toggle_favorite

# --- aliases kept for backward-compatible test imports ---

_build_channels_map = build_channels_map
_build_favorites_set = build_favorites_set
_extract_countries = extract_countries
_extract_categories = extract_categories

logger = logging.getLogger("HomeScreen")


@ft.component
def HomeScreen() -> Control:
    state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    def _init_filters():
        f = _default_filters()
        if getattr(state, "user_country", None):
            f["country"] = state.user_country
        return f

    filters, set_filters = ft.use_state(_init_filters)
    add_dialog_open, set_add_dialog_open = ft.use_state(False)

    channels_map = ft.use_memo(
        lambda: _build_channels_map(state.channels), [state.channels_hash]
    )
    fav_dep = (
        tuple(state.favorites)
        if isinstance(state.favorites, (list, set, tuple))
        else state.favorites
    )
    favorites_set = ft.use_memo(
        lambda: _build_favorites_set(state), [state.channels_hash, fav_dep]
    )

    # Separate built-in vs custom channels for filters
    built_in_channels = ft.use_memo(
        lambda: [c for c in state.channels if not c.get("is_custom", False)],
        [state.channels_hash],
    )
    custom_playlists = ft.use_memo(
        lambda: sorted(
            {c["playlist_name"] for c in state.channels if c.get("playlist_name")}
        ),
        [state.channels_hash],
    )

    visible = ft.use_memo(
        lambda: apply_filters(state.channels, filters, favorites_set),
        [state.channels_hash, filters, favorites_set],
    )

    logger.info(
        "Rendered HomeScreen (total_channels=%d, visible_filtered=%d)",
        len(state.channels),
        len(visible),
    )

    # --- handlers ---

    def on_play(url: str):
        import asyncio

        from core.theme import AppColors

        async def _play():
            try:
                await controller.play_stream(url, None)
            except Exception:
                from flet.controls.context import context

                try:
                    context.page.show_dialog(
                        ft.SnackBar(ft.Text("Playback failed"), bgcolor=AppColors.ERROR)
                    )
                except Exception:
                    pass

        asyncio.create_task(_play())

    def on_toggle_favorite(url: str):
        toggle_favorite(url, state)

    def on_filters_updated(new_filters: dict):
        updated = {**filters, **new_filters}
        set_filters(updated)

    async def on_add_content_complete():
        set_add_dialog_open(False)
        await controller.refresh_channels()

    # --- Build tree ---

    def on_refresh_home():
        import asyncio

        asyncio.create_task(controller.refresh_channels())

    header = Header(
        search_value=filters.get("search", ""),
        on_search_change=lambda q: on_filters_updated({"search": q}),
        on_add_content=lambda: set_add_dialog_open(True),
        on_refresh=on_refresh_home,
    )

    recently = RecentlyWatched(
        history=state.history,
        channels_map=channels_map,
        on_play=on_play,
    )

    filter_bar = FilterBar(
        filters=filters,
        on_change=on_filters_updated,
        available_countries=_extract_countries(built_in_channels),
        available_categories=_extract_categories(built_in_channels),
        user_country=state.user_country,
        custom_playlists=custom_playlists,
        total_count=len(visible),
        on_add_content=lambda: set_add_dialog_open(True),
    )

    if not state.channels and state.is_loading:
        body = LoadingState()
    elif not visible:
        body = EmptyState(
            title="No channels found",
            message="Try changing filters or add custom content.",
            action_label="Add Content",
            on_action=lambda e: set_add_dialog_open(True),
        )
    else:
        body = ChannelGrid(
            channels=visible,
            favorites_set=favorites_set,
            on_play=on_play,
            on_toggle_favorite=on_toggle_favorite,
            liveliness_cache_obj=None,
            ad_service=getattr(controller, "ad_service", None),
        )

    dialog = AddCustomContentDialog(
        open=add_dialog_open,
        on_close=lambda: set_add_dialog_open(False),
        on_added=on_add_content_complete,
    )

    return ft.Container(
        expand=True,
        content=ft.Column(
            controls=[
                header,
                recently,
                filter_bar,
                body,
                dialog,
            ],
            expand=True,
            spacing=0,
        ),
    )
