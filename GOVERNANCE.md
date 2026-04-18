# UK Crime Analytics Pipeline governance

A small, focused pipeline for public crime data. Governance matches the
project's scope — short, clear, explicit about the data-provenance bar.

## Roles

### Maintainer

Currently: **[@Pawansingh3889](https://github.com/Pawansingh3889)**.

Final decision on:

- merges to `main`
- dependency additions
- changes to `ingestion/` (the data-integrity surface)
- changes to SLOs in `slos.yml`
- this governance document

Commits to:

- replying to issues and PRs within **7 calendar days**
- merging green, in-scope PRs within **14 calendar days** of the last
  review comment being addressed

### Triage collaborator

Granted to contributors with three merged, in-scope PRs. Can label,
assign, and close duplicate / off-topic issues. Cannot merge or change
repository settings.

### Contributor

Anyone who files an issue or opens a PR.

## Decisions

Small changes (docs, tests, bug fixes) — one maintainer approval on the
PR.

Larger changes — new cities, new data sources, new dbt marts, schema
changes to published datasets — start as an **issue with a proposal**:

1. what question it helps researchers / journalists / citizens answer
2. the change in bullet form
3. how data provenance and licensing are preserved
4. whether existing SLOs need to adjust

## Issue assignment (first-PR-wins)

1. Comment "I'd like to work on this" — 7-day soft claim.
2. Expire silently after 7 days; anyone may pick up.
3. If two PRs land, the first to pass CI and request review wins.

## Scope discipline

Hard lines that will not move:

- **Public-data-only.** Every source must be publicly accessible
  without a paid credential. Police.UK's Open Government Licence is
  the current anchor; new sources must have a comparable public
  licence documented in `NOTICE`.
- **Declarative validation at ingest.** Rows that fail the bounds /
  nulls / categories checks go to a rejected bucket; they do not
  enter the warehouse quietly.
- **SLOs are measured, not asserted.** Freshness / completeness /
  volume targets live in `slos.yml` and run in CI. Adding a new SLO
  means adding the test that measures it.
- **No private analytics.** This project makes public data easier
  to analyse, not harder to understand. PRs that obscure provenance
  or hide the raw query layer are off-scope.

## Release cadence

Continuous deployment from `main`. No tagged releases today. If that
changes:

- SemVer starting at 0.x
- breaking changes get one minor version of deprecation notice
- `CHANGELOG.md` will land before the first non-zero release

## Security

See `SECURITY.md`. Security issues route via private advisory.

## Changes to this document

Via PR from the maintainer. Community input welcome in issues.
