import re
from typing import Optional

from playwright.async_api import async_playwright

from scrapers.base import ScrapedPrice


class GenericPriceScraper:
    """
    Fallback scraper for new websites.

    This uses a heuristic: find visible rupee price text, then look nearby for
    hotel-like heading text. It is useful for testing a new website quickly,
    but site-specific selectors are more reliable.
    """

    price_pattern = r"(?:Rs\.?|INR|₹)\s?[\d,]{3,}(?:\.\d+)?"

    def __init__(self, source_name: str, url: str, headless: bool = False):
        self.source_name = source_name
        self.url = url
        self.headless = headless

    @staticmethod
    def clean_price(raw: str) -> Optional[float]:
        match = re.search(r"\d[\d,]*(?:\.\d+)?", raw)
        if match is None:
            return None

        try:
            return float(match.group(0).replace(",", ""))
        except ValueError:
            return None

    async def scrape(self) -> list[ScrapedPrice]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            try:
                page = await browser.new_page()
                await page.goto(self.url, wait_until="domcontentloaded", timeout=60000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

                raw_results = await page.evaluate(
                    """
                    (priceRegexSrc) => {
                        const priceRegex = new RegExp(priceRegexSrc);
                        const candidates = Array.from(
                            document.querySelectorAll('div, span, p, li, b, strong')
                        );
                        const out = [];
                        const seen = new Set();

                        for (const el of candidates) {
                            const text = (el.textContent || '').trim();
                            if (!text || text.length > 40 || !priceRegex.test(text)) continue;

                            let node = el;
                            let name = null;
                            for (let i = 0; i < 6 && node; i++) {
                                node = node.parentElement;
                                if (!node) break;
                                const heading = node.querySelector(
                                    'h1, h2, h3, h4, h5, a[href*="hotel"], strong, b'
                                );
                                if (!heading) continue;

                                const headingText = (heading.textContent || '').trim();
                                if (
                                    headingText.length >= 4 &&
                                    headingText.length <= 100 &&
                                    !priceRegex.test(headingText)
                                ) {
                                    name = headingText;
                                    break;
                                }
                            }

                            if (name) {
                                const key = name + '|' + text;
                                if (!seen.has(key)) {
                                    seen.add(key);
                                    out.push({ hotelName: name, priceText: text });
                                }
                            }
                        }
                        return out;
                    }
                    """,
                    self.price_pattern,
                )
            finally:
                await browser.close()

        results: list[ScrapedPrice] = []
        for item in raw_results:
            price = self.clean_price(item["priceText"])
            if price is not None:
                results.append(
                    ScrapedPrice(
                        hotel_name=" ".join(item["hotelName"].split()),
                        price=price,
                        source=self.source_name,
                    )
                )

        return results
