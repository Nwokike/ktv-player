"""OnboardingScreen — first-launch country select + terms acceptance."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import flet as ft
from flet import Control

from components.loading_state import LoadingState
from components.offline_flow import OfflineFlow
from core.constants import (
    LBL_CONNECTING,
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
from hooks.use_storage import Storage, use_storage
from state.app_state import AppStateCtx
from utils.channels import extract_country_dicts
from utils.notifications import notify_error, notify_warning

logger = logging.getLogger(__name__)


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
    # Start loading only when a probe can actually run: without a prober
    # there is nothing to wait for, and starting True would flash the
    # spinner for one frame before the form appears.
    is_loading, set_is_loading = ft.use_state(prober is not None)
    is_offline, set_is_offline = ft.use_state(False)
    is_saving, set_is_saving = ft.use_state(False)
    probe_error, set_probe_error = ft.use_state("")
    storage = use_storage()
    state = ft.use_context(AppStateCtx)

    async def _load_and_probe() -> bool:
        """Call the prober to load channels, then return True if any loaded."""
        if prober:
            try:
                await prober()
            except Exception:
                logger.debug("Onboarding channel probe failed", exc_info=True)
        return bool(state.channels)

    async def _run_probe():
        set_is_loading(True)
        set_probe_error("")
        try:
            ok = await _load_and_probe()
            set_is_offline(not ok)
        finally:
            set_is_loading(False)

    ft.on_mounted(_run_probe)

    # Derive country list from loaded channels, falling back to static prop.
    # extract always appends "Other", so `or` can never fire on its result —
    # the emptiness check must be on state.channels itself.
    available_countries = ft.use_memo(
        lambda: extract_country_dicts(state.channels) if state.channels else countries,
        [state.channels_hash],
    )

    # A re-probe can shrink the list (fewer countries this launch): drop a
    # selection that no longer exists instead of submitting a ghost.
    def _clamp_selection():
        names = {c.get("name", "") for c in available_countries}
        if selected_country and selected_country not in names:
            set_selected_country("")

    ft.use_effect(_clamp_selection, [available_countries])

    async def _on_retry(e):
        set_is_offline(False)
        await _run_probe()

    async def _on_skip(e):
        if is_saving:
            return
        set_is_saving(True)
        try:
            await _persist_offline_defaults(storage, state)
        except Exception:
            logger.exception("Onboarding offline-defaults persist failed")
            notify_error("Could not save settings — try again.")
            return
        finally:
            set_is_saving(False)
        await _maybe_invoke(on_complete)

    async def _on_submit(e):
        if is_saving:
            return
        if not terms_accepted:
            _notify_warning(LBL_PLEASE_ACCEPT_TERMS)
            return
        if not selected_country:
            _notify_warning(LBL_PLEASE_SELECT_COUNTRY)
            return
        set_is_saving(True)
        try:
            await _persist_terms_and_country(storage, state, selected_country)
        except Exception:
            logger.exception("Onboarding submit persist failed")
            notify_error("Could not save settings — try again.")
            return
        finally:
            set_is_saving(False)
        await _maybe_invoke(on_complete)

    if is_loading:
        return LoadingState(label=LBL_CONNECTING)

    if is_offline:
        return OfflineFlow(on_retry=_on_retry, on_skip=_on_skip)

    if not available_countries:
        return ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.PUBLIC_OFF, size=48),
                    ft.Text(
                        "No countries found yet.",
                        size=16,
                        weight=ft.FontWeight.W_600,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        probe_error or LBL_CONNECTING,
                        size=13,
                        color=AppColors.grey_dim(),
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.OutlinedButton(
                        "Retry",
                        icon=ft.Icons.REFRESH,
                        on_click=_on_retry,
                        autofocus=True,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
            ),
        )

    return _build_online_form(
        countries=available_countries,
        selected_country=selected_country,
        on_select=set_selected_country,
        terms_accepted=terms_accepted,
        on_terms_toggle=set_terms_accepted,
        on_submit=_on_submit,
        is_saving=is_saving,
    )


# --- helpers ---


async def _maybe_invoke(fn: Callable[[], Awaitable[None] | None]) -> None:
    result = fn()
    if hasattr(result, "__await__"):
        await result


_notify_warning = notify_warning


def _build_online_form(
    countries: list[dict],
    selected_country: str,
    on_select: Callable[[str], None],
    terms_accepted: bool,
    on_terms_toggle: Callable[[bool], None],
    on_submit: Callable[[Any], Awaitable[None]],
    is_saving: bool = False,
) -> Control:
    """Build the online country + terms form."""
    # Flat Column under a size cap: a nested ListView inside the outer
    # scroll traps wheel/D-pad scroll events inside the 180px box. The
    # country list is short (<= 178 rows, small tiles) and the outer form
    # already scrolls, so a bounded column is the honest layout.
    tiles = [_country_tile(c, selected_country, on_select) for c in countries]
    capped = tiles[:200]
    country_list = ft.Column(
        controls=capped,
        spacing=2,
    )

    ready = can_submit(selected_country, terms_accepted)
    if not selected_country:
        hint = "Pick your country above to continue."
    elif not terms_accepted:
        hint = "Accept the usage agreement to continue."
    else:
        hint = ""

    return ft.Container(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=40),
        content=ft.ListView(
            controls=[
                ft.Container(height=30),
                ft.Column(
                    controls=[
                        ft.Image(
                            src="/icon.svg",
                            width=90,
                            height=90,
                            error_content=ft.Icon(ft.Icons.LIVE_TV_ROUNDED, size=64),
                            semantics_label="KTV Player",
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
                            color=AppColors.grey_dim(),
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
                    color=AppColors.grey_dim(),
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
                    content=ft.Text(TERMS_TEXT, size=12, color=AppColors.grey_dim()),
                    padding=16,
                    border_radius=14,
                    border=ft.Border.all(1, AppColors.grey_dim()),
                ),
                ft.Row(
                    controls=[
                        ft.Checkbox(
                            value=terms_accepted,
                            on_change=lambda e: on_terms_toggle(e.control.value),
                            autofocus=True,
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
                        LBL_START_WATCHING if not is_saving else "Saving...",
                        size=16,
                        weight=ft.FontWeight.W_600,
                    ),
                    on_click=on_submit,
                    disabled=not ready or is_saving,
                    width=float("inf"),
                ),
                *(
                    [
                        ft.Text(
                            hint,
                            size=12,
                            italic=True,
                            color=AppColors.grey_dim(),
                            text_align=ft.TextAlign.CENTER,
                        )
                    ]
                    if hint and not is_saving
                    else []
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
        bgcolor=AppColors.PRIMARY if is_selected else None,
        title=ft.Text(
            name,
            color=ft.Colors.WHITE if is_selected else None,
            weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.NORMAL,
        ),
        leading=ft.Icon(
            ft.Icons.CHECK_CIRCLE if is_selected else ft.Icons.RADIO_BUTTON_UNCHECKED,
            color=ft.Colors.WHITE if is_selected else AppColors.grey_dim(),
        ),
        on_click=lambda e, n=name: on_select(n),
        dense=True,
        shape=ft.RoundedRectangleBorder(radius=8),
    )
