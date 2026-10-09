"""HomeScreen — main browsing screen with header, filters, and channel grid."""

import contextlib
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
from core.state import state as core_state
from hooks.apply_filters import _default_filters, apply_filters, reconcile_filters
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

    # Auto-load channels on first mount (page task, not orphan create_task:
    # unmount during flight must not set state on a dead component).
    def _auto_load():
        if not state.channels and callable(
            getattr(controller, "refresh_channels", None)
        ):
            try:
                from flet import context as _ctx

                _ctx.page.run_task(controller.refresh_channels)
            except Exception:
                logger.debug("Auto-load scheduling failed", exc_info=True)

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
    available_countries = ft.use_memo(
        lambda: extract_country_counts(built_in_channels),
        [state.channels_hash],
    )
    available_categories = ft.use_memo(
        lambda: extract_category_counts(built_in_channels),
        [state.channels_hash],
    )

    # No channel data is NOT evidence that a folder died: on first render
    # the channels are still loading, and reconciling against empty maps
    # used to wipe the saved country on every launch (and toast about it).
    # Reconcile only once channels are loaded.
    channels_loaded = bool(state.channels)

    # A playlist swap can delete the folder a stored selection points at;
    # exact-match filtering would then return zero channels forever with
    # no error. Reconcile as pure data, then sync the reset back into
    # state once so the pill label and the filter dict cannot disagree.
    filters_eff = ft.use_memo(
        lambda: (
            filters
            if not channels_loaded
            else reconcile_filters(
                filters, available_countries, available_categories, custom_playlists
            )
        ),
        [
            filters,
            channels_loaded,
            available_countries,
            available_categories,
            custom_playlists,
        ],
    )

    # One reset notice per real event (a swap that removed the selected
    # folder), never per launch and never per render.
    reset_notified = use_ref(False)

    def _sync_reconciled():
        if not channels_loaded or filters == filters_eff:
            # Back at steady state: re-arm the one-shot reset notice.
            if channels_loaded and filters == filters_eff:
                reset_notified.current = False
            return
        from utils.notifications import notify

        set_filters(filters_eff)
        if not reset_notified.current:
            reset_notified.current = True
            notify("Your channel list was updated. Check your filters.")

    ft.use_effect(_sync_reconciled, [filters_eff])

    # Filtered visible channels
    visible = ft.use_memo(
        lambda: apply_filters(state.channels, filters_eff, favorites_set),
        [state.channels_hash, filters_eff, favorites_set],
    )

    # Liveliness dots are owned per-card (LivelinessChannelCard subscribes
    # for its own url): the screen-level coalesced re-render is gone, so a
    # verdict repaints one card instead of rebuilding header/filter/grid.

    logger.info(
        "Rendered HomeScreen (total_channels=%d, visible_filtered=%d)",
        len(state.channels),
        len(visible),
    )

    # --- handlers ---

    _play_in_flight = use_ref(False)

    def on_play(url: str, title: str | None = None):
        # Double-tap guard: rapid taps must not stack concurrent play_stream
        # races (double player view). run_task, not orphan create_task.
        if _play_in_flight.current:
            return
        _play_in_flight.current = True

        async def _play():
            try:
                await controller.play_stream(url, title)
            except Exception:
                # Log before notifying: the snackbar is best-effort and
                # silent when it fails, which once hid a play click that
                # produced zero output at all.
                logger.exception("play_stream failed for %s", url)
                from utils.notifications import notify_error

                notify_error(ERR_PLAYBACK_FAILED)
            finally:
                _play_in_flight.current = False

        try:
            from flet import context as _ctx

            _ctx.page.run_task(_play)
        except Exception:
            _play_in_flight.current = False
            logger.debug("Play scheduling failed", exc_info=True)

    def on_toggle_favorite(url: str):
        toggle_favorite(url, state)

    def on_filters_updated(new_filters: dict):
        # Functional update: the render-closure `filters` may be stale when a
        # pill change lands between keystrokes — merge onto latest instead.
        set_filters(lambda prev: {**prev, **new_filters})

    async def on_add_content_complete():
        set_add_dialog_open(False)
        await controller.refresh_channels()

    # --- Build tree ---

    def on_refresh_home():
        from utils.notifications import notify

        notify("Refreshing channels...")
        try:
            from flet import context as _ctx

            _ctx.page.run_task(controller.refresh_channels, force=True)
        except Exception:
            logger.debug("Refresh scheduling failed", exc_info=True)

    def _open_search():
        if callable(getattr(controller, "open_search", None)):
            controller.open_search("tv")

    def _toggle_favorites_filter():
        fav_selected = filters.get("fav_only", False)
        set_filters(
            {
                "fav_only": not fav_selected,
                "country": "all",
                "category": "all",
                "custom": "none",
                "search": "",
            }
        )

    _update_data = core_state.update_data
    header = Header(
        on_search_click=_open_search,
        on_favorites_toggle=_toggle_favorites_filter,
        on_add_content=lambda: set_add_dialog_open(True),
        on_refresh=on_refresh_home,
        on_version_click=lambda: (
            controller.open_version_dialog()
            if callable(getattr(controller, "open_version_dialog", None))
            else None
        ),
        refresh_tooltip="Refresh Channels",
        fav_active=filters.get("fav_only", False),
        # Lifted update state: HomeScreen rebuilds on the observable, so
        # the chip repaints on every state flip (see Header docstring).
        update_available=core_state.update_available,
        update_label=getattr(_update_data, "version", None),
        update_announcement=getattr(_update_data, "type", "") == "announcement",
    )

    def _open_recently_watched():
        from flet import context

        from screens.recently_watched_screen import RecentlyWatchedScreen

        try:
            page = context.page
        except Exception:
            return
        if any(getattr(v, "route", "") == "/recently-watched" for v in page.views):
            # Already open: stacking duplicates grows the back stack without
            # bound and strands Back navigation. Focus the existing view.
            with contextlib.suppress(Exception):
                page.update()
            return

        def _close_history(e=None):
            if page.views and getattr(page.views[-1], "route", "") == (
                "/recently-watched"
            ):
                page.views.pop()
                with contextlib.suppress(Exception):
                    page.update()

        page.views.append(
            ft.View(
                route="/recently-watched",
                appbar=ft.AppBar(
                    title=ft.Text("Recently Watched", weight=ft.FontWeight.BOLD),
                    center_title=False,
                    leading=ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        tooltip="Back",
                        on_click=_close_history,
                    ),
                ),
                controls=[
                    RecentlyWatchedScreen(
                        history=state.history,
                        channels_map=channels_map,
                        on_play=on_play,
                        on_back=_close_history,
                        page=page,
                    )
                ],
            )
        )
        with contextlib.suppress(Exception):
            page.update()

    from components.banner_ad import build_banner_ad

    try:
        from flet import context as _banner_ctx

        _banner_page = _banner_ctx.page
    except Exception:
        _banner_page = None

    recently = RecentlyWatched(
        history=state.history,
        channels_map=channels_map,
        on_play=on_play,
        on_view_all=_open_recently_watched,
    )

    # Memoized per mount (premium/platform deps): the old per-render build
    # re-created a native ad view on every 500ms liveliness tick.
    top_banner_ad = ft.use_memo(
        lambda: build_banner_ad(_banner_page),
        [state.is_premium],
    )

    filter_bar = FilterBar(
        filters=filters,
        on_change=on_filters_updated,
        available_countries=available_countries,
        available_categories=available_categories,
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
        try:
            from flet import context as _page_ctx

            _grid_page = _page_ctx.page
        except Exception:
            _grid_page = None
        body = ChannelGrid(
            channels=visible,
            favorites_set=favorites_set,
            on_play=on_play,
            on_toggle_favorite=on_toggle_favorite,
            page=_grid_page,
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
