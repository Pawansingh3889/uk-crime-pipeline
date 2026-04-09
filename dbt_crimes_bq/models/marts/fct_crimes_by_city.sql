-- Mart: crime count and unsolved % by city, category, month

SELECT
    city,
    category,
    month,
    COUNT(*) AS crime_count,
    COUNTIF(outcome_status = 'under-investigation' OR outcome_status = 'awaiting-court-result') AS unsolved,
    ROUND(
        COUNTIF(outcome_status = 'under-investigation' OR outcome_status = 'awaiting-court-result') / COUNT(*) * 100,
        1
    ) AS unsolved_pct
FROM {{ ref('stg_crimes') }}
GROUP BY city, category, month
ORDER BY city, month, crime_count DESC
