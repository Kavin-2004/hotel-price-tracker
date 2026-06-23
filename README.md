# Hotel Price Tracker — Coimbatore

Live web app to scrape hotel prices from Booking.com & OYO.

## Deploy to Render.com (Free)

1. **GitHub la upload pannu:**
   - github.com → New repository → "hotel-price-tracker"
   - Intha folder la irukka ellaa files-um upload pannu

2. **Render.com la deploy pannu:**
   - render.com → Sign up (free)
   - "New +" → "Web Service"
   - GitHub repo connect pannu
   - Settings auto-detect aagum (`render.yaml` irukku)
   - "Create Web Service" click pannu

3. **Wait for deploy** (~5 mins first time)

4. **Live link:** `https://hotel-price-tracker.onrender.com`

## Local Test

```bash
pip install -r requirements.txt
playwright install chromium
python app.py
```

Open: http://localhost:5000
