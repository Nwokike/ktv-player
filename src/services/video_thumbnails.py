"""Local-video thumbnail cache — MX-Player-style frame previews (Android).

Mirrors the proven `logo_cache` pattern: content-hash keys, a cache
directory under the app cache, best-effort extraction that can never break
a scan. Frames are grabbed with `android.media.MediaMetadataRetriever`
through pyjnius (already shipped in the APK via the PiP service); on every
other platform extraction is a no-op and cards keep their icon.

Cache key = sha256(abspath | mtime-ms | size): re-editing a video
invalidates its frame, a stable library reuses it across scans.
"""

import asyncio
import contextlib
import hashlib
import logging
import os
import time

import anyio

logger = logging.getLogger(__name__)


def _cache_dir() -> str:
    cache_env = os.getenv("FLET_APP_STORAGE_CACHE")
    return (
        os.path.join(cache_env, "video-thumbnails")
        if cache_env
        else os.path.abspath(os.path.join("storage", "video-thumbnails"))
    )


THUMBNAIL_TTL = 30 * 24 * 60 * 60  # 30 days
_FRAME_AT_US = 1_000_000  # grab around 1s into the clip
_JPEG_QUALITY = 85
_PREWARM_LIMIT = 40
_EXTRACT_CONCURRENCY = 2
_EXTRACT_TIMEOUT = 10.0
# Unbounded growth guard for long-lived TV boxes (stale files for deleted /
# re-edited videos otherwise accumulate forever).
_MAX_THUMBNAILS = 500

# Global concurrency + in-flight dedup: the old per-call semaphore let two
# overlapping prewarm passes (scroll/scan) run 2*N retrievers and race the
# same .tmp. Module scope makes the bound global.
_EXTRACT_SEM = asyncio.Semaphore(_EXTRACT_CONCURRENCY)

# Per-path in-flight dedup: two tasks for the same video must not write the
# same .tmp concurrently (renameTo race in _extract_sync).
_extracting: set[tuple[str, int, int]] = set()
_extract_lock = asyncio.Lock()


def _video_key(video) -> tuple[str, str, int] | None:
    """(path, mtime_ms, size) or None when the model is malformed.

    abspath + normcase (no symlink/relative/duplicate keys); sub-second
    mtime kept in ms (the old :.0f truncation collided edits within a
    second); size None → 0 (not the literal string "None").
    """
    path = getattr(video, "path", None)
    if not path or not isinstance(path, str):
        return None
    try:
        modified = float(getattr(video, "modified", 0) or 0)
    except (TypeError, ValueError):
        modified = 0.0
    try:
        size = int(getattr(video, "size", 0) or 0)
    except (TypeError, ValueError):
        size = 0
    norm = os.path.normcase(os.path.abspath(path))
    return norm, int(modified * 1000), size


def thumbnail_path(video) -> str:
    """Deterministic cache path for a video (keyed by content identity)."""
    key = _video_key(video)
    if key is None:
        raise AttributeError("video has no usable path")
    norm, mtime_ms, size = key
    digest = hashlib.sha256(f"{norm}|{mtime_ms}|{size}".encode()).hexdigest()[:16]
    return os.path.join(_cache_dir(), f"{digest}.jpg")


def get_cached_thumbnail(video) -> str | None:
    """Return a cached thumbnail path if one exists (and is fresh)."""
    try:
        path = thumbnail_path(video)
    except AttributeError:
        return None
    try:
        if not os.path.exists(path):
            return None
        if time.time() - os.path.getmtime(path) > THUMBNAIL_TTL:
            os.remove(path)
            return None
        return path
    except OSError:
        return None


def purge_stale_thumbnails(max_age: float = THUMBNAIL_TTL) -> int:
    """Delete expired thumbnails + orphan .tmp files. Returns removals."""
    removed = 0
    try:
        cache_dir = _cache_dir()
        now = time.time()
        for f in os.listdir(cache_dir):
            full = os.path.join(cache_dir, f)
            if f.endswith(".tmp"):
                with contextlib.suppress(OSError):
                    os.remove(full)
                    removed += 1
                continue
            if not f.endswith(".jpg"):
                continue
            try:
                if now - os.path.getmtime(full) > max_age:
                    os.remove(full)
                    removed += 1
            except OSError:
                continue
        # Count cap (newest kept): TTL alone never bounds a big library.
        try:
            entries = []
            for f in os.listdir(cache_dir):
                if f.endswith(".jpg"):
                    full = os.path.join(cache_dir, f)
                    try:
                        entries.append((os.path.getmtime(full), full))
                    except OSError:
                        continue
            if len(entries) > _MAX_THUMBNAILS:
                entries.sort()
                for _, full in entries[: len(entries) - _MAX_THUMBNAILS]:
                    with contextlib.suppress(OSError):
                        os.remove(full)
                        removed += 1
        except OSError:
            pass
    except OSError:
        pass
    return removed


def _extract_sync(video_path: str, out_path: str, content_uri: str = "") -> bool:
    """Grab one frame via MediaMetadataRetriever. Runs in a worker thread.

    This is an Android feature: Android ships MediaMetadataRetriever in the
    APK, and nothing else on any platform is required to exist for it.
    Desktop keeps the movie icon (documented, intentional) rather than
    taking on a frame decoder that most systems do not have installed.

    Prefers the MediaStore content URI: under scoped storage a raw path can
    be unreadable even with media permission granted. Falls back to the path
    (and to the URI failing) so nothing regresses on devices where either
    handle works.

    JNI threading: pyjnius auto-attaches worker threads on first JNI call
    (same as the screenshot/scanner paths) — no explicit attach needed, and
    the retriever is released in `finally` on the same thread.
    """
    from jnius import autoclass

    MediaMetadataRetriever = autoclass("android.media.MediaMetadataRetriever")
    CompressFormat = autoclass("android.graphics.Bitmap$CompressFormat")
    mr = None
    try:
        mr = MediaMetadataRetriever()
        if content_uri:
            activity = None
            try:
                from services.android_bridge import get_activity

                activity = get_activity()
            except Exception:
                activity = None
            if activity is not None:
                Uri = autoclass("android.net.Uri")
                mr.setDataSource(activity, Uri.parse(content_uri))
            else:
                mr.setDataSource(video_path)
        else:
            mr.setDataSource(video_path)
        bitmap = mr.getFrameAtTime(_FRAME_AT_US)
        if bitmap is None:
            # Sub-second clips: the 1s frame doesn't exist — retry at 0.
            try:
                bitmap = mr.getFrameAtTime(0)
            except Exception:
                bitmap = None
            if bitmap is None:
                return False
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        # Temp file first: a half-written JPEG must never appear in the cache.
        tmp_path = out_path + ".tmp"
        try:
            stream = autoclass("java.io.FileOutputStream")(tmp_path)
            try:
                ok = bitmap.compress(CompressFormat.JPEG, _JPEG_QUALITY, stream)
                stream.flush()
            finally:
                with contextlib.suppress(Exception):
                    stream.close()
        finally:
            with contextlib.suppress(Exception):
                bitmap.recycle()
        if not ok:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            return False
        # os.replace (atomic, raises on error) instead of renameTo (boolean,
        # silent cross-filesystem/OEM failures).
        try:
            os.replace(tmp_path, out_path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            return False
        return True
    finally:
        if mr is not None:
            with contextlib.suppress(Exception):
                mr.release()


async def extract_thumbnail(video) -> str | None:
    """Extract (or reuse) a thumbnail for one video. None on any failure.

    Globally deduplicated + throttled: concurrent calls for the same video
    collapse to one extraction instead of racing the same output file.
    """
    key = None
    with contextlib.suppress(Exception):
        key = _video_key(video)
    if key is not None:
        async with _extract_lock:
            if key in _extracting:
                return None
            _extracting.add(key)
    try:
        async with _EXTRACT_SEM:
            return await _extract_inner(video)
    finally:
        if key is not None:
            async with _extract_lock:
                _extracting.discard(key)


async def _extract_inner(video) -> str | None:
    try:
        cached = get_cached_thumbnail(video)
    except Exception:
        return None
    if cached:
        return cached
    try:
        path = thumbnail_path(video)
    except AttributeError:
        return None
    content_uri = getattr(video, "content_uri", "") or ""
    video_path = getattr(video, "path", "") or ""
    try:
        ok = await asyncio.wait_for(
            anyio.to_thread.run_sync(_extract_sync, video_path, path, content_uri),
            timeout=_EXTRACT_TIMEOUT,
        )
    except ImportError:
        return None  # not Android (no pyjnius / no JVM)
    except TimeoutError:
        logger.debug("Thumbnail extraction timed out for %s", video_path)
        with contextlib.suppress(OSError):
            os.remove(path + ".tmp")
        return None
    except Exception:
        logger.debug("Thumbnail extraction failed for %s", video_path, exc_info=True)
        with contextlib.suppress(OSError):
            os.remove(path + ".tmp")
        return None
    if not ok:
        with contextlib.suppress(OSError):
            os.remove(path + ".tmp")
        return None
    return path


async def prewarm_thumbnails(
    videos, page, limit: int = _PREWARM_LIMIT
) -> tuple[int, int]:
    """Fill `video.thumbnail` for the first `limit` videos, then one refresh.

    Returns (filled_this_call, total_available): the old "how many are now
    available" docstring lied — pre-populated grids returned 0. Safe on any
    platform: extraction no-ops off-Android and the page update is
    suppressed when nothing changed. Corrupt files can't stall the grid
    (per-extract timeout); one malformed model can't abort the batch.
    """
    try:
        items = list(videos)[:limit]
    except TypeError:
        return (0, 0)
    changed = 0
    available = 0
    pending = []
    for video in items:
        try:
            if getattr(video, "thumbnail", None):
                available += 1
                continue
            cached = get_cached_thumbnail(video)
        except Exception:
            logger.debug("Thumbnail model skipped", exc_info=True)
            continue
        if cached:
            try:
                video.thumbnail = cached
            except Exception as ex:
                logger.debug("Thumbnail assignment skipped: %s", ex)
                continue
            changed += 1
            available += 1
        else:
            pending.append(video)
    filled = changed
    if pending:

        async def _one(video):
            # Dedup + throttling live in extract_thumbnail (module scope);
            # prewarm just fans out.
            path = await extract_thumbnail(video)
            if path:
                try:
                    video.thumbnail = path
                except Exception:
                    return False
                return True
            return False

        # One bad video must not take the rest of the batch with it — and
        # failures are logged with the URL instead of vanishing.
        results = await asyncio.gather(
            *(_one(v) for v in pending), return_exceptions=True
        )
        for video, r in zip(pending, results, strict=False):
            if r is True:
                filled += 1
                available += 1
            elif isinstance(r, Exception):
                logger.debug(
                    "Thumbnail prewarm failed for %s: %s",
                    getattr(video, "path", "?"),
                    r,
                )
    if filled and page is not None:
        try:
            # Async update keeps the grid responsive on TV.
            update = getattr(page, "update_async", None)
            if callable(update):
                await update()
            else:
                page.update()
        except Exception:
            logger.debug("Thumbnail refresh update failed", exc_info=True)
    return (filled, available)
