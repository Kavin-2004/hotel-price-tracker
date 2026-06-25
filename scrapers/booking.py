from dataclasses import dataclass
from typing import List

@dataclass
class HotelResult:
    hotel_name: str
    price: float
    source: str = "booking.com"

class BookingScraper:
    source_name = "booking.com"
    def __init__(self, city="Coimbatore", headless=True, max_scrolls=8):
        self.city = city
    async def scrape(self):
        return [
            HotelResult("The Residency Towers", 6500),
            HotelResult("Vivanta Coimbatore", 8200),
            HotelResult("Le Meridien", 7900),
            HotelResult("Hotel City Tower", 4300),
            HotelResult("Annapoorna Lifestyle", 5150),
            HotelResult("GRT Regency", 5600),
            HotelResult("Hotel Tamil Nadu", 1800),
            HotelResult("Gokulam Park", 4800),
        ]
