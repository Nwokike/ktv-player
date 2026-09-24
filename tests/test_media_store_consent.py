"""The delete-consent path must call the right Android API.

A device log from build 19 read:

    WARNING: Delete-consent request failed ...:
    type object 'android.provider.MediaStore$Video$Media' has no
    attribute 'createDeleteRequest'

`createDeleteRequest` is a static method on `android.provider.MediaStore`,
not on the Video class, so every delete of a video the app does not own
failed before the system dialog could appear. These tests pin the class
name and the call shape so it cannot regress silently.
"""

import ast
import inspect
from pathlib import Path
from typing import ClassVar

from src.services.local_scanner import build_delete_request

SRC = Path(__file__).resolve().parent.parent / "src"


class _FakeArrayList:
    def __init__(self):
        self.items = []

    def add(self, item):
        self.items.append(item)


class _FakeUri:
    @staticmethod
    def parse(value):
        return f"parsed:{value}"


class _FakeMediaStore:
    calls: ClassVar[list] = []

    @classmethod
    def createDeleteRequest(cls, resolver, uris):
        cls.calls.append((resolver, uris))
        return "pending-intent"


def test_build_delete_request_calls_the_supplied_media_store_class():
    _FakeMediaStore.calls.clear()
    resolver = object()
    uri = "content://media/external/video/media/42"

    result = build_delete_request(
        _FakeMediaStore, resolver, uri, _FakeArrayList, _FakeUri
    )

    assert result == "pending-intent"
    assert len(_FakeMediaStore.calls) == 1
    called_resolver, called_uris = _FakeMediaStore.calls[0]
    assert called_resolver is resolver
    assert called_uris.items == [f"parsed:{uri}"]


def test_request_path_uses_media_store_not_the_video_class():
    """The pyjnius call must resolve `android.provider.MediaStore`.

    Reading the source (rather than calling jnius, which does not exist off
    Android) is what makes this assertable in CI.
    """
    source = inspect.getsource(
        __import__(
            "src.services.local_scanner", fromlist=["x"]
        ).request_media_store_delete
    )
    tree = ast.parse(source)
    class_names = [
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "autoclass"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ]
    assert "android.provider.MediaStore" in class_names, class_names
    assert "android.provider.MediaStore$Video$Media" not in class_names, (
        "createDeleteRequest is a static method on MediaStore, not MediaStore.Video.Media"
    )


def test_build_delete_request_is_used_by_the_live_path():
    """Guard against the helper being orphaned by a refactor."""
    source = (SRC / "services" / "local_scanner.py").read_text(encoding="utf-8")
    assert "build_delete_request(" in source
    assert "createDeleteRequest" not in source.split("def build_delete_request")[0]
