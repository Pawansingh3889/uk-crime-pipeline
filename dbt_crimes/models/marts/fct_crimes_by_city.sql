with base as (
    select * from {{ ref('stg_crimes') }}
)
select
    city,
    category,
    month,
    count(*)                                           as crime_count,
    sum(case when outcome_status is null then 1 else 0 end)     as unsolved_count,
    round(
        sum(case when outcome_status is null then 1 else 0 end)::numeric
        / nullif(count(*), 0) * 100, 1
    )                                                  as unsolved_pct
from base
group by city, category, month
order by city, month, crime_count desc