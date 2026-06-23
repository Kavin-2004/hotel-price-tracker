import asyncio
import logging
from datetime import datetime

from flask import Flask, jsonify, render_template

from scrapers.booking import BookingScraper
from scrapers.oyo import OyoScraper

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Cache to avoid too-frequent scraping
_cache = {"data": [], "last_updated": None}


def build_scrapers():
    return [
        BookingScraper(city="Coimbatore", headless=True, max_scrolls=8),
        OyoScraper(city_slug="coimbatore", headless=True, max_scrolls=4),
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
        _cache["last_updated"] = datetime.now().strftime("%d %b %Y, %I:%M %p")
        return jsonify({"success": True, "data": data, "last_updated": _cache["last_updated"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/cached")
def cached():
    return jsonify({"data": _cache["data"], "last_updated": _cache["last_updated"]})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
