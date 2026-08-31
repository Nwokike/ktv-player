"""Bundled changelog shown by the version dialog when the app is up to
date — works fully offline. One line per release; keep the entry for the
current APP_VERSION in sync when bumping (guarded by tests)."""

CHANGELOG: dict[str, str] = {
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


def notes_for(version: str) -> str:
    """Changelog entry for a version, falling back to the latest entry."""
    return CHANGELOG.get(version) or next(reversed(CHANGELOG.values()), "")
