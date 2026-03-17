with source as (
    select * from raw.crimes
),
staged as (
    select
        crime_id,
        city,
        month,
        fetch_month,
        category,
        latitude::float         as latitude,
        longitude::float        as longitude,
        street_name,
        outcome_status,
        loaded_at,
        case
            when outcome_status is null then 'Under Investigation'
            else outcome_status
        end as outcome_category
    from source
)
select * from staged