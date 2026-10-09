"""Phase 7 — theme, tokens, changelog, crash reporter, logging tests."""

from types import SimpleNamespace

import flet as ft
import pytest


def _dark_page():
    return SimpleNamespace(
        theme_mode=ft.ThemeMode.DARK, platform_brightness=ft.Brightness.DARK
    )


def _light_page():
    return SimpleNamespace(
        theme_mode=ft.ThemeMode.LIGHT, platform_brightness=ft.Brightness.LIGHT
    )


def _system_dark_page():
    return SimpleNamespace(
        theme_mode=ft.ThemeMode.SYSTEM, platform_brightness=ft.Brightness.DARK
    )


def _system_light_page():
    return SimpleNamespace(
        theme_mode=ft.ThemeMode.SYSTEM, platform_brightness=ft.Brightness.LIGHT
    )


# --- theme ---


def test_is_dark_explicit_modes():
    from core.theme import AppColors

    assert AppColors.is_dark(_dark_page()) is True
    assert AppColors.is_dark(_light_page()) is False


def test_is_dark_system_follows_device():
    from core.theme import AppColors

    assert AppColors.is_dark(_system_dark_page()) is True
    assert AppColors.is_dark(_system_light_page()) is False


def test_is_dark_unified_fallback():
    """Missing/unreadable page falls back to the SAME default as grey_dim."""
    from core.theme import AppColors

    assert AppColors.is_dark(None) is True

    class _RaisingPage:
        theme_mode = ft.ThemeMode.SYSTEM

        @property
        def platform_brightness(self):
            raise RuntimeError("no session")

    assert AppColors.is_dark(_RaisingPage()) is True
    # A readable-but-None brightness simply isn't DARK (no raise involved).
    assert AppColors.is_dark(_system_light_page()) is False


def test_grey_dim_agrees_with_is_dark(monkeypatch):
    """The two helpers must never disagree about which theme is active."""
    import flet.controls.context as ctx_mod

    from core.theme import AppColors

    assert AppColors.grey_dim(_dark_page()) == "#AAAAAA"
    assert AppColors.grey_dim(_light_page()) == "#555555"
    # Off-session: context.page raises -> shared _FALLBACK_DARK default.
    monkeypatch.setattr(ctx_mod, "_context_page", _RaisingVar())
    assert AppColors.grey_dim() == "#AAAAAA"
    assert AppColors.is_dark(None) is True


class _RaisingVar:
    def get(self):
        raise RuntimeError("no session")


def test_on_secondary_is_white_both_schemes():
    from core.theme import AppTheme

    for theme in (AppTheme.get_dark_theme(), AppTheme.get_light_theme()):
        assert theme.color_scheme.on_secondary in (
            ft.Colors.WHITE,
            "white",
            "#FFFFFF",
            "#ffffff",
        ), theme.color_scheme.on_secondary


def test_secondary_aliases_primary_dark():
    from core.theme import AppColors

    assert AppColors.SECONDARY == AppColors.PRIMARY_DARK


def test_get_card_bg_matches_get_surface():
    from core.theme import AppColors

    assert AppColors.get_card_bg(_dark_page()) == AppColors.get_surface(_dark_page())
    assert AppColors.get_card_bg(_light_page()) == AppColors.get_surface(_light_page())


def test_themes_carry_scaffold_dialog_transitions():
    from core.theme import AppColors, AppTheme

    dark = AppTheme.get_dark_theme()
    light = AppTheme.get_light_theme()
    assert dark.scaffold_bgcolor == AppColors.DARK_BG
    assert light.scaffold_bgcolor == AppColors.LIGHT_BG
    assert dark.dialog_theme.bgcolor == AppColors.DARK_SURFACE
    assert light.dialog_theme.bgcolor == AppColors.LIGHT_SURFACE
    for theme in (dark, light):
        pt = theme.page_transitions
        assert pt.windows is not None
        assert pt.macos is not None
        assert pt.linux is not None
    # Empty AppBarTheme is gone — both themes pin the surface color.
    assert dark.appbar_theme.bgcolor == AppColors.DARK_SURFACE
    assert light.appbar_theme.bgcolor == AppColors.LIGHT_SURFACE


# --- tokens ---


def test_no_space_radius_aliases():
    from core import tokens

    for name in ("SPACE_XS", "SPACE_MD", "RADIUS_SM", "RADIUS_FULL"):
        assert not hasattr(tokens, name), name
    assert "FONT_MD" in tokens.__all__


def test_spacing_grid_and_fonts():
    from core import tokens

    for v in (
        tokens.SPACING_XS,
        tokens.SPACING_SM,
        tokens.SPACING_MD,
        tokens.SPACING_LG,
        tokens.SPACING_XL,
    ):
        assert v % 4 == 0, v
    assert tokens.SPACING_MD == 12
    assert tokens.FONT_MD == 12
    assert tokens.FONT_LG == 16
    assert tokens.BORDER_RADIUS_FULL == 999
    assert pytest.approx(0.75) == tokens.CARD_ASPECT_RATIO


# --- changelog ---


def test_fallback_returns_latest_not_oldest():
    from core.changelog import CHANGELOG, latest_version, notes_for
    from core.constants import APP_VERSION

    assert latest_version() == APP_VERSION
    assert notes_for("0.0.0") == CHANGELOG[APP_VERSION]
    # Never the oldest entry (the old reversed() fallback served 2.0.6).
    assert notes_for("0.0.0") != CHANGELOG[next(reversed(CHANGELOG))]


def test_notes_normalize_input():
    from core.changelog import notes_for
    from core.constants import APP_VERSION

    assert notes_for(f"  v{APP_VERSION} ") == notes_for(APP_VERSION)
    assert len(notes_for(APP_VERSION)) > 0


# --- crash reporter ---


def test_record_crash_returns_path_and_preserves_cause(tmp_path, monkeypatch):
    import core.crash_reporter as cr

    monkeypatch.setattr(cr, "_get_crash_dir", lambda: str(tmp_path))
    try:
        raise ValueError("boom")
    except ValueError as ex:
        cause_ex = RuntimeError("wrapper")
        cause_ex.__cause__ = ex
        path = cr.record_crash(cause_ex, context="test")
    assert path is not None
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "wrapper" in content
    assert "boom" in content
    assert "Traceback" in content


def test_record_crash_filenames_unique(tmp_path, monkeypatch):
    import core.crash_reporter as cr

    monkeypatch.setattr(cr, "_get_crash_dir", lambda: str(tmp_path))
    p1 = cr.record_crash(Exception("a"))
    p2 = cr.record_crash(Exception("b"))
    assert p1 is not None and p2 is not None and p1 != p2


def test_record_crash_bounds_file_count(tmp_path, monkeypatch):
    import core.crash_reporter as cr

    monkeypatch.setattr(cr, "_get_crash_dir", lambda: str(tmp_path))
    monkeypatch.setattr(cr, "MAX_CRASH_FILES", 3)
    for i in range(5):
        cr.record_crash(Exception(f"e{i}"))
    logs = [f for f in tmp_path.iterdir() if f.suffix == ".log"]
    assert len(logs) <= 3


def test_install_crash_handler_idempotent():
    import core.crash_reporter as cr

    cr.uninstall_crash_handler_for_tests()
    page = SimpleNamespace(on_error=None)
    cr.install_crash_handler(page)
    first = page.on_error
    cr.install_crash_handler(page)
    assert page.on_error is first
    cr.uninstall_crash_handler_for_tests()


# --- logging ---


def test_setup_logging_reconfigures_level():
    import logging

    from core.logging_config import setup_logging

    setup_logging(logging.DEBUG, force=True)
    assert logging.getLogger().level == logging.DEBUG
    setup_logging(logging.WARNING, force=True)
    assert logging.getLogger().level == logging.WARNING
    setup_logging(logging.INFO, force=True)


def test_setup_logging_idempotent_handlers():
    import logging

    from core.logging_config import setup_logging

    setup_logging(force=True)
    root = logging.getLogger()
    n = len(root.handlers)
    setup_logging()
    assert len(root.handlers) == n


def test_memory_handler_locked_roundtrip():
    from core.logger_handler import MemoryLogHandler

    h = MemoryLogHandler(maxlen=3)
    logger = __import__("logging").getLogger("ktv_test_phase7")
    logger.addHandler(h)
    try:
        logger.warning("one")
        assert h.get_logs()[-1].endswith("one")
        h.clear_logs()
        assert h.get_logs() == []
    finally:
        logger.removeHandler(h)
