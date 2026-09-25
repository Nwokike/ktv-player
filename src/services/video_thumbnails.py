"""Local-video thumbnail cache — MX-Player-style frame previews (Android).

Mirrors the proven `logo_cache` pattern: content-hash keys, a cache
directory under the app cache, best-effort extraction that can never break
a scan. Frames are grabbed with `android.media.MediaMetadataRetriever`
through pyjnius (already shipped in the APK via the PiP service); on every
other platform extraction is a no-op and cards keep their icon.

Cache key = sha256(path | mtime | size): re-editing a video invalidates
its frame, a stable library reuses it across scans.
"""

import asyncio
import contextlib
import hashlib
import logging
import os
import time

logger = logging.getLogger(__name__)

_cache_env = os.getenv("FLET_APP_STORAGE_CACHE")
THUMBNAIL_CACHE_DIR = (
    os.path.join(_cache_env, "video-thumbnails")
    if _cache_env
    else os.path.join("storage", "video-thumbnails")
)
THUMBNAIL_TTL = 30 * 24 * 60 * 60  # 30 days
_FRAME_AT_US = 1_000_000  # grab around 1s into the clip
_JPEG_QUALITY = 85
_PREWARM_LIMIT = 40
_EXTRACT_CONCURRENCY = 2


def thumbnail_path(video) -> str:
    """Deterministic cache path for a video (keyed by content identity)."""
    try:
        modified = float(getattr(video, "modified", 0) or 0)
    except (TypeError, ValueError):
        modified = 0.0
    key = f"{video.path}|{modified:.0f}|{video.size}".encode()
    safe = hashlib.sha256(key).hexdigest()[:16]
    return os.path.join(THUMBNAIL_CACHE_DIR, f"{safe}.jpg")


def get_cached_thumbnail(video) -> str | None:
    """Return a cached thumbnail path if one exists (and is fresh)."""
    path = thumbnail_path(video)
    try:
        if not os.path.exists(path):
            return None
        if time.time() - os.path.getmtime(path) > THUMBNAIL_TTL:
            os.remove(path)
            return None
        return path
    except OSError:
        return None


def _extract_sync(video_path: str, out_path: str, content_uri: str = "") -> bool:
    """Grab one frame via MediaMetadataRetriever. Runs in a worker thread.

    Prefers the MediaStore content URI: under scoped storage a raw path can
    be unreadable even with media permission granted. Falls back to the path
    (and to the URI failing) so nothing regresses on devices where either
    handle works.
    """
    from jnius import autoclass

    MediaMetadataRetriever = autoclass("android.media.MediaMetadataRetriever")
    CompressFormat = autoclass("android.graphics.Bitmap$CompressFormat")
    FileOutputStream = autoclass("java.io.FileOutputStream")
    File = autoclass("java.io.File")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # Temp file first: a half-written JPEG must never appear in the cache.
    tmp_path = out_path + ".tmp"
    mr = MediaMetadataRetriever()
    try:
        if content_uri:
            try:
                from services.local_scanner import _android_activity

                activity = _android_activity(autoclass)
                if activity is not None:
                    Uri = autoclass("android.net.Uri")
                    mr.setDataSource(activity, Uri.parse(content_uri))
                else:
                    mr.setDataSource(video_path)
            except Exception:
                logger.debug(
                    "content:// source failed for %s, falling back to path",
                    video_path,
                )
                mr.setDataSource(video_path)
        else:
            mr.setDataSource(video_path)
        bitmap = mr.getFrameAtTime(_FRAME_AT_US)
        if bitmap is None:
            return False
        try:
            stream = FileOutputStream(tmp_path)
            try:
                ok = bitmap.compress(CompressFormat.JPEG, _JPEG_QUALITY, stream)
            finally:
                stream.close()
        finally:
            bitmap.recycle()
        if not ok:
            return False
        # renameTo returns a boolean — an unchecked failure left a cache
        # entry pointing at a file that was never created (broken images).
        if not File(tmp_path).renameTo(File(out_path)):
            logger.debug("Thumbnail rename failed for %s", out_path)
            return False
        return True
    finally:
        with contextlib.suppress(Exception):
            mr.release()


async def extract_thumbnail(video) -> str | None:
    """Extract (or reuse) a thumbnail for one video. None on any failure."""
    cached = get_cached_thumbnail(video)
    if cached:
        return cached
    path = thumbnail_path(video)
    try:
        ok = await asyncio.to_thread(
            _extract_sync,
            video.path,
            path,
            getattr(video, "content_uri", "") or "",
        )
    except ImportError:
        return None  # not Android (no pyjnius / no JVM)
    except Exception:
        logger.debug("Thumbnail extraction failed for %s", video.path, exc_info=True)
        with contextlib.suppress(OSError):
            os.remove(path + ".tmp")
        return None
    if not ok:
        with contextlib.suppress(OSError):
            os.remove(path + ".tmp")
        return None
    return path


async def prewarm_thumbnails(videos, page, limit: int = _PREWARM_LIMIT) -> int:
    """Fill `video.thumbnail` for the first `limit` videos, then one refresh.

    Returns how many thumbnails are now available. Safe to call on any
    platform: extraction no-ops off-Android and the page update is
    suppressed when nothing changed.
    """
    pending = []
    changed = 0
    for video in list(videos)[:limit]:
        if not video.thumbnail:
            cached = get_cached_thumbnail(video)
            if cached:
                video.thumbnail = cached
                changed += 1
            else:
                pending.append(video)
    filled = changed
    if pending:
        sem = asyncio.Semaphore(_EXTRACT_CONCURRENCY)

        async def _one(video):
            async with sem:
                path = await extract_thumbnail(video)
                if path:
                    video.thumbnail = path
                    return True
                return False

        # One bad video must not take the rest of the batch with it.
        results = await asyncio.gather(
            *(_one(v) for v in pending), return_exceptions=True
        )
        filled += sum(1 for r in results if r is True)
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
    return filled
