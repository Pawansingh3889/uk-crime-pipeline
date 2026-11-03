# Runbook: running and operating the pipeline

How to start, run, check, fix and stop the UK crime pipeline on Snowflake, in plain language.
First-time setup (Snowflake account, key, roles) is in [`snowflake/README.md`](snowflake/README.md). Do that once, then use this page.

## The pipeline in one picture

```
Police website ──▶ loader (Python) ──▶ Snowflake raw shelf ──▶ dbt ──▶ summary tables
                       ▲                                        ▲
                       └──────────── Airflow runs both, in order ┘
```

| Part | What it is | Where |
|---|---|---|
| Loader | Fetches one month of crimes for 10 cities and puts new ones on the raw shelf | `ingestion/load_snowflake.py` |
| Raw shelf | Table holding every crime exactly as fetched | `CRIME_DB.RAW.CRIMES` |
| dbt | Tidies the raw crimes and builds 5 summary tables, then tests them | `dbt_crimes/` |
| Summary tables | What dashboards and analysts read | `CRIME_DB.ANALYTICS.*` |
| Airflow | The timetable that runs loader then dbt, and retries if something fails | `dags/crime_pipeline_snowflake_dag.py` |

## Before any command: set your two settings

Every terminal window needs these, or Snowflake will refuse the login.

```bash
cd ~/Projects/uk-crime-pipeline
export SNOWFLAKE_ACCOUNT=YOUR-ACCOUNT-ID                      # from Snowsight: your name, bottom left, Account
export SNOWFLAKE_PRIVATE_KEY_PATH=~/.snowflake/crime_rsa_key.p8  # the robot worker's secret key
```

## Everyday operations

### Load one month by hand
```bash
PYTHONPATH=. .venv/bin/python -m ingestion.load_snowflake 2024-10
```
Ends with `Fetched N rows, inserted M new`. Police data appears about two months late, so the latest month may return nothing.

### Load several months (backfill)
```bash
PYTHONPATH=. .venv/bin/python -m ingestion.load_snowflake 2024-05 2024-06 2024-07
```

### Run the same month again
Safe. Already-loaded crimes are skipped, so it says `inserted 0 new`. Use this after any failure.

### Rebuild and test all summary tables
```bash
cd dbt_crimes && dbt build --target snowflake --profiles-dir . && cd ..
```
Expect `PASS=37`. If a test on the tidied data fails, dbt skips the summary tables so bad data never reaches them.

### Rebuild just one table
```bash
cd dbt_crimes && dbt build --target snowflake --profiles-dir . --select fct_monthly_trend && cd ..
```
Add `+` in front (`--select +fct_monthly_trend`) to also rebuild everything it depends on.

### Run the tests only
```bash
cd dbt_crimes && dbt test --target snowflake --profiles-dir . && cd ..
```

### Check the raw shelf was refilled recently
```bash
cd dbt_crimes && dbt source freshness --target snowflake --profiles-dir . && cd ..
```
Warns after 35 days without new data, fails after 70.

### See the documentation and lineage picture
```bash
cd dbt_crimes && dbt docs generate --target snowflake --profiles-dir . && dbt docs serve --port 8081 --profiles-dir .
```
Opens a website. Click the blue circle bottom right to see how tables connect. Press Ctrl+C to stop it.

## Running it with Airflow

### Start Airflow (first time on this laptop)
Runs Airflow inside Docker, because Airflow's web server crashes on macOS.
```bash
docker run -d --name ukc-airflow -p 8080:8080 \
  -v "$PWD":/opt/airflow/project \
  -v ~/.snowflake:/opt/airflow/.snowflake:ro \
  -e AIRFLOW__CORE__DAGS_FOLDER=/opt/airflow/project/dags \
  -e AIRFLOW__CORE__LOAD_EXAMPLES=False \
  -e PYTHONPATH=/opt/airflow/project \
  -e SNOWFLAKE_ACCOUNT="$SNOWFLAKE_ACCOUNT" \
  -e SNOWFLAKE_PRIVATE_KEY_PATH=/opt/airflow/.snowflake/crime_rsa_key.p8 \
  apache/airflow:2.10.5-python3.12 \
  bash -c 'pip install -q snowflake-connector-python python-dotenv && python -m venv /opt/airflow/dbtenv && /opt/airflow/dbtenv/bin/pip install -q dbt-core dbt-snowflake && ln -sf /opt/airflow/dbtenv/bin/dbt $(dirname $(which airflow))/dbt && exec airflow standalone'
```
Takes about 80 seconds to be ready.

### Start Airflow (after the first time)
```bash
docker start ukc-airflow
```

### Log in
```bash
docker exec ukc-airflow cat /opt/airflow/standalone_admin_password.txt
```
Open http://localhost:8080, user `admin`, password from the command above.

### Run the pipeline for a month
1. Switch on `uk_crime_snowflake` with the toggle on the left.
2. Press ▶ on the right, choose **Trigger DAG w/ config**.
3. Enter `{"month": "2024-10"}` (year-month, with quotes) and press **Trigger**.
4. Open the DAG, **Graph** tab: four boxes turn green in order.

Switching the DAG on also starts one automatic run for two months ago. If the police have not published that month yet, it fails and that is expected.

### Read what a step did
Click a box in the Graph, then **Logs**.

### Fix a failed run
1. Click the red box, read **Logs** to find why.
2. Fix the cause (wrong month format, Snowflake settings, website down).
3. Click the box, then **Clear** to run it again. Safe, because loads skip duplicates.

### Stop a run that keeps retrying
Click the yellow box, then **Mark state as → failed**.

### Stop Airflow
```bash
docker stop ukc-airflow
```

## Checking things in Snowflake

Run these in a Snowsight SQL file (Work with data → Projects).

```sql
USE ROLE SYSADMIN;
USE WAREHOUSE CRIME_WH;

-- How many crimes per month on the raw shelf
SELECT month, COUNT(*) FROM CRIME_DB.RAW.CRIMES GROUP BY month ORDER BY month;

-- How many crimes per city
SELECT city, COUNT(*) FROM CRIME_DB.RAW.CRIMES GROUP BY city ORDER BY 2 DESC;

-- A summary table
SELECT * FROM CRIME_DB.ANALYTICS.FCT_MONTHLY_TREND ORDER BY city, month;

-- When each month was last loaded
SELECT fetch_month, MAX(loaded_at) FROM CRIME_DB.RAW.CRIMES GROUP BY 1 ORDER BY 1;
```

To see what the pipeline ran: **Monitoring → Query History**, filter user `CRIME_PIPELINE`.

## Less common operations

### Remove a bad month and load it again
```sql
DELETE FROM CRIME_DB.RAW.CRIMES WHERE fetch_month = '2024-10';
```
Then load that month by hand and run `dbt build`.

### Undo an accidental delete (Time Travel)
Snowflake keeps the table's past for 1 day. Put back rows as they were 10 minutes ago:
```sql
INSERT INTO CRIME_DB.RAW.CRIMES
SELECT * FROM CRIME_DB.RAW.CRIMES AT(OFFSET => -600)
WHERE fetch_month = '2024-10'
  AND crime_id NOT IN (SELECT crime_id FROM CRIME_DB.RAW.CRIMES WHERE fetch_month = '2024-10');
```

### Make a safe copy to experiment on (zero-copy clone)
```sql
CREATE DATABASE CRIME_DB_DEV CLONE CRIME_DB;   -- instant, costs nothing until you change it
DROP DATABASE CRIME_DB_DEV;                    -- when finished
```

### Add a new city
1. Add it to `LOCATIONS` in `ingestion/fetch_crimes.py` (name, latitude, longitude).
2. Add the name to the `city` accepted values in `dbt_crimes/models/staging/_stg_crimes.yml`, or the test will fail.
3. Load the months you want, then `dbt build`.

### Check what it is costing
- **Manage → Compute → CRIME_WH**: credits used.
- **Admin → Cost management**: spend over time.
- The budget `CRIME_RM` switches the warehouse off at 5 credits a month.

### Switch the warehouse off now
```sql
ALTER WAREHOUSE CRIME_WH SUSPEND;
```
It wakes up by itself on the next query.

### Replace the robot worker's key
```bash
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out ~/.snowflake/crime_rsa_key.p8 -nocrypt
openssl rsa -in ~/.snowflake/crime_rsa_key.p8 -pubout | grep -v "PUBLIC KEY" | tr -d '\n'; echo
```
Then in Snowflake, as ACCOUNTADMIN: `ALTER USER CRIME_PIPELINE SET RSA_PUBLIC_KEY='<the printed line>';`

## When something goes wrong

| You see | It means | Do this |
|---|---|---|
| `JWT token is invalid` | Snowflake does not recognise the robot worker's key | Check `DESC USER CRIME_PIPELINE;` shows a key fingerprint; reset the key (above) |
| `KeyError: 'SNOWFLAKE_ACCOUNT'` | The two settings are not set in this terminal | Run the two `export` lines at the top |
| `No records fetched for [...]` | The police website returned nothing for that month | Check the month is `YYYY-MM` and is at least two months ago |
| `Validation: [FAIL] Manchester ... (min 50)` | Fewer crimes than expected for a city | Only a warning; the load continues. Greater Manchester data has known gaps |
| `Insufficient privileges` | The badge in use is not allowed to do that | Check which role you are using; loader writes raw, transformer builds analytics |
| dbt test `accepted_values ... city` fails | A city name appeared that is not on the list | Fix the data, or add the city to `_stg_crimes.yml` |
| dbt shows `SKIP` | A test on the tidied data failed first | Fix that failing test; skipped tables build next time |
| Airflow banner "scheduler does not appear to be running" | The simple local setup runs one task at a time | Normal locally; it clears when the task finishes |
| `Worker was sent SIGSEGV!` | Airflow run directly on macOS | Use the Docker way above |
| http://localhost:8080 does not open | Airflow is not running | `docker start ukc-airflow`, wait about a minute |
| Port 8080 already in use for dbt docs | Airflow is using it | Use `--port 8081` |

## Finish for the day

```bash
docker stop ukc-airflow
```
```sql
ALTER WAREHOUSE CRIME_WH SUSPEND;
```
