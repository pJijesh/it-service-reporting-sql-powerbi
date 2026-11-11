# Convenience targets. Every target just calls Python, so the same commands work without make.
PYTHON ?= python3

.PHONY: all data db model report test clean

all:
	$(PYTHON) run_pipeline.py

data:
	$(PYTHON) -m generator --out data

db: data
	$(PYTHON) -m sql.loader --data data --db build/service_reporting.db

model: db
	$(PYTHON) -m sql.loader --data data --db build/service_reporting.db --export-model model

report: db
	$(PYTHON) -m reports.build_report --db build/service_reporting.db --out reports

test:
	$(PYTHON) -m pytest -q

clean:
	rm -rf build .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
