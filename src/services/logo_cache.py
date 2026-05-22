import asyncio
import contextlib
import hashlib
import os
import time

import httpx

from core.constants import LOGO_CACHE_MAX_FILES, LOGO_DOWNLOAD_TIMEOUT

LOGO_CACHE_DIR = os.path.join("storage", "logos")
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
_logo_queue: asyncio.Queue[str] | None = None
_logo_workers_started = False

os.makedirs(LOGO_CACHE_DIR, exist_ok=True)


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


def _evict_oldest_if_needed():
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
        resp = await client.get(logo_url, timeout=LOGO_DOWNLOAD_TIMEOUT)
        resp.raise_for_status()

        detected = _detect_image_type(resp.content)
        if detected is None:
            return None

        safe_name = hashlib.sha256(logo_url.encode()).hexdigest()[:16]
        cached_path = os.path.join(LOGO_CACHE_DIR, f"{safe_name}.{detected}")

        with open(cached_path, "wb") as f:
            f.write(resp.content)
        return cached_path
    except Exception:
        return None
    finally:
        _in_flight.discard(logo_url)


async def _logo_worker():
    while True:
        url = await _logo_queue.get()
        try:
            await _download_one(url)
        finally:
            _logo_queue.task_done()


def _ensure_queue():
    global _logo_queue, _logo_workers_started
    if _logo_queue is None:
        _logo_queue = asyncio.Queue(maxsize=_LOGO_QUEUE_MAX)
    if not _logo_workers_started:
        _logo_workers_started = True
        for _ in range(_LOGO_WORKERS):
            asyncio.create_task(_logo_worker())


def enqueue_logo_download(logo_url: str):
    if not logo_url or logo_url == "/icon.png":
        return
    if get_cached_logo(logo_url):
        return
    if logo_url in _in_flight:
        return

    _evict_oldest_if_needed()
    _ensure_queue()
    asyncio.create_task(_logo_queue.put(logo_url))


async def download_logo(
    logo_url: str, http_client: httpx.AsyncClient | None = None
) -> str | None:
    if not logo_url or logo_url == "/icon.png":
        return None

    _evict_oldest_if_needed()
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
