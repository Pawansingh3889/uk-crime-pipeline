.PHONY: setup test-pg test-bq ingest clean

setup:
	pip install -r requirements.txt

test-pg:
	cd dbt_crimes && dbt test --profiles-dir .

test-bq:
	cd dbt_crimes_bq && dbt test --profiles-dir .

ingest:
	python ingestion/fetch_crimes.py

clean:
	rm -rf __pycache__
