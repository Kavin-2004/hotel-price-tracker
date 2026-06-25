"""
============================================================
Hotel Dynamic Pricing — Scraper + Scheduler (SINGLE FILE)
============================================================
Stage 1: competitor hotel prices scrape + 5-min scheduler.
DB illa, pricing logic illa (intha stage la venam).

------------------------------------------------------------
SETUP (VS Code terminal la oru thadava run pannu):
------------------------------------------------------------
    pip install playwright apscheduler
    playwright install chromium

------------------------------------------------------------
RUN:
------------------------------------------------------------
    python app.py          ->  initial scrape + scheduler (every 5 min)
    python app.py once     ->  one scrape mattum, apparam exit (test)

Run pannumbodhu app.py irukkura folder la "mock_hotels.html"
auto create aagum (test page). Real site venam.
============================================================
"""

import asyncio
import logging
import os
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from playwright.async_api import async_playwright, Page
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger


# ============================================================
# CONFIG
# ============================================================
SCRAPE_INTERVAL_MINUTES = 5      # eththana nimisham ku oru thadava scrape
HEADLESS = True                  # False vechaa browser window visible (debug)
PAGE_TIMEOUT_MS = 30000          # page load wait limit


# ============================================================
# LOGGER
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("hotel_scraper")


# ============================================================
# MOCK TEST PAGE  (real site venam — out-of-box velai pannum)
# ============================================================
MOCK_HTML = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Mock Competitor Hotels</title></head>
<body>
  <h1>Hotels in Coimbatore</h1>
  <div id="hotel-list">
    <div class="hotel-card"><span class="hotel-name">The Residency Towers</span><span class="hotel-price">Rs.6,500</span></div>
    <div class="hotel-card"><span class="hotel-name">Vivanta Coimbatore</span><span class="hotel-price">Rs.8,200</span></div>
    <div class="hotel-card"><span class="hotel-name">Le Meridien</span><span class="hotel-price">Rs.7,900</span></div>
    <div class="hotel-card"><span class="hotel-name">Hotel City Tower</span><span class="hotel-price">Rs.4,300</span></div>
    <div class="hotel-card"><span class="hotel-name">Annapoorna Lifestyle</span><span class="hotel-price">Rs.5,150</span></div>
    <div class="hotel-card"><span class="hotel-name">Grand Regent</span><span class="hotel-price">Rs.3,800</span></div>
    <div class="hotel-card"><span class="hotel-name">KK Residency</span><span class="hotel-price">Rs.2,950</span></div>
    <div class="hotel-card"><span class="hotel-name">Park Plaza Coimbatore</span><span class="hotel-price">Rs.6,100</span></div>
  </div>
</body>
</html>"""


def write_mock_page() -> str:
    """Mock HTML ah script folder la write panni file:// URL return pannum."""
    folder = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(folder, "mock_hotels.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(MOCK_HTML)
    return "file://" + path


def get_targets() -> List[dict]:
    """Scrape panna vendiya sites. Real competitor add panna inga podu."""
    return [
        {"name": "mock-competitors", "url": write_mock_page()},
        # Real site example (HotelScraper la selectors maathunaa podhum):
        # {"name": "competitor-booking", "url": "https://example.com/coimbatore"},
    ]


# ============================================================
# DATA MODEL
# ============================================================
@dataclass
class ScrapedPrice:
    """Oru hotel-oda scraped data. DB venam — plain dataclass."""
    hotel_name: str
    price: float
    source: str
    scraped_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ============================================================
# SCRAPERS
# ============================================================
class BaseScraper(ABC):
    """Common Playwright lifecycle. Per-site scraper extract() implement pannum."""

    def __init__(self, name: str, url: str, headless: bool = True):
        self.name = name
        self.url = url
        self.headless = headless

    @abstractmethod
    async def extract(self, page: Page) -> List[ScrapedPrice]:
        raise NotImplementedError

    async def scrape(self) -> List[ScrapedPrice]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            try:
                page = await browser.new_page()
                await page.goto(
                    self.url,
                    wait_until="domcontentloaded",
                    timeout=PAGE_TIMEOUT_MS,
                )
                return await self.extract(page)
            finally:
                await browser.close()


class HotelScraper(BaseScraper):
    """Card-based hotel scraper. Real site-ku indha 3 selectors maathunaa podhum."""

    CARD_SELECTOR = ".hotel-card"
    NAME_SELECTOR = ".hotel-name"
    PRICE_SELECTOR = ".hotel-price"

    async def extract(self, page: Page) -> List[ScrapedPrice]:
        results: List[ScrapedPrice] = []

        await page.wait_for_selector(self.CARD_SELECTOR, timeout=10000)
        cards = await page.query_selector_all(self.CARD_SELECTOR)

        for card in cards:
            name_el = await card.query_selector(self.NAME_SELECTOR)
            price_el = await card.query_selector(self.PRICE_SELECTOR)

            if name_el is None or price_el is None:
                continue

            name = (await name_el.inner_text()).strip()
            raw_price = (await price_el.inner_text()).strip()
            price = self._clean_price(raw_price)

            if price is None:
                logger.warning("Price parse fail: %s (raw=%r)", name, raw_price)
                continue

            results.append(
                ScrapedPrice(hotel_name=name, price=price, source=self.name)
            )

        logger.info("[%s] %d hotels scraped", self.name, len(results))
        return results

    @staticmethod
    def _clean_price(raw: str) -> Optional[float]:
        # "Rs.6,500" / "INR 4500.00" -> 6500.0 / 4500.0
        # First number pattern eduthu, currency dot/comma handle pannum.
        match = re.search(r"\d[\d,]*(?:\.\d+)?", raw)
        if match is None:
            return None
        num = match.group(0).replace(",", "")
        try:
            return float(num)
        except ValueError:
            return None


# ============================================================
# SERVICE  (orchestrator — ella scrapers run pannum)
# ============================================================
class ScrapeService:
    def __init__(self):
        self.scrapers = [
            HotelScraper(name=t["name"], url=t["url"], headless=HEADLESS)
            for t in get_targets()
        ]

    async def run_once(self) -> List[ScrapedPrice]:
        all_results: List[ScrapedPrice] = []

        for scraper in self.scrapers:
            try:
                results = await scraper.scrape()
                all_results.extend(results)
            except Exception as exc:
                # Oru site fail aana matha sites continue aaganum
                logger.error("Scraper '%s' failed: %s", scraper.name, exc)

        logger.info("=== Total scraped this run: %d ===", len(all_results))
        for r in all_results:
            logger.info("   %-28s Rs.%-10.2f (%s)", r.hotel_name, r.price, r.source)
        return all_results


# ============================================================
# SCHEDULER
# ============================================================
def create_scheduler(service: ScrapeService) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        service.run_once,
        trigger=IntervalTrigger(minutes=SCRAPE_INTERVAL_MINUTES),
        id="scrape_competitor_prices",
        name="Scrape competitor hotel prices",
        replace_existing=True,
        max_instances=1,   # last run mudiyala na overlap pannathu
        coalesce=True,
    )
    logger.info("Scheduler ready — every %d min scrape pannum", SCRAPE_INTERVAL_MINUTES)
    return scheduler


# ============================================================
# ENTRY POINT
# ============================================================
async def run_with_scheduler() -> None:
    service = ScrapeService()

    # 1. Startup la udane oru thadava scrape (5 min wait pannama)
    logger.info("Initial scrape running on startup...")
    await service.run_once()

    # 2. Apparam scheduler start
    scheduler = create_scheduler(service)
    scheduler.start()

    logger.info("Running. Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()


async def run_once_only() -> None:
    await ScrapeService().run_once()


if __name__ == "__main__":
    # python app.py once  -> oru scrape mattum
    # python app.py       -> scheduler + initial scrape
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        asyncio.run(run_once_only())
    else:
        asyncio.run(run_with_scheduler())
