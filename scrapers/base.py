from dataclasses import dataclass
from typing import Protocol


@dataclass
class ScrapedPrice:
    hotel_name: str
    price: float
    source: str


class HotelScraper(Protocol):
    source_name: str

    async def scrape(self) -> list[ScrapedPrice]:
        raise NotImplementedError
