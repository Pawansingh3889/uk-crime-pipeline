# Contributing to UK Crime Analytics Pipeline

A public-data pipeline, continuously deployed, solo-maintained.
Contributions are welcome; the rules below keep the project honest
about provenance, SLOs, and anonymity (there is none required — this
is all public data — but the **no-spoofing** rule matters).

Before you start, skim:

- [**`GOVERNANCE.md`**](GOVERNANCE.md) — decision-making, first-PR-wins.
- [**`CODE_OF_CONDUCT.md`**](CODE_OF_CONDUCT.md) — behavioural bar.
- [**`SECURITY.md`**](SECURITY.md) — security bugs go there, not
  in a public issue.

## The Prime Directive

**Public data only. Declarative validation before the warehouse.**
Every row that enters the project-owned warehouse has either passed
the checks in `ingestion/validators.py` or been diverted to a rejected
bucket. PRs that skip validation for any reason (speed, convenience,
"just this one source") will be rejected.

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/uk-crime-pipeline.git
cd uk-crime-pipeline
pip install -r requirements.txt
pytest -q               # 65 tests across postgres + bigquery
```

Running the pipeline locally against your own PostgreSQL is documented
in README. The published dashboards run off the project-owned warehouse.

## How to Contribute

1. **Find or open an issue.** Good labels to watch: `good first issue`,
   `help wanted`, `data-quality`.
2. **Claim it** by commenting — earns a 7-day soft claim per
   `GOVERNANCE.md`.
3. **Branch.** `feature/<short-name>` or `bugfix/<short-name>`.
4. **Code + test.** Every new ingestion path gets validator coverage;
   every new SLO gets a test that measures it.
5. **Before pushing** — run `ruff check .`, `mypy ingestion/`, and
   `pytest -q`. Don't skip CI locally; GitHub Actions will fail the
   same checks.
6. **Open the PR.** Explain *what*, *why*, and *what you tested*.
   One logical change per commit, conventional commit style
   (`feat:`, `fix:`, `docs:`, `chore:`, `ci:`, `test:`, `style:`).

Larger changes (new cities, new data sources, new dbt marts, schema
changes to published datasets) start as an **issue with a proposal**,
not a surprise PR. See `GOVERNANCE.md` § Decisions for the shape.

## Code Standards

- Python 3.11+.
- Ruff + mypy must pass.
- Type hints on public functions.
- Docstrings explain the *why*, not just the *what*.
- Tests for new code go under `tests/`.

## Data provenance rules

- Source every new dataset to a publicly accessible URL with a known
  licence. Police.UK is Open Government Licence v3.0; that's documented
  in `NOTICE`. A new source needs a comparable entry before the PR
  lands.
- Do not sync, cache, or republish personal identifiers. The Police
  API redacts these before publication — don't undo that.
- Derived datasets inherit the upstream licence. Don't accidentally
  re-license downstream.

## Reporting bugs

Open an issue with:

- Reproduction steps
- Expected vs actual
- Python version, OS
- Redacted traceback. **Do not paste warehouse credentials.**

## Feature requests

Open an issue describing:

- The question this helps researchers / journalists / citizens answer
- Which module it affects
- Whether it needs a new dependency (default answer: no)

## Recognition

Merged PRs land in the commit history permanently. Substantial
contributions are acknowledged in the README when appropriate.
