import re
from typing import Optional
from playwright.async_api import async_playwright
from scrapers.base import ScrapedPrice


class GobiboScraper:
    source_name = "goibibo"

    def __init__(
        self,
        city: str = "coimbatore",
        headless: bool = True,
        max_scrolls: int = 6,
    ):
        self.city = city
        self.headless = headless
        self.max_scrolls = max_scrolls

    def build_url(self) -> str:
        return f"https://www.goibibo.com/hotels/hotels-in-{self.city}/"

    @staticmethod
    def clean_price(raw: str) -> Optional[float]:
        match = re.search(r"[\u20b9₹]?\s*(\d[\d,]*)", raw)
        if match is None:
            return None
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None

    async def scroll_results(self, page) -> None:
        previous_height = 0
        unchanged = 0
        for _ in range(self.max_scrolls):
            await page.mouse.wheel(0, 2500)
            await page.wait_for_timeout(2000)
            current_height = await page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                unchanged += 1
            else:
                unchanged = 0
            previous_height = current_height
            if unchanged >= 2:
                break

    async def scrape(self) -> list[ScrapedPrice]:
        results = []
        seen = set()

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

                raw = await page.evaluate("""
                    () => {
                        const cards = document.querySelectorAll('[class*="hotelCard"], [class*="hotel-card"], [class*="HotelCard"]');
                        return Array.from(cards).map(card => ({
                            name: (card.querySelector('[class*="hotelName"], [class*="hotel-name"], h3, h2') || {}).textContent || '',
                            price: (card.querySelector('[class*="price"], [class*="Price"], [class*="rate"], [class*="Rate"]') || {}).textContent || ''
                        }));
                    }
                """)

                for item in raw:
                    name = " ".join(item["name"].split()).strip()
                    if not name or name in seen:
                        continue
                    price = self.clean_price(item["price"])
                    if price is None or price < 100:
                        continue
                    seen.add(name)
                    results.append(ScrapedPrice(
                        hotel_name=name,
                        price=price,
                        source=self.source_name,
                    ))
            finally:
                await browser.close()

        return results
