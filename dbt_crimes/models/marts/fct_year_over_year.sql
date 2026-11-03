-- Year-over-year crime comparison by city and category.
-- Compares each month against the same month in the prior year.

-- Count crimes per city, type and month.
with monthly as (
    select
        city,
        category,
        month,
        count(*) as crime_count
    from {{ ref('stg_crimes') }}
    group by city, category, month
),

-- Line up each month with the same month one year earlier and work out the change.
with_prior as (
    select
        curr.city,
        curr.category,
        curr.month as current_month,
        curr.crime_count as current_count,
        prior.month as prior_month,
        prior.crime_count as prior_count,
        curr.crime_count - coalesce(prior.crime_count, 0) as absolute_change,
        case
            when prior.crime_count is null or prior.crime_count = 0 then null
            else round(
                (curr.crime_count - prior.crime_count)::numeric
                / prior.crime_count * 100, 1
            )
        end as pct_change
    from monthly curr
    left join monthly prior
        on curr.city = prior.city
        and curr.category = prior.category
        and prior.month = to_char(
            to_date(curr.month, 'YYYY-MM') - interval '12 months',
            'YYYY-MM'
        )
)

select
    *,
    case
        -- Label the change: no data last year, up more than 10%, down more than 10%, or stable.
        when prior_count is null then 'no prior data'
        when pct_change > 10 then 'increasing'
        when pct_change < -10 then 'decreasing'
        else 'stable'
    end as trend
from with_prior
order by city, category, current_month
