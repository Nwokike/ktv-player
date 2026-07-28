"""OnboardingScreen — first-launch country select + terms acceptance.

A @ft.component that owns four pieces of local state with use_state:
selected_country, terms_accepted, is_loading, is_offline.

Online flow:  Image + Welcome + Tagline + CountryPicker + Terms + Start.
Offline flow: OfflineFlow (retry re-runs probe, skip persists defaults).

Persistence calls write the SAME keys AppController.init() reads (see
src/main.py lines 65-71): `user_country` and `accepted_terms=true`. On
success we flip the observable `state.has_accepted_terms` so the parent
AppShell re-renders to the dashboard without page.update().

OBSERVABLE SUBSCRIPTION NOTE: We access global state via
`ft.use_context(AppStateCtx)` rather than a plain `from ... import state`.
This matters because `use_context` automatically attaches an
ObservableSubscription to the component when the resolved value is an
Observable (verified in
.venv/lib/python3.13/site-packages/flet/components/hooks/use_context.py
lines 105-106). A plain import would NOT subscribe.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import flet as ft
from flet.controls.control import Control

from app_next.components.loading_state import LoadingState
from app_next.hooks.use_storage import Storage, use_storage
from app_next.state.app_state import AppStateCtx
from core.constants import (
    LBL_PLEASE_ACCEPT_TERMS,
    LBL_PLEASE_SELECT_COUNTRY,
    LBL_SELECT_COUNTRY,
    LBL_START_WATCHING,
    LBL_TV_NAV_HINT,
    LBL_USAGE_AGREEMENT,
    LBL_WELCOME,
    LBL_WELCOME_SUB,
    TERMS_TEXT,
)
from core.theme import AppColors


def can_submit(country: str, terms: bool) -> bool:
    """Submit is enabled only when a country is selected AND terms checked."""
    return bool(country) and bool(terms)


async def _persist_terms_and_country(
    storage: Storage, state: Any, country: str
) -> None:
    """Persist the user's country + terms acceptance and flip observable state.

    Writes `user_country=<name>` and `accepted_terms=true` — the SAME keys
    `AppController.init()` reads on next launch. Mutates the provided
    observable state so the parent AppShell re-renders automatically.
    """
    await storage.set_setting("user_country", country)
    await storage.set_setting("accepted_terms", "true")
    state.user_country = country
    state.has_accepted_terms = True
    state.is_first_launch = False


async def _persist_offline_defaults(storage: Storage, state: Any) -> None:
    """Skip-to-offline: default country to 'Other' and accept terms."""
    await storage.set_setting("user_country", "Other")
    await storage.set_setting("accepted_terms", "true")
    state.user_country = "Other"
    state.has_accepted_terms = True
    state.is_first_launch = False


@ft.component
def OnboardingScreen(
    countries: list[dict],
    on_complete: Callable[[], Awaitable[None] | None],
    prober: Callable[[], Awaitable[None]] | None = None,
) -> Control:
    """Render the first-launch onboarding.

    Args:
        countries: list of {"name": "...", ...} dicts from ChannelProvider.
        on_complete: called (sync or async) after the user submits or skips.
        prober: optional async callable that loads channels (e.g.
            controller.refresh_channels). Runs on mount; if it
            successfully populates state.channels the online form is shown.
    """
    selected_country, set_selected_country = ft.use_state("")
    terms_accepted, set_terms_accepted = ft.use_state(False)
    is_loading, set_is_loading = ft.use_state(False)
    is_offline, set_is_offline = ft.use_state(False)
    storage = use_storage()
    state = ft.use_context(AppStateCtx)

    async def _load_and_probe() -> bool:
        """Call the prober to load channels, then return True if any loaded."""
        if prober:
            try:
                await prober()
            except Exception:
                pass
        return bool(state.channels)

    async def _run_probe():
        set_is_loading(True)
        try:
            ok = await _load_and_probe()
            set_is_offline(not ok)
        finally:
            set_is_loading(False)

    ft.on_mounted(_run_probe)

    # Derive country list from loaded channels, falling back to static prop
    available_countries = ft.use_memo(
        lambda: _extract_countries(state.channels) or countries,
        [state.channels_hash],
    )

    async def _on_retry(e):
        set_is_offline(False)
        await _run_probe()

    async def _on_skip(e):
        await _persist_offline_defaults(storage, state)
        await _maybe_invoke(on_complete)

    async def _on_submit(e):
        if not terms_accepted:
            _notify_warning(LBL_PLEASE_ACCEPT_TERMS)
            return
        if not selected_country:
            _notify_warning(LBL_PLEASE_SELECT_COUNTRY)
            return
        await _persist_terms_and_country(storage, state, selected_country)
        await _maybe_invoke(on_complete)

    if is_loading:
        return LoadingState(label="Connecting...")

    if is_offline:
        from app_next.components.offline_flow import OfflineFlow as _OfflineFlow

        return _OfflineFlow(on_retry=_on_retry, on_skip=_on_skip)

    return _build_online_form(
        countries=available_countries,
        selected_country=selected_country,
        on_select=set_selected_country,
        terms_accepted=terms_accepted,
        on_terms_toggle=set_terms_accepted,
        on_submit=_on_submit,
    )


# --- helpers ---


def _extract_countries(channels: list[dict]) -> list[dict]:
    """Derive country list from channel data (matches home_screen._extract_countries)."""
    seen = set()
    result = []
    for c in channels:
        group = c.get("group", "General")
        country = group.split(";")[0].strip()
        if country and country not in seen and c.get("country_code"):
            seen.add(country)
            result.append({"name": country})
    return sorted(result, key=lambda x: x["name"])


async def _maybe_invoke(fn: Callable[[], Awaitable[None] | None]) -> None:
    result = fn()
    if hasattr(result, "__await__"):
        await result


def _notify_warning(msg: str) -> None:
    """Show a SnackBar-as-dialog warning. Best-effort — swallow if no page."""
    from flet.controls.context import context

    try:
        page = context.page
        page.show_dialog(ft.SnackBar(ft.Text(msg), bgcolor=AppColors.WARNING))
    except Exception:
        pass


def _build_online_form(
    countries: list[dict],
    selected_country: str,
    on_select: Callable[[str], None],
    terms_accepted: bool,
    on_terms_toggle: Callable[[bool], None],
    on_submit: Callable[[Any], Awaitable[None]],
) -> Control:
    """Build the online country + terms form."""
    country_list = ft.ListView(
        controls=[_country_tile(c, selected_country, on_select) for c in countries],
        height=180,
        spacing=2,
        padding=5,
        build_controls_on_demand=True,
    )

    return ft.Container(
        expand=True,
        alignment=ft.Alignment(0.0, 0.0),
        padding=ft.Padding.symmetric(horizontal=40),
        content=ft.ListView(
            controls=[
                ft.Container(height=30),
                ft.Column(
                    controls=[
                        ft.Image(
                            src="/icon.png", width=90, height=90, border_radius=20
                        ),
                        ft.Text(
                            LBL_WELCOME,
                            size=34,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            LBL_WELCOME_SUB,
                            size=15,
                            text_align=ft.TextAlign.CENTER,
                            color=AppColors.GREY_DIM,
                            width=400,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
                ft.Divider(height=24, color=ft.Colors.TRANSPARENT),
                ft.Text(
                    LBL_SELECT_COUNTRY,
                    size=18,
                    weight=ft.FontWeight.W_600,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    LBL_TV_NAV_HINT,
                    size=12,
                    color=AppColors.GREY_DIM,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(
                    content=country_list,
                    border=ft.Border.all(1.5, AppColors.PRIMARY),
                    border_radius=16,
                    padding=6,
                ),
                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                ft.Container(
                    content=ft.Text(TERMS_TEXT, size=12, color=AppColors.GREY_DIM),
                    padding=16,
                    border_radius=14,
                    border=ft.Border.all(1, AppColors.GREY_DIM),
                ),
                ft.Row(
                    controls=[
                        ft.Checkbox(
                            value=terms_accepted,
                            on_change=lambda e: on_terms_toggle(e.control.value),
                        ),
                        ft.Text(
                            LBL_USAGE_AGREEMENT, size=14, weight=ft.FontWeight.W_500
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=8,
                    wrap=True,
                ),
                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                ft.FilledButton(
                    content=ft.Text(
                        LBL_START_WATCHING, size=16, weight=ft.FontWeight.W_600
                    ),
                    on_click=on_submit,
                    disabled=not can_submit(selected_country, terms_accepted),
                    width=float("inf"),
                ),
                ft.Container(height=30),
            ],
            expand=True,
            spacing=10,
        ),
    )


def _country_tile(
    country: dict,
    selected_country: str,
    on_select: Callable[[str], None],
) -> ft.ListTile:
    name = country.get("name", "")
    is_selected = name == selected_country
    return ft.ListTile(
        key=ft.ValueKey(name),
        title=ft.Text(
            name,
            color=ft.Colors.WHITE if is_selected else None,
            weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.NORMAL,
        ),
        leading=ft.Icon(
            ft.Icons.CHECK_CIRCLE if is_selected else ft.Icons.RADIO_BUTTON_UNCHECKED,
            color=ft.Colors.WHITE if is_selected else AppColors.GREY_DIM,
        ),
        on_click=lambda e, n=name: on_select(n),
        dense=True,
        shape=ft.RoundedRectangleBorder(radius=8),
    )
