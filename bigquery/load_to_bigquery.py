"""Load crime data CSV to BigQuery.

Usage:
    1. Export crime data from PostgreSQL:
       psql -c "COPY (SELECT * FROM raw.crimes) TO STDOUT CSV HEADER" > crimes.csv

    2. Or use the existing ingestion to create a CSV:
       python ingestion/fetch_crimes.py --output csv

    3. Run this script:
       python bigquery/load_to_bigquery.py

Requires:
    pip install google-cloud-bigquery pandas pyarrow db-dtypes
"""

from __future__ import annotations

import os
from pathlib import Path

from google.cloud import bigquery


PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "mediask-491710")
DATASET_ID = "crime_analytics"
TABLE_ID = "raw_crimes"

CSV_PATH = Path(__file__).parent.parent / "data" / "crimes.csv"


def create_dataset(client: bigquery.Client) -> None:
    """Create the BigQuery dataset if it doesn't exist."""
    dataset_ref = f"{PROJECT_ID}.{DATASET_ID}"
    try:
        client.get_dataset(dataset_ref)
        print(f"Dataset {dataset_ref} already exists.")
    except Exception:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "EU"
        client.create_dataset(dataset)
        print(f"Created dataset {dataset_ref}")


def load_csv(client: bigquery.Client) -> None:
    """Load CSV into BigQuery with auto-detect schema."""
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        autodetect=True,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    with open(CSV_PATH, "rb") as f:
        job = client.load_table_from_file(f, table_ref, job_config=job_config)

    job.result()  # Wait for completion

    table = client.get_table(table_ref)
    print(f"Loaded {table.num_rows} rows into {table_ref}")


def main() -> None:
    client = bigquery.Client(project=PROJECT_ID)
    create_dataset(client)
    load_csv(client)

    # Quick verification query
    query = f"""
    SELECT city, COUNT(*) as incident_count
    FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`
    GROUP BY city
    ORDER BY incident_count DESC
    """
    print("\nRow counts by city:")
    for row in client.query(query):
        print(f"  {row.city}: {row.incident_count:,}")


if __name__ == "__main__":
    main()
