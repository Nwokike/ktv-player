"""Version dialog — always available from the Settings version row.

Two modes:
- Up to date: current version's bundled changelog (works offline) plus a
  Check for Updates button that re-checks live.
- Update available (server build newer): server release notes as Markdown
  with launch buttons — Android gets Play Store + Direct APK (when a
  playstore_url is published), every other platform gets the GitHub
  release only. Android TV is GitHub-only by product intent: there is no
  Play listing for the TV shell, and sideloading via the APK is the
  supported path there.

Delivery is deliberately browser-based: URLs launch externally; there is
no in-app APK download or install.

Dialog instance: ``show_version_dialog`` tracks the open instance and
re-shows it instead of stacking duplicates. The Check button morphs the
open dialog to a ProgressRing state in place — the dialog never closes
during a re-check, so there is no silent window.
"""

import logging
from urllib.parse import urlparse

import flet as ft

from core.changelog import notes_for
from core.constants import (
    APP_VERSION,
    ERR_OPEN_LINK,
    GITHUB_RELEASES_URL,
)
from core.state import state
from core.theme import AppColors

logger = logging.getLogger(__name__)

_ALLOWED_LINK_SCHEMES = ("http", "https", "mailto", "market")

# The currently open version dialog (if any). Module-level so a second
# open while one is showing reuses instead of stacking.
_open_dialog: ft.AlertDialog | None = None


def is_launchable_url(url: object) -> bool:
    """Non-empty http/https/mailto/market URL — checked before any launch."""
    if not isinstance(url, str) or not url.strip():
        return False
    try:
        scheme = urlparse(url.strip()).scheme.lower()
    except ValueError:
        return False
    return scheme in _ALLOWED_LINK_SCHEMES


def _launch(page: ft.Page, url: str):
    """Imperative launch for contexts without a gesture (Markdown links).

    Buttons use ``ft.OpenUrl`` actions instead (in-gesture, never
    popup-blocked). This path stays for ``Markdown.on_tap_link``, where no
    action-capable control exists to carry the URL.
    """
    from utils.notifications import notify_error

    async def _run():
        try:
            await ft.UrlLauncher().launch_url(url)
        except Exception as ex:
            logger.debug("Update URL launch failed: %s", ex)
            notify_error(ERR_OPEN_LINK)

    if not is_launchable_url(url):
        logger.debug("Refused to launch non-web URL: %r", url)
        notify_error(ERR_OPEN_LINK)
        return
    page.run_task(_run)


def _open_url_action(url: str) -> ft.OpenUrl:
    """In-gesture open action for buttons (never popup-blocked on web)."""
    return ft.OpenUrl(url, target=ft.UrlTarget.BLANK)


def _dismiss(page: ft.Page) -> None:
    """Pop the tracked dialog (or whatever is on top) and clear tracking."""
    global _open_dialog
    try:
        page.pop_dialog()
    except Exception:
        logger.debug("Version dialog pop failed", exc_info=True)
    _open_dialog = None


async def check_from_dialog(page: ft.Page):
    """Live re-check from the up-to-date dialog; morphs it to update mode
    if the server now reports a newer build.

    The dialog stays open behind a ProgressRing while the check runs —
    the old close-check-reopen sequence left a silent window where a
    failure looked like the button did nothing.
    """
    from services.update_service import UpdateService
    from utils.notifications import notify

    dlg = _open_dialog
    if dlg is None:
        result = await UpdateService().check_for_update()
        if result:
            state.update_available = True
            state.update_data = result
            show_version_dialog(page, result)
        else:
            state.update_available = False
            state.update_data = None
            notify(f"✓ {APP_VERSION} is up to date")
        return

    body = dlg.content
    checking = ft.Column(
        controls=[
            ft.ProgressRing(width=28, height=28),
            ft.Text("Checking for updates...", size=13),
        ],
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    )
    dlg.content = checking
    for action in dlg.actions:
        action.disabled = True
    try:
        dlg.update()
    except Exception:
        logger.debug("Version dialog checking-state update failed", exc_info=True)

    try:
        result = await UpdateService().check_for_update()
    except Exception as ex:
        logger.debug("Version dialog re-check failed: %s", ex)
        result = None

    if result:
        state.update_available = True
        state.update_data = result
        _dismiss(page)
        show_version_dialog(page, result)
    else:
        # A None re-check clears a stale update flag: the cached "Update!"
        # pill must not survive a check that just proved us current.
        had_update = bool(state.update_available)
        state.update_available = False
        state.update_data = None
        if had_update:
            _dismiss(page)
            show_version_dialog(page)
            notify(f"✓ {APP_VERSION} is up to date")
            return
        dlg.content = body
        for action in dlg.actions:
            action.disabled = False
        try:
            dlg.update()
        except Exception:
            logger.debug("Version dialog restore update failed", exc_info=True)
        notify(f"✓ {APP_VERSION} is up to date")


def _info_dict(data) -> dict:
    """Normalize UpdateInfo-or-dict to a plain dict at the dialog boundary.

    Storage (state.update_data) holds the typed UpdateInfo; everything below
    works on dicts so Markdown/buttons code stays untouched.
    """
    if data is None:
        return {}
    if hasattr(data, "to_dict"):
        try:
            return data.to_dict()
        except Exception:
            return {}
    return data if isinstance(data, dict) else {}


def _build_update_buttons(page: ft.Page, data: dict) -> list[ft.Control]:
    """Platform rule: Android → Play Store (when published) + Direct APK;
    Android TV → GitHub APK only (no Play TV listing; sideload supported);
    every other platform → GitHub release only."""
    buttons: list[ft.Control] = []
    is_android = page.platform == ft.PagePlatform.ANDROID
    github_url = data.get("github_url") or GITHUB_RELEASES_URL

    if is_android and data.get("playstore_url"):
        buttons.append(
            ft.FilledButton(
                content=ft.Text("Google Play", font_family="Outfit"),
                icon=ft.Icons.SHOP_ROUNDED,
                action=_open_url_action(data["playstore_url"]),
                on_click=lambda e: _dismiss(page),
            )
        )
        buttons.append(
            ft.OutlinedButton(
                content=ft.Text("Direct APK (GitHub)", font_family="Outfit"),
                icon=ft.Icons.DOWNLOAD_ROUNDED,
                action=_open_url_action(github_url),
                on_click=lambda e: _dismiss(page),
            )
        )
    else:
        buttons.append(
            ft.FilledButton(
                content=ft.Text("Download from GitHub", font_family="Outfit"),
                icon=ft.Icons.DOWNLOAD_ROUNDED,
                action=_open_url_action(github_url),
                on_click=lambda e: _dismiss(page),
            )
        )
    if not data.get("mandatory"):
        buttons.append(
            ft.TextButton(
                content=ft.Text("Later", font_family="Outfit"),
                on_click=lambda e: _dismiss(page),
            )
        )
    return buttons


def _build_current_buttons(page: ft.Page) -> list[ft.Control]:
    return [
        ft.OutlinedButton(
            content=ft.Text("Check for Updates", font_family="Outfit"),
            icon=ft.Icons.SYNC_ROUNDED,
            on_click=lambda e: page.run_task(check_from_dialog, page),
        ),
        ft.TextButton(
            content=ft.Text("Close", font_family="Outfit"),
            on_click=lambda e: _dismiss(page),
        ),
    ]


def _dialog_width(page: ft.Page) -> float:
    """Markdown body width clamped to narrow windows (360 default)."""
    try:
        w = page.width or 0
    except (RuntimeError, AttributeError):
        w = 0
    if w and w < 420:
        return max(240.0, w - 80.0)
    return 360


def show_version_dialog(page: ft.Page, update_data=None):
    """Open the version dialog. Uses a fresh check result when given (the
    dialog's own Check button), else the observable state. Accepts
    UpdateInfo or dict; normalized once here.

    Reuses the tracked instance when one is already open. Mandatory
    updates set ``modal=True`` and re-show on dismiss: the update cannot
    be back-dismissed past.
    """
    global _open_dialog
    data = _info_dict(update_data if update_data is not None else state.update_data)
    is_update = bool(data)
    mandatory = bool(data.get("mandatory"))

    if is_update:
        title_text = data.get("title") or (
            f"Version {data.get('version', '')} Available!"
        )
        icon = (
            ft.Icons.CAMPAIGN_ROUNDED
            if data.get("type") == "announcement"
            else ft.Icons.ROCKET_LAUNCH_ROUNDED
        )
        icon_color = (
            AppColors.WARNING
            if data.get("type") == "announcement"
            else AppColors.PRIMARY
        )
        body = ft.Column(
            controls=[
                ft.Text(
                    f"Version {data.get('version', '')} is now available.",
                    size=13,
                ),
                ft.Text("What's New:", size=13, weight=ft.FontWeight.W_600),
                ft.Container(
                    content=ft.Markdown(
                        data.get("release_notes", ""),
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        on_tap_link=lambda e: _launch(page, e.data),
                    ),
                    width=_dialog_width(page),
                ),
            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            tight=True,
        )
        actions = _build_update_buttons(page, data)
    else:
        title_text = "You're up to date"
        icon = ft.Icons.VERIFIED_ROUNDED
        icon_color = AppColors.PRIMARY
        body = ft.Column(
            controls=[
                ft.Text(f"✓ Latest version · v{APP_VERSION}", size=13),
                ft.Text("What's New:", size=13, weight=ft.FontWeight.W_600),
                ft.Container(
                    content=ft.Markdown(
                        notes_for(APP_VERSION),
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        on_tap_link=lambda e: _launch(page, e.data),
                    ),
                    width=_dialog_width(page),
                ),
            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            tight=True,
        )
        actions = _build_current_buttons(page)

    if _open_dialog is not None:
        try:
            _open_dialog.title = ft.Row(
                controls=[
                    ft.Icon(icon, color=icon_color, size=24),
                    ft.Text(
                        title_text, weight=ft.FontWeight.BOLD, font_family="Outfit"
                    ),
                ],
                spacing=10,
            )
            _open_dialog.content = body
            _open_dialog.actions = actions
            _open_dialog.modal = mandatory
            _open_dialog.update()
        except Exception:
            logger.debug("Version dialog reuse failed; opening fresh", exc_info=True)
            _open_dialog = None
        else:
            return

    def _on_dismiss(e):
        global _open_dialog
        _open_dialog = None
        if mandatory:
            # A mandatory update cannot be dismissed past: re-show so the
            # system-back path lands back on the dialog.
            show_version_dialog(page, data if is_update else None)

    dlg = ft.AlertDialog(
        modal=mandatory,
        title=ft.Row(
            controls=[
                ft.Icon(icon, color=icon_color, size=24),
                ft.Text(title_text, weight=ft.FontWeight.BOLD, font_family="Outfit"),
            ],
            spacing=10,
        ),
        content=body,
        actions=actions,
        actions_alignment=ft.MainAxisAlignment.END,
        on_dismiss=_on_dismiss,
    )
    _open_dialog = dlg
    page.show_dialog(dlg)
