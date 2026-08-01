"""HomeScreen — main browsing screen with header, filters, and channel grid."""

import asyncio
import logging

import flet as ft
from flet import Control, use_ref

from components.add_custom_content_dialog import AddCustomContentDialog
from components.channel_grid import ChannelGrid
from components.empty_state import EmptyState
from components.filter_bar import FilterBar
from components.header import Header
from components.loading_state import LoadingState
from components.recently_watched import RecentlyWatched
from core.constants import (
    ERR_PLAYBACK_FAILED,
    LBL_ADD_CONTENT_SHORT,
    LBL_NO_CHANNELS_FOUND,
    LBL_NO_CHANNELS_HINT,
)
from hooks.apply_filters import _default_filters, apply_filters
from hooks.use_debounce import use_debounce
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx
from utils.channels import (
    build_channels_map,
    build_favorites_set,
    extract_category_counts,
    extract_country_counts,
    extract_custom_group_counts,
)
from utils.favorites import toggle_favorite

logger = logging.getLogger("HomeScreen")


@ft.component
def HomeScreen() -> Control:
    state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    def _init_filters():
        f = _default_filters()
        if getattr(state, "user_country", None):
            f["country"] = (
                "Global" if state.user_country == "Other" else state.user_country
            )
        return f

    filters, set_filters = ft.use_state(_init_filters)
    add_dialog_open, set_add_dialog_open = ft.use_state(False)
    liveliness_version, set_liveliness_version = ft.use_state(0)
    pending_render = use_ref(False)

    # Auto-load channels on first mount
    def _auto_load():
        if not state.channels and callable(
            getattr(controller, "refresh_channels", None)
        ):
            asyncio.create_task(controller.refresh_channels())

    ft.use_effect(_auto_load, [])

    # Memoized channel data
    channels_map = ft.use_memo(
        lambda: build_channels_map(state.channels), [state.channels_hash]
    )
    fav_dep = (
        tuple(state.favorites)
        if isinstance(state.favorites, (list, set, tuple))
        else state.favorites
    )
    favorites_set = ft.use_memo(
        lambda: build_favorites_set(state), [state.channels_hash, fav_dep]
    )
    built_in_channels = ft.use_memo(
        lambda: [c for c in state.channels if not c.get("is_custom", False)],
        [state.channels_hash],
    )
    custom_playlists = ft.use_memo(
        lambda: extract_custom_group_counts(state.channels),
        [state.channels_hash],
    )

    # Filtered visible channels
    visible = ft.use_memo(
        lambda: apply_filters(state.channels, filters, favorites_set),
        [state.channels_hash, filters, favorites_set, liveliness_version],
    )

    # ---- Liveliness: filter-driven priority system ----
    # When filters change → drain old queue → enqueue only what's on screen now.
    def _seed_visible():
        from services.liveliness_checker import drain_queue, enqueue_liveliness_check
        from services.logo_cache import enqueue_logo_download

        # DUMP old work — whatever is on screen NOW is priority
        drain_queue()

        # Enqueue only the filtered visible channels (first screen)
        for ch in visible[:24]:
            url = ch.get("url", "")
            if url:
                enqueue_liveliness_check(url)
            logo = ch.get("logo") or ""
            if logo and not logo.startswith("/"):
                enqueue_logo_download(logo)

    ft.use_effect(_seed_visible, [filters, state.channels_hash])

    # Wire liveliness cache → debounced re-render (500ms coalesce)
    def _on_liveliness_change():
        if pending_render.current:
            return
        pending_render.current = True

        async def _flush():
            await asyncio.sleep(0.5)
            pending_render.current = False
            set_liveliness_version(lambda v: v + 1)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_flush())
        except RuntimeError:
            pending_render.current = False
            set_liveliness_version(lambda v: v + 1)

    from services.liveliness import liveliness_cache

    ft.use_effect(lambda: liveliness_cache.set_on_change(_on_liveliness_change), [])

    logger.info(
        "Rendered HomeScreen (total_channels=%d, visible_filtered=%d)",
        len(state.channels),
        len(visible),
    )

    # --- handlers ---

    def on_play(url: str):
        async def _play():
            try:
                await controller.play_stream(url, None)
            except Exception:
                from utils.notifications import notify_error

                notify_error(ERR_PLAYBACK_FAILED)

        asyncio.create_task(_play())

    def on_toggle_favorite(url: str):
        toggle_favorite(url, state)

    def on_filters_updated(new_filters: dict):
        updated = {**filters, **new_filters}
        set_filters(updated)

    search_input, set_search_input = ft.use_state(filters.get("search", ""))
    debounced_search = use_debounce(search_input, 250)

    # Sync text field when other chips reset search
    def _sync_search_field():
        target = filters.get("search", "")
        if search_input != target:
            set_search_input(target)

    ft.use_effect(_sync_search_field, [filters])

    async def _commit_search():
        new_search = debounced_search
        if filters.get("search") != new_search:
            set_filters(
                {
                    "search": new_search,
                    "country": "all",
                    "category": "all",
                    "custom": "none",
                    "fav_only": False,
                }
            )

    ft.use_effect(_commit_search, [debounced_search])

    async def on_add_content_complete():
        set_add_dialog_open(False)
        await controller.refresh_channels()

    # --- Build tree ---

    def on_refresh_home():
        from utils.notifications import notify

        notify("Refreshing channels...")
        asyncio.create_task(controller.refresh_channels(force=True))

    def _open_search():
        if callable(getattr(controller, "open_search", None)):
            controller.open_search("tv")

    def _toggle_favorites_filter():
        set_filters({**filters, "fav_only": not filters.get("fav_only", False)})

    header = Header(
        on_search_click=_open_search,
        on_favorites_toggle=_toggle_favorites_filter,
        on_add_content=lambda: set_add_dialog_open(True),
        on_refresh=on_refresh_home,
        refresh_tooltip="Refresh Channels",
        fav_active=filters.get("fav_only", False),
    )

    def _open_recently_watched():
        from flet import context

        from screens.recently_watched_screen import RecentlyWatchedScreen

        page = context.page
        page.views.append(
            ft.View(
                route="/recently-watched",
                controls=[
                    RecentlyWatchedScreen(
                        history=state.history,
                        channels_map=channels_map,
                        on_play=on_play,
                    )
                ],
            )
        )
        page.update()

    from flet import context

    from components.banner_ad import build_banner_ad

    page = context.page

    recently = RecentlyWatched(
        history=state.history,
        channels_map=channels_map,
        on_play=on_play,
        on_view_all=_open_recently_watched,
    )

    top_banner_ad = build_banner_ad(page)

    filter_bar = FilterBar(
        filters=filters,
        on_change=on_filters_updated,
        available_countries=extract_country_counts(built_in_channels),
        available_categories=extract_category_counts(built_in_channels),
        user_country=state.user_country,
        custom_playlists=custom_playlists,
        total_count=len(visible),
        on_add_content=lambda: set_add_dialog_open(True),
    )

    if not state.channels:
        return ft.Container(
            expand=True,
            content=ft.Column(
                controls=[
                    header,
                    LoadingState(label="Loading channels..."),
                ],
                expand=True,
                spacing=0,
            ),
        )

    if not visible:
        body = EmptyState(
            title=LBL_NO_CHANNELS_FOUND,
            message=LBL_NO_CHANNELS_HINT,
            action_label=LBL_ADD_CONTENT_SHORT,
            on_action=lambda e: set_add_dialog_open(True),
        )
    else:
        body = ChannelGrid(
            channels=visible,
            favorites_set=favorites_set,
            on_play=on_play,
            on_toggle_favorite=on_toggle_favorite,
            ad_service=getattr(controller, "ad_service", None),
        )

    dialog = AddCustomContentDialog(
        open=add_dialog_open,
        on_close=lambda: set_add_dialog_open(False),
        on_added=on_add_content_complete,
    )

    return ft.Stack(
        controls=[
            ft.Column(
                controls=[
                    header,
                    recently,
                    top_banner_ad,
                    filter_bar,
                    body,
                    dialog,
                ],
                expand=True,
                spacing=0,
            ),
            ft.FloatingActionButton(
                content=ft.Icon(ft.Icons.ADD),
                mini=True,
                tooltip="Add Custom Content",
                on_click=lambda e: set_add_dialog_open(True),
                bottom=80,
                right=12,
            ),
        ],
        expand=True,
    )
