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


def _chip_in_bar(bar, tooltip):
    return next(
        (c for c in (bar or []) if getattr(c, "tooltip", None) == tooltip),
        None,
    )


def test_quality_btn_mounted_in_bottom_bar():
    player = mock.MagicMock()
    player.speed_text = mock.MagicMock()
    controls = build_player_controls(player)
    mobile = _chip_in_bar(controls.material.bottom_button_bar, "Quality")
    desktop = _chip_in_bar(controls.material_desktop.bottom_button_bar, "Quality")
    assert mobile is not None
    assert desktop is not None
    # Factory split: each branch owns a FRESH instance (single-parent rule).
    assert mobile is not desktop
    assert hasattr(player, "quality_btn")


def test_audio_btn_mounted_in_bottom_bar():
    player = mock.MagicMock()
    player.speed_text = mock.MagicMock()
    controls = build_player_controls(player)
    mobile = _chip_in_bar(controls.material.bottom_button_bar, "Audio Track")
    desktop = _chip_in_bar(controls.material_desktop.bottom_button_bar, "Audio Track")
    assert mobile is not None
    assert desktop is not None
    assert mobile is not desktop
    assert hasattr(player, "audio_btn")


def test_branch_instances_are_distinct():
    """Material and desktop branches must not share button instances."""
    player = mock.MagicMock()
    player.speed_text = mock.MagicMock()
    controls = build_player_controls(player)
    mobile_ids = {id(c) for c in controls.material.bottom_button_bar or []}
    desktop_ids = {id(c) for c in controls.material_desktop.bottom_button_bar or []}
    assert not (mobile_ids & desktop_ids), "branches share instances"


def test_single_update_per_favorite_toggle():
    """One video.update() per star toggle (no triple-update)."""
    player = mock.MagicMock()
    player.speed_text = mock.MagicMock()
    player.resource = "http://example.com/stream.m3u8"
    player.show_favorite_button = True
    player.video = mock.MagicMock()
    player.page = mock.MagicMock()
    player.safe_page = mock.MagicMock()
    controls = build_player_controls(player)
    favs = _fav_buttons(controls.material.bottom_button_bar)
    assert favs, "fav button must be mounted"
    favs[0].on_click(mock.MagicMock())
    player.video.update.assert_called_once()
    # No child .update() storm and no full page.update() for one star toggle.
    player.page.update.assert_not_called()
