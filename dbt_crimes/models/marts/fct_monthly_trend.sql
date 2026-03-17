with base as (
    select * from {{ ref('stg_crimes') }}
)
select
    month,
    city,
    count(*)                 as total_crimes,
    count(distinct category) as crime_types,
    count(*) filter (where outcome_status is null) as unsolved
from base
group by month, city
order by month, city