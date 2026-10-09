"""Tiny UI sound effects: Android phone and TV only.

Rationale: in native fullscreen the toast chip cannot reliably draw (the
player owns that surface), but audio does not care about the view tree,
so a short click confirms favorite toggles and snapshots everywhere,
fullscreen included. Desktop is deliberately a no-op: no winsound, no
system beeps (owner's call).

Implementation: one lazy module-level android.media.ToneGenerator through
pyjnius (already a hard Android dependency), released only on teardown.
Per-tap construction was the documented anti-pattern (native churn +
RuntimeException under rapid taps). STREAM_MUSIC at 60 follows the user
volume — STREAM_SYSTEM is muted on TV/silent mode, which is exactly where
the clicks matter most. No new packages, no bundled assets.
"""

import logging
import threading

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_generator = None
_TONE_MS = 80


def _get_generator():
    """Lazy singleton (created once, never per-tap)."""
    global _generator
    if _generator is not None:
        return _generator
    with _lock:
        if _generator is not None:
            return _generator
        from jnius import autoclass

        tone_generator = autoclass("android.media.ToneGenerator")
        audio_manager = autoclass("android.media.AudioManager")
        _generator = tone_generator(audio_manager.STREAM_MUSIC, 60)
        return _generator


def _safe_release() -> None:
    global _generator
    with _lock:
        generator, _generator = _generator, None
    if generator is None:
        return
    try:
        generator.release()
    except Exception:
        logger.debug("SFX release failed", exc_info=True)


def release() -> None:
    """Release the shared generator (app teardown). Safe to call anytime."""
    _safe_release()


def play_click() -> None:
    """Short confirmation click. Silently does nothing off Android."""
    try:
        generator = _get_generator()
    except Exception:
        # Desktop, TV without the service, or jnius unavailable: silence
        # is the designed behavior, not an error.
        logger.debug("SFX unavailable (not Android/JVM)")
        return
    try:
        played = generator.startTone(generator.TONE_PROP_BEEP, _TONE_MS)
        if played is False:
            # startTone returns boolean: False = busy/in-call, not success.
            logger.debug("SFX tone suppressed (resource busy)")
    except Exception:
        # startTone threw after construction (old leak: bare return without
        # release). The singleton owns the generator, so nothing leaks and
        # the next tap reuses it — just log.
        logger.debug("SFX startTone failed", exc_info=True)
