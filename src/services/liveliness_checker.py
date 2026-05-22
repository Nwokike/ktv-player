import asyncio
import logging

import httpx

from core.constants import (
    LIVELINESS_BATCH_SIZE,
    LIVELINESS_SEMAPHORE,
    LIVELINESS_UPDATE_INTERVAL,
)
from core.theme import AppColors
from services.http_client import get_http_client
from services.liveliness import liveliness_cache

logger = logging.getLogger(__name__)


class LivelinessChecker:
    def __init__(self, page_obj):
        self.page_obj = page_obj
        self._semaphore = asyncio.Semaphore(LIVELINESS_SEMAPHORE)

    def _get_http_client(self) -> httpx.AsyncClient:
        return get_http_client()

    async def check_single(self, url: str) -> tuple[str, bool]:
        cached = liveliness_cache.get(url)
        if cached is not None:
            return (url, cached)

        async with self._semaphore:
            try:
                client = self._get_http_client()
                try:
                    resp = await client.head(url, timeout=2.0)
                    is_live = resp.status_code < 400
                except Exception:
                    resp = await client.get(
                        url,
                        headers={"Range": "bytes=0-0"},
                        timeout=2.0,
                    )
                    is_live = resp.status_code in (200, 206, 301, 302, 304)
                liveliness_cache.set(url, is_live)
                return (url, is_live)
            except Exception:
                liveliness_cache.set(url, False)
                return (url, False)

    async def fire_batch(self, cards_data: list):
        for i in range(0, len(cards_data), LIVELINESS_BATCH_SIZE):
            batch = cards_data[i : i + LIVELINESS_BATCH_SIZE]
            tasks = [self.check_single(cd["url"]) for cd in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for cd, result in zip(batch, results, strict=True):
                if isinstance(result, tuple):
                    _, is_live = result
                    cd["indicator"].bgcolor = (
                        AppColors.SUCCESS if is_live else AppColors.ERROR
                    )
                else:
                    cd["indicator"].bgcolor = AppColors.ERROR

            batch_num = i // LIVELINESS_BATCH_SIZE
            is_last = (i + LIVELINESS_BATCH_SIZE) >= len(cards_data)
            if is_last or (batch_num % LIVELINESS_UPDATE_INTERVAL == 0):
                try:
                    self.page_obj.update()
                except Exception:
                    pass

            if not is_last:
                await asyncio.sleep(0.05)

        # Persist dirty cache entries to DB
        dirty = liveliness_cache.drain_dirty()
        if dirty:
            from database.manager import db_manager

            await db_manager.save_liveliness_batch(dirty)

    def collect_cards_data(self, grid) -> list:
        cards_data = []
        for wrapper in grid.controls:
            card = getattr(wrapper, "content", None)
            if card and getattr(card, "data", None):
                url = card.data.get("url")
                indicator = card.data.get("indicator")
                if url and indicator:
                    cards_data.append({"url": url, "indicator": indicator})
        return cards_data

    async def close(self):
        pass
