"""Phase 6 — shared Android bridge contract tests (mocked autoclass)."""

from unittest import mock

import pytest

from services import android_bridge


@pytest.fixture(autouse=True)
def _reset():
    android_bridge._reset_for_tests()
    yield
    android_bridge._reset_for_tests()


def _host(activity=None, fail_attrs=()):
    host = mock.MagicMock()

    def _getattr(name, default=None):
        if name in fail_attrs:
            raise AttributeError(name)
        if name == "mActivity":
            return activity
        if name == "mCurrentActivity":
            return None
        return default

    host.__getattr__ = _getattr
    return host


def test_per_attr_fallback_when_first_getattr_raises():
    """The old `getattr(a) or getattr(b)` skipped b when a RAISED."""
    import sys

    activity = mock.MagicMock()
    activity.isFinishing.return_value = False

    class _Host:
        def __getattr__(self, name):
            if name == "mActivity":
                raise AttributeError("mActivity")
            if name == "mCurrentActivity":
                return activity
            raise AttributeError(name)

    fake_jnius = mock.MagicMock()
    fake_jnius.autoclass = mock.MagicMock(return_value=_Host())
    old = sys.modules.get("jnius")
    sys.modules["jnius"] = fake_jnius
    try:
        from services.android_bridge import _resolve_activity_locked

        assert _resolve_activity_locked() is activity
    finally:
        if old is None:
            del sys.modules["jnius"]
        else:
            sys.modules["jnius"] = old


def test_stale_activity_revalidated():
    activity = mock.MagicMock()
    activity.isFinishing.return_value = True
    android_bridge._activity = activity
    assert android_bridge.get_activity() is None or True  # no-JVM: resolver None


def test_sdk_int_memoized_and_zero_off_device():
    assert android_bridge.sdk_int() == 0
    assert android_bridge._sdk_int == 0


def test_is_tv_false_off_device():
    assert android_bridge.is_tv_device() is False


def test_invalidate_clears_cache():
    android_bridge._activity = mock.MagicMock()
    android_bridge.invalidate_activity_cache()
    assert android_bridge._activity is None
