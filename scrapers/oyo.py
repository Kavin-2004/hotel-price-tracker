import re
from typing import Optional

from playwright.async_api import Page, async_playwright

from scrapers.base import ScrapedPrice


class OyoScraper:
    source_name = "oyo"

    def __init__(
        self,
        city_slug: str = "coimbatore",
        headless: bool = False,
        max_scrolls: int = 6,
    ):
        self.city_slug = city_slug
        self.headless = headless
        self.max_scrolls = max_scrolls

    def build_url(self) -> str:
        return f"https://www.oyorooms.com/hotels-in-{self.city_slug}/"

    @staticmethod
    def clean_price(raw: str) -> Optional[float]:
        match = re.search(
            "(?:\\u20b9|Rs\\.?|INR)\\s?(\\d[\\d,]*(?:\\.\\d+)?)",
            raw,
            re.IGNORECASE,
        )
        if match is None:
            return None

        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None

    async def scroll_results(self, page: Page) -> None:
        previous_height = 0
        unchanged_scrolls = 0

        for _ in range(self.max_scrolls):
            await page.mouse.wheel(0, 2200)
            await page.wait_for_timeout(1500)

            current_height = await page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                unchanged_scrolls += 1
            else:
                unchanged_scrolls = 0

            previous_height = current_height
            if unchanged_scrolls >= 2:
                break

    async def scrape(self) -> list[ScrapedPrice]:
        results: list[ScrapedPrice] = []
        seen_names: set[str] = set()

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
                await page.wait_for_timeout(4000)
                await self.scroll_results(page)

                raw_results = await page.evaluate(
                    """
                    () => Array.from(document.querySelectorAll('h3'))
                        .map(heading => {
                            const name = (heading.textContent || '').trim();
                            let node = heading;
                            let containerText = '';

                            for (let i = 0; i < 10 && node; i++) {
                                containerText = (node.textContent || '').trim();
                                if (/\\u20b9|Rs\\.?|INR/.test(containerText)) break;
                                node = node.parentElement;
                            }

                            return { hotelName: name, containerText };
                        })
                    """
                )
            finally:
                await browser.close()

        for item in raw_results:
            hotel_name = " ".join(item["hotelName"].split())
            if not hotel_name or hotel_name in seen_names:
                continue
            if hotel_name.lower() in {"price", "hotels in coimbatore"}:
                continue

            price = self.clean_price(item["containerText"])
            if price is None:
                continue
            if price < 100:
                continue

            seen_names.add(hotel_name)
            results.append(
                ScrapedPrice(
                    hotel_name=hotel_name,
                    price=price,
                    source=self.source_name,
                )
            )

        return results
