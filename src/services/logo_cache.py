import contextlib
import hashlib
import os
import time

import httpx

LOGO_CACHE_DIR = os.path.join("storage", "logos")
LOGO_CACHE_TTL = 7 * 24 * 60 * 60


def _get_cached_path(logo_url: str) -> str:
    safe_name = hashlib.md5(logo_url.encode()).hexdigest()[:12]
    ext = "png"
    if "." in logo_url:
        ext = logo_url.rsplit(".", 1)[-1].split("?")[0].lower()
        if ext not in ("png", "jpg", "jpeg", "gif", "webp", "svg"):
            ext = "png"
    return os.path.join(LOGO_CACHE_DIR, f"{safe_name}.{ext}")


def get_cached_logo(logo_url: str) -> str | None:
    if not logo_url or logo_url == "/icon.png":
        return None

    cached_path = _get_cached_path(logo_url)
    if os.path.exists(cached_path):
        age = time.time() - os.path.getmtime(cached_path)
        if age < LOGO_CACHE_TTL:
            return cached_path
        with contextlib.suppress(OSError):
            os.remove(cached_path)
    return None


async def download_logo(logo_url: str) -> str | None:
    if not logo_url or logo_url == "/icon.png":
        return None

    os.makedirs(LOGO_CACHE_DIR, exist_ok=True)
    cached_path = _get_cached_path(logo_url)

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(logo_url)
            resp.raise_for_status()
            with open(cached_path, "wb") as f:
                f.write(resp.content)
            return cached_path
    except Exception:
        return None


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
