"""Bundled changelog shown by the version dialog when the app is up to
date — works fully offline. One line per release; keep the entry for the
current APP_VERSION in sync when bumping (guarded by tests).

Ordering: newest version FIRST. ``latest_version()`` returns the first
key, and the ``notes_for`` fallback serves the newest entry — never
``reversed()`` on this dict.
"""

from types import MappingProxyType
from typing import Final

CHANGELOG: Final = MappingProxyType(
    {
        "2.3.0": (
            "- Independent release audit, then every finding fixed: crash on "
            "empty custom playlists, a back press that exited the app instead "
            "of returning Home, the search screen failing to open, folder "
            "expansion crashing, and liveliness dots that went permanently "
            "stale\n"
            "- Faster cold start: the parsed channel list is cached beside the "
            "playlist file, so the first frame no longer waits on parsing\n"
            "- One channel verdict now repaints one card instead of rebuilding "
            "the whole grid, so scrolling stays smooth while dots update\n"
            "- Cleaner shutdown: background probes and downloads finish their "
            "current item and no work is orphaned when the app closes\n"
            "- The toast that hides after 3 seconds now actually cancels when "
            "a new one arrives, and the theme toggle writes your final choice\n"
            "- Storage caches are msgpack with schema checks and clean "
            "fallbacks, so a corrupt file degrades instead of crashing\n"
            "- Security: deep link headers can no longer smuggle in "
            "Authorization, and protocol-relative URLs are rejected as local "
            "files\n"
            "- Accessible contrast, correct folder grouping on Android 10+, "
            "and placeholders on every remote image so cards never flash\n"
            "- Test suite is 783 tests, parallel and warning-free, with "
            "regression tests for every audit fix"
        ),
        "2.2.0": (
            "- Premium unlocks the channel pack (10,000+ channels across "
            "177 countries, the top channels in every field), keeps the "
            "YouTube channels from the free lineup, and removes ads on "
            "phones. Bought through your own Flutterwave checkout (APK, "
            "Windows, Linux)\n"
            "- Payments finish themselves: pay in the browser, the app "
            "unlocks on its own, and your receipt email carries the recovery "
            "ID\n"
            "- The Play Store build is free-only: ads on, no purchase UI\n"
            "- Speed control for every video except live channels\n"
            "- Contact the developer, rate 5 stars, and more Kiri apps now "
            "in Settings\n"
            "- A click confirms favorites and snapshots on Android and TV\n"
            "- Back button behaves: a tab returns Home, Home exits, a video "
            "saves its position\n"
            "- Deleting a local video now asks Android for permission and "
            "confirms the file is gone\n"
            "- Local video thumbnails and an always-visible options menu\n"
            "- Shimmer loading skeletons, clearer D-pad focus, fullscreen "
            "controls that fit the mode\n"
            "- Faster boot: the license check no longer delays the first frame\n"
            "- Fixes: crash on back press, empty channel list on Windows, "
            "filters resetting at launch, long video dates showing blank"
        ),
        "2.1.0": (
            "- In-player Quality switching for multi-variant HLS streams\n"
            "- In-player Audio Track selection with language labels\n"
            "- Android Picture-in-Picture (button + auto-enter while playing)\n"
            "- Auto-resume for VOD and local videos, with periodic checkpoints\n"
            "- Resume survives the Android system back gesture\n"
            "- In-player toast notifications work in fullscreen on phones\n"
            "- Rebuilt playback retry system — never a dead-end overlay\n"
            "- Full-title display in the player (no shrinking)\n"
            "- Deep links open fast and exit back to the calling app"
        ),
        "2.0.6": (
            "- Fullscreen notifications inside the video controls\n"
            "- Playback retry watchdog (10s network timeout, 20s stall guard)\n"
            "- Offline liveliness neutrality — no red dots while offline\n"
            "- Local-file subtitle picker fixed on Android"
        ),
    }
)


def _normalize(version: str) -> str:
    """Strip whitespace and a leading "v" so "  v2.2.0 " still matches."""
    return version.strip().lstrip("v").lstrip("V")


def latest_version() -> str:
    """Newest bundled version — the first key (dict is newest-first)."""
    return next(iter(CHANGELOG), "")


def notes_for(version: str) -> str:
    """Changelog entry for a version, falling back to the newest entry."""
    return CHANGELOG.get(_normalize(version)) or CHANGELOG.get(latest_version(), "")
