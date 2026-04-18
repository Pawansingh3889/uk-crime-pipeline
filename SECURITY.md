# Security policy

This pipeline ingests public data and writes to project-owned PostgreSQL
and BigQuery warehouses. The security surface is narrower than a typical
production system, but still worth taking seriously.

## Supported versions

Continuous deployment from `main`. The supported version is always the
latest commit on `main`.

## Threat model

| Surface | Protection | Where |
| --- | --- | --- |
| Police.UK API | Public data, rate-limited at the source; resilient fetch via `stamina` + `diskcache` | `ingestion/` |
| Ingestion | Declarative bounds / nulls / category checks before warehouse load | `ingestion/validators.py` |
| Warehouse credentials | Environment variables only; no secrets in code | `.github/workflows/*.yml`, `infra/` |
| Dashboard | Read-only SQL queries via the warehouse's service-role credentials | `dashboard/`, `dbt_crimes/` |
| SLO monitoring | Tests in CI that read `slos.yml` and fail the build if thresholds slip | `slos.yml`, `tests/test_slos.py` |

## Reporting a vulnerability

**Do not open a public GitHub issue.**

Report privately via the GitHub security advisory form:

<https://github.com/Pawansingh3889/uk-crime-pipeline/security/advisories/new>

Include:

1. **What you found** — one-sentence description.
2. **Reproduction** — exact steps or commands.
3. **Impact** — what an attacker could do.
4. **Suggested fix** — optional, but appreciated.

## What to expect

| Severity | Initial response | Fix target |
| --- | --- | --- |
| Critical (warehouse write bypass, credential leak) | within 48 hours | within 7 days |
| High (data corruption, SLO spoofing) | within 5 days | within 14 days |
| Medium | within 7 days | next minor cycle |
| Low / info | within 14 days | when scoped |

## Coordinated disclosure

90 days from report to public disclosure by default; earlier if the
fix is deployed and you agree.

## Scope

**In scope:**

- `ingestion/`, `dbt_crimes/`, `dashboard/`, `dags/`, `tests/`, `infra/`
- Workflow definitions in `.github/workflows/`
- Configuration files (`slos.yml`, `requirements.txt`, `pyproject.toml`)

**Out of scope:**

- Upstream data issues in Police.UK (report to them)
- Upstream dependency CVEs (report upstream; link here so we can pin)
- Social engineering of the maintainer or contributors
- Streamlit Cloud / Looker Studio / Hugging Face platform issues

## Previous advisories

None.
