# UK Crime Pipeline

End-to-end data pipeline. Police UK API to PostgreSQL to dbt to Streamlit.

\`\`\`
records   = 99675
dbt_tests = 53
ci_cd     = 3
stack     = ["Python", "PostgreSQL", "dbt", "Airflow", "Streamlit", "Terraform", "GitHub Actions"]
\`\`\`

[Live Dashboard](https://uk-crime-pipeline-6nydeza7je8kiwsfl6deuw.streamlit.app/)

---

## Architecture

\`\`\`
Police UK API -> Python -> PostgreSQL -> dbt (staging/marts) -> Streamlit
                                           |
                                      Airflow DAG
\`\`\`

**Ingestion** — pulls crime data from Police UK API into PostgreSQL

**Transformation** — dbt with staging/marts, 53 tests, incremental loads

**Orchestration** — Airflow DAG: ingest -> load -> quality check -> dbt run -> dbt test

**Infrastructure** — Terraform for AWS (RDS PostgreSQL + S3)

**Dashboard** — Streamlit with crime breakdowns, temporal trends, geographic analysis

---

## Quick start

\`\`\`bash
pip install -r requirements.txt
python scripts/ingest.py
dbt run && dbt test
streamlit run app.py
\`\`\`
