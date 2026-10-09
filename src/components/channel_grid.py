"""ChannelGrid — paginated grid with banner slot."""

from collections.abc import Callable

import flet as ft
from flet import Control

from components.channel_card import LivelinessChannelCard
from components.empty_state import EmptyState
from core.constants import PAGE_SIZE


def _build_channel_card(ch, favorites_set, on_play, on_toggle_favorite):
    """Build a single channel card control.

    Liveliness is owned by LivelinessChannelCard (per-card subscription):
    a verdict repaints its one card, not the whole grid.
    """
    url = ch.get("url") or ""
    return ft.Container(
        content=LivelinessChannelCard(
            channel=ch,
            is_favorite=url in favorites_set,
            on_play=on_play,
            on_toggle_favorite=on_toggle_favorite,
        ),
        col={"xs": 6, "sm": 4, "md": 3, "lg": 2, "xl": 2},
        padding=4,
        key=url or None,
    )


def _page_button(
    label: str, icon, disabled: bool, on_click, autofocus: bool = False
) -> Control:
    """Focusable pagination button honoring disabled (no fire when disabled).

    The old Container(on_click) was invisible to D-pad/keyboard tab order and
    fired hit-tests even when "disabled" (guarded only inside the lambda).
    """
    from core.theme import AppColors

    color = AppColors.grey_dim() if disabled else AppColors.PRIMARY
    content = (
        [
            ft.Icon(icon, size=14, color=color),
            ft.Text(label, size=12, weight=ft.FontWeight.BOLD, color=color),
        ]
        if label == "Previous"
        else [
            ft.Text(label, size=12, weight=ft.FontWeight.BOLD, color=color),
            ft.Icon(icon, size=14, color=color),
        ]
    )
    return ft.OutlinedButton(
        content=ft.Row(controls=content, spacing=6),
        style=ft.ButtonStyle(
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            shape=ft.RoundedRectangleBorder(radius=10),
            side={
                ft.ControlState.DISABLED: ft.BorderSide(1.5, AppColors.grey_dim()),
                ft.ControlState.DEFAULT: ft.BorderSide(
                    1.5, AppColors.grey_dim() if disabled else AppColors.PRIMARY
                ),
            },
        ),
        tooltip=label,
        autofocus=autofocus,
        disabled=disabled,
        on_click=on_click,
    )


@ft.component
def ChannelGrid(
    channels: list[dict],
    favorites_set: set[str],
    on_play: Callable[..., None],
    on_toggle_favorite: Callable[[str], None],
    page=None,
) -> Control:
    from state.app_state import AppStateCtx

    state = ft.use_context(AppStateCtx)
    current_page, set_current_page = ft.use_state(0)

    total_pages = max(1, (len(channels) + PAGE_SIZE - 1) // PAGE_SIZE)

    # Clamp via effect + setter (never set state during render): restoring a
    # full filter after narrowing snapped back to the stale page.
    def _clamp_page():
        if current_page >= total_pages:
            set_current_page(total_pages - 1)

    ft.use_effect(_clamp_page, [total_pages])
    page_idx = min(current_page, total_pages - 1)

    start = page_idx * PAGE_SIZE
    end = min(start + PAGE_SIZE, len(channels))
    visible = channels[start:end]
    # Content identity (not len): a filter swap with the same count must
    # still re-seed, or new channels sit grey with no checks enqueued.
    content_key = tuple(c.get("url", "") for c in visible)

    def _seed_page_liveliness():
        if visible:
            from services.liveliness_checker import (
                drain_queue,
                enqueue_liveliness_check,
            )
            from services.logo_cache import enqueue_logo_download

            drain_queue()
            for ch in visible:
                url = ch.get("url", "")
                if url:
                    enqueue_liveliness_check(url)
                logo = ch.get("logo") or ""
                if logo and not logo.startswith("/"):
                    enqueue_logo_download(logo)

    # is_online in deps: reconnect re-enqueues this page's checks immediately
    ft.use_effect(_seed_page_liveliness, [page_idx, content_key, state.is_online])

    from components.banner_ad import build_banner_ad

    # Memoized per mount: the old per-render build_banner_ad(page) re-created
    # a native ad view on every liveliness tick (request storm + flicker).
    # Hoisted ABOVE the early return: hooks must run unconditionally every
    # render or hook order shifts across the empty/non-empty boundary.
    bot_ad = ft.use_memo(lambda: build_banner_ad(page), [page])

    if not visible:
        return EmptyState(
            title="No channels found",
            message="Adjust filters or add content.",
            action_label=None,
        )

    # Build grid sections with ads between chunks
    sections: list[Control] = []
    grid_controls = [
        _build_channel_card(ch, favorites_set, on_play, on_toggle_favorite)
        for ch in visible
    ]
    sections.append(
        ft.ResponsiveRow(
            controls=grid_controls,
            spacing=12,
            run_spacing=12,
        )
    )

    if bot_ad:
        sections.append(bot_ad)

    if total_pages > 1:
        prev_disabled = page_idx == 0
        next_disabled = page_idx >= total_pages - 1

        def _go_prev(e=None):
            if not prev_disabled:
                set_current_page(max(0, page_idx - 1))

        def _go_next(e=None):
            if not next_disabled:
                set_current_page(min(total_pages - 1, page_idx + 1))

        sections.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        _page_button(
                            "Previous",
                            ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                            prev_disabled,
                            _go_prev,
                        ),
                        ft.Text(
                            f"Page {page_idx + 1} of {total_pages}  ·  {len(channels)} channels",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.with_opacity(0.8, ft.Colors.ON_SURFACE),
                        ),
                        _page_button(
                            "Next",
                            ft.Icons.ARROW_FORWARD_IOS_ROUNDED,
                            next_disabled,
                            _go_next,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=16,
                ),
                padding=ft.Padding(0, 16, 0, 24),
            )
        )

    # Key swap resets scroll offset on page flip (the Column kept its scroll
    # position, landing users at the bottom of the new page). The
    # AnimatedSwitcher crossfades the flip — the only swap in the app where
    # a hard cut is actually visible (TV D-pad page turns).
    return ft.AnimatedSwitcher(
        ft.Column(
            controls=sections,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            key=f"channel-grid-{page_idx}-{len(channels)}",
        ),
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=200,
        switch_in_curve=ft.AnimationCurve.EASE_OUT,
    )
