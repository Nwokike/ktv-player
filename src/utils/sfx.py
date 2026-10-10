"""Tiny UI sound effects: Android phone and TV only.

Rationale: in native fullscreen the toast chip cannot reliably draw (the
player owns that surface), but audio does not care about the view tree,
so a short click confirms favorite toggles and snapshots everywhere,
fullscreen included. Desktop is deliberately a no-op: no winsound, no
system beeps (owner's call).

Implementation: android.media.ToneGenerator through pyjnius, which is
already a hard Android dependency. No new packages, no bundled assets.
The generator is released after a moment so repeated taps do not leak.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


def play_click() -> None:
    """Short confirmation click. Silently does nothing off Android."""
    try:
        from jnius import autoclass

        tone_generator = autoclass("android.media.ToneGenerator")
        audio_manager = autoclass("android.media.AudioManager")
        generator = tone_generator(audio_manager.STREAM_SYSTEM, 80)
        generator.startTone(tone_generator.TONE_PROP_BEEP, 80)
    except Exception:
        # Desktop, TV without the service, or jnius unavailable: silence
        # is the designed behavior, not an error.
        return

    try:
        loop = asyncio.get_running_loop()
        loop.call_later(1.0, generator.release)
    except RuntimeError:
        # No running loop (rare): release on a timer thread instead of
        # leaking the native generator.
        import threading

        threading.Timer(1.0, generator.release).start()
