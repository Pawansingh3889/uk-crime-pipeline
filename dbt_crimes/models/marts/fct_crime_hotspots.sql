-- Start from tidied crimes that have a street name.
with base as (
    select * from {{ ref('stg_crimes') }}
    where street_name is not null
)
select
    city,
    street_name,
    category,
    count(*) as incident_count
from base
group by city, street_name, category
-- Keep only streets with at least 5 crimes of the same type, then the 100 busiest.
having count(*) >= 5
order by incident_count desc
limit 100