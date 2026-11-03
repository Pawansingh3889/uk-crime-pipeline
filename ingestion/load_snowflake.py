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

# Reuse the city list, the API caller, the row tidier and the quality checker from the Postgres loader.
from ingestion.fetch_crimes import LOCATIONS, MONTHS, fetch_crimes, to_rows
from ingestion.validators import validate_batch

log = logging.getLogger(__name__)

# The ten pieces of information we keep about each crime, same as the shelf's column names.
COLUMNS = [
    "crime_id", "fetch_month", "city", "category", "location_type",
    "latitude", "longitude", "street_name", "outcome_status", "month",
]

# Put a crime on the main shelf only if that exact crime (same id, month and city) is not already there.
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
    # Log in to Snowflake as the robot worker, using the secret key file instead of a password.
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
    # Collect every crime for every city and month into one big list.
    rows = []
    for loc in LOCATIONS:
        for month in months:
            # Ask the police website for this city's crimes in this month.
            crimes = fetch_crimes(loc["lat"], loc["lng"], month, loc["city"])
            # Check the batch looks sensible (enough rows, no blanks) and warn if not, but keep going.
            result = validate_batch(crimes, city=loc["city"], month=month)
            log.log(logging.INFO if result.passed else logging.WARNING, "Validation: %s", result.summary())
            # Tidy each crime into the ten columns and add it to the list.
            rows.extend(to_rows(crimes))
            # Wait half a second so we are polite to the police website.
            time.sleep(0.5)
    return rows


def load(rows, conn):
    """Stage rows as one JSON-lines file and merge them into raw.crimes. Returns rows inserted."""
    with tempfile.TemporaryDirectory() as tmp:
        # Write all the crimes into one file on the laptop, one crime per line.
        path = Path(tmp) / f"crimes_{int(time.time())}.json"
        path.write_text("\n".join(json.dumps(r) for r in rows))
        cur = conn.cursor()
        # Upload the file to Snowflake's loading dock, squashed small to travel faster.
        cur.execute(f"PUT file://{path} @crimes_stage AUTO_COMPRESS=TRUE")
        # Make a scratch table, like the main shelf, that disappears when we log out.
        cur.execute("CREATE OR REPLACE TEMPORARY TABLE crimes_batch LIKE raw.crimes")
        # Unpack the file from the dock onto the scratch table, matching fields by name.
        cur.execute(
            f"COPY INTO crimes_batch FROM @crimes_stage/{path.name}.gz "
            "FILE_FORMAT = (TYPE = JSON) MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE"
        )
        # Move only the new crimes from the scratch table to the main shelf.
        cur.execute(MERGE_SQL)
        # Snowflake tells us how many crimes were actually new.
        inserted = cur.fetchone()[0]
        # Clear the file off the loading dock now that it is unpacked.
        cur.execute(f"REMOVE @crimes_stage/{path.name}.gz")
    return inserted


def run(months):
    # The whole job: fetch, stop loudly if nothing came back, then load.
    rows = fetch_rows(months)
    if not rows:
        raise RuntimeError(f"No records fetched for {months}")
    with connect() as conn:
        inserted = load(rows, conn)
    log.info("Fetched %d rows, inserted %d new into raw.crimes", len(rows), inserted)
    return inserted


# When run from the terminal, load the months typed after the command, or the default six.
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(sys.argv[1:] or MONTHS)
