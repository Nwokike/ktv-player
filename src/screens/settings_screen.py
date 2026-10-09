"""SettingsScreen — modern Material 3 grouped settings."""

import asyncio
import contextlib
import logging
import time

import flet as ft
from flet import Control

from channels.provider import channel_provider
from core.channel import CHANNEL
from core.constants import (
    APP_NAME,
    APP_VERSION,
    CONTACT_EMAIL,
    ERR_CLEAR_HISTORY_FAILED,
    ERR_RESET_LIBRARY_FAILED,
    GITHUB_REPO_URL,
    KIRI_APPS_PLAY_URL,
    KIRI_APPS_URL,
    LBL_ACTIVITY_TERMINAL,
    LBL_CLEAR,
    LBL_CLEAR_HISTORY,
    LBL_CLEAR_HISTORY_DESC,
    LBL_CLEARING,
    LBL_CLOSE,
    LBL_COPY_TO_CLIPBOARD,
    LBL_COUNTRY_UPDATED,
    LBL_DARK_MODE,
    LBL_DARK_MODE_DESC,
    LBL_DEFAULT_REGION,
    LBL_FILTER_BY_COUNTRY,
    LBL_HISTORY_CLEARED,
    LBL_LIBRARY_RESET,
    LBL_LIVE_ACTIVITY_TERMINAL,
    LBL_LOG_CLEARED,
    LBL_LOG_COPIED,
    LBL_LOG_NEWER,
    LBL_LOG_NEWEST,
    LBL_LOG_NO_NEW,
    LBL_LOG_OLDER,
    LBL_LOG_REFRESH,
    LBL_NO_ACTIVITY_LOG,
    LBL_OPEN_TERMINAL,
    LBL_RESET_LIBRARY,
    LBL_RESET_LIBRARY_DESC,
    LBL_RESETTING,
    LBL_TERMINAL_DESC,
    LBL_USAGE_AGREEMENT_BUTTON,
    LBL_USAGE_AGREEMENT_TITLE,
    PLAY_STORE_URL,
    TERMS_TEXT,
)
from core.logger_handler import in_memory_log_handler
from core.state import state as core_state
from core.theme import AppColors
from database.manager import db_manager
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx
from utils.channels import extract_countries
from utils.notifications import (
    notify,
    notify_warning,
    page_has_ads,
    premium_unlocked_message,
)
from utils.theme_utils import toggle_theme as _toggle_theme_util

logger = logging.getLogger("SettingsScreen")

_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def _is_store_device(page) -> bool:
    """Phones and TV are the Play audience; desktop has no Play listing."""
    try:
        return page.platform in (
            ft.PagePlatform.ANDROID,
            ft.PagePlatform.IOS,
            ft.PagePlatform.ANDROID_TV,
        )
    except Exception:
        return False


def _rate_url(page) -> str:
    return PLAY_STORE_URL if _is_store_device(page) else GITHUB_REPO_URL


def _rate_subtitle(page) -> str:
    return "Rate us on Google Play" if _is_store_device(page) else "Star us on GitHub"


def _more_apps_url(page) -> str:
    """Store devices open the Play developer listing; everything else
    the kiri.ng showcase that links every repo with downloads."""
    return KIRI_APPS_PLAY_URL if _is_store_device(page) else KIRI_APPS_URL


def _more_apps_subtitle(page) -> str:
    return (
        "All our apps on Google Play"
        if _is_store_device(page)
        else "Sherlock, DDGS, CollabShell and more"
    )


def _premium_subtitle(is_premium, claims, has_ads: bool = True) -> str:
    """Premium row subtitle: honest benefits for this platform.

    The channel pack is the benefit everywhere; "no ads" is claimed only
    where ads are actually requested (phones). paid-through comes from the
    signed token (exp-guarded), so the dates stay truthful offline, and
    its absence marks a lifetime license.
    """
    pack = "the premium channel pack: 10,000+ channels across 177 countries, top channels in every field"
    if not is_premium:
        return f"Remove all ads and unlock {pack}" if has_ads else f"Unlock {pack}"
    base = (
        "Ads removed · premium channels unlocked"
        if has_ads
        else "Premium channels unlocked"
    )
    paid_through = getattr(claims, "paid_through", None)
    if not paid_through:
        return f"{base} · thank you!"
    product = str(getattr(claims, "product", "") or "")
    renewal = {"monthly": "renews monthly", "yearly": "renews yearly"}.get(
        product, "renews automatically"
    )
    try:
        moment = time.gmtime(int(paid_through) / 1000)
        label = f"{moment.tm_mday} {_MONTHS[moment.tm_mon - 1]} {moment.tm_year}"
    except (TypeError, ValueError, OverflowError, OSError):
        return f"{base} · thank you!"
    return f"{base} · active until {label} · {renewal}"


_SECTIONS = [
    {"key": "appearance", "title": "Appearance", "icon": ft.Icons.PALETTE},
    {"key": "localization", "title": "Localization", "icon": ft.Icons.PUBLIC},
    {"key": "data_management", "title": "Data Management", "icon": ft.Icons.STORAGE},
    # Key stays "custom_content" for compat; the card shows the Activity
    # Terminal (title "Development"), not custom-content management.
    {"key": "custom_content", "title": "Development", "icon": ft.Icons.TERMINAL},
    {"key": "premium", "title": "Premium", "icon": ft.Icons.WORKSPACE_PREMIUM},
    {"key": "about", "title": "About", "icon": ft.Icons.INFO},
]


# ---------------------------------------------------------------------------
# Log terminal dialog
# ---------------------------------------------------------------------------


def _build_logs_dialog(page: ft.Page) -> ft.AlertDialog:
    from services.device_info import get_device_summary

    def _compose() -> str:
        logs = in_memory_log_handler.get_logs()
        # Cap the dump: a long session can hold 500 lines and dumping all
        # of them into one Text control janks low-end TV boxes.
        tail = logs[-500:]
        if len(logs) > len(tail):
            tail = [f"... ({len(logs) - len(tail)} older lines omitted) ...", *tail]
        body = "\n".join(tail) if tail else LBL_NO_ACTIVITY_LOG
        # Device header travels WITH the logs so the existing "Copy to clipboard"
        # produces a complete TV diagnostics dump (no way to pipe TV adb logs).
        return f"{get_device_summary()}\n\n--- logs ---\n{body}"

    log_text = ft.Text(
        value=_compose(),
        font_family="Courier New",
        size=12,
        color=AppColors.TERMINAL_TEXT,
        selectable=True,
    )
    log_col = ft.Column(
        controls=[log_text],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    async def _scroll(delta: float) -> None:
        with contextlib.suppress(Exception):
            await log_col.scroll_to(delta=delta, duration=120)

    async def _to_end() -> None:
        # offset=-1 is flet's documented "jump to the very end".
        with contextlib.suppress(Exception):
            await log_col.scroll_to(offset=-1, duration=120)

    async def _to_start() -> None:
        with contextlib.suppress(Exception):
            await log_col.scroll_to(offset=0, duration=120)

    async def _on_key(e) -> None:
        # Laptop keyboard and the Android TV D-pad both land here as
        # arrow / page keys while the dialog holds focus.
        k = str(getattr(e, "key", "") or "").strip().lower().replace(" ", "")
        if "page" in k and "down" in k:
            await _scroll(800)
        elif "page" in k and "up" in k:
            await _scroll(-800)
        elif k in ("down", "arrowdown", "dpaddown"):
            await _scroll(160)
        elif k in ("up", "arrowup", "dpadup"):
            await _scroll(-160)
        elif k == "end":
            await _to_end()
        elif k == "home":
            await _to_start()

    async def _copy(e=None):
        try:
            await ft.Clipboard().set(log_text.value)
            notify(LBL_LOG_COPIED)
        except Exception:
            # Android TV has no clipboard service in some images, and a
            # silent failure looks like the button is broken.
            notify_warning("Copy failed — clipboard unavailable on this device")

    def _clear(e=None):
        from flet import context as _ctx

        in_memory_log_handler.clear_logs()
        log_text.value = LBL_LOG_CLEARED
        try:
            log_text.update()
        except Exception:
            try:
                _ctx.page.update()
            except (RuntimeError, AttributeError):
                logger.debug("Log dialog clear update failed", exc_info=True)

    async def _refresh():
        new_value = _compose()
        if new_value == log_text.value:
            # A refresh that changes nothing must SAY so, or the button
            # looks broken when the log simply has no new lines yet.
            notify(LBL_LOG_NO_NEW)
            return
        log_text.value = new_value
        try:
            log_text.update()
        except Exception:
            logger.debug("Log dialog refresh update failed", exc_info=True)
        await asyncio.sleep(0.15)
        await _to_end()

    async def _prepare() -> None:
        # Open showing the NEWEST lines (the answer is always at the end):
        # wait for the dialog to lay out first, then jump down.
        await asyncio.sleep(0.5)
        await _to_end()

    async def _scroll_guarded(delta: float) -> None:
        try:
            await _scroll(delta)
        except Exception:
            logger.debug("Log dialog scroll failed", exc_info=True)

    async def _to_end_guarded() -> None:
        try:
            await _to_end()
        except Exception:
            logger.debug("Log dialog scroll-to-end failed", exc_info=True)

    async def _on_key_guarded(e) -> None:
        try:
            await _on_key(e)
        except Exception:
            logger.debug("Log dialog key handling failed", exc_info=True)

    async def _copy_guarded() -> None:
        try:
            await _copy()
        except Exception:
            logger.debug("Log dialog copy failed", exc_info=True)
            notify_warning("Copy failed — clipboard unavailable on this device")

    async def _refresh_guarded() -> None:
        try:
            await _refresh()
        except Exception:
            logger.debug("Log dialog refresh failed", exc_info=True)
            notify_warning("Could not refresh the log view.")

    page.run_task(_prepare)

    nav = ft.Row(
        controls=[
            ft.TextButton(
                LBL_LOG_OLDER,
                icon=ft.Icons.KEYBOARD_ARROW_UP,
                on_click=lambda e: page.run_task(_scroll_guarded, -300),
            ),
            ft.TextButton(
                LBL_LOG_NEWER,
                icon=ft.Icons.KEYBOARD_ARROW_DOWN,
                on_click=lambda e: page.run_task(_scroll_guarded, 300),
            ),
            ft.TextButton(
                LBL_LOG_NEWEST,
                on_click=lambda e: page.run_task(_to_end_guarded),
            ),
            ft.TextButton(
                LBL_LOG_REFRESH,
                icon=ft.Icons.REFRESH,
                on_click=lambda e: page.run_task(_refresh_guarded),
            ),
        ],
        spacing=6,
        run_spacing=4,
        wrap=True,
        run_alignment=ft.CrossAxisAlignment.CENTER,
    )

    body = ft.Column(
        controls=[
            ft.Text(LBL_TERMINAL_DESC, size=12, color=AppColors.grey_dim()),
            nav,
            ft.Container(
                content=log_col,
                bgcolor=AppColors.TERMINAL_BG,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
                border_radius=8,
                padding=12,
                expand=True,
            ),
        ],
        spacing=8,
    )

    return ft.AlertDialog(
        title=ft.Text(LBL_LIVE_ACTIVITY_TERMINAL, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.KeyboardListener(
                content=body,
                autofocus=True,
                on_key_down=lambda e: page.run_task(_on_key_guarded, e),
            ),
            width=480,
            height=400,
        ),
        actions=[
            ft.TextButton(
                LBL_COPY_TO_CLIPBOARD,
                icon=ft.Icons.COPY,
                on_click=lambda e: page.run_task(_copy_guarded),
            ),
            ft.TextButton(LBL_CLEAR, icon=ft.Icons.DELETE_SWEEP, on_click=_clear),
            ft.TextButton(LBL_CLOSE, on_click=lambda e: page.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )


# ---------------------------------------------------------------------------
# Reusable setting row
# ---------------------------------------------------------------------------


def _setting_row(
    leading: Control,
    title: str,
    subtitle: str,
    trailing: Control | None = None,
    on_click=None,
) -> ft.Container:
    """A single-line setting: [icon+text] ---- [control].

    `trailing` is optional: omitting it used to raise TypeError mid-render
    (the exception killed the whole Settings tab for non-premium users,
    with nothing logged — Flet's update scheduler swallows it).
    `on_click` makes the whole row tappable (Contact developer, Rate).
    """
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        leading,
                        ft.Column(
                            controls=[
                                ft.Text(title, size=13, weight=ft.FontWeight.W_500),
                                ft.Text(subtitle, size=11, color=AppColors.grey_dim()),
                            ],
                            spacing=1,
                            expand=True,
                        ),
                    ],
                    spacing=12,
                    expand=True,
                ),
                *([trailing] if trailing is not None else []),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(4, 10, 4, 10),
        ink=on_click is not None,
        on_click=on_click,
    )


def _section_card(title: str, icon: str, items: list[Control]) -> ft.Container:
    """A grouped settings card with header + divider + rows."""
    from flet import context

    page = context.page
    card_bg = AppColors.get_card_bg(page)
    border_color = AppColors.get_border_color(page)

    rows: list[Control] = []
    for i, item in enumerate(items):
        rows.append(item)
        if i < len(items) - 1:
            rows.append(
                ft.Divider(
                    height=1, color=border_color, leading_indent=44, trailing_indent=0
                )
            )

    return ft.Container(
        bgcolor=card_bg,
        border=ft.Border.all(1, border_color),
        border_radius=16,
        padding=ft.Padding(16, 8, 16, 8),
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(icon, color=AppColors.PRIMARY, size=20),
                        ft.Text(title, size=14, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=10,
                ),
                *rows,
            ],
            spacing=0,
        ),
    )


# ---------------------------------------------------------------------------
# Main screen
# ---------------------------------------------------------------------------


@ft.component
def SettingsScreen() -> Control:
    state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)
    is_clearing, set_is_clearing = ft.use_state(False)
    is_resetting, set_is_resetting = ft.use_state(False)

    # -- handlers --

    def _is_dark() -> bool:
        from flet import context

        try:
            return AppColors.is_dark(context.page)
        except (RuntimeError, AttributeError):
            return True

    def _toggle_theme(e):
        from flet import context

        try:
            _toggle_theme_util(context.page)
        except (RuntimeError, AttributeError):
            logger.debug("Theme toggle off-session", exc_info=True)
        # No local state: toggle_theme updates the page itself, and the
        # Switch reads _is_dark() on every render, so the repaint follows.

    def _on_country_select(name: str):
        from flet import context

        async def _do():
            try:
                await db_manager.set_setting("user_country", name)
            except Exception:
                logger.exception("Country save failed")
                notify_warning("Could not save country — try again.")
                return
            core_state.user_country = name
            notify(LBL_COUNTRY_UPDATED.format(country=name))

        try:
            context.page.run_task(_do)
        except (RuntimeError, AttributeError):
            logger.debug("Country save off-session", exc_info=True)

    async def _clear_history():
        set_is_clearing(True)
        try:
            await db_manager.clear_history()
            core_state.history.clear()
            notify(LBL_HISTORY_CLEARED)
        except Exception:
            logger.exception("Clear history failed")
            notify_warning(ERR_CLEAR_HISTORY_FAILED)
        finally:
            set_is_clearing(False)

    async def _reset_custom():
        set_is_resetting(True)
        try:
            await db_manager.clear_custom_content()
            notify(LBL_LIBRARY_RESET)
            await controller.refresh_channels()
        except Exception:
            logger.exception("Reset library failed")
            notify_warning(ERR_RESET_LIBRARY_FAILED)
        finally:
            set_is_resetting(False)

    def _open_terminal(e):
        from flet import context

        context.page.show_dialog(_build_logs_dialog(context.page))

    def _run_guarded(coro_fn):
        """Schedule a settings coroutine on the page loop with a toast on scheduling failure."""
        from flet import context

        try:
            context.page.run_task(coro_fn)
        except (RuntimeError, AttributeError):
            logger.debug("Settings task off-session", exc_info=True)
            notify_warning("Could not start that action — try again.")

    def _open_version_row(e=None):
        # The controller default is a silent no-op (off-shell render):
        # say so instead of looking dead.
        opener = getattr(controller, "open_version_dialog", None)
        if not callable(opener):
            notify_warning("Version details are unavailable right now.")
            return
        try:
            opener()
        except Exception:
            logger.debug("Version dialog open failed", exc_info=True)
            notify_warning("Could not open version details.")

    def _show_terms(e=None):
        from flet import context

        context.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(LBL_USAGE_AGREEMENT_TITLE, weight=ft.FontWeight.BOLD),
                content=ft.Container(
                    content=ft.Text(TERMS_TEXT, size=12, selectable=True),
                    width=420,
                ),
                actions=[
                    ft.TextButton(
                        LBL_CLOSE, on_click=lambda e: context.page.pop_dialog()
                    )
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    # -- build sections --

    # 1. Appearance
    appearance = _section_card(
        "Appearance",
        ft.Icons.PALETTE,
        [
            _setting_row(
                leading=ft.Icon(ft.Icons.DARK_MODE, size=18, color=AppColors.PRIMARY),
                title=LBL_DARK_MODE,
                subtitle=LBL_DARK_MODE_DESC,
                trailing=ft.Switch(value=_is_dark(), on_change=_toggle_theme),
            ),
        ],
    )

    # 2. Localization — same derived list as the Home country pill, so the
    # picker can never offer a folder the grid does not have (a playlist
    # swap used to leave this list stale while the pill changed).
    country_names = extract_countries(
        [c for c in state.channels if not c.get("is_custom", False)]
    )
    if not country_names:
        # Before the first channel load: provider reads its tier cache.
        country_names = [
            c.get("name", "") for c in channel_provider.get_countries() if c.get("name")
        ]
    if "Other" not in country_names:
        country_names.append("Other")
    current = state.user_country
    default_country = (
        current
        if current in country_names
        else (country_names[0] if country_names else None)
    )

    def _country_rows(query: str) -> list[Control]:
        q = query.strip().casefold()
        names = [c for c in country_names if not q or q in c.casefold()]
        return [
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE
                            if c == default_country
                            else ft.Icons.RADIO_BUTTON_UNCHECKED,
                            size=16,
                            color=AppColors.PRIMARY
                            if c == default_country
                            else AppColors.grey_dim(),
                        ),
                        ft.Text(c, size=13),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.all(8),
                border_radius=8,
                ink=True,
                on_click=lambda e, c=c: _pick_country(c),
            )
            for c in names
        ]

    def _pick_country(name: str):
        _on_country_select(name)
        _close_country_dialog()

    def _open_country_dialog(e):
        # Built at open time, filtered imperatively: component state can't
        # reach the shown instance (a re-render builds a NEW dialog while
        # the page shows the old one), so the search filters the live
        # column in place instead.
        from flet import context

        rows_col = ft.Column(
            controls=_country_rows(""),
            spacing=2,
            scroll=ft.ScrollMode.AUTO,
            height=320,
        )

        def _on_search(ev):
            rows_col.controls = _country_rows(ev.control.value or "")
            try:
                rows_col.update()
            except Exception:
                logger.debug("Country search update failed", exc_info=True)

        dlg = ft.AlertDialog(
            title=ft.Text("Select Country", size=16, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.TextField(
                            hint_text="Search 177 countries...",
                            on_change=_on_search,
                            autofocus=True,
                        ),
                        rows_col,
                    ],
                    spacing=8,
                    tight=True,
                ),
                width=380,
                height=420,
            ),
            actions_alignment=ft.MainAxisAlignment.END,
        )
        context.page.show_dialog(dlg)

    def _close_country_dialog():
        from flet import context

        context.page.pop_dialog()

    localization = _section_card(
        "Localization",
        ft.Icons.PUBLIC,
        [
            _setting_row(
                leading=ft.Icon(ft.Icons.PUBLIC, color=AppColors.PRIMARY),
                title=LBL_DEFAULT_REGION,
                subtitle=LBL_FILTER_BY_COUNTRY,
                trailing=ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text(default_country or "Select", size=13),
                            ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=16),
                        ],
                        spacing=4,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    width=150,
                    padding=ft.Padding(8, 6, 8, 6),
                    border=ft.Border.all(
                        1, ft.Colors.with_opacity(0.3, ft.Colors.OUTLINE_VARIANT)
                    ),
                    border_radius=8,
                    ink=True,
                    on_click=_open_country_dialog,
                ),
            ),
        ],
    )

    # 3. Data Management
    data_mgmt = _section_card(
        "Data Management",
        ft.Icons.STORAGE,
        [
            _setting_row(
                leading=ft.Icon(ft.Icons.HISTORY, size=18, color=AppColors.PRIMARY),
                title=LBL_CLEAR_HISTORY,
                subtitle=LBL_CLEAR_HISTORY_DESC,
                trailing=ft.OutlinedButton(
                    content=ft.Text(
                        LBL_CLEARING if is_clearing else LBL_CLEAR_HISTORY, size=12
                    ),
                    icon=ft.Icons.DELETE_OUTLINED,
                    disabled=is_clearing,
                    on_click=lambda e: _run_guarded(_clear_history),
                ),
            ),
            _setting_row(
                leading=ft.Icon(ft.Icons.RESTART_ALT, size=18, color=AppColors.PRIMARY),
                title=LBL_RESET_LIBRARY,
                subtitle=LBL_RESET_LIBRARY_DESC,
                trailing=ft.OutlinedButton(
                    content=ft.Text(
                        LBL_RESETTING if is_resetting else LBL_RESET_LIBRARY, size=12
                    ),
                    icon=ft.Icons.RESTART_ALT,
                    disabled=is_resetting,
                    on_click=lambda e: _run_guarded(_reset_custom),
                ),
            ),
        ],
    )

    # 4. Activity Terminal
    logs_count = len(in_memory_log_handler.get_logs())
    terminal = _section_card(
        "Development",
        ft.Icons.TERMINAL,
        [
            _setting_row(
                leading=ft.Icon(ft.Icons.TERMINAL, size=18, color=AppColors.PRIMARY),
                title=LBL_ACTIVITY_TERMINAL,
                subtitle=f"{logs_count} entries in memory",
                trailing=ft.OutlinedButton(
                    content=ft.Text(LBL_OPEN_TERMINAL, size=12),
                    icon=ft.Icons.TERMINAL,
                    on_click=_open_terminal,
                ),
            ),
        ],
    )

    # 5. About
    # page_obj is assigned further down; this block resolves the page from
    # the context directly so construction order cannot bite.
    about_page = ft.context.page

    def _launch_url(url: str):
        from utils.notifications import notify_warning as _warn

        if not isinstance(url, str) or not url.strip():
            logger.debug("Refused to launch empty URL")
            _warn("Could not open that link on this device.")
            return

        async def _run():
            try:
                await ft.UrlLauncher().launch_url(url)
            except Exception:
                logger.debug("About URL launch failed", exc_info=True)
                _warn("Could not open that link on this device.")

        try:
            about_page.run_task(_run)
        except (RuntimeError, AttributeError):
            logger.debug("About URL launch off-session", exc_info=True)

    def _on_contact(e=None):
        _launch_url(f"mailto:{CONTACT_EMAIL}")

    def _on_rate(e=None):
        _launch_url(_rate_url(about_page))

    def _on_more_apps(e=None):
        _launch_url(_more_apps_url(about_page))

    about = _section_card(
        "About",
        ft.Icons.INFO,
        [
            _setting_row(
                leading=ft.Icon(
                    ft.Icons.MAIL_OUTLINE, size=18, color=AppColors.PRIMARY
                ),
                title="Contact developer",
                subtitle=CONTACT_EMAIL,
                trailing=ft.Icon(
                    ft.Icons.OPEN_IN_NEW_ROUNDED,
                    size=15,
                    color=AppColors.grey_dim(),
                ),
                on_click=_on_contact,
            ),
            _setting_row(
                leading=ft.Icon(
                    ft.Icons.STAR_ROUNDED, size=18, color=AppColors.PRIMARY
                ),
                title="Rate 5 stars",
                subtitle=_rate_subtitle(about_page),
                trailing=ft.Icon(
                    ft.Icons.OPEN_IN_NEW_ROUNDED,
                    size=15,
                    color=AppColors.grey_dim(),
                ),
                on_click=_on_rate,
            ),
            _setting_row(
                leading=ft.Icon(
                    ft.Icons.APPS_ROUNDED, size=18, color=AppColors.PRIMARY
                ),
                title="More apps from Kiri",
                subtitle=_more_apps_subtitle(about_page),
                trailing=ft.Icon(
                    ft.Icons.OPEN_IN_NEW_ROUNDED,
                    size=15,
                    color=AppColors.grey_dim(),
                ),
                on_click=_on_more_apps,
            ),
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Image(
                            src="/icon.svg",
                            width=56,
                            height=56,
                            fit=ft.BoxFit.CONTAIN,
                            # No color tint: the SVG is blue line-art; SRC_IN
                            # tinting would flatten it to a silhouette.
                            error_content=ft.Icon(ft.Icons.LIVE_TV_ROUNDED, size=40),
                            semantics_label="KTV Player",
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(APP_NAME, size=16, weight=ft.FontWeight.BOLD),
                                ft.Text(
                                    "Update available · tap to view"
                                    if core_state.update_available
                                    else f"Version {APP_VERSION} · Flet {ft.__version__}",
                                    size=12,
                                    color=(
                                        AppColors.PRIMARY
                                        if core_state.update_available
                                        else AppColors.grey_dim()
                                    ),
                                ),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=14,
                ),
                padding=ft.Padding(4, 8, 4, 8),
                ink=True,
                border_radius=10,
                on_click=_open_version_row,
            ),
            ft.Divider(height=1, color=AppColors.get_border_color(ft.context.page)),
            ft.TextButton(
                LBL_USAGE_AGREEMENT_BUTTON,
                icon=ft.Icons.GAVEL_ROUNDED,
                on_click=_show_terms,
            ),
        ],
    )

    from components.banner_ad import build_banner_ad

    page_obj = ft.context.page

    def _is_empty_banner(control: Control) -> bool:
        """build_banner_ad returns a 0x0 placeholder when ads don't apply
        (desktop, TV, premium, no unit id) — filter those so they don't
        inject dead padding into the list."""
        try:
            return (
                isinstance(control, ft.Container)
                and control.content is None
                and (control.width or 0) == 0
                and (control.height or 0) == 0
            )
        except Exception:
            return False

    def _live_banner() -> Control | None:
        try:
            banner = build_banner_ad(page_obj)
        except Exception:
            logger.debug("Settings banner build failed", exc_info=True)
            return None
        return None if _is_empty_banner(banner) else banner

    banner_1 = _live_banner()
    banner_2 = _live_banner()

    # -- 6. Premium (remove-ads) -------------------------------------------
    premium_service = getattr(page_obj, "premium", None)
    # The license verdict can change while this screen is open (purchase,
    # restore, expiry), so the card follows the service instead of a
    # snapshot taken at build time.
    is_premium, set_is_premium = ft.use_state(core_state.is_premium)

    def _sync_premium():
        set_is_premium(core_state.is_premium)

    def _watch_premium():
        if premium_service is None:
            return
        try:
            premium_service.add_listener(_sync_premium)
        except Exception:
            logger.debug("Premium listener attach failed", exc_info=True)
            return
        _sync_premium()

    def _unwatch_premium():
        if premium_service is None:
            return
        try:
            premium_service.remove_listener(_sync_premium)
        except Exception:
            logger.debug("Premium listener detach failed", exc_info=True)

    ft.use_effect(_watch_premium, [], _unwatch_premium)

    # -- Kiri License (the backend for installs Play cannot bill) -----------

    products, set_products = ft.use_state([])
    recovery_id, set_recovery_id = ft.use_state("")
    license_busy, set_license_busy = ft.use_state(False)
    license_error, set_license_error = ft.use_state("")

    async def _load_license():
        if not premium_service or not premium_service.available:
            return
        set_license_error("")
        try:
            set_products(await premium_service.kiri_catalog())
        except Exception:
            logger.debug("License catalog load failed", exc_info=True)
            set_license_error("Could not reach the license service.")
            return
        try:
            license_svc = premium_service.license
            set_recovery_id(await license_svc.recovery_id() if license_svc else "")
        except Exception:
            logger.debug("Recovery ID load failed", exc_info=True)

    ft.on_mounted(_load_license)

    def _ask_email(product_label: str):
        """Email is required by the payment provider and is the only field
        the user has to type."""
        field = ft.TextField(
            label="Email for your receipt",
            hint_text="you@example.com",
            keyboard_type=ft.KeyboardType.EMAIL,
            width=320,
        )
        dialog = ft.AlertDialog(
            title=ft.Text(f"Unlock KTV Premium — {product_label}", size=15),
            content=field,
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: page_obj.pop_dialog()),
                ft.FilledButton(
                    "Continue",
                    on_click=lambda e: page_obj.run_task(
                        _start_kiri_checkout, product_label, field
                    ),
                ),
            ],
        )
        page_obj.show_dialog(dialog)

    async def _start_kiri_checkout(product_id: str, field):
        email = (field.value or "").strip()
        if not email or "@" not in email:
            notify_warning("Enter a valid email address")
            return
        page_obj.pop_dialog()
        set_license_busy(True)
        try:
            checkout = await premium_service.kiri_checkout(product_id, email)
            set_recovery_id(checkout.recovery_id)
            # Flutterwave hosts the payment; the app never sees card data.
            # kiri_checkout already started the watcher — no manual step.
            checkout_url = checkout.checkout_url or ""
            if not checkout_url.startswith("https://"):
                logger.debug("Refused non-https checkout URL")
                notify_warning("Could not start the payment — try again.")
                return
            await ft.UrlLauncher().launch_url(checkout_url)
            notify("Complete the payment. This screen unlocks itself when it lands")
        except Exception as ex:
            logger.debug("Kiri checkout failed", exc_info=True)
            notify_warning(str(ex) or "Could not start the payment")
        finally:
            set_license_busy(False)

    def _ask_recovery_id(e=None):
        field = ft.TextField(
            label="Recovery ID",
            hint_text=recovery_id or "KIRI-L-...",
            width=340,
        )
        page_obj.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Restore your license", size=15),
                content=ft.Column(
                    [
                        field,
                        ft.Text(
                            "Your recovery ID is in your receipt email. "
                            "It is also stored on this device.",
                            size=11,
                        ),
                    ],
                    tight=True,
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda e: page_obj.pop_dialog()),
                    ft.FilledButton(
                        "Restore",
                        on_click=lambda e: page_obj.run_task(_redeem_kiri, field),
                    ),
                ],
            )
        )

    async def _redeem_kiri(field):
        code = (field.value or "").strip() or recovery_id
        if not code:
            notify_warning("Enter your recovery ID first.")
            return
        page_obj.pop_dialog()
        set_license_busy(True)
        try:
            status = await premium_service.kiri_restore(code)
            set_recovery_id(status.recovery_id)
            _sync_premium()
            notify(
                premium_unlocked_message(page_obj)
                if core_state.is_premium
                else f"License status: {status.status}"
            )
        except Exception as ex:
            logger.debug("License restore failed", exc_info=True)
            notify_warning(str(ex) or "Could not restore that license")
        finally:
            set_license_busy(False)

    async def _copy_recovery_id(e=None):
        if not recovery_id:
            return
        try:
            await ft.Clipboard().set(recovery_id)
            notify("Recovery ID copied")
        except Exception:
            notify_warning("Copy failed — clipboard unavailable on this device")

    def _kiri_product_row(product):
        return _setting_row(
            leading=ft.Icon(
                ft.Icons.LOCK_OPEN_ROUNDED
                if product.id == "lifetime"
                else ft.Icons.AUTORENEW,
                size=18,
                color=AppColors.PRIMARY,
            ),
            title=product.id.capitalize(),
            subtitle=product.description or product.price_label,
            trailing=ft.FilledButton(
                product.price_label,
                on_click=lambda e, p=product: _ask_email(p.id),
                disabled=license_busy,
            ),
        )

    _kiri_rows: list = []
    # Built only where the card is shown: assembling these on the play
    # channel still executed the raise, even though the card was discarded.
    if CHANNEL != "play" and not is_premium:
        _kiri_rows = [
            *[_kiri_product_row(p) for p in products],
            *(
                [
                    _setting_row(
                        leading=ft.Icon(ft.Icons.KEY, size=18, color=AppColors.PRIMARY),
                        title="Your recovery ID",
                        subtitle=(recovery_id or "Created when you start a payment"),
                        trailing=ft.OutlinedButton(
                            "Copy",
                            on_click=_copy_recovery_id,
                            disabled=not recovery_id,
                        ),
                    )
                ]
                if recovery_id
                else []
            ),
        ]
        if not products:
            if license_error:
                _kiri_rows.append(
                    _setting_row(
                        leading=ft.Icon(
                            ft.Icons.CLOUD_OFF, size=18, color=AppColors.grey_dim()
                        ),
                        title="Unlock options unavailable",
                        subtitle=f"{license_error} Tap Retry to try again.",
                        trailing=ft.OutlinedButton(
                            "Retry",
                            icon=ft.Icons.REFRESH,
                            on_click=lambda e: _run_guarded(_load_license),
                        ),
                    )
                )
            else:
                _kiri_rows.append(
                    _setting_row(
                        leading=ft.Icon(
                            ft.Icons.CLOUD_OFF, size=18, color=AppColors.grey_dim()
                        ),
                        title="Unlock options unavailable",
                        subtitle="Could not reach the license service — check your connection",
                    )
                )

    _license_svc = getattr(premium_service, "license", None)
    premium = _section_card(
        "Premium",
        ft.Icons.WORKSPACE_PREMIUM,
        [
            _setting_row(
                leading=ft.Icon(
                    ft.Icons.VERIFIED_ROUNDED,
                    size=18,
                    color=AppColors.PRIMARY if is_premium else AppColors.grey_dim(),
                ),
                title="KTV Premium",
                subtitle=_premium_subtitle(
                    is_premium,
                    getattr(_license_svc, "claims", None),
                    has_ads=page_has_ads(page_obj),
                ),
                trailing=ft.Icon(
                    ft.Icons.CHECK_CIRCLE if is_premium else ft.Icons.CIRCLE_OUTLINED,
                    size=20,
                    color=(AppColors.PRIMARY if is_premium else AppColors.grey_dim()),
                ),
            ),
            # Kiri rows are absent from the Play build entirely — that
            # guard sits in the list assembly below (CHANNEL check).
            *([] if is_premium else _kiri_rows),
            _setting_row(
                leading=ft.Icon(ft.Icons.RESTORE, size=18, color=AppColors.PRIMARY),
                title="Restore purchases",
                subtitle="Re-check ownership (new device / reinstall)",
                trailing=ft.OutlinedButton("Restore", on_click=_ask_recovery_id),
            ),
        ],
    )

    controls = [appearance]
    if banner_1:
        controls.append(banner_1)
    controls.extend([localization, data_mgmt, terminal])
    if banner_2:
        controls.append(banner_2)
    # The play channel (the Play Store AAB) has no premium at all: the
    # console behind it has no Google Payments merchant profile, and an
    # external-checkout button inside a Play-distributed build is a policy
    # violation. Not even a disabled card — nothing to declare, nothing to
    # reach, ads stay on. See core/channel.py.
    if CHANNEL != "play":
        controls.append(premium)
    controls.append(about)

    return ft.ListView(
        controls=controls,
        expand=True,
        spacing=12,
        padding=ft.Padding(16, 16, 16, 24),
    )
