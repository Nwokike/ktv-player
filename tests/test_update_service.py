"""Tests for the update service: integer build-number comparison against
version.json, silent failure paths, and the bundled-changelog guard that
keeps the always-clickable version dialog KeyError-free."""

from types import SimpleNamespace
from unittest import mock

import pytest

from core.changelog import CHANGELOG, notes_for
from core.constants import APP_BUILD_NUMBER, APP_VERSION
from services.update_service import UpdateService


def _resp(status_code=200, json_data=None):
    resp = SimpleNamespace(status_code=status_code)
    if json_data is not None:
        resp.json = lambda: json_data
    return resp


def _client(resp=None, error=None):
    client = mock.MagicMock()
    client.__aenter__ = mock.AsyncMock(return_value=client)
    client.__aexit__ = mock.AsyncMock(return_value=False)
    if error is not None:
        client.get = mock.AsyncMock(side_effect=error)
    else:
        client.get = mock.AsyncMock(return_value=resp)
    return client


class TestCheckForUpdate:
    @pytest.mark.asyncio
    async def test_newer_build_returns_update(self):
        data = {
            "build_number": APP_BUILD_NUMBER + 1,
            "version": "2.2.0",
            "release_notes": "notes",
            "mandatory": False,
            "github_url": "https://example.com/releases",
        }
        svc = UpdateService()
        with mock.patch(
            "services.update_service.get_http_client",
            return_value=_client(_resp(json_data=data)),
        ):
            result = await svc.check_for_update()
        assert result is not None
        assert result.version == "2.2.0"
        assert result.build_number == APP_BUILD_NUMBER + 1
        assert result.github_url == "https://example.com/releases"
        assert result.playstore_url is None

    @pytest.mark.asyncio
    async def test_equal_build_returns_none(self):
        """Dormant manifest: build_number == current -> no update."""
        svc = UpdateService()
        with mock.patch(
            "services.update_service.get_http_client",
            return_value=_client(_resp(json_data={"build_number": APP_BUILD_NUMBER})),
        ):
            assert await svc.check_for_update() is None

    @pytest.mark.asyncio
    async def test_older_build_returns_none(self):
        svc = UpdateService()
        with mock.patch(
            "services.update_service.get_http_client",
            return_value=_client(_resp(json_data={"build_number": 1})),
        ):
            assert await svc.check_for_update() is None

    @pytest.mark.asyncio
    async def test_announcement_type_preserved(self):
        data = {
            "build_number": APP_BUILD_NUMBER + 1,
            "type": "announcement",
            "title": "News",
            "release_notes": "something",
        }
        svc = UpdateService()
        with mock.patch(
            "services.update_service.get_http_client",
            return_value=_client(_resp(json_data=data)),
        ):
            result = await svc.check_for_update()
        assert result.type == "announcement"
        assert result.title == "News"

    @pytest.mark.asyncio
    async def test_playstore_url_forwarded_when_published(self):
        data = {
            "build_number": APP_BUILD_NUMBER + 1,
            "playstore_url": "https://play.google.com/store/apps/details?id=ng.kiri.ktvplayer",
        }
        svc = UpdateService()
        with mock.patch(
            "services.update_service.get_http_client",
            return_value=_client(_resp(json_data=data)),
        ):
            result = await svc.check_for_update()
        assert result.playstore_url.startswith("https://play.google.com")

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self):
        svc = UpdateService()
        with mock.patch(
            "services.update_service.get_http_client",
            return_value=_client(_resp(status_code=404)),
        ):
            assert await svc.check_for_update() is None

    @pytest.mark.asyncio
    async def test_network_exception_returns_none(self):
        """Offline devices must never see an error from the check."""
        svc = UpdateService()
        with mock.patch(
            "services.update_service.get_http_client",
            return_value=_client(error=OSError("no network")),
        ):
            assert await svc.check_for_update() is None


class TestChangelogGuard:
    def test_changelog_has_entry_for_current_version(self):
        """The version dialog's up-to-date mode reads CHANGELOG[APP_VERSION]
        — a bump without a changelog line must fail here, not in the UI."""
        assert APP_VERSION in CHANGELOG
        assert len(notes_for(APP_VERSION)) > 0

    def test_notes_for_unknown_version_falls_back(self):
        assert notes_for("0.0.0") != ""


class TestPhase4UpdateNormalize:
    @pytest.mark.asyncio
    async def test_string_false_mandatory_is_not_mandatory(self):
        """bool("false") is True — string payloads must parse explicitly."""
        from unittest import mock

        from services.update_service import UpdateService

        data = {
            "build_number": APP_BUILD_NUMBER + 1,
            "version": "9.9.9",
            "mandatory": "false",
        }
        svc = UpdateService()
        with mock.patch(
            "services.update_service.get_http_client",
            return_value=_client(_resp(json_data=data)),
        ):
            result = await svc.check_for_update()
        assert result is not None
        assert result.mandatory is False

    @pytest.mark.asyncio
    async def test_same_build_announcement_delivers(self):
        """Announcements display even when the build is not newer."""
        from unittest import mock

        from services.update_service import UpdateService

        data = {
            "build_number": APP_BUILD_NUMBER,
            "type": "announcement",
            "title": "Heads up",
            "release_notes": "hello",
        }
        svc = UpdateService()
        with mock.patch(
            "services.update_service.get_http_client",
            return_value=_client(_resp(json_data=data)),
        ):
            result = await svc.check_for_update()
        assert result is not None
        assert result.type == "announcement"
        assert result.title == "Heads up"

    @pytest.mark.asyncio
    async def test_returns_update_info_not_dict(self):
        from unittest import mock

        from services.update_service import UpdateInfo, UpdateService

        data = {"build_number": APP_BUILD_NUMBER + 1, "version": "9.9.9"}
        svc = UpdateService()
        with mock.patch(
            "services.update_service.get_http_client",
            return_value=_client(_resp(json_data=data)),
        ):
            result = await svc.check_for_update()
        assert isinstance(result, UpdateInfo)
        assert isinstance(result.to_dict(), dict)

    def test_non_https_config_rejected(self):
        from services.update_service import UpdateService

        with pytest.raises(ValueError):
            UpdateService(config_url="http://example.com/version.json")
