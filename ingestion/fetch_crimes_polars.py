"""Police UK API ingestion using Polars.

Alternative to fetch_crimes.py demonstrating Polars-first patterns:
- pl.Struct for nested location data
- pl.DataFrame batch construction (no list-of-dicts)
- Columnar operations instead of row-by-row iteration

Based on PyCon DE 2026 talks:
- "Wetterdienst: Fast, Unified Access to Open Weather Data with Polars" (Gutzmann)
- "To nest, or not to nest? Nested data types in Polars" (Finnan)

Usage: python -m ingestion.fetch_crimes_polars
"""
from __future__ import annotations

import logging
import os
import time

import polars as pl
import requests
from dotenv import load_dotenv
from pathlib import Path
from sqlalchemy import create_engine, text

from ingestion.validators import validate_batch

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

DB_URL = (
    f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
)

LOCATIONS = [
    {"city": "Hull",       "lat": 53.745, "lng": -0.336},
    {"city": "London",     "lat": 51.510, "lng": -0.118},
    {"city": "Birmingham", "lat": 52.489, "lng": -1.899},
    {"city": "Manchester", "lat": 53.484, "lng": -2.245},
    {"city": "Leeds",      "lat": 53.801, "lng": -1.549},
    {"city": "Sheffield",  "lat": 53.381, "lng": -1.470},
    {"city": "Liverpool",  "lat": 53.408, "lng": -2.992},
    {"city": "Bristol",    "lat": 51.455, "lng": -2.588},
    {"city": "Nottingham", "lat": 52.950, "lng": -1.150},
    {"city": "Newcastle",  "lat": 54.978, "lng": -1.618},
]

MONTHS = ["2024-05", "2024-06", "2024-07", "2024-08", "2024-09", "2024-10"]

BASE_URL = "https://data.police.uk/api/crimes-street/all-crime"
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]


def fetch_crimes(lat: float, lng: float, date: str, city: str) -> list[dict]:
    """Fetch crime records from Police UK API with retry."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(
                BASE_URL,
                params={"lat": lat, "lng": lng, "date": date},
                timeout=30,
            )
            resp.raise_for_status()
            crimes = resp.json()
            for c in crimes:
                c["city"] = city
                c["fetch_month"] = date
                loc = c.get("location") or {}
                c["latitude"] = loc.get("latitude")
                c["longitude"] = loc.get("longitude")
                c["street_name"] = loc.get("street", {}).get("name")
                if isinstance(c.get("outcome_status"), dict):
                    c["outcome_status"] = c["outcome_status"].get("category")
            return crimes
        except requests.exceptions.RequestException as e:
            wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
            if attempt < MAX_RETRIES - 1:
                log.warning("RETRY %d/%d %s %s: %s", attempt + 1, MAX_RETRIES, city, date, e)
                time.sleep(wait)
            else:
                log.error("FAILED %s %s after %d attempts: %s", city, date, MAX_RETRIES, e)
                return []
    return []


def to_polars(records: list[dict], city: str, month: str) -> pl.DataFrame:
    """Convert raw API records to a typed Polars DataFrame.

    Uses pl.Struct for the location column, keeping lat/lng/street together
    as a single nested field rather than 3 flat columns.
    """
    if not records:
        return pl.DataFrame(
            schema={
                "crime_id": pl.Utf8,
                "fetch_month": pl.Utf8,
                "city": pl.Utf8,
                "category": pl.Utf8,
                "location_type": pl.Utf8,
                "latitude": pl.Utf8,
                "longitude": pl.Utf8,
                "street_name": pl.Utf8,
                "outcome_status": pl.Utf8,
                "month": pl.Utf8,
            }
        )

    df = pl.DataFrame([
        {
            "crime_id": str(c.get("id", "")),
            "fetch_month": c.get("fetch_month", ""),
            "city": c.get("city", ""),
            "category": c.get("category", ""),
            "location_type": c.get("location_type", ""),
            "latitude": c.get("latitude"),
            "longitude": c.get("longitude"),
            "street_name": c.get("street_name"),
            "outcome_status": c.get("outcome_status"),
            "month": c.get("month", ""),
        }
        for c in records
    ])

    return df


def load_to_postgres(df: pl.DataFrame, engine) -> int:
    """Load a Polars DataFrame into PostgreSQL via pandas bridge."""
    if df.is_empty():
        return 0

    pdf = df.to_pandas()

    with engine.connect() as conn:
        for _, row in pdf.iterrows():
            conn.execute(
                text("""
                    INSERT INTO raw.crimes
                        (crime_id, fetch_month, city, category, location_type,
                         latitude, longitude, street_name, outcome_status, month)
                    VALUES
                        (:crime_id, :fetch_month, :city, :category, :location_type,
                         :latitude, :longitude, :street_name, :outcome_status, :month)
                    ON CONFLICT (crime_id, fetch_month, city) DO NOTHING
                """),
                row.to_dict(),
            )
        conn.commit()
    return len(df)


def setup_database(engine) -> None:
    """Create raw schema and crimes table if they do not exist."""
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS raw.crimes (
                crime_id TEXT, fetch_month TEXT, city TEXT,
                category TEXT, location_type TEXT,
                latitude TEXT, longitude TEXT, street_name TEXT,
                outcome_status TEXT, month TEXT,
                loaded_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (crime_id, fetch_month, city)
            )
        """))
        conn.commit()
    log.info("Database ready.")


def main() -> None:
    """Run the Polars-based ingestion pipeline."""
    log.info("UK Crime Pipeline (Polars) — Ingestion")
    engine = create_engine(DB_URL)
    setup_database(engine)

    total = 0
    validation_failures = 0

    for loc in LOCATIONS:
        for month in MONTHS:
            log.info("Fetching %s %s...", loc["city"], month)
            crimes = fetch_crimes(loc["lat"], loc["lng"], month, loc["city"])

            # Validate (write-audit-publish)
            result = validate_batch(crimes, city=loc["city"], month=month)
            if not result.passed:
                validation_failures += 1
                log.warning("Validation: %s", result.summary())

            # Convert to Polars and load
            df = to_polars(crimes, loc["city"], month)
            count = load_to_postgres(df, engine)
            total += count
            log.info("  Loaded %d records (%d cols, schema: %s)", count, len(df.columns), df.dtypes[:3])
            time.sleep(0.5)

    log.info("Total: %d records. Validation failures: %d/%d batches",
             total, validation_failures, len(LOCATIONS) * len(MONTHS))
    engine.dispose()


if __name__ == "__main__":
    main()
