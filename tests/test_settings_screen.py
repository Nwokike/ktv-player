"""Tests for SettingsScreen component + Phase 7 source contracts."""

import inspect

from screens.settings_screen import SettingsScreen


def test_settings_screen_marked_as_component():
    assert getattr(SettingsScreen, "__is_component__", False) is True


def test_sections_have_6_entries():
    from screens.settings_screen import _SECTIONS

    assert len(_SECTIONS) == 6


def test_sections_cover_expected_keys():
    from screens.settings_screen import _SECTIONS

    keys = {s["key"] for s in _SECTIONS}
    expected = {
        "appearance",
        "localization",
        "data_management",
        "custom_content",
        "premium",
        "about",
    }
    assert keys == expected


def test_phase7_source_contracts():
    """Pin the Phase 7 settings fixes at the source level."""
    import inspect

    from screens import settings_screen as mod

    src = inspect.getsource(mod.SettingsScreen)
    module_src = inspect.getsource(mod)
    # No raw create_task: everything schedules on the page loop.
    assert "asyncio.create_task" not in module_src
    assert "run_task" in module_src
    # Dead theme state gone; Switch reads live state, no autofocus.
    assert "_theme_mode" not in module_src
    assert "set_theme_mode" not in module_src
    # License retry path exists.
    assert "Retry" in src
    assert "_load_license" in src
    # Claims hop is guarded via getattr on the service, not direct.
    assert 'getattr(premium_service, "license", None)' in src
    # Empty banners filtered, not appended blindly.
    assert "_is_empty_banner" in src
    # Version row guards the no-op controller default.
    assert "_open_version_row" in src
    # Country dialog is bounded + searchable.
    assert "Search 177 countries" in src
    # Log dialog caps its dump and updates dialog-locally.
    assert "older lines omitted" in module_src
    assert "log_text.update()" in module_src


def test_onboarding_source_contracts():
    """Pin the Phase 7 onboarding fixes at the source level."""
    from screens import onboarding_screen as mod

    src = inspect.getsource(mod)
    # No nested ListView: flat column under a cap.
    assert "build_controls_on_demand" not in src
    # Persist paths guarded with error toasts.
    assert "Could not save settings" in src
    # Double-submit guard.
    assert "is_saving" in src
    # No-flash init from prober presence.
    assert "prober is not None" in src
    # Fallback checks channels, not the always-truthy extract result.
    assert "if state.channels" in src
    # Disabled-button explanation + bounded country list.
    assert "Pick your country above" in src
    # Top-level offline flow import (not deferred).
    assert "from components.offline_flow import OfflineFlow" in src
    # Brand image has error fallback, no tint.
    assert "LIVE_TV_ROUNDED" in src
