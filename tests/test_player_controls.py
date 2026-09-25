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


def _fav_buttons(bar):
    return [
        c
        for c in (bar or [])
        if getattr(c, "tooltip", None) in ("Add to Favorites", "Remove from Favorites")
    ]


def test_fav_button_shown_by_default():
    import flet_video as fv

    player = mock.MagicMock()
    player.speed_text = mock.MagicMock()
    player.show_favorite_button = True
    controls = build_player_controls(player)
    assert isinstance(controls, fv.AdaptiveVideoControls)
    assert _fav_buttons(controls.material.bottom_button_bar)
    assert _fav_buttons(controls.material_desktop.bottom_button_bar)


def test_fav_button_hidden_when_show_favorite_false():
    """Deep-link plays must not show the in-player favorite star."""
    import flet_video as fv

    player = mock.MagicMock()
    player.speed_text = mock.MagicMock()
    player.show_favorite_button = False
    controls = build_player_controls(player)
    assert isinstance(controls, fv.AdaptiveVideoControls)
    assert not _fav_buttons(controls.material.bottom_button_bar)
    assert not _fav_buttons(controls.material_desktop.bottom_button_bar)


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


def test_quality_btn_mounted_in_bottom_bar():
    player = mock.MagicMock()
    player.speed_text = mock.MagicMock()
    controls = build_player_controls(player)
    assert hasattr(player, "quality_btn")
    assert player.quality_btn in controls.material.bottom_button_bar
    assert player.quality_btn in controls.material_desktop.bottom_button_bar


def test_audio_btn_mounted_in_bottom_bar():
    player = mock.MagicMock()
    player.speed_text = mock.MagicMock()
    controls = build_player_controls(player)
    assert hasattr(player, "audio_btn")
    assert player.audio_btn in controls.material.bottom_button_bar
    assert player.audio_btn in controls.material_desktop.bottom_button_bar
