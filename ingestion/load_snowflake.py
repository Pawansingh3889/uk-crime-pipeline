"""
Police UK API -> Snowflake ingestion.

Same fetch and validation as fetch_crimes.py, loaded the Snowflake way:
PUT a JSON file to a stage, COPY INTO a temporary table, MERGE into raw.crimes.
Idempotent: re-running a month inserts nothing new.

Usage: python -m ingestion.load_snowflake [YYYY-MM ...]   (defaults to MONTHS)
Needs SNOWFLAKE_ACCOUNT and SNOWFLAKE_PRIVATE_KEY_PATH; see snowflake/README.md.
"""

import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

import snowflake.connector

from ingestion.fetch_crimes import LOCATIONS, MONTHS, fetch_crimes, to_rows
from ingestion.validators import validate_batch

log = logging.getLogger(__name__)

COLUMNS = [
    "crime_id", "fetch_month", "city", "category", "location_type",
    "latitude", "longitude", "street_name", "outcome_status", "month",
]

MERGE_SQL = f"""
MERGE INTO raw.crimes t
USING (
    SELECT * FROM crimes_batch
    QUALIFY ROW_NUMBER() OVER (PARTITION BY crime_id, fetch_month, city ORDER BY crime_id) = 1
) s
ON t.crime_id = s.crime_id AND t.fetch_month = s.fetch_month AND t.city = s.city
WHEN NOT MATCHED THEN INSERT ({", ".join(COLUMNS)}, loaded_at)
VALUES ({", ".join("s." + c for c in COLUMNS)}, CURRENT_TIMESTAMP())
"""


def connect():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user="CRIME_PIPELINE",
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        role="CRIME_LOADER",
        warehouse="CRIME_WH",
        database="CRIME_DB",
        schema="RAW",
    )


def fetch_rows(months):
    rows = []
    for loc in LOCATIONS:
        for month in months:
            crimes = fetch_crimes(loc["lat"], loc["lng"], month, loc["city"])
            result = validate_batch(crimes, city=loc["city"], month=month)
            log.log(logging.INFO if result.passed else logging.WARNING, "Validation: %s", result.summary())
            rows.extend(to_rows(crimes))
            time.sleep(0.5)
    return rows


def load(rows, conn):
    """Stage rows as one JSON-lines file and merge them into raw.crimes. Returns rows inserted."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"crimes_{int(time.time())}.json"
        path.write_text("\n".join(json.dumps(r) for r in rows))
        cur = conn.cursor()
        cur.execute(f"PUT file://{path} @crimes_stage AUTO_COMPRESS=TRUE")
        cur.execute("CREATE OR REPLACE TEMPORARY TABLE crimes_batch LIKE raw.crimes")
        cur.execute(
            f"COPY INTO crimes_batch FROM @crimes_stage/{path.name}.gz "
            "FILE_FORMAT = (TYPE = JSON) MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE"
        )
        cur.execute(MERGE_SQL)
        inserted = cur.fetchone()[0]
        cur.execute(f"REMOVE @crimes_stage/{path.name}.gz")
    return inserted


def run(months):
    rows = fetch_rows(months)
    if not rows:
        raise RuntimeError(f"No records fetched for {months}")
    with connect() as conn:
        inserted = load(rows, conn)
    log.info("Fetched %d rows, inserted %d new into raw.crimes", len(rows), inserted)
    return inserted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(sys.argv[1:] or MONTHS)
