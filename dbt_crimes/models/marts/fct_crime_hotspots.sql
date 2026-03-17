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
having count(*) >= 5
order by incident_count desc
limit 100