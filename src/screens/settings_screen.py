"""SettingsScreen — modern Material 3 grouped settings."""

import asyncio
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
from core.logger_handler import MemoryLogHandler
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


def _premium_subtitle(is_premium, claims, has_ads: bool = True) -> str:
    """Premium row subtitle: honest benefits for this platform.

    The channel pack is the benefit everywhere; "no ads" is claimed only
    where ads are actually requested (phones). paid-through comes from the
    signed token (exp-guarded), so the dates stay truthful offline, and
    its absence marks a lifetime license.
    """
    pack = "the premium channel pack: the top channels in every field and more country support"
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
    {"key": "custom_content", "title": "Development", "icon": ft.Icons.TERMINAL},
    {"key": "premium", "title": "Premium", "icon": ft.Icons.WORKSPACE_PREMIUM},
    {"key": "about", "title": "About", "icon": ft.Icons.INFO},
]


# ---------------------------------------------------------------------------
# Log terminal dialog
# ---------------------------------------------------------------------------


def _build_logs_dialog(page: ft.Page) -> ft.AlertDialog:
    from services.device_info import get_device_summary

    logs = MemoryLogHandler.get_logs()
    logs_str = "\n".join(logs) if logs else LBL_NO_ACTIVITY_LOG
    # Device header travels WITH the logs so the existing "Copy to clipboard"
    # produces a complete TV diagnostics dump (no way to pipe TV adb logs).
    full_text = f"{get_device_summary()}\n\n--- logs ---\n{logs_str}"

    log_text = ft.Text(
        value=full_text,
        font_family="Courier New",
        size=12,
        color=AppColors.TERMINAL_TEXT,
        selectable=True,
    )

    async def _copy(e=None):
        try:
            await ft.Clipboard().set(log_text.value)
            notify(LBL_LOG_COPIED)
        except Exception:
            # Android TV has no clipboard service in some images, and a
            # silent failure looks like the button is broken.
            notify_warning("Copy failed — clipboard unavailable on this device")

    def _clear(e=None):
        MemoryLogHandler.clear_logs()
        log_text.value = LBL_LOG_CLEARED
        page.update()

    return ft.AlertDialog(
        title=ft.Text(LBL_LIVE_ACTIVITY_TERMINAL, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(LBL_TERMINAL_DESC, size=12, color=AppColors.grey_dim()),
                    ft.Container(
                        content=ft.Column(
                            controls=[log_text],
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        bgcolor=AppColors.TERMINAL_BG,
                        border=ft.Border.all(
                            1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)
                        ),
                        border_radius=8,
                        padding=12,
                        expand=True,
                    ),
                ],
                spacing=8,
            ),
            width=480,
            height=400,
        ),
        actions=[
            ft.TextButton(
                LBL_COPY_TO_CLIPBOARD,
                icon=ft.Icons.COPY,
                on_click=lambda e: asyncio.create_task(_copy()),
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
    _theme_mode, set_theme_mode = ft.use_state(
        lambda: AppColors._is_dark(ft.context.page)
    )

    # -- handlers --

    def _is_dark() -> bool:
        from flet import context

        return AppColors._is_dark(context.page)

    def _toggle_theme(e):
        from flet import context

        _toggle_theme_util(context.page)
        set_theme_mode(AppColors._is_dark(context.page))

    def _on_country_select(name: str):
        async def _do():
            await db_manager.set_setting("user_country", name)
            core_state.user_country = name
            notify(LBL_COUNTRY_UPDATED.format(country=name))

        asyncio.create_task(_do())

    async def _clear_history():
        set_is_clearing(True)
        try:
            await db_manager.clear_history()
            core_state.history.clear()
            notify(LBL_HISTORY_CLEARED)
        except Exception:
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
            notify_warning(ERR_RESET_LIBRARY_FAILED)
        finally:
            set_is_resetting(False)

    def _open_terminal(e):
        from flet import context

        context.page.show_dialog(_build_logs_dialog(context.page))

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
                trailing=ft.Switch(
                    value=_is_dark(), on_change=_toggle_theme, autofocus=True
                ),
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

    country_dialog = ft.AlertDialog(
        title=ft.Text("Select Country", size=16, weight=ft.FontWeight.BOLD),
        content=ft.Column(
            controls=[
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
                    padding=ft.Padding(8, 8, 8, 8),
                    border_radius=8,
                    ink=True,
                    on_click=lambda e, c=c: (
                        _on_country_select(c),
                        _close_country_dialog(),
                    ),
                )
                for c in country_names
            ],
            spacing=2,
            scroll=ft.ScrollMode.AUTO,
        ),
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def _open_country_dialog(e):
        from flet import context

        context.page.show_dialog(country_dialog)

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
                    on_click=lambda e: asyncio.create_task(_clear_history()),
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
                    on_click=lambda e: asyncio.create_task(_reset_custom()),
                ),
            ),
        ],
    )

    # 4. Activity Terminal
    logs_count = len(MemoryLogHandler.get_logs())
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
        async def _run():
            await ft.UrlLauncher().launch_url(url)

        about_page.run_task(_run)

    def _on_contact(e=None):
        _launch_url(f"mailto:{CONTACT_EMAIL}")

    def _on_rate(e=None):
        _launch_url(_rate_url(about_page))

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
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Image(
                            src="/icon.svg",
                            width=56,
                            height=56,
                            fit=ft.BoxFit.CONTAIN,
                            color=ft.Colors.ON_SURFACE,
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
                on_click=lambda e: controller.open_version_dialog(),
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
    banner_1 = build_banner_ad(page_obj)
    banner_2 = build_banner_ad(page_obj)

    # -- 6. Premium (remove-ads) -------------------------------------------
    premium_service = getattr(page_obj, "premium", None)
    # The license verdict can change while this screen is open (purchase,
    # restore, expiry), so the card follows the service instead of a
    # snapshot taken at build time.
    is_premium, set_is_premium = ft.use_state(core_state.is_premium)

    def _sync_premium():
        set_is_premium(core_state.is_premium)

    def _watch_premium(e=None):
        if premium_service is None:
            return None
        premium_service.add_listener(_sync_premium)
        _sync_premium()

        def _cleanup():
            premium_service.remove_listener(_sync_premium)

        return _cleanup

    ft.on_mounted(_watch_premium)

    # -- Kiri License (the backend for installs Play cannot bill) -----------

    products, set_products = ft.use_state([])
    recovery_id, set_recovery_id = ft.use_state("")
    license_busy, set_license_busy = ft.use_state(False)

    async def _load_license(e=None):
        if not premium_service or not premium_service.available:
            return
        set_products(await premium_service.kiri_catalog())
        set_recovery_id(await premium_service.license.recovery_id())

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
            await ft.UrlLauncher().launch_url(checkout.checkout_url)
            notify("Complete the payment. This screen unlocks itself when it lands")
        except Exception as ex:
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
            _kiri_rows.append(
                _setting_row(
                    leading=ft.Icon(
                        ft.Icons.CLOUD_OFF, size=18, color=AppColors.grey_dim()
                    ),
                    title="Unlock options unavailable",
                    subtitle="Could not reach the license service — check your connection",
                )
            )

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
                    getattr(premium_service.license, "claims", None)
                    if premium_service
                    else None,
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
