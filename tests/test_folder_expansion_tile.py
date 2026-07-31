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
