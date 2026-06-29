from dataclasses import dataclass 
from typing import List 
import re, logging 
from playwright.async_api import async_playwright 
logger = logging.getLogger('goibibo_scraper') 
@dataclass 
class HotelResult: 
    hotel_name: str 
    price: float 
    source: str = 'goibibo' 
class GobiboScraper: 
    source_name = 'goibibo' 
    def __init__(self, city='coimbatore', headless=True, max_scrolls=6): 
        self.city = city 
    async def scrape(self): 
