# Repository validation gate.
#
# Mirrors the PR gate in .github/workflows/pr_gate.yml. The three checks
# run in this order:
#
#   lint (ruff check src/ tests/)          [sequential]
#   test (pytest --cov, 80% floor)
#   audit (pip-audit -r requirements.txt)  [parallel to lint + test]
#
# The gate is self-contained: ci-install creates a virtual environment and
# installs the locked requirements (mirroring the `pip install -r
# requirements.txt` step in the CI test job) before the checks run, so a
# fresh checkout can execute `make ci` without manual dependency setup.
# The virtual environment is reused on subsequent runs. On hosts where the
# system Python is externally managed (PEP 668), the venv is the only safe
# way to install the locked requirements.
.PHONY: ci ci-lint ci-test ci-audit ci-install

ci: ci-lint ci-test ci-audit

ci-install:  ## Create .venv and install the locked requirements (idempotent)
	@test -d .venv || python3 -m venv .venv
	.venv/bin/pip install --disable-pip-version-check --upgrade pip
	.venv/bin/pip install --disable-pip-version-check -r requirements.txt
	.venv/bin/pip install --disable-pip-version-check -r requirements-dev.txt

ci-lint: ci-install  ## Lint source and test code with ruff
	.venv/bin/ruff check src/ tests/

ci-test: ci-install  ## Run pytest with coverage and an 80% floor
	.venv/bin/pytest --cov=src --cov-report=term-missing --cov-fail-under=80 tests/

ci-audit: ci-install  ## Audit installed dependencies with pip-audit
	.venv/bin/pip-audit -r requirements.txt
