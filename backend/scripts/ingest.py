"""Manual trigger for live GAF ingestion (requires a real display — see
app/services/gaf_scraper.py). Not used in fixture mode.

Usage: python -m scripts.ingest [zip_code] [radius_miles]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.gaf_scraper import run_ingestion

if __name__ == "__main__":
    zip_code = sys.argv[1] if len(sys.argv) > 1 else "10013"
    radius = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    records = run_ingestion(zip_code, radius)
    print(f"Scraped {len(records)} contractors for {zip_code} / {radius}mi")
    for r in records:
        print(r.get("gaf_contractor_id"), r.get("name"))
