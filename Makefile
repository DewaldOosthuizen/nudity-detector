# Repository validation gate.
.PHONY: ci

ci:
	ruff check src/ tests/
	pytest --cov=src --cov-report=term-missing --cov-fail-under=80 tests/
	pip-audit -r requirements.txt
