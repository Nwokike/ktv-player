"""SearchScreen — debounced search over channels with ChannelGrid results."""

import flet as ft
from flet.controls.control import Control

from app_next.components.channel_grid import ChannelGrid
from app_next.components.empty_state import EmptyState
from app_next.hooks.use_debounce import use_debounce
from app_next.state.app_state import AppStateCtx
from app_next.state.controller_ctx import ControllerMethodsCtx
from core.constants import LBL_SEARCH_HINT, MAX_SEARCH_RESULTS


def _search_filter(channels: list[dict], query: str) -> list[dict]:
    """Case-insensitive name/URL match, capped at MAX_SEARCH_RESULTS."""
    if not query.strip():
        return channels[:MAX_SEARCH_RESULTS]
    q = query.lower().strip()
    return [
        c
        for c in channels
        if q in c.get("name", "").lower() or q in c.get("url", "").lower()
    ][:MAX_SEARCH_RESULTS]


@ft.component
def SearchScreen() -> Control:
    state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    query, set_query = ft.use_state("")
    debounced_query = use_debounce(query, 250)

    visible = ft.use_memo(
        lambda: _search_filter(state.channels, debounced_query),
        [state.channels_hash, debounced_query],
    )

    fav_dep = (
        tuple(state.favorites)
        if isinstance(state.favorites, (list, set, tuple))
        else state.favorites
    )
    favorites_set = ft.use_memo(
        lambda: (
            set(state.favorites) if isinstance(state.favorites, (list, set)) else set()
        ),
        [state.channels_hash, fav_dep],
    )

    def on_play(url):
        import asyncio

        asyncio.create_task(controller.play_stream(url, None))

    search_field = ft.TextField(
        value=query,
        on_change=lambda e: set_query(e.control.value),
        hint_text=LBL_SEARCH_HINT,
        autofocus=True,
        prefix_icon=ft.Icons.SEARCH,
        expand=True,
    )

    body = (
        ChannelGrid(
            channels=visible,
            favorites_set=favorites_set,
            on_play=on_play,
            on_toggle_favorite=lambda url: _toggle_fav_simple(url, state),
            ad_service=getattr(controller, "ad_service", None),
        )
        if visible
        else EmptyState(
            title="No results",
            message="Try a different search term."
            if query.strip()
            else "Type to search channels.",
            icon=ft.Icons.SEARCH_OFF,
            action_label=None,
        )
    )

    return ft.Container(
        expand=True,
        content=ft.Column(
            controls=[
                ft.Container(
                    content=search_field,
                    padding=ft.Padding(12, 8, 12, 4),
                ),
                ft.Container(content=body, expand=True),
            ],
            spacing=0,
        ),
    )


def _toggle_fav_simple(url: str, state):
    """Fire-and-forget favorite toggle."""
    import asyncio

    from database.manager import db_manager

    async def _do():
        try:
            if url in (state.favorites or set()):
                await db_manager.remove_favorite(url)
                if hasattr(state.favorites, "discard"):
                    state.favorites.discard(url)
                else:
                    state.favorites.remove(url)
            else:
                await db_manager.add_favorite(url)
                if isinstance(state.favorites, set):
                    state.favorites.add(url)
                elif isinstance(state.favorites, list):
                    state.favorites.append(url)
        except Exception:
            pass

    asyncio.create_task(_do())
