import asyncio
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy

from scrapers.booking import BookingScraper
from scrapers.oyo import OyoScraper
from scrapers.goibibo import GobiboScraper

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hotels.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

logging.basicConfig(level=logging.INFO)

# Install chromium at startup (Railway needs this)
try:
    logging.info("Installing chromium...")
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
        check=True, timeout=300
    )
    logging.info("Chromium installed!")
except Exception as e:
    logging.error(f"Chromium install failed: {e}")

IST = timezone(timedelta(hours=5, minutes=30))

# ── Database Model ──
class Hotel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hotel_name = db.Column(db.String(300), nullable=False)
    price = db.Column(db.Float, nullable=False)
    source = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'hotel_name': self.hotel_name,
            'price': self.price,
            'source': self.source,
            'updated_at': self.updated_at.strftime('%d %b %Y, %I:%M %p') if self.updated_at else ''
        }

with app.app_context():
    db.create_all()

# ── Cache ──
_cache = {"data": [], "last_updated": None}

def build_scrapers():
    return [
        BookingScraper(city="Coimbatore", headless=True, max_scrolls=8),
        OyoScraper(city_slug="coimbatore", headless=True, max_scrolls=4),
        GobiboScraper(city="coimbatore", headless=True, max_scrolls=6),
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

def run_scrape_sync():
    """
    gunicorn + asyncio fix:
    Always create a fresh event loop — asyncio.run() crashes if a loop
    is already running (e.g. under some gunicorn worker types).
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run_scrape())
    finally:
        loop.close()

# ── Pages ──
@app.route("/")
def index():
    return render_template("index.html")

# ── Scrape API ──
@app.route("/api/scrape")
def scrape():
    try:
        results = run_scrape_sync()
        data = [
            {"hotel_name": r.hotel_name, "price": r.price, "source": r.source}
            for r in results
        ]
        data.sort(key=lambda x: x["price"])
        _cache["data"] = data
        _cache["last_updated"] = datetime.now(IST).strftime("%d %b %Y, %I:%M %p")
        return jsonify({"success": True, "data": data, "last_updated": _cache["last_updated"]})
    except Exception as e:
        logging.error(f"/api/scrape error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/cached")
def cached():
    return jsonify({"data": _cache["data"], "last_updated": _cache["last_updated"]})

# ── CRUD APIs ──

@app.route("/api/hotels", methods=["POST"])
def create_hotel():
    data = request.json
    if not data or not data.get("hotel_name") or not data.get("price"):
        return jsonify({"success": False, "error": "hotel_name and price required"}), 400
    hotel = Hotel(
        hotel_name=data["hotel_name"],
        price=float(data["price"]),
        source=data.get("source", "manual")
    )
    db.session.add(hotel)
    db.session.commit()
    return jsonify({"success": True, "hotel": hotel.to_dict()})

@app.route("/api/hotels", methods=["GET"])
def get_hotels():
    hotels = Hotel.query.order_by(Hotel.price).all()
    return jsonify({"success": True, "data": [h.to_dict() for h in hotels]})

@app.route("/api/hotels/<int:hotel_id>", methods=["PUT"])
def update_hotel(hotel_id):
    hotel = Hotel.query.get_or_404(hotel_id)
    data = request.json
    if "hotel_name" in data:
        hotel.hotel_name = data["hotel_name"]
    if "price" in data:
        hotel.price = float(data["price"])
    if "source" in data:
        hotel.source = data["source"]
    hotel.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"success": True, "hotel": hotel.to_dict()})

@app.route("/api/hotels/<int:hotel_id>", methods=["DELETE"])
def delete_hotel(hotel_id):
    hotel = Hotel.query.get_or_404(hotel_id)
    db.session.delete(hotel)
    db.session.commit()
    return jsonify({"success": True, "message": "Deleted"})

@app.route("/api/save-scraped", methods=["POST"])
def save_scraped():
    if not _cache["data"]:
        return jsonify({"success": False, "error": "No scraped data. Run scrape first."}), 400
    Hotel.query.filter(Hotel.source.in_(["booking.com", "oyo"])).delete()
    for item in _cache["data"]:
        db.session.add(Hotel(
            hotel_name=item["hotel_name"],
            price=item["price"],
            source=item["source"]
        ))
    db.session.commit()
    return jsonify({"success": True, "saved": len(_cache["data"])})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
