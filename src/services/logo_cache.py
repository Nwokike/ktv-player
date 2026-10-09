import asyncio
import contextlib
import hashlib
import logging
import os
import time

import anyio
import httpx

from core.constants import LOGO_CACHE_MAX_FILES, LOGO_DOWNLOAD_TIMEOUT
from services.anyio_pools import TaskPool

logger = logging.getLogger(__name__)


def _cache_dir() -> str:
    """Resolve per call (not import time): tests and late storage setup can
    change FLET_APP_STORAGE_CACHE after import."""
    cache_env = os.getenv("FLET_APP_STORAGE_CACHE")
    return (
        os.path.join(cache_env, "logos")
        if cache_env
        else os.path.join("storage", "logos")
    )


LOGO_CACHE_TTL = 7 * 24 * 60 * 60
_LOGO_QUEUE_MAX = 200
_LOGO_WORKERS = 4

_IMAGE_SIGNATURES = {
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpg",
    b"GIF87a": "gif",
    b"GIF89a": "gif",
}

# NOTE: SVG is intentionally NOT cached. Playlists carry <svg text (not magic
# bytes), ft.Image renders remote SVG directly, and a text-sniffing cache
# would store markup as ".svg" with no size bound. Documented, not a silent
# miss: _detect_image_type returns None → failed-TTL → remote render.

_in_flight: set[str] = set()
_queued: set[str] = set()
_failed_logos: dict[str, float] = {}  # url -> timestamp of last failure
_pool: TaskPool | None = None
_cache_dir_initialized = False
_last_evict_time = 0.0
_last_failed_evict_time = 0.0
_FAILED_LOGO_TTL = 300  # Don't retry failed logos for 5 minutes
# A hostile or broken host must not be able to make the app buffer an
# unbounded body: refuse anything past this and treat it as a failure.
LOGO_MAX_BYTES = 2 * 1024 * 1024
_FAILED_LOGO_EVICT_INTERVAL = 60.0  # Evict stale failed entries every 60s


def _detect_image_type(data: bytes) -> str | None:
    for sig, fmt in _IMAGE_SIGNATURES.items():
        if data[: len(sig)] == sig:
            return fmt
    if data[:2] == b"\xff\xd8":
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _safe_name(logo_url: str) -> str:
    return hashlib.sha256(logo_url.encode()).hexdigest()[:16]


def _get_cached_path(logo_url: str, ext: str = "png") -> str:
    return os.path.join(_cache_dir(), f"{_safe_name(logo_url)}.{ext}")


def _ensure_cache_dir():
    global _cache_dir_initialized
    if not _cache_dir_initialized:
        os.makedirs(_cache_dir(), exist_ok=True)
        _cache_dir_initialized = True


def _failed_recently(logo_url: str) -> bool:
    failed_at = _failed_logos.get(logo_url)
    return bool(failed_at and (time.time() - failed_at) < _FAILED_LOGO_TTL)


async def _evict_oldest_if_needed():
    global _last_evict_time
    now = time.time()
    if now - _last_evict_time < 30.0:
        return
    _last_evict_time = now

    def _evict_sync():
        try:
            entries = []
            for f in os.listdir(_cache_dir()):
                # .part files are crash debris, not cache entries: never count
                # them toward the cap, purge them instead.
                if f.endswith(".part"):
                    with contextlib.suppress(OSError):
                        os.remove(os.path.join(_cache_dir(), f))
                    continue
                try:
                    entries.append((f, os.path.getmtime(os.path.join(_cache_dir(), f))))
                except OSError:
                    # Raced with a concurrent write/delete: skip the file,
                    # don't abort the whole eviction.
                    continue
            if len(entries) >= LOGO_CACHE_MAX_FILES:
                entries.sort(key=lambda x: x[1])
                to_remove = len(entries) - LOGO_CACHE_MAX_FILES + 10
                for f, _ in entries[:to_remove]:
                    with contextlib.suppress(OSError):
                        os.remove(os.path.join(_cache_dir(), f))
        except OSError:
            pass

    await anyio.to_thread.run_sync(_evict_sync)


def get_cached_logo(logo_url: str) -> str | None:
    if not logo_url or logo_url == "/icon.png":
        return None

    safe_name = _safe_name(logo_url)
    for ext in ("png", "jpg", "gif", "webp"):
        cached_path = os.path.join(_cache_dir(), f"{safe_name}.{ext}")
        if os.path.exists(cached_path):
            try:
                age = time.time() - os.path.getmtime(cached_path)
            except OSError:
                continue
            if age < LOGO_CACHE_TTL:
                return cached_path
            with contextlib.suppress(OSError):
                os.remove(cached_path)
    return None


def _valid_logo_url(logo_url: object) -> str | None:
    """http/https only. file://, ftp://, and internal addresses never reach
    the HTTP client (failure was previously swallowed as a generic miss)."""
    if not isinstance(logo_url, str) or not logo_url or logo_url == "/icon.png":
        return None
    cleaned = logo_url.strip()
    if not cleaned.startswith(("http://", "https://")):
        return None
    return cleaned


async def _download_one(
    logo_url: str, http_client: httpx.AsyncClient | None = None
) -> str | None:
    cleaned = _valid_logo_url(logo_url)
    if cleaned is None:
        return None
    logo_url = cleaned

    if logo_url in _in_flight:
        return None
    if _failed_recently(logo_url):
        return None
    _in_flight.add(logo_url)

    try:
        _ensure_cache_dir()
        from services.http_client import get_http_client

        # The caller's client wins: download_logo() has always accepted one
        # and never passed it down, so the parameter was dead.
        client = http_client or get_http_client()
        logo_timeout = httpx.Timeout(
            LOGO_DOWNLOAD_TIMEOUT, connect=3.0, read=4.0, write=4.0, pool=2.0
        )
        # Streamed, capped read: `resp.content` buffers the whole body
        # in memory first, which a 50MB response would make visible on
        # low-memory Android devices.
        buf = bytearray()
        async with client.stream("GET", logo_url, timeout=logo_timeout) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes(65536):
                buf.extend(chunk)
                if len(buf) > LOGO_MAX_BYTES:
                    logger.warning(
                        "Refusing oversized logo (%d bytes): %s", len(buf), logo_url
                    )
                    _failed_logos[logo_url] = time.time()
                    return None
        content = bytes(buf)

        detected = _detect_image_type(content)
        if detected is None:
            _failed_logos[logo_url] = time.time()
            return None

        safe_name = _safe_name(logo_url)
        cache_dir = _cache_dir()
        cached_path = os.path.join(cache_dir, f"{safe_name}.{detected}")

        def _write_file(path: str, data: bytes):
            # Write beside the target, then rename: a crash mid-download
            # must never leave a half-written image being served as a logo
            # for the next week (cache files are content-addressed and
            # only expire by TTL).
            partial = path + ".part"
            try:
                with open(partial, "wb") as f:
                    f.write(data)
                os.replace(partial, path)
            except Exception:
                with contextlib.suppress(OSError):
                    os.unlink(partial)
                raise

        await anyio.to_thread.run_sync(_write_file, cached_path, content)
        # Sibling-extension cleanup: a png→jpg content change used to leave
        # the stale .png shadowing the fresh .jpg (get_cached_logo probes
        # png first).
        for ext in ("png", "jpg", "gif", "webp"):
            if ext != detected:
                with contextlib.suppress(OSError):
                    stale = os.path.join(cache_dir, f"{safe_name}.{ext}")
                    if os.path.exists(stale):
                        os.remove(stale)
        await _evict_oldest_if_needed()
        return cached_path
    except asyncio.CancelledError:
        raise
    except Exception as ex:
        logger.debug("Logo download failed for %s: %s", logo_url, ex)
        _failed_logos[logo_url] = time.time()
        return None
    finally:
        _in_flight.discard(logo_url)
        _queued.discard(logo_url)


async def _download_worker(url: str) -> None:
    try:
        await _download_one(url)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Logo download failed for %s", url)


def _get_pool() -> TaskPool:
    global _pool
    if _pool is None:
        _pool = TaskPool(
            "logo",
            _download_worker,
            workers=_LOGO_WORKERS,
            queue_max=_LOGO_QUEUE_MAX,
        )
    return _pool


def _ensure_queue() -> bool:
    """Start the worker pool. False when no running loop (caller must
    handle: the old version raised RuntimeError out of enqueue)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    _get_pool().ensure_started()
    return True


def shutdown_workers():
    """Sync emergency stop: cancel the pool supervisor.

    Prefer ashutdown_workers() in async contexts (app close) — it drains
    first and awaits the join.
    """
    global _pool
    if _pool is not None and _pool._supervisor is not None:
        _pool._supervisor.cancel()
    _pool = None
    _queued.clear()
    _in_flight.clear()


async def ashutdown_workers():
    """Drain the queue, stop + join the pool, clear all transient sets."""
    global _pool
    if _pool is not None:
        await _pool.stop(drain=True)
    _pool = None
    _queued.clear()
    _in_flight.clear()


def _evict_stale_failed_logos():
    """Remove _failed_logos entries older than _FAILED_LOGO_TTL."""
    global _last_failed_evict_time
    now = time.time()
    if now - _last_failed_evict_time < _FAILED_LOGO_EVICT_INTERVAL:
        return
    _last_failed_evict_time = now
    stale = [url for url, ts in _failed_logos.items() if (now - ts) >= _FAILED_LOGO_TTL]
    for url in stale:
        _failed_logos.pop(url, None)


def enqueue_logo_download(logo_url: str):
    cleaned = _valid_logo_url(logo_url)
    if cleaned is None:
        return
    logo_url = cleaned
    if get_cached_logo(logo_url):
        return
    if logo_url in _in_flight or logo_url in _queued:
        return
    if _failed_recently(logo_url):
        return

    _ensure_cache_dir()
    _evict_stale_failed_logos()
    if not _ensure_queue():
        logger.debug("Logo enqueue with no running loop for %s", logo_url)
        return

    # Non-blocking insert: the old create_task was untracked, so shutdown
    # could neither cancel nor await it.
    _queued.add(logo_url)
    if not _get_pool().submit(logo_url):
        _queued.discard(logo_url)
        logger.debug("Logo queue full or stopped, dropping: %s", logo_url)


async def download_logo(
    logo_url: str,
    http_client: httpx.AsyncClient | None = None,
) -> str | None:
    cleaned = _valid_logo_url(logo_url)
    if cleaned is None:
        return None
    logo_url = cleaned

    # Positive cache first (the old path always fetched): a fresh file costs
    # nothing. Failed-TTL second: a dead host isn't hammered per list rebuild.
    cached = get_cached_logo(logo_url)
    if cached:
        return cached
    if _failed_recently(logo_url):
        return None

    _ensure_cache_dir()
    await _evict_oldest_if_needed()
    return await _download_one(logo_url, http_client)


async def resolve_logo(logo_url: str) -> str:
    if not logo_url or logo_url == "/icon.png":
        return "/icon.png"

    cached = get_cached_logo(logo_url)
    if cached:
        return cached

    result = await download_logo(logo_url)
    if result:
        return result

    return logo_url
