"""HomeScreen — main browsing screen compositing carousel + filters + grid.

Reads observable AppState via use_context. Memoizes channel maps and
filtered results. Owns the "Add Custom Content" dialog state and the
favorites toggle flow. Delegates to sub-components.
"""

import flet as ft
from flet.controls.control import Control

from app_next.components.add_custom_content_dialog import AddCustomContentDialog
from app_next.components.channel_grid import ChannelGrid
from app_next.components.empty_state import EmptyState
from app_next.components.filter_bar import FilterBar
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
from app_next.utils.theme_utils import toggle_theme as _toggle_theme_util
from core.constants import LBL_ADD_CONTENT
from database.manager import db_manager

# --- aliases kept for backward-compatible test imports ---

_build_channels_map = build_channels_map
_build_favorites_set = build_favorites_set
_extract_countries = extract_countries
_extract_categories = extract_categories


@ft.component
def HomeScreen() -> Control:
    state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    filters, set_filters = ft.use_state(_default_filters())
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
    visible = ft.use_memo(
        lambda: apply_filters(state.channels, filters, favorites_set),
        [state.channels_hash, filters, favorites_set],
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
        set_filters(new_filters)

    async def on_add_content_complete():
        set_add_dialog_open(False)
        await controller.refresh_channels()

    def _handle_toggle_theme(e):
        from flet.controls.context import context

        _toggle_theme_util(context.page)

    # --- Build tree ---

    header = ft.Row(
        controls=[
            ft.Image(
                src="/icon.png",
                width=36,
                height=36,
                fit=ft.BoxFit.CONTAIN,
                border_radius=8,
            ),
            ft.IconButton(
                icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                tooltip=LBL_ADD_CONTENT,
                on_click=lambda e: set_add_dialog_open(True),
                icon_size=22,
                autofocus=True,
            ),
            ft.IconButton(
                icon=ft.Icons.LIGHT_MODE,
                tooltip="Toggle Theme",
                on_click=_handle_toggle_theme,
                icon_size=18,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    recently = RecentlyWatched(
        history=state.history,
        channels_map=channels_map,
        on_play=on_play,
    )

    filter_bar = FilterBar(
        filters=filters,
        on_change=on_filters_updated,
        available_countries=_extract_countries(state.channels),
        available_categories=_extract_categories(state.channels),
        user_country=state.user_country,
        total_count=len(visible),
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
                ft.Container(content=header, padding=ft.Padding(12, 8, 12, 4)),
                recently,
                filter_bar,
                body,
                dialog,
            ],
            expand=True,
            spacing=0,
        ),
    )
