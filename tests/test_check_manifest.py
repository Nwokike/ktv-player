"""The TV device-catalog gate (tools/check_manifest.py) must actually fail
when the manifest regresses — a check that can only pass is worthless, and
the regression it exists for (2.0.5 vanishing from the Android TV store)
shipped precisely because the old job asserted nothing.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from check_manifest import check_manifest

GOOD = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
  <uses-sdk android:minSdkVersion="24" android:targetSdkVersion="36" />
  <uses-permission android:name="android.permission.INTERNET" />
  <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
  <uses-feature android:name="android.software.leanback" android:required="true" />
  <uses-feature android:name="android.hardware.microphone" android:required="false" />
  <application android:banner="@drawable/banner">
    <activity android:supportsPictureInPicture="true">
      <intent-filter>
        <action android:name="android.intent.action.MAIN" />
        <category android:name="android.intent.category.LEANBACK_LAUNCHER" />
      </intent-filter>
    </activity>
  </application>
</manifest>
"""


def _write(tmp_path: Path, body: str) -> str:
    path = tmp_path / "AndroidManifest.xml"
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_shipped_shape_passes_every_check(tmp_path):
    report = check_manifest(
        _write(tmp_path, GOOD),
        require_banner=True,
        require_pip=True,
        allow_optional_mic=True,
    )
    assert report.failures == []


def test_optional_leanback_fails_the_gate(tmp_path):
    """The 2.0.5 bug: leanback marked not-required hides the TV listing."""
    body = GOOD.replace(
        'android:name="android.software.leanback" android:required="true"',
        'android:name="android.software.leanback" android:required="false"',
    )
    report = check_manifest(_write(tmp_path, body))
    assert "leanback is a REQUIRED uses-feature" in report.failures


def test_missing_leanback_feature_fails(tmp_path):
    body = GOOD.replace(
        '  <uses-feature android:name="android.software.leanback" android:required="true" />\n',
        "",
    )
    report = check_manifest(_write(tmp_path, body))
    assert "leanback is a REQUIRED uses-feature" in report.failures


def test_missing_leanback_launcher_category_fails(tmp_path):
    body = GOOD.replace(
        "android.intent.category.LEANBACK_LAUNCHER", "android.intent.category.LAUNCHER"
    )
    report = check_manifest(_write(tmp_path, body))
    assert "an activity is launchable from the TV home screen" in report.failures


def test_required_microphone_fails_when_checked(tmp_path):
    body = GOOD.replace(
        'android:name="android.hardware.microphone" android:required="false"',
        'android:name="android.hardware.microphone" android:required="true"',
    )
    report = check_manifest(_write(tmp_path, body), allow_optional_mic=True)
    assert "microphone is NOT required" in report.failures


def test_missing_ima_permission_fails(tmp_path):
    body = GOOD.replace(
        '  <uses-permission android:name="android.permission.INTERNET" />\n', ""
    )
    report = check_manifest(_write(tmp_path, body))
    assert "permission android.permission.INTERNET" in report.failures


def test_low_sdk_fails(tmp_path):
    body = GOOD.replace('android:minSdkVersion="24"', 'android:minSdkVersion="21"')
    report = check_manifest(_write(tmp_path, body))
    assert "minSdkVersion >= 24" in report.failures


def test_low_target_sdk_fails(tmp_path):
    body = GOOD.replace(
        'android:targetSdkVersion="36"', 'android:targetSdkVersion="31"'
    )
    report = check_manifest(_write(tmp_path, body))
    assert "targetSdkVersion >= 33" in report.failures


def test_missing_banner_and_pip_fail_when_required(tmp_path):
    body = GOOD.replace(' android:banner="@drawable/banner"', "")
    body = body.replace(' android:supportsPictureInPicture="true"', "")
    report = check_manifest(
        _write(tmp_path, body), require_banner=True, require_pip=True
    )
    assert "application declares a TV banner" in report.failures
    assert "an activity supports Picture-in-Picture" in report.failures


def test_unreadable_manifest_fails_instead_of_passing(tmp_path):
    report = check_manifest(str(tmp_path / "does-not-exist.xml"))
    assert report.failures == ["merged manifest is readable"]


def test_cli_exit_codes(tmp_path, capsys):
    from check_manifest import main

    good = _write(tmp_path, GOOD)
    assert main([good]) == 0
    bad = _write(
        tmp_path, GOOD.replace("android.intent.category.LEANBACK_LAUNCHER", "x")
    )
    assert main([bad]) == 1
    assert "FAILED" in capsys.readouterr().out


@pytest.mark.parametrize("path", ["/does/not/exist.xml"])
def test_cli_handles_missing_file(path):
    from check_manifest import main

    assert main([path]) == 1
