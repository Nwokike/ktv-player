"""Tests for FolderExpansionTile component."""

from components.folder_expansion_tile import FolderExpansionTile
from services.local_scanner import LocalVideo, VideoFolder


def test_folder_expansion_tile_is_component():
    assert getattr(FolderExpansionTile, "__is_component__", False) is True


def test_folder_expansion_tile_callable():
    VideoFolder(
        name="Videos",
        path="/videos",
        videos=[
            LocalVideo(name="a.mp4", path="/videos/a.mp4"),
        ],
    )
    assert callable(FolderExpansionTile)


def test_tile_source_uses_wrapping_row_not_nested_gridview():
    """No scrollable GridView inside the outer ListView (flex-in-unbounded);
    no ResponsiveRow-only col= dicts on grid children; max_extent alone."""
    import inspect

    from components import folder_expansion_tile as tile_mod

    src = inspect.getsource(tile_mod.FolderExpansionTile)
    # ft.Wrap does not exist in Flet 1.0.1 — the wrapping-row equivalent.
    assert "ft.Row(" in src
    assert "wrap=True" in src
    assert "ft.GridView(" not in src
    assert "runs_count" not in src
    assert "col={" not in src
    # Sizing comes from the child width (Row wrap has no delegate).
    assert "width=160" in src


def test_tile_children_keyed_and_state_functional():
    """Keys on video wrappers; functional updaters (no stale closures)."""
    import inspect

    from components import folder_expansion_tile as tile_mod

    src = inspect.getsource(tile_mod.FolderExpansionTile)
    assert "key=v.path" in src
    assert "set_expanded(lambda prev:" in src
    assert "set_count(lambda prev:" in src


def test_tile_empty_folder_placeholder():
    """Expanded empty folders render a placeholder, not a zero-child grid."""
    import inspect

    from components import folder_expansion_tile as tile_mod

    src = inspect.getsource(tile_mod.FolderExpansionTile)
    assert "Empty folder" in src
