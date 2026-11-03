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

DBT_DIR = Path(__file__).resolve().parents[1] / "dbt_crimes"


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
    @task
    def pick_month(params=None) -> str:
        return params["month"] or pendulum.now("UTC").subtract(months=2).format("YYYY-MM")

    @task
    def extract_load(month: str) -> int:
        from ingestion.load_snowflake import run

        return run([month])

    @task.bash(cwd=str(DBT_DIR))
    def dbt_source_freshness() -> str:
        return "dbt source freshness --target snowflake --profiles-dir ."

    @task.bash(cwd=str(DBT_DIR))
    def dbt_build() -> str:
        return "dbt build --target snowflake --profiles-dir ."

    extract_load(pick_month()) >> dbt_source_freshness() >> dbt_build()


uk_crime_snowflake()
