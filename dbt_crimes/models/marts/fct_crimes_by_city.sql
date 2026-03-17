with base as (
    select * from {{ ref('stg_crimes') }}
)
select
    city,
    category,
    month,
    count(*)                                           as crime_count,
    count(*) filter (where outcome_status is null)     as unsolved_count,
    round(
        count(*) filter (where outcome_status is null)::numeric
        / nullif(count(*), 0) * 100, 1
    )                                                  as unsolved_pct
from base
group by city, category, month
order by city, month, crime_count desc