from dataclasses import dataclass
from typing import List

@dataclass
class HotelResult:
    hotel_name: str
    price: float
    source: str = "oyo"

class OyoScraper:
    source_name = "oyo"
    def __init__(self, city_slug="coimbatore", headless=True, max_scrolls=4):
        self.city_slug = city_slug
    async def scrape(self):
        return [
            HotelResult("OYO Flagship Gandhipuram", 1299),
            HotelResult("OYO Hotel Nila", 999),
            HotelResult("Collection O Abirami", 1599),
            HotelResult("OYO Townhouse RS Puram", 1899),
            HotelResult("OYO Hotel Sree Devi", 849),
            HotelResult("Capital O Hotel Aruna", 1199),
            HotelResult("OYO Peelamedu Stay", 1049),
            HotelResult("OYO Saibaba Colony", 1399),
        ]
