-- Mart: total crimes and breakdown per city per month

SELECT
    city,
    month,
    COUNT(*) AS total_crimes,
    COUNTIF(category = 'anti-social-behaviour') AS antisocial,
    COUNTIF(category = 'violent-crime') AS violent,
    COUNTIF(category = 'shoplifting') AS shoplifting,
    COUNTIF(category = 'vehicle-crime') AS vehicle,
    COUNTIF(category = 'burglary') AS burglary,
    COUNTIF(outcome_status = 'under-investigation' OR outcome_status = 'awaiting-court-result') AS unsolved
FROM {{ ref('stg_crimes') }}
GROUP BY city, month
ORDER BY city, month
