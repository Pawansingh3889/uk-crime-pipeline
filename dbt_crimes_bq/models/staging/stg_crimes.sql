-- Staging: clean and cast raw crime data
-- BigQuery version — uses SAFE_CAST and BigQuery date functions

SELECT
    crime_id,
    LOWER(TRIM(category)) AS category,
    TRIM(city) AS city,
    TRIM(street_name) AS street_name,
    SAFE_CAST(latitude AS FLOAT64) AS latitude,
    SAFE_CAST(longitude AS FLOAT64) AS longitude,
    TRIM(month) AS month,
    TRIM(outcome_status) AS outcome_status
FROM {{ source('raw', 'raw_crimes') }}
WHERE crime_id IS NOT NULL
