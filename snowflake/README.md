# Snowflake + Airflow + dbt path

The same pipeline, run on Snowflake and orchestrated by Airflow:

```
Police UK API → load_snowflake.py → @CRIMES_STAGE → COPY INTO temp table → MERGE into RAW.CRIMES
                                                                                   │
                         Airflow DAG uk_crime_snowflake  ──────────────────────────┤
                                                                                   ▼
                                     dbt source freshness → dbt build (ANALYTICS schema)
```

The dbt models are shared with the PostgreSQL path: `--target dev` builds on Postgres, `--target snowflake` on Snowflake.

This page is the one-time setup. For day-to-day running, fixing and stopping, see [`RUNBOOK.md`](../RUNBOOK.md).

## 1. Snowflake account (10 min)

1. Sign up for a free trial at signup.snowflake.com (Standard edition, AWS, any region).
2. Find your account identifier: Snowsight → bottom-left menu → your account → "Connect a tool to Snowflake". It looks like `ORGNAME-ACCOUNTNAME`.

## 2. Key pair for the pipeline user (2 min)

```bash
mkdir -p ~/.snowflake
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out ~/.snowflake/crime_rsa_key.p8 -nocrypt
openssl rsa -in ~/.snowflake/crime_rsa_key.p8 -pubout -out ~/.snowflake/crime_rsa_key.pub
grep -v "PUBLIC KEY" ~/.snowflake/crime_rsa_key.pub | tr -d '\n'; echo
```

Copy the last line's output.

## 3. Create warehouse, database, roles, user (5 min)

Open a worksheet in Snowsight, paste `snowflake/setup.sql`, replace `PASTE_PUBLIC_KEY_HERE` with your key, and run all.

## 4. Local tools (10 min)

```bash
cd ~/Projects/uk-crime-pipeline
uv tool install --python 3.12 dbt-core --with dbt-snowflake --with dbt-postgres
uv venv --python 3.12 .venv
uv pip install --python .venv "apache-airflow==2.10.5" snowflake-connector-python requests python-dotenv pandas \
  --constraint https://raw.githubusercontent.com/apache/airflow/constraints-2.10.5/constraints-3.12.txt

export SNOWFLAKE_ACCOUNT=ORGNAME-ACCOUNTNAME
export SNOWFLAKE_PRIVATE_KEY_PATH=~/.snowflake/crime_rsa_key.p8
```

## 5. Run each piece by hand first

```bash
# Extract and load one month
PYTHONPATH=. .venv/bin/python -m ingestion.load_snowflake 2024-10

# Run it again: "inserted 0 new" proves the load is idempotent
PYTHONPATH=. .venv/bin/python -m ingestion.load_snowflake 2024-10

# Transform and test
cd dbt_crimes
dbt debug --target snowflake --profiles-dir .
dbt source freshness --target snowflake --profiles-dir .
dbt build --target snowflake --profiles-dir .
dbt docs generate --target snowflake --profiles-dir . && dbt docs serve --profiles-dir .
cd ..
```

## 6. Run it from Airflow

```bash
export AIRFLOW_HOME=$PWD/.airflow AIRFLOW__CORE__DAGS_FOLDER=$PWD/dags AIRFLOW__CORE__LOAD_EXAMPLES=False PYTHONPATH=$PWD
.venv/bin/airflow standalone
```

Open http://localhost:8080 (login printed in the terminal), switch on `uk_crime_snowflake`, then "Trigger DAG w/ config" with `{"month": "2024-09"}`. Watch the four tasks go green and open each task's log.

Without the UI: `.venv/bin/airflow dags test uk_crime_snowflake`.

## 7. Look around in Snowsight

```sql
USE ROLE SYSADMIN; USE WAREHOUSE CRIME_WH;
SELECT city, COUNT(*) FROM CRIME_DB.RAW.CRIMES GROUP BY city;
SELECT * FROM CRIME_DB.ANALYTICS.FCT_MONTHLY_TREND ORDER BY month, city;

-- Query history: what each step cost and how many partitions it scanned
SELECT query_text, warehouse_size, total_elapsed_time, partitions_scanned, partitions_total
FROM TABLE(CRIME_DB.INFORMATION_SCHEMA.QUERY_HISTORY()) ORDER BY start_time DESC LIMIT 20;

-- Time Travel and zero-copy clone
DELETE FROM CRIME_DB.RAW.CRIMES WHERE city = 'Hull';
SELECT COUNT(*) FROM CRIME_DB.RAW.CRIMES AT(OFFSET => -120) WHERE city = 'Hull';
INSERT INTO CRIME_DB.RAW.CRIMES SELECT * FROM CRIME_DB.RAW.CRIMES AT(OFFSET => -120) WHERE city = 'Hull';
CREATE DATABASE CRIME_DB_DEV CLONE CRIME_DB;
DROP DATABASE CRIME_DB_DEV;
```

## 8. Break it on purpose (this is the interview practice)

| Break | What you should see | Then explain |
|---|---|---|
| Unset `SNOWFLAKE_ACCOUNT`, trigger the DAG | `extract_load` fails, retries twice, `dbt_*` never run | retries, upstream failure, fail loudly |
| `UPDATE RAW.CRIMES SET city = 'Paris' WHERE crime_id IN (SELECT crime_id FROM RAW.CRIMES LIMIT 5)` then `dbt build` | `accepted_values` test on `city` fails | tests as a quality gate |
| Wrong role: `USE ROLE CRIME_TRANSFORMER; INSERT INTO RAW.CRIMES ...` | insufficient privileges | RBAC, least privilege |
| `ALTER WAREHOUSE CRIME_WH SET WAREHOUSE_SIZE = 'SMALL'`, rerun `dbt build` | faster or not, double credits/hour | sizing and cost |
| Make `fct_crimes_by_city` incremental with `unique_key` | second run only merges new months | incremental models, MERGE |

When finished: `ALTER WAREHOUSE CRIME_WH SUSPEND;` The resource monitor in setup.sql also stops it at 5 credits a month.
