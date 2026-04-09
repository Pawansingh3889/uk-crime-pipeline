-- Mart: top street-level hotspots with 5+ incidents

SELECT
    city,
    street_name,
    category,
    COUNT(*) AS incident_count
FROM {{ ref('stg_crimes') }}
WHERE street_name IS NOT NULL AND street_name != ''
GROUP BY city, street_name, category
HAVING COUNT(*) >= 5
ORDER BY incident_count DESC
LIMIT 100
