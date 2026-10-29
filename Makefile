# Repository validation gate.
.PHONY: ci ci-lint ci-test ci-audit

ci: ci-lint ci-test ci-audit

ci-lint:
	ruff check src/ tests/

ci-test:
	pytest --cov=src --cov-report=term-missing --cov-fail-under=80 tests/

ci-audit:
	pip-audit -r requirements.txt
