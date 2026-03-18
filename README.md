# UK Crime Analytics Pipeline

[![CI](https://github.com/Pawansingh3889/uk-crime-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/Pawansingh3889/uk-crime-pipeline/actions/workflows/ci.yml)
[![Health Check](https://github.com/Pawansingh3889/uk-crime-pipeline/actions/workflows/health_check.yml/badge.svg)](https://github.com/Pawansingh3889/uk-crime-pipeline/actions/workflows/health_check.yml)
[![Scheduled Ingest](https://github.com/Pawansingh3889/uk-crime-pipeline/actions/workflows/scheduled_ingest.yml/badge.svg)](https://github.com/Pawansingh3889/uk-crime-pipeline/actions/workflows/scheduled_ingest.yml)

A live end-to-end data engineering pipeline that ingests real crime data from the Police UK API, transforms it with dbt, orchestrates runs with Prefect, and serves a public interactive dashboard on Streamlit Cloud.

**Live dashboard:** https://uk-crime-pipeline-6nydeza7je8kiwsfl6deuw.streamlit.app

---

## What this project proves

| Capability | Why it matters |
|---|---|
| Live API ingestion | Real government data, not static CSVs |
| PostgreSQL | Operational database in 60% of DE job descriptions |
| Incremental-ready dbt models | Production pattern — only process new data |
| Cloud database (Neon) | Data accessible from anywhere, not just localhost |
| Public Streamlit dashboard | Proof of delivery — a URL you can share |
| Prefect orchestration | Scheduled, monitored, automated |

---

## Architecture

```
Police UK API (data.police.uk — free, no auth, updates monthly)
        ↓
Python ingestion (fetch_crimes.py)
— 10 cities × 6 months
— Idempotent upserts via ON CONFLICT DO NOTHING
        ↓
PostgreSQL — raw.crimes (99,675 rows)
        ↓
dbt-postgres transformation layer
— stg_crimes (view)
— fct_crimes_by_city (table — 814 rows)
— fct_monthly_trend (table — 60 rows)
— fct_crime_hotspots (table — 100 rows)
        ↓
Neon cloud PostgreSQL (free tier — analytics schema)
        ↓
Streamlit dashboard (deployed on Streamlit Cloud — public URL)
```

---

## Data

| Source | Records | Coverage |
|---|---|---|
| Police UK API | 99,675 crime incidents | 10 UK cities, May–Oct 2024 |

**Cities covered:** Hull, London, Birmingham, Manchester, Leeds, Sheffield, Liverpool, Bristol, Nottingham, Newcastle

**Crime categories:** anti-social behaviour, violent crime, shoplifting, vehicle crime, burglary, drugs, public order, and more.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Ingestion | Python, Requests, SQLAlchemy |
| Storage | PostgreSQL (local), Neon (cloud) |
| Transformation | dbt-postgres — 4 models, staging + marts |
| Orchestration | Prefect 3 |
| Dashboard | Streamlit, Plotly |
| Deployment | Streamlit Cloud (free), Neon free tier |

---

## dbt Models

```
dbt_crimes/models/
├── staging/
│   └── stg_crimes.sql          — view: cleans and casts raw.crimes
└── marts/
    ├── fct_crimes_by_city.sql   — table: crime count + unsolved % by city/category/month
    ├── fct_monthly_trend.sql    — table: total crimes + crime types per city per month
    └── fct_crime_hotspots.sql   — table: top 100 street-level hotspots (≥5 incidents)
```

---

## Dashboard Features

- **KPI cards** — total incidents, cities, months, under investigation count
- **Monthly trend** — interactive multi-city line chart with city filter
- **City comparison** — horizontal bar chart sorted by total crimes
- **Category breakdown** — top 10 crime types per selected city
- **Crime hotspots** — street-level table filtered by city, sorted by incident count

---

## Project Structure

```
uk-crime-pipeline/
├── .github/workflows/
│   ├── ci.yml                # Lint + API health + dbt validation on push/PR
│   ├── scheduled_ingest.yml  # Weekly Monday 6am auto-ingestion
│   └── health_check.yml      # Daily 8am API + DB + data freshness checks
├── ingestion/
│   └── fetch_crimes.py       # Police UK API → PostgreSQL (idempotent)
├── dbt_crimes/
│   ├── dbt_project.yml
│   ├── profiles.yml
│   └── models/
│       ├── staging/
│       └── marts/
├── tests/
│   ├── test_api_health.py    # Verifies Police UK API reachability
│   ├── test_db_health.py     # Verifies database connectivity
│   └── test_data_freshness.py # Validates row counts and city coverage
├── dashboard/
│   └── app.py                # Streamlit dashboard
├── .streamlit/
│   └── secrets.toml          # Not committed — set in Streamlit Cloud
├── .env                      # Not committed — local development only
├── requirements.txt
└── .gitignore
```

---

## How to Run Locally

**1. Clone and install**

```bash
git clone https://github.com/Pawansingh3889/uk-crime-pipeline.git
cd uk-crime-pipeline
pip install -r requirements.txt
```

**2. Create `.env`**

```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=crime_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

**3. Start PostgreSQL via Docker**

```bash
docker run -d --name crimes-postgres \
  -e POSTGRES_PASSWORD=crimes123 \
  -e POSTGRES_DB=crime_db \
  -p 5432:5432 postgres:15
```

**4. Run ingestion**

```bash
python ingestion/fetch_crimes.py
```

Fetches ~99,000 crime records from the live Police UK API across 10 cities and 6 months. Takes ~3 minutes.

**5. Run dbt**

```bash
cd dbt_crimes
dbt run --profiles-dir .
dbt test --profiles-dir .
```

**6. Run Streamlit**

```bash
cd ..
streamlit run dashboard/app.py
```

Opens at `http://localhost:8501`.

---

## CI/CD Pipeline

Three GitHub Actions workflows automate testing, ingestion, and monitoring:

| Workflow | Trigger | What it does |
|---|---|---|
| **CI** | Every push/PR to `main` | Lints Python with ruff, checks Police UK API health, runs full dbt compile + run + test against a fresh PostgreSQL service container |
| **Scheduled Ingest** | Every Monday 6am UTC | Fetches latest crime data from API, loads to PostgreSQL, runs dbt transformations, uploads pipeline logs as artifacts |
| **Health Check** | Daily 8am UTC | Verifies API reachability, database connectivity, and data freshness (row counts + city coverage) |

All workflows can also be triggered manually via `workflow_dispatch`.

---

## Key Engineering Decisions

| Decision | Why |
|---|---|
| `ON CONFLICT DO NOTHING` upserts | Safe to re-run ingestion without duplicating data |
| Neon free tier for cloud PostgreSQL | Serverless, scales to zero, free 0.5GB — enough for this dataset |
| Single `DATABASE_URL` secret | Simpler than 5 separate secrets; works identically locally and on Streamlit Cloud |
| dbt staging → marts pattern | Same architecture as Apex — consistent, testable, lineage-tracked |
| `@st.cache_data(ttl=300)` | Dashboard caches DB queries for 5 minutes — fast page loads |