"""Tests for player control configuration."""

from unittest import mock

from components.player.controls import build_player_controls


def test_player_controls_returns_adaptive_controls():
    """build_player_controls should return an AdaptiveVideoControls instance."""
    import flet_video as fv

    player = mock.MagicMock()
    player.speed_text = mock.MagicMock()
    controls = build_player_controls(player)
    assert isinstance(controls, fv.AdaptiveVideoControls)


def test_desktop_controls_have_no_skip_buttons():
    """Desktop controls should NOT have skip buttons (single-item playlist)."""
    import flet_video as fv

    player = mock.MagicMock()
    player.speed_text = mock.MagicMock()
    controls = build_player_controls(player)
    desktop = controls.material_desktop
    assert isinstance(desktop, fv.MaterialDesktopVideoControls)
    if desktop.primary_button_bar:
        for btn in desktop.primary_button_bar:
            assert not isinstance(
                btn, (fv.VideoSkipPreviousButton, fv.VideoSkipNextButton)
            )


def test_mobile_controls_have_no_skip_buttons():
    """Mobile controls should NOT have skip buttons (single-item playlist)."""
    import flet_video as fv

    player = mock.MagicMock()
    player.speed_text = mock.MagicMock()
    controls = build_player_controls(player)
    mobile = controls.material
    assert isinstance(mobile, fv.MaterialVideoControls)
    if mobile.primary_button_bar:
        for btn in mobile.primary_button_bar:
            assert not isinstance(
                btn, (fv.VideoSkipPreviousButton, fv.VideoSkipNextButton)
            )


def test_desktop_play_and_pause_on_tap_enabled():
    """Desktop controls should disable play_and_pause_on_tap per user request."""
    import flet_video as fv

    player = mock.MagicMock()
    player.speed_text = mock.MagicMock()
    controls = build_player_controls(player)
    desktop = controls.material_desktop
    assert isinstance(desktop, fv.MaterialDesktopVideoControls)
    assert desktop.play_and_pause_on_tap is False
