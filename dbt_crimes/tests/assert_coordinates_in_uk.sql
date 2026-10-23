-- Rows returned here are crimes placed outside the UK bounding box used in ingestion/validators.py.
select crime_id, city, latitude, longitude
from {{ ref('stg_crimes') }}
where latitude is not null
  and (latitude not between 49.9 and 60.9 or longitude not between -8.2 and 1.8)
