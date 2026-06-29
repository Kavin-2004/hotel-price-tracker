import re
from datetime import date, timedelta
from typing import Optional
from urllib.parse import urlencode

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from scrapers.base import ScrapedPrice


class BookingScraper:
    source_name = "booking.com"

    def __init__(
        self,
        city: str = "Coimbatore",
        headless: bool = True,
        max_scrolls: int = 12,
    ):
        self.city = city
        self.headless = headless
        self.max_scrolls = max_scrolls

    def build_url(self) -> str:
        today = date.today()
        tomorrow = today + timedelta(days=1)
        params = {
            "ss": self.city,
            "checkin": today.isoformat(),
            "checkout": tomorrow.isoformat(),
            "group_adults": 2,
            "no_rooms": 1,
            "group_children": 0,
            "selected_currency": "INR",
        }
        return "https://www.booking.com/searchresults.html?" + urlencode(params)

    @staticmethod
    def clean_price(raw: str) -> Optional[float]:
        match = re.search(r"\d[\d,]*(?:\.\d+)?", raw)
        if match is None:
            return None

        try:
            return float(match.group(0).replace(",", ""))
        except ValueError:
            return None

    async def close_popups(self, page: Page) -> None:
        selectors = [
            'button[aria-label="Dismiss sign-in info."]',
            'button[aria-label="Close"]',
        ]

        for selector in selectors:
            try:
                button = page.locator(selector).first
                if await button.count() and await button.is_visible():
                    await button.click(timeout=2000)
                    await page.wait_for_timeout(1000)
            except Exception:
                pass

    async def scroll_results(self, page: Page) -> None:
        previous_height = 0
        unchanged_scrolls = 0

        for _ in range(self.max_scrolls):
            await page.mouse.wheel(0, 2500)
            await page.wait_for_timeout(1500)

            load_more = page.locator('[data-testid="load-more-results"]').first
            try:
                if await load_more.count() and await load_more.is_visible():
                    await load_more.click(timeout=3000)
                    await page.wait_for_timeout(2500)
            except Exception:
                pass

            current_height = await page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                unchanged_scrolls += 1
            else:
                unchanged_scrolls = 0

            previous_height = current_height
            if unchanged_scrolls >= 3:
                break

    async def scrape(self) -> list[ScrapedPrice]:
        results: list[ScrapedPrice] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            try:
                page = await browser.new_page(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                )
                await page.goto(self.build_url(), wait_until="domcontentloaded", timeout=60000)
                await self.close_popups(page)

                try:
                    await page.locator('[data-testid="property-card"]').first.wait_for(timeout=30000)
                except PlaywrightTimeoutError:
                    return results

                await self.scroll_results(page)

                cards = page.locator('[data-testid="property-card"]')
                for index in range(await cards.count()):
                    card = cards.nth(index)
                    try:
                        hotel_name = await card.locator('[data-testid="title"]').first.inner_text(timeout=5000)
                        raw_price = await card.locator(
                            '[data-testid="price-and-discounted-price"]'
                        ).first.inner_text(timeout=5000)
                    except Exception:
                        continue

                    price = self.clean_price(raw_price)
                    if hotel_name and price is not None:
                        results.append(
                            ScrapedPrice(
                                hotel_name=" ".join(hotel_name.split()),
                                price=price,
                                source=self.source_name,
                            )
                        )
            finally:
                await browser.close()

        return results
