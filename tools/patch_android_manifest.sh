#!/usr/bin/env bash
# Patch the generated AndroidManifest.xml for Android TV + Picture-in-Picture.
#
# Why this is a script and not inline `sed` in the workflow:
#
#   * The three Android jobs (audit, split APKs, AAB) must patch the manifest
#     IDENTICALLY, otherwise the audit validates a manifest that never ships —
#     which is how a TV-catalog regression passed CI in the first place.
#   * Flet's CLI emits `android.software.leanback` with required=false unless
#     `[tool.flet.android.feature]` overrides it (we do), and nothing in the
#     toolchain adds the LEANBACK_LAUNCHER category at all. Play hides apps
#     with no TV launch activity, and the TV home screen cannot show them.
#   * Every patch is idempotent, so re-running is safe.
#
# Usage: patch_android_manifest.sh <manifest-path> [--release]
#   --release  also applies the TV banner and PiP attributes (release builds
#              only — they need the drawable/icon resources staged first).

set -euo pipefail

MANIFEST="${1:-}"
RELEASE=0
shift || true
for arg in "$@"; do
  [ "$arg" = "--release" ] && RELEASE=1
done

if [ -z "$MANIFEST" ] || [ ! -f "$MANIFEST" ]; then
  echo "ERROR: manifest not found: '${MANIFEST}'" >&2
  exit 1
fi

changed=0

# tools:replace needs the namespace bound on the manifest root.
if ! grep -q 'xmlns:tools' "$MANIFEST"; then
  sed -i '0,/<manifest/{s|<manifest|<manifest xmlns:tools="http://schemas.android.com/tools"|}' "$MANIFEST"
  echo "patched: xmlns:tools"
  changed=1
fi

# A library manifest declares the microphone as REQUIRED, which excludes TV
# boxes without one from the Play listing. Force it optional.
# NOTE: the replacement uses sed's \n escape — a literal newline inside the
# quoted s|...|...| expression is an "unterminated s command" error.
if ! grep -q 'android.hardware.microphone.*required="false"' "$MANIFEST"; then
  sed -i 's|<application|<uses-feature android:name="android.hardware.microphone" android:required="false" tools:replace="android:required" />\n          <application|' "$MANIFEST"
  echo "patched: microphone optional"
  changed=1
fi

# Leanback must be REQUIRED or Play keeps the app out of the TV catalog.
# pyproject already sets this; this is the belt to that suspenders, because
# the failure mode is an app that silently disappears from TV.
if grep -q 'android.software.leanback.*required="false"' "$MANIFEST"; then
  sed -i 's|android:name="android.software.leanback" android:required="false"|android:name="android.software.leanback" android:required="true"|' "$MANIFEST"
  echo "patched: leanback required"
  changed=1
fi

# LEANBACK_LAUNCHER category — nothing in the Flet toolchain emits it.
# Appended (not substituted) so it matches regardless of how the template
# spaces its tags: `<category ... />` and `<category .../>` both hit.
if ! grep -q 'LEANBACK_LAUNCHER' "$MANIFEST"; then
  sed -i '/android\.intent\.category\.LAUNCHER/a\                <category android:name="android.intent.category.LEANBACK_LAUNCHER" />' "$MANIFEST"
  if grep -q 'LEANBACK_LAUNCHER' "$MANIFEST"; then
    echo "patched: LEANBACK_LAUNCHER category"
    changed=1
  else
    echo "ERROR: could not add the LEANBACK_LAUNCHER category — no LAUNCHER category line to anchor to" >&2
    exit 1
  fi
fi

if [ "$RELEASE" = "1" ]; then
  if ! grep -q 'android:banner' "$MANIFEST"; then
    sed -i 's|<application|<application android:banner="@drawable/banner"|' "$MANIFEST"
    echo "patched: TV banner"
    changed=1
  fi
  if ! grep -q 'supportsPictureInPicture' "$MANIFEST"; then
    sed -i 's|<activity|<activity android:supportsPictureInPicture="true"|g' "$MANIFEST"
    if ! grep -q 'supportsPictureInPicture' "$MANIFEST"; then
      echo "ERROR: could not enable Picture-in-Picture" >&2
      exit 1
    fi
    echo "patched: supportsPictureInPicture"
    changed=1
  fi
fi

[ "$changed" = "0" ] && echo "manifest already patched — nothing to do"
echo "manifest patches applied to $MANIFEST"
