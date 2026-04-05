"""Airflow DAG for UK Crime Pipeline.

Orchestrates: API ingestion → PostgreSQL load → dbt transform → data quality checks.
Schedule: Daily at 6am UTC.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago


default_args = {
    "owner": "pawan",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="uk_crime_pipeline",
    default_args=default_args,
    description="Ingest UK crime data, load to PostgreSQL, transform with dbt",
    schedule_interval="0 6 * * *",
    start_date=days_ago(1),
    catchup=False,
    tags=["crime", "pipeline", "dbt"],
) as dag:

    def fetch_crime_data(**context):
        """Pull latest crime data from Police UK API."""
        import requests
        import json
        from pathlib import Path

        forces = ["west-yorkshire", "metropolitan", "greater-manchester"]
        all_crimes = []
        date = context["ds"][:7]  # YYYY-MM

        for force in forces:
            url = f"https://data.police.uk/api/crimes-no-location?category=all-crime&force={force}&date={date}"
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                all_crimes.extend(resp.json())

        output_path = Path("/tmp/crime_data.json")
        output_path.write_text(json.dumps(all_crimes))
        return len(all_crimes)

    def load_to_postgres(**context):
        """Load crime records into PostgreSQL staging table."""
        import json
        from pathlib import Path
        from sqlalchemy import create_engine, text

        data = json.loads(Path("/tmp/crime_data.json").read_text())
        if not data:
            return 0

        engine = create_engine("postgresql://localhost:5432/crime_db")
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM staging.raw_crimes WHERE month = :month"),
                        {"month": context["ds"][:7]})
            for record in data:
                conn.execute(
                    text("""INSERT INTO staging.raw_crimes (category, month, outcome_status)
                            VALUES (:cat, :month, :outcome)"""),
                    {"cat": record.get("category"), "month": record.get("month"),
                     "outcome": json.dumps(record.get("outcome_status"))},
                )
        return len(data)

    def check_data_quality(**context):
        """Validate row counts and null rates after load."""
        from sqlalchemy import create_engine, text

        engine = create_engine("postgresql://localhost:5432/crime_db")
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM staging.raw_crimes")).scalar()
            null_rate = conn.execute(
                text("SELECT COUNT(*) FILTER (WHERE category IS NULL)::float / COUNT(*) FROM staging.raw_crimes")
            ).scalar()

        if count == 0:
            raise ValueError("No rows loaded — pipeline failed")
        if null_rate > 0.05:
            raise ValueError(f"Null rate {null_rate:.1%} exceeds 5% threshold")

        return {"rows": count, "null_rate": null_rate}

    ingest = PythonOperator(
        task_id="fetch_crime_data",
        python_callable=fetch_crime_data,
    )

    load = PythonOperator(
        task_id="load_to_postgres",
        python_callable=load_to_postgres,
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd /opt/dbt/uk_crime && dbt run --profiles-dir /opt/dbt/profiles",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/dbt/uk_crime && dbt test --profiles-dir /opt/dbt/profiles",
    )

    quality_check = PythonOperator(
        task_id="check_data_quality",
        python_callable=check_data_quality,
    )

    ingest >> load >> quality_check >> dbt_run >> dbt_test
