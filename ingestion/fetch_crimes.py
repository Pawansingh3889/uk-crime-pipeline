"""
Police UK API → PostgreSQL ingestion
Fetches crime data for 10 UK cities and loads into PostgreSQL.
Idempotent — safe to run multiple times.
"""

import os
import time
import requests
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load .env from project root regardless of where script is run from
load_dotenv(Path(__file__).parent.parent / ".env")

load_dotenv()

DB_URL = (
    f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
)

LOCATIONS = [
    {"city": "Hull",         "lat": 53.745000, "lng": -0.336000},
    {"city": "London",       "lat": 51.509865, "lng": -0.118092},
    {"city": "Birmingham",   "lat": 52.489471, "lng": -1.898575},
    {"city": "Manchester",   "lat": 53.483959, "lng": -2.244644},
    {"city": "Leeds",        "lat": 53.800755, "lng": -1.549077},
    {"city": "Sheffield",    "lat": 53.381129, "lng": -1.470085},
    {"city": "Liverpool",    "lat": 53.408371, "lng": -2.991573},
    {"city": "Bristol",      "lat": 51.454514, "lng": -2.587910},
    {"city": "Nottingham",   "lat": 52.950001, "lng": -1.150000},
    {"city": "Newcastle",    "lat": 54.978252, "lng": -1.617780},
]

MONTHS = [
    "2024-05", "2024-06", "2024-07",
    "2024-08", "2024-09", "2024-10"
]

BASE_URL = "https://data.police.uk/api/crimes-street/all-crime"


def setup_database(engine):
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS raw.crimes (
                crime_id          TEXT,
                fetch_month       TEXT,
                city              TEXT,
                category          TEXT,
                location_type     TEXT,
                latitude          TEXT,
                longitude         TEXT,
                street_name       TEXT,
                outcome_status    TEXT,
                month             TEXT,
                loaded_at         TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (crime_id, fetch_month, city)
            )
        """))
        conn.commit()
    print("Database ready.")


def fetch_crimes(lat, lng, date, city):
    try:
        resp = requests.get(
            BASE_URL,
            params={"lat": lat, "lng": lng, "date": date},
            timeout=30
        )
        resp.raise_for_status()
        crimes = resp.json()
        for c in crimes:
            c["city"] = city
            c["fetch_month"] = date
            if c.get("location"):
                c["latitude"]    = c["location"].get("latitude")
                c["longitude"]   = c["location"].get("longitude")
                c["street_name"] = c["location"].get("street", {}).get("name")
            else:
                c["latitude"] = c["longitude"] = c["street_name"] = None
            if isinstance(c.get("outcome_status"), dict):
                c["outcome_status"] = c["outcome_status"].get("category")
        return crimes
    except Exception as e:
        print(f"  ERROR {city} {date}: {e}")
        return []


def load_crimes(records, engine):
    if not records:
        return 0
    rows = []
    for c in records:
        rows.append({
            "crime_id":       str(c.get("id", "")),
            "fetch_month":    c.get("fetch_month", ""),
            "city":           c.get("city", ""),
            "category":       c.get("category", ""),
            "location_type":  c.get("location_type", ""),
            "latitude":       c.get("latitude"),
            "longitude":      c.get("longitude"),
            "street_name":    c.get("street_name"),
            "outcome_status": c.get("outcome_status"),
            "month":          c.get("month", ""),
        })
    with engine.connect() as conn:
        for row in rows:
            conn.execute(text("""
                INSERT INTO raw.crimes
                    (crime_id, fetch_month, city, category, location_type,
                     latitude, longitude, street_name, outcome_status, month)
                VALUES
                    (:crime_id, :fetch_month, :city, :category, :location_type,
                     :latitude, :longitude, :street_name, :outcome_status, :month)
                ON CONFLICT (crime_id, fetch_month, city) DO NOTHING
            """), row)
        conn.commit()
    return len(rows)


def main():
    print("UK Crime Pipeline — Ingestion")
    print("=" * 50)
    engine = create_engine(DB_URL)
    setup_database(engine)

    total = 0
    for loc in LOCATIONS:
        for month in MONTHS:
            print(f"  Fetching {loc['city']} {month}...")
            crimes = fetch_crimes(loc["lat"], loc["lng"], month, loc["city"])
            count = load_crimes(crimes, engine)
            total += count
            print(f"    Loaded {count:,} records")
            time.sleep(0.5)

    print("=" * 50)
    print(f"Total loaded: {total:,} crime records")
    engine.dispose()


if __name__ == "__main__":
    main()