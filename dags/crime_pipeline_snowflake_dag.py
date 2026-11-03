"""Airflow DAG: Police UK API -> Snowflake -> dbt.

extract_load runs ingestion/load_snowflake.py for one month, then dbt checks
source freshness and builds and tests every model on the snowflake target.
Police UK publishes about two months late, so a run loads the month two months back
unless the "month" param is set (trigger with config {"month": "2024-10"}).
"""

from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.decorators import dag, task

# Where the dbt project lives, worked out from where this file sits.
DBT_DIR = Path(__file__).resolve().parents[1] / "dbt_crimes"


# The timetable: run once a month from Jan 2026, don't catch up on missed months, retry a failed step twice after 5 minutes.
@dag(
    dag_id="uk_crime_snowflake",
    schedule="@monthly",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    params={"month": ""},
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["crime", "snowflake", "dbt"],
)
def uk_crime_snowflake():
    # Step 1: decide which month to load, the one you typed, or two months ago because police data arrives late.
    @task
    def pick_month(params=None) -> str:
        return params["month"] or pendulum.now("UTC").subtract(months=2).format("YYYY-MM")

    # Step 2: fetch that month from the police website and load it into Snowflake.
    @task
    def extract_load(month: str) -> int:
        from ingestion.load_snowflake import run

        return run([month])

    # Step 3: check the raw data was loaded recently, not weeks ago.
    @task.bash(cwd=str(DBT_DIR))
    def dbt_source_freshness() -> str:
        return "dbt source freshness --target snowflake --profiles-dir ."

    # Step 4: build all the summary tables in Snowflake and test them.
    @task.bash(cwd=str(DBT_DIR))
    def dbt_build() -> str:
        return "dbt build --target snowflake --profiles-dir ."

    # The order: each step only starts if the one before it succeeded.
    extract_load(pick_month()) >> dbt_source_freshness() >> dbt_build()


# Register the timetable with Airflow.
uk_crime_snowflake()
