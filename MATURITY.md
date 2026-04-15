# Pipeline Maturity Scorecard

Self-assessment against the Data Pipeline Operations Maturity Model (PyCon DE 2026, Akif Cakir).

## Scoring: 5 Levels

1. **Struggling** — Manual scripts, no monitoring, reactive firefighting
2. **Basic** — Some automation, ad-hoc quality checks
3. **Decent** — Scheduled orchestration, declarative validation, basic SLOs
4. **Strong** — Event-driven triggers, anomaly detection, automated alerting
5. **Mastery** — Self-healing, fully measured SLOs with error budgets

---

## Pillar 1: Orchestration — Level 3 (Decent)

| Evidence | Where |
|---|---|
| Scheduled weekly ingest | `.github/workflows/scheduled_ingest.yml` (cron: Monday 6am) |
| Airflow DAG defined | `dags/crime_pipeline_dag.py` (daily 6am, retry x2) |
| 3 CI/CD workflows | ci.yml, health_check.yml, scheduled_ingest.yml |
| Idempotent upserts | `ON CONFLICT DO NOTHING` in fetch_crimes.py |
| Retry with backoff | 3 retries, exponential backoff on API calls |

**Why not Level 4:** No event-driven triggers (e.g. "Police UK published new data" -> pipeline runs). No dynamic DAGs. No automated backfills for missed months.

**Next steps to Level 4:**
- Add a webhook or polling check for Police UK API data availability
- Implement backfill logic for months that failed ingestion
- Add Prefect or Dagster as a more capable orchestrator

---

## Pillar 2: Data Quality — Level 3-4

| Evidence | Where |
|---|---|
| Declarative validation | `ingestion/validators.py` (fluent API, 5 checks) |
| Write-audit-publish | Validation runs before load in fetch_crimes.py |
| 65 dbt tests | `dbt_crimes/` (53 PostgreSQL + 12 BigQuery) |
| Known category set | `POLICE_UK_CATEGORIES` frozenset validation |
| UK bounds checking | Lat/lng validated against bounding box |
| Pre-commit SQL lint | `.pre-commit-config.yaml` with sql-sop |

**Why not Level 4:** No anomaly detection (e.g. sudden 50% crime spike = data issue or real event?). No automated data profiling. Validators check structure but not statistical properties.

**Next steps to Level 4:**
- Add z-score anomaly detection on batch row counts per city
- Add Great Expectations or dataframe-expectations for richer validation
- Profile data distributions monthly and alert on drift

---

## Pillar 3: Data SLOs — Level 3

| Evidence | Where |
|---|---|
| SLOs defined | `slos.yml` (freshness, completeness, volume, availability) |
| Monitoring tests | `tests/test_slos.py` (freshness, null rates, batch volumes) |
| Health check workflow | `.github/workflows/health_check.yml` (daily 8am) |

**Why not Level 4:** No automated alerting when SLOs breach (Slack/email). No error budgets. No SLO dashboard. Tests run but nobody gets notified automatically.

**Next steps to Level 4:**
- Add Slack webhook alerts when SLO tests fail
- Define error budgets (e.g. 2 SLO breaches per month allowed)
- Build an SLO dashboard in Streamlit or Grafana
- Track SLO history over time (not just current state)

---

## Summary

| Pillar | Current | Target | Gap |
|---|---|---|---|
| Orchestration | 3 | 4 | Event-driven triggers, backfills |
| Data Quality | 3-4 | 4 | Anomaly detection, data profiling |
| Data SLOs | 3 | 4 | Automated alerting, error budgets |

**Overall: Level 3 (Decent)** — The pipeline is automated, tested, and monitored. The main gap is proactive alerting and anomaly detection.
