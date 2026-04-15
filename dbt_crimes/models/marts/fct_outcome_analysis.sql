-- Outcome analysis: resolution rates by city, category, and month.
-- Shows how different crime types get resolved across cities.

with base as (
    select * from {{ ref('stg_crimes') }}
),

outcome_counts as (
    select
        city,
        category,
        month,
        outcome_category,
        count(*) as outcome_count
    from base
    group by city, category, month, outcome_category
),

totals as (
    select
        city,
        category,
        month,
        count(*) as total_crimes,
        count(*) filter (
            where outcome_category in (
                'Local resolution',
                'Offender given a caution',
                'Offender given a drugs possession warning',
                'Offender given community resolution',
                'Offender given penalty notice',
                'Court result unavailable',
                'Awaiting court outcome',
                'Offender fined',
                'Suspect charged',
                'Suspect charged as part of another case',
                'Offender otherwise dealt with',
                'Offender sent to prison'
            )
        ) as resolved_count
    from base
    group by city, category, month
)

select
    oc.city,
    oc.category,
    oc.month,
    oc.outcome_category,
    oc.outcome_count,
    t.total_crimes,
    round(oc.outcome_count::numeric / nullif(t.total_crimes, 0) * 100, 1) as outcome_pct,
    round(t.resolved_count::numeric / nullif(t.total_crimes, 0) * 100, 1) as resolution_rate
from outcome_counts oc
join totals t
    on oc.city = t.city
    and oc.category = t.category
    and oc.month = t.month
order by oc.city, oc.category, oc.month, oc.outcome_count desc
