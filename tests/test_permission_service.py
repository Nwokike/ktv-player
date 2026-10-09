"""Phase 6 — permission tri-state contract tests (mocked handler)."""

from unittest import mock

import pytest

from services import permission_service


def _page(platform="android"):
    import flet as ft

    page = mock.MagicMock()
    page.platform = {
        "android": ft.PagePlatform.ANDROID,
        "tv": ft.PagePlatform.ANDROID_TV,
        "ios": ft.PagePlatform.IOS,
        "windows": ft.PagePlatform.WINDOWS,
    }[platform]
    page.services = []
    return page


def _handler(status_map, fail_status=()):
    from flet_permission_handler import PermissionHandler, PermissionStatus

    ph = mock.MagicMock(spec=PermissionHandler)
    ph.get_status = mock.AsyncMock(
        side_effect=lambda p: status_map.get(p, PermissionStatus.DENIED)
    )

    async def _request(p):
        if p in fail_status:
            return None
        return status_map.get("request:" + str(p), PermissionStatus.DENIED)

    ph.request = mock.AsyncMock(side_effect=_request)
    ph.open_app_settings = mock.AsyncMock(return_value=True)
    return ph


@pytest.mark.asyncio
async def test_granted_status_never_prompts():
    from flet_permission_handler import Permission, PermissionStatus

    page = _page()
    ph = _handler({Permission.VIDEOS: PermissionStatus.GRANTED})
    page.services.append(ph)
    with mock.patch("services.android_bridge.sdk_int", return_value=34):
        result = await permission_service.request_storage_permission(page)
    assert result == "granted"
    ph.request.assert_not_called()


@pytest.mark.asyncio
async def test_limited_counts_as_granted():
    from flet_permission_handler import Permission, PermissionStatus

    page = _page()
    ph = _handler({Permission.VIDEOS: PermissionStatus.LIMITED})
    page.services.append(ph)
    with mock.patch("services.android_bridge.sdk_int", return_value=34):
        result = await permission_service.request_storage_permission(page)
    assert result == "granted"


@pytest.mark.asyncio
async def test_permanent_denial_returns_permanent():
    from flet_permission_handler import Permission, PermissionStatus

    page = _page()
    ph = _handler({Permission.VIDEOS: PermissionStatus.PERMANENTLY_DENIED})
    page.services.append(ph)
    with mock.patch("services.android_bridge.sdk_int", return_value=34):
        result = await permission_service.request_storage_permission(page)
    assert result == "permanent"
    ph.request.assert_not_called()


@pytest.mark.asyncio
async def test_denied_then_request_grants():
    from flet_permission_handler import Permission, PermissionStatus

    page = _page()
    ph = _handler(
        {
            Permission.VIDEOS: PermissionStatus.DENIED,
            "request:" + str(Permission.VIDEOS): PermissionStatus.GRANTED,
        }
    )
    page.services.append(ph)
    with mock.patch("services.android_bridge.sdk_int", return_value=34):
        result = await permission_service.request_storage_permission(page)
    assert result == "granted"
    ph.request.assert_awaited_once()


@pytest.mark.asyncio
async def test_off_mobile_returns_granted_without_handler():
    page = _page("windows")
    assert await permission_service.request_storage_permission(page) == "granted"


@pytest.mark.asyncio
async def test_open_app_settings_delegates():
    page = _page()
    ph = _handler({})
    page.services.append(ph)
    assert await permission_service.open_app_settings(page) is True
