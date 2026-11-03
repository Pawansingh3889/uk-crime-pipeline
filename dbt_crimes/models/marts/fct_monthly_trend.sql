with base as (
    select * from {{ ref('stg_crimes') }}
)
select
    month,
    city,
    count(*)                 as total_crimes,
    count(distinct category) as crime_types,
    sum(case when outcome_status is null then 1 else 0 end) as unsolved
from base
group by month, city
order by month, city