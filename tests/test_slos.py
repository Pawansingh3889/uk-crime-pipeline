"""SLO monitoring tests for UK Crime Pipeline.

Checks the service level objectives defined in slos.yml against live data.
Run after ingestion + dbt to verify data quality guarantees.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")

# SLO thresholds (mirrored from slos.yml)
FRESHNESS_MAX_DAYS = 7
NULL_RATE_THRESHOLD = 0.01  # 1 %
MIN_ROWS_PER_BATCH = 50
KEY_COLUMNS = ["crime_id", "category", "city"]


def _engine():
    if not DATABASE_URL:
        print("  DATABASE_URL not set"); sys.exit(1)
    return create_engine(DATABASE_URL)


def test_freshness():
    """SLO: most recent loaded_at within the last 7 days."""
    print("Checking freshness SLO...")
    engine = _engine()
    with engine.connect() as conn:
        row = conn.execute(text("SELECT MAX(loaded_at) FROM raw.crimes")).fetchone()
        last_load = row[0]
        if last_load is None:
            print("  FAILED \u2014 no data in raw.crimes"); sys.exit(1)
        if last_load.tzinfo is None:
            last_load = last_load.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - last_load
        assert age <= timedelta(days=FRESHNESS_MAX_DAYS), (
            f"Data is {age.days} days old (SLO: {FRESHNESS_MAX_DAYS}d)"
        )
    print(f"  OK \u2014 last load {age.days}d ago (limit {FRESHNESS_MAX_DAYS}d)")


def test_completeness():
    """SLO: <1% null rate on crime_id, category, city."""
    print("Checking completeness SLO...")
    engine = _engine()
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM raw.crimes")).fetchone()[0]
        if total == 0:
            print("  FAILED \u2014 table is empty"); sys.exit(1)
        for col in KEY_COLUMNS:
            null_count = conn.execute(
                text(f"SELECT COUNT(*) FROM raw.crimes WHERE {col} IS NULL OR {col} = ''")
            ).fetchone()[0]
            rate = null_count / total
            assert rate < NULL_RATE_THRESHOLD, (
                f"{col} null rate {rate:.2%} exceeds {NULL_RATE_THRESHOLD:.0%}"
            )
            print(f"  {col}: {rate:.4%} null ({null_count:,}/{total:,})")
    print("  OK \u2014 all columns within threshold")


def test_volume():
    """SLO: every city/month batch has >50 records."""
    print("Checking volume SLO...")
    engine = _engine()
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT city, fetch_month, COUNT(*) AS cnt
            FROM raw.crimes
            GROUP BY city, fetch_month
            HAVING COUNT(*) <= :min_rows
        """), {"min_rows": MIN_ROWS_PER_BATCH}).fetchall()
        if rows:
            for city, month, cnt in rows:
                print(f"  WARN \u2014 {city} {month}: {cnt} rows (min {MIN_ROWS_PER_BATCH})")
            print(f"  FAILED \u2014 {len(rows)} batches below threshold"); sys.exit(1)
    print("  OK \u2014 all batches above minimum")


if __name__ == "__main__":
    test_freshness()
    test_completeness()
    test_volume()
    print("All SLO checks passed.")
