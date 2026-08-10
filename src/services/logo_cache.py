import asyncio
import contextlib
import hashlib
import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

from core.constants import LOGO_CACHE_MAX_FILES, LOGO_DOWNLOAD_TIMEOUT

_cache_env = os.getenv("FLET_APP_STORAGE_CACHE")
LOGO_CACHE_DIR = os.path.join(_cache_env, "logos") if _cache_env else os.path.join("storage", "logos")
LOGO_CACHE_TTL = 7 * 24 * 60 * 60
_LOGO_QUEUE_MAX = 200
_LOGO_WORKERS = 4

_IMAGE_SIGNATURES = {
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpg",
    b"GIF87a": "gif",
    b"GIF89a": "gif",
}

_in_flight: set[str] = set()
_failed_logos: dict[str, float] = {}  # url -> timestamp of last failure
_logo_queue: asyncio.Queue[str] | None = None
_logo_worker_tasks: list[asyncio.Task] = []
_logo_workers_started = False
_cache_dir_initialized = False
_last_evict_time = 0.0
_last_failed_evict_time = 0.0
_FAILED_LOGO_TTL = 300  # Don't retry failed logos for 5 minutes
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


def _get_cached_path(logo_url: str, ext: str = "png") -> str:
    safe_name = hashlib.sha256(logo_url.encode()).hexdigest()[:16]
    return os.path.join(LOGO_CACHE_DIR, f"{safe_name}.{ext}")


def _ensure_cache_dir():
    global _cache_dir_initialized
    if not _cache_dir_initialized:
        os.makedirs(LOGO_CACHE_DIR, exist_ok=True)
        _cache_dir_initialized = True


async def _evict_oldest_if_needed():
    global _last_evict_time
    now = time.time()
    if now - _last_evict_time < 30.0:
        return
    _last_evict_time = now

    def _evict_sync():
        try:
            files = [
                (f, os.path.getmtime(os.path.join(LOGO_CACHE_DIR, f)))
                for f in os.listdir(LOGO_CACHE_DIR)
            ]
            if len(files) >= LOGO_CACHE_MAX_FILES:
                files.sort(key=lambda x: x[1])
                to_remove = len(files) - LOGO_CACHE_MAX_FILES + 10
                for f, _ in files[:to_remove]:
                    with contextlib.suppress(OSError):
                        os.remove(os.path.join(LOGO_CACHE_DIR, f))
        except OSError:
            pass

    await asyncio.to_thread(_evict_sync)


def get_cached_logo(logo_url: str) -> str | None:
    if not logo_url or logo_url == "/icon.png":
        return None

    safe_name = hashlib.sha256(logo_url.encode()).hexdigest()[:16]
    for ext in ("png", "jpg", "gif", "webp"):
        cached_path = os.path.join(LOGO_CACHE_DIR, f"{safe_name}.{ext}")
        if os.path.exists(cached_path):
            age = time.time() - os.path.getmtime(cached_path)
            if age < LOGO_CACHE_TTL:
                return cached_path
            with contextlib.suppress(OSError):
                os.remove(cached_path)
    return None


async def _download_one(logo_url: str) -> str | None:
    if not logo_url or logo_url == "/icon.png":
        return None

    if logo_url in _in_flight:
        return None
    _in_flight.add(logo_url)

    try:
        from services.http_client import get_http_client

        client = get_http_client()
        logo_timeout = httpx.Timeout(LOGO_DOWNLOAD_TIMEOUT, connect=3.0, read=4.0)
        resp = await client.get(logo_url, timeout=logo_timeout)
        resp.raise_for_status()

        detected = _detect_image_type(resp.content)
        if detected is None:
            _failed_logos[logo_url] = time.time()
            return None

        safe_name = hashlib.sha256(logo_url.encode()).hexdigest()[:16]
        cached_path = os.path.join(LOGO_CACHE_DIR, f"{safe_name}.{detected}")

        def _write_file(path: str, data: bytes):
            with open(path, "wb") as f:
                f.write(data)

        await asyncio.to_thread(_write_file, cached_path, resp.content)
        return cached_path
    except Exception:
        _failed_logos[logo_url] = time.time()
        return None
    finally:
        _in_flight.discard(logo_url)


async def _logo_worker():
    while True:
        try:
            url = await _logo_queue.get()
            try:
                await _download_one(url)
            except Exception:
                logger.exception("Logo download failed for %s", url)
            finally:
                _logo_queue.task_done()
        except Exception:
            await asyncio.sleep(1)


def _ensure_queue():
    global _logo_queue, _logo_workers_started
    if _logo_queue is None:
        _logo_queue = asyncio.Queue(maxsize=_LOGO_QUEUE_MAX)
    if not _logo_workers_started:
        _logo_workers_started = True
        for _ in range(_LOGO_WORKERS):
            _logo_worker_tasks.append(asyncio.create_task(_logo_worker()))


def shutdown_workers():
    """Cancel all background logo download workers. Call on app exit."""
    for task in _logo_worker_tasks:
        if not task.done():
            task.cancel()
    _logo_worker_tasks.clear()


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
    if not logo_url or logo_url == "/icon.png":
        return
    if get_cached_logo(logo_url):
        return
    if logo_url in _in_flight:
        return
    failed_at = _failed_logos.get(logo_url)
    if failed_at and (time.time() - failed_at) < _FAILED_LOGO_TTL:
        return

    _ensure_cache_dir()
    _evict_stale_failed_logos()
    _ensure_queue()

    async def _enqueue():
        try:
            await _logo_queue.put(logo_url)
        except Exception:
            logger.debug("Failed to enqueue logo download: %s", logo_url)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_enqueue())
    except RuntimeError:
        pass


async def download_logo(
    logo_url: str,
    http_client: httpx.AsyncClient | None = None,
) -> str | None:
    if not logo_url or logo_url == "/icon.png":
        return None

    _ensure_cache_dir()
    await _evict_oldest_if_needed()
    return await _download_one(logo_url)


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
