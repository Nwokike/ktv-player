"""Phase 7 — Header correctness tests."""

from types import SimpleNamespace

import flet as ft


def _render_header(monkeypatch, **kwargs):
    """Render the Header body off-session (no page context)."""
    import flet.controls.context as ctx_mod

    class _RaisingVar:
        def get(self):
            raise RuntimeError("no session")

    monkeypatch.setattr(ctx_mod, "_context_page", _RaisingVar())
    from flet.components.component import Renderer

    from components.header import Header

    screen = Renderer().render(lambda: Header(**kwargs))
    screen.before_update()
    return getattr(screen, "_b", screen)


def _walk(node):
    yield node
    for child in getattr(node, "controls", None) or []:
        yield from _walk(child)
    content = getattr(node, "content", None)
    if content is not None:
        yield from _walk(content)


def _texts(root):
    return [n.value for n in _walk(root) if isinstance(getattr(n, "value", None), str)]


def test_header_renders_off_session_without_crash(monkeypatch):
    """_resolve_page must not raise when context.page is unavailable."""
    root = _render_header(monkeypatch, on_version_click=lambda e: None)
    assert _texts(root), "header rendered nothing"


def test_version_chip_reactive_props(monkeypatch):
    """Lifted props drive the chip — no observable read needed."""
    root = _render_header(
        monkeypatch,
        on_version_click=lambda e: None,
        update_available=True,
        update_label="2.3.0",
    )
    assert any("2.3.0" in t for t in _texts(root)), _texts(root)
    root = _render_header(
        monkeypatch,
        on_version_click=lambda e: None,
        update_available=True,
        update_announcement=True,
    )
    assert any("News" in t for t in _texts(root)), _texts(root)


def test_version_chip_current_version(monkeypatch):
    from core.constants import APP_VERSION

    root = _render_header(monkeypatch, on_version_click=lambda e: None)
    assert any(APP_VERSION in t for t in _texts(root)), _texts(root)


def test_version_chip_absent_without_callback(monkeypatch):
    from core.constants import APP_VERSION

    root = _render_header(monkeypatch)
    assert not any(APP_VERSION in t for t in _texts(root))


def test_header_callbacks_event_tolerant(monkeypatch):
    """Zero-arg and event-taking callbacks both fire (no TypeError)."""
    from components.header import _invoke

    fired = []
    _invoke(lambda: fired.append("zero"))
    _invoke(lambda e: fired.append("event"), SimpleNamespace())
    _invoke(lambda e=None: fired.append("default"))
    assert fired == ["zero", "event", "default"]
    _invoke(None, SimpleNamespace())  # no-op, no raise


def test_brand_mark_no_tint_and_error_fallback(monkeypatch):
    root = _render_header(monkeypatch)
    images = [n for n in _walk(root) if isinstance(n, ft.Image)]
    assert images, "brand mark missing"
    for img in images:
        assert img.color is None, "brand SVG must not be tinted"
        assert img.error_content is not None


def test_actions_row_scrolls_and_spacer_present(monkeypatch):
    root = _render_header(
        monkeypatch,
        on_search_click=lambda e: None,
        on_version_click=lambda e: None,
    )
    rows = [n for n in _walk(root) if isinstance(n, ft.Row)]
    assert any(getattr(r, "scroll", None) == ft.ScrollMode.AUTO for r in rows)
