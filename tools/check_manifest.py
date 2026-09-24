"""Assert the Android facts the Play device catalog and IMA depend on.

Why this exists: the `manifest-audit` CI job was built to catch the exact
regression that made KTV Player vanish from Android TV in 2.0.5 — Play hides
an app from the TV catalog when a required `<uses-feature>` no TV device
satisfies. It printed an `aapt dump badging` transcript as evidence but
asserted nothing, and a grep-based assert proved brittle (the aapt binary
is not present in every runner image; `aapt2` is).

So the assertions read the *merged* manifest — the artifact the build
actually produced — and check attribute semantics properly instead of
matching text:

- ``android.software.leanback`` must be REQUIRED (optional = phones only)
- some activity must carry the ``LEANBACK_LAUNCHER`` category
- ``INTERNET`` + ``ACCESS_NETWORK_STATE`` (Google IMA cannot request ads
  without them)
- minSdk >= 24, targetSdk >= 33 (Play upload requirements)

Usage:
    python tools/check_manifest.py MERGED_MANIFEST [--require-banner]
                                              [--require-pip]
                                              [--allow-optional-mic]
Exit code 0 = every enabled check passed; 1 = at least one failed (each
failure is printed, so one run reports everything that is wrong).
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET

ANDROID_NS = "{http://schemas.android.com/apk/res/android}"
LEANBACK_FEATURE = "android.software.leanback"
LEANBACK_CATEGORY = "android.intent.category.LEANBACK_LAUNCHER"
MIN_SDK = 24
MIN_TARGET_SDK = 33
REQUIRED_PERMISSIONS = (
    "android.permission.INTERNET",
    "android.permission.ACCESS_NETWORK_STATE",
)


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks = 0

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        self.checks += 1
        mark = "PASS" if ok else "FAIL"
        suffix = f" — {detail}" if detail else ""
        print(f"  [{mark}] {label}{suffix}")
        if not ok:
            self.failures.append(label)
        return ok


def _int_attr(value: str | None) -> int:
    try:
        return int((value or "0").strip())
    except (TypeError, ValueError):
        return 0


def check_manifest(
    path: str,
    *,
    require_banner: bool = False,
    require_pip: bool = False,
    allow_optional_mic: bool = False,
) -> Report:
    report = Report()
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as ex:
        report.check(False, "merged manifest is readable", f"{path}: {ex}")
        return report

    features: dict[str, str] = {}
    for node in root.iter("uses-feature"):
        name = node.get(f"{ANDROID_NS}name")
        if name:
            # Android's default for android:required is "true".
            features[name] = node.get(f"{ANDROID_NS}required", "true")

    leanback = features.get(LEANBACK_FEATURE)
    report.check(
        leanback == "true",
        "leanback is a REQUIRED uses-feature",
        f"{LEANBACK_FEATURE}={leanback!r} (missing means TV boxes are filtered out)",
    )

    categories = {
        node.get(f"{ANDROID_NS}name")
        for node in root.iter("category")
        if node.get(f"{ANDROID_NS}name") == LEANBACK_CATEGORY
    }
    report.check(
        bool(categories),
        "an activity is launchable from the TV home screen",
        LEANBACK_CATEGORY,
    )

    permissions = {
        node.get(f"{ANDROID_NS}name") for node in root.iter("uses-permission")
    }
    for permission in REQUIRED_PERMISSIONS:
        report.check(
            permission in permissions,
            f"permission {permission}",
            "required by Google IMA / AdMob",
        )

    uses_sdk = next(root.iter("uses-sdk"), None)
    min_sdk = (
        _int_attr(uses_sdk.get(f"{ANDROID_NS}minSdkVersion"))
        if uses_sdk is not None
        else 0
    )
    target_sdk = (
        _int_attr(uses_sdk.get(f"{ANDROID_NS}targetSdkVersion"))
        if uses_sdk is not None
        else 0
    )
    report.check(
        min_sdk >= MIN_SDK,
        f"minSdkVersion >= {MIN_SDK}",
        f"found {min_sdk}",
    )
    report.check(
        target_sdk >= MIN_TARGET_SDK,
        f"targetSdkVersion >= {MIN_TARGET_SDK}",
        f"found {target_sdk}",
    )

    if allow_optional_mic:
        mic = features.get("android.hardware.microphone")
        report.check(
            mic != "true",
            "microphone is NOT required",
            "a required mic excludes TV boxes with no microphone",
        )

    if require_banner:
        application = next(root.iter("application"), None)
        # Element truthiness is deprecated (an element with no children is
        # falsy), so compare against None explicitly.
        banner = (
            application.get(f"{ANDROID_NS}banner") if application is not None else None
        )
        report.check(
            bool(banner),
            "application declares a TV banner",
            f"android:banner={banner!r}",
        )

    if require_pip:
        activities = list(root.iter("activity"))
        pip = [node.get(f"{ANDROID_NS}supportsPictureInPicture") for node in activities]
        report.check(
            "true" in pip,
            "an activity supports Picture-in-Picture",
            f"values={sorted(set(pip))}",
        )

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="path to the merged AndroidManifest.xml")
    parser.add_argument("--require-banner", action="store_true")
    parser.add_argument("--require-pip", action="store_true")
    parser.add_argument("--allow-optional-mic", action="store_true")
    args = parser.parse_args(argv)

    print(f"Android manifest check: {args.manifest}")
    report = check_manifest(
        args.manifest,
        require_banner=args.require_banner,
        require_pip=args.require_pip,
        allow_optional_mic=args.allow_optional_mic,
    )
    if report.failures:
        print(f"FAILED {len(report.failures)}/{report.checks} checks:")
        for failure in report.failures:
            print(f"  - {failure}")
        return 1
    print(f"All {report.checks} manifest checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
