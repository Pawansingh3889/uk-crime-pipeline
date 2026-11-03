-- Start from the raw crimes shelf exactly as the loader left it.
with source as (
    select * from {{ source('raw', 'crimes') }}
),
-- Tidy each crime: turn map positions from text into numbers and give unsolved crimes a clear label.
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
        -- If the police have not recorded an outcome yet, call it 'Under Investigation'.
        case
            when outcome_status is null then 'Under Investigation'
            else outcome_status
        end as outcome_category
    from source
)
-- Hand the tidied crimes on to the summary tables.
select * from staged