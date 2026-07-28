"""Tests for OnboardingScreen component logic.

We keep screen tests focused on the logic that's easy to verify off-screen:
the persistence side-effects of submit/skip, and the gating that decides
whether submit is enabled. Heavy rendering is exercised by integration
smoke tests (Task 10) which mount the component under a fake page.
"""

from unittest import mock

import pytest

from app_next.screens.onboarding_screen import (
    OnboardingScreen,
    _persist_offline_defaults,
    _persist_terms_and_country,
    can_submit,
)


@pytest.mark.parametrize(
    "country,terms,expected",
    [
        ("Nigeria", True, True),
        ("Nigeria", False, False),
        ("", True, False),
        ("", False, False),
    ],
)
def test_can_submit(country, terms, expected):
    assert can_submit(country, terms) is expected


@pytest.mark.anyio
async def test_persist_terms_and_country_writes_both_keys():
    storage = mock.AsyncMock()
    state = mock.Mock()
    await _persist_terms_and_country(storage=storage, state=state, country="Nigeria")
    storage.set_setting.assert_any_await("user_country", "Nigeria")
    storage.set_setting.assert_any_await("accepted_terms", "true")
    assert state.user_country == "Nigeria"
    assert state.has_accepted_terms is True
    assert state.is_first_launch is False


@pytest.mark.anyio
async def test_persist_offline_defaults_writes_other_country():
    storage = mock.AsyncMock()
    state = mock.Mock()
    await _persist_offline_defaults(storage=storage, state=state)
    storage.set_setting.assert_any_await("user_country", "Other")
    storage.set_setting.assert_any_await("accepted_terms", "true")
    assert state.user_country == "Other"
    assert state.has_accepted_terms is True
    assert state.is_first_launch is False


def test_onboarding_screen_is_component_callable():
    """The screen is a @ft.component — marked as component."""
    assert getattr(OnboardingScreen, "__is_component__", False) is True
    assert callable(OnboardingScreen)
