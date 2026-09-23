"""Tests for player control configuration."""

from unittest import mock

import flet as ft

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


def test_no_toast_stack_in_top_bars():
    """The toast-chip workaround is gone: top bars show the title directly.

    The dedicated fullscreen control set (VideoControlsMode.FULLSCREEN)
    replaced the chip that used to live in a Stack over the title.
    """
    player = mock.MagicMock()
    player.speed_text = mock.MagicMock()
    player.show_favorite_button = True
    controls = build_player_controls(player)
    for bar in (
        controls.material.top_button_bar,
        controls.material_desktop.top_button_bar,
    ):
        assert not any(isinstance(c, ft.Stack) for c in bar)


def test_fullscreen_variant_has_bigger_controls_and_minimal_bar():
    import flet_video as fv

    player = mock.MagicMock()
    player.speed_text = mock.MagicMock()
    player.title = "Some Channel"
    full = build_player_controls(player, variant="fullscreen")
    assert isinstance(full, fv.AdaptiveVideoControls)
    # Bigger play/pause than the normal set (48 mobile / 32 desktop).
    mobile_play = next(
        c
        for c in full.material.primary_button_bar
        if isinstance(c, fv.VideoPlayOrPauseButton)
    )
    desktop_play = next(
        c
        for c in full.material_desktop.primary_button_bar
        if isinstance(c, fv.VideoPlayOrPauseButton)
    )
    assert mobile_play.icon_size > 48.0
    assert desktop_play.icon_size > 32.0
    # Minimal bar: no quality/audio/favorite controls in fullscreen.
    for bar in (
        full.material.bottom_button_bar,
        full.material_desktop.bottom_button_bar,
    ):
        assert player.quality_btn not in bar
        assert player.audio_btn not in bar
        assert not _fav_buttons(bar)


def test_fullscreen_and_normal_sets_are_independent():
    """Two sets must not share control instances (one parent each)."""
    import flet_video as fv

    player = mock.MagicMock()
    player.speed_text = mock.MagicMock()
    normal = build_player_controls(player)
    full = build_player_controls(player, variant="fullscreen")
    assert isinstance(normal, fv.AdaptiveVideoControls)
    assert isinstance(full, fv.AdaptiveVideoControls)
    # The fullscreen set must not mount the normal set's buttons.
    assert all(
        c is not player.speed_text
        for bar in (
            full.material.bottom_button_bar,
            full.material_desktop.bottom_button_bar,
        )
        for c in bar
    )


def test_immersive_player_wires_fullscreen_controls_mode():
    """Source contract: the Video gets a NORMAL/FULLSCREEN controls dict."""
    import inspect

    from components.player.immersive_player import ImmersivePlayer

    source = inspect.getsource(ImmersivePlayer)
    assert "fv.VideoControlsMode.NORMAL" in source
    assert "fv.VideoControlsMode.FULLSCREEN" in source
    assert "toast_chip" not in source


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
