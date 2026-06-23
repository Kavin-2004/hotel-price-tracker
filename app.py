import asyncio
import logging
import subprocess
import sys
from datetime import datetime, timezone, timedelta

from flask import Flask, jsonify, render_template

from scrapers.booking import BookingScraper
from scrapers.oyo import OyoScraper
from scrapers.goibibo import GobiboScraper
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

try:
    logging.info("Installing chromium...")
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
        check=True
    )
    logging.info("Chromium installed!")
except Exception as e:
    logging.error(f"Chromium install failed: {e}")

IST = timezone(timedelta(hours=5, minutes=30))
_cache = {"data": [], "last_updated": None}

def build_scrapers():
    return [
        BookingScraper(city="Coimbatore", headless=True, max_scrolls=8),
        OyoScraper(city_slug="coimbatore", headless=True, max_scrolls=4),
        GobiboScraper(city="coimbatore", headless=True, max_scrolls=4),
    ]

async def run_scrape():
    all_results = []
    for scraper in build_scrapers():
        try:
            results = await scraper.scrape()
            all_results.extend(results)
        except Exception as e:
            logging.error(f"[{scraper.source_name}] failed: {e}")
    return all_results

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/scrape")
def scrape():
    try:
        results = asyncio.run(run_scrape())
        data = [
            {"hotel_name": r.hotel_name, "price": r.price, "source": r.source}
            for r in results
        ]
        data.sort(key=lambda x: x["price"])
        _cache["data"] = data
        _cache["last_updated"] = datetime.now(IST).strftime("%d %b %Y, %I:%M %p")
        return jsonify({"success": True, "data": data, "last_updated": _cache["last_updated"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/cached")
def cached():
    return jsonify({"data": _cache["data"], "last_updated": _cache["last_updated"]})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
