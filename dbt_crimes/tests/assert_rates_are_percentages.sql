-- Unsolved counts can never exceed the total, and every rate must sit between 0 and 100.
select 'fct_crimes_by_city' as model, city, month
from {{ ref('fct_crimes_by_city') }}
where unsolved_count > crime_count or unsolved_pct not between 0 and 100
union all
select 'fct_outcome_analysis', city, month
from {{ ref('fct_outcome_analysis') }}
where outcome_pct not between 0 and 100 or resolution_rate not between 0 and 100
