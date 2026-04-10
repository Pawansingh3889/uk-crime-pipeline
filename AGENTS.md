# AGENTS.md

## Purpose

End-to-end crime data pipeline that ingests real incident data from the Police UK API, transforms it through dbt, and serves it via interactive dashboards. This is a production system with automated ingestion, health checks, and a public Streamlit dashboard.

## Architecture

```
Police UK API  ->  Python ingestion (fetch_crimes.py)
                        |
                        v
               PostgreSQL / Neon (raw.crimes)
                        |
               +--------+--------+
               |                 |
               v                 v
        dbt-postgres        dbt-bigquery
        (dbt_crimes/)       (dbt_crimes_bq/)
               |                 |
               v                 v
        Streamlit Cloud     Looker Studio
        (dashboard/app.py)  (via BigQuery)
```

- **Ingestion**: `ingestion/fetch_crimes.py` -- fetches 10 cities x 6 months from data.police.uk, loads into PostgreSQL with idempotent `ON CONFLICT DO NOTHING` upserts.
- **PostgreSQL storage**: Neon serverless (free tier, scales to zero). Connection uses a single `DATABASE_URL` env var with retry/backoff logic.
- **dbt (PostgreSQL)**: `dbt_crimes/` -- 1 staging view + 3 mart tables, 53 tests.
- **dbt (BigQuery)**: `dbt_crimes_bq/` -- same model structure, 12 tests. Uses `SAFE_CAST` for type conversions. Authenticates via service account keyfile.
- **Dashboard**: `dashboard/app.py` -- Streamlit with Plotly charts, `@st.cache_data(ttl=300)` for 5-minute query caching.
- **Orchestration**: Prefect 3 DAG (ingest -> load -> quality checks -> dbt run -> dbt test).
- **CI/CD**: 3 GitHub Actions workflows (CI on push, Scheduled Ingest Monday 6am UTC, Health Check daily 8am UTC).

## Key files

| Path | Description |
|---|---|
| `ingestion/fetch_crimes.py` | API ingestion script -- fetches and loads crime data |
| `dbt_crimes/` | dbt project for PostgreSQL (Neon) |
| `dbt_crimes/models/staging/stg_crimes.sql` | Staging view -- cleans and casts raw data |
| `dbt_crimes/models/marts/fct_crimes_by_city.sql` | Crime counts and unsolved % by city/category/month |
| `dbt_crimes/models/marts/fct_monthly_trend.sql` | Total crimes and types per city per month |
| `dbt_crimes/models/marts/fct_crime_hotspots.sql` | Top streets with >= 5 incidents |
| `dbt_crimes_bq/` | dbt project for BigQuery (Looker Studio) |
| `dbt_crimes_bq/models/staging/stg_crimes.sql` | BigQuery staging view with SAFE_CAST |
| `dbt_crimes_bq/models/marts/` | BigQuery mart models (same structure as PostgreSQL) |
| `dashboard/app.py` | Streamlit dashboard entry point |
| `orchestration/flow.py` | Prefect flow definition |

## Data overview

- **10 cities**: Hull, London, Birmingham, Manchester, Leeds, Sheffield, Liverpool, Bristol, Nottingham, Newcastle
- **99,675 records** across 6 months (May--Oct 2024)
- **3 CI/CD workflows** with `workflow_dispatch` support

## Testing

### PostgreSQL (53 tests)

```bash
cd dbt_crimes
dbt test --profiles-dir .
```

Tests include: `not_null` on every key column, `unique` on composite keys, `accepted_values` on crime categories, `relationships` between staging and marts, row count assertions.

### BigQuery (12 tests)

```bash
cd dbt_crimes_bq
dbt test --profiles-dir .
```

Tests include: `not_null`, `unique`, and `accepted_values` on staging and mart models.

### Running dbt models

```bash
# PostgreSQL
cd dbt_crimes && dbt run --profiles-dir .

# BigQuery
cd dbt_crimes_bq && dbt run --profiles-dir .
```

## Conventions

- **Staging views + mart tables**: staging models are views that clean/cast raw data; mart models are tables with business logic.
- **Idempotent upserts**: all INSERT statements use `ON CONFLICT DO NOTHING` so ingestion is safe to re-run.
- **SAFE_CAST in BigQuery**: all type conversions in `dbt_crimes_bq/` use `SAFE_CAST` to avoid runtime errors on bad data.
- **Single DATABASE_URL**: PostgreSQL connection uses one env var rather than separate host/port/db/user/pass.
- **Dashboard caching**: Streamlit queries are cached for 5 minutes via `@st.cache_data(ttl=300)`.

## Sensitive files -- never commit

- `keyfile.json` -- BigQuery service account credentials
- `.env` -- environment variables including `DATABASE_URL`
- Any file containing database credentials or API keys

## Local development

```bash
# Prerequisites: Docker, Python 3.x, pip
pip install -r requirements.txt

# Start local PostgreSQL
docker run -d --name crimes-postgres \
  -e POSTGRES_PASSWORD=crimes123 \
  -e POSTGRES_DB=crime_db \
  -p 5432:5432 postgres:15

# Ingest data (~3 minutes)
python ingestion/fetch_crimes.py

# Transform and test (PostgreSQL)
cd dbt_crimes
dbt run --profiles-dir .
dbt test --profiles-dir .

# Launch dashboard
streamlit run dashboard/app.py
```
