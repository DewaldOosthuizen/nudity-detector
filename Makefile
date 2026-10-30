# Repository validation gate.
#
# Mirrors the PR gate in .github/workflows/pr_gate.yml. The three checks
# run in this order, serially:
#
#   lint (ruff check src/ tests/)          [sequential]
#   test (pytest --cov, 80% floor)         [sequential]
#   audit (pip-audit -r requirements.txt)  [sequential]
#
# The gate is self-contained: ci-install creates a virtual environment and
# installs the locked requirements (mirroring the `pip install -r
# requirements.txt` and `pip install -r requirements-dev.txt` steps in the
# CI test and pip-audit jobs) before the checks run, so a fresh checkout
# can execute `make ci` without manual dependency setup. The virtual
# environment is reused on subsequent runs.
.PHONY: ci ci-install ci-lint ci-test ci-audit help lint test audit build clean format start

ci: ci-install ci-lint ci-test ci-audit  ## Run the full CI gate (lint, test, audit)

ci-install:  ## Create .venv and install the locked requirements (idempotent)
	@test -d .venv || python3 -m venv .venv
	.venv/bin/pip install --disable-pip-version-check --upgrade pip
	.venv/bin/pip install --disable-pip-version-check -r requirements.txt
	.venv/bin/pip install --disable-pip-version-check -r requirements-dev.txt

ci-lint: ci-install  ## Lint source and test code with ruff (E, F, I; py312)
	.venv/bin/ruff check src/ tests/

ci-test: ci-install  ## Run pytest with coverage and an 80% floor
	.venv/bin/pytest --cov=src --cov-report=term-missing --cov-fail-under=80 tests/

ci-audit: ci-install  ## Audit installed dependencies with pip-audit
	.venv/bin/pip-audit -r requirements.txt

help:  ## Show this help message
	@grep -E '^[a-zA-Z0-9_-]+:.*##.*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN { FS = ":.*## " }; { printf "  %-22s %s\n", $$1, $$2 }'

lint: ci-install  ## Lint source and test code with ruff (E, F, I; py312)
	.venv/bin/ruff check src/ tests/

test: ci-install  ## Run pytest with coverage and an 80% floor
	.venv/bin/pytest --cov=src --cov-report=term-missing --cov-fail-under=80 tests/

audit: ci-install  ## Audit installed dependencies with pip-audit
	.venv/bin/pip-audit -r requirements.txt

build:  ## Build the AppImage locally and verify the two artifacts
	bash scripts/build_linux.sh
	test -f dist/NudityDetector-x86_64.AppImage
	test -d dist/nudity-detector

clean:  ## Remove build artifacts and caches (consistent with .gitignore)
	rm -rf dist/ build/ .coverage .coverage.* htmlcov/ .pytest_cache/ .ruff_cache/
	find src tests -type d -name __pycache__ -exec rm -rf {} +
	find src tests -type f -name '*.pyc' -delete

format: ci-install  ## Format code to the project's ruff style (py312, 160)
	.venv/bin/ruff format --target-version py312 --line-length 160 src/ tests/

start: ci-install  ## Launch the GTK4/libadwaita GUI app (xvfb-run when headless)
ifndef DISPLAY
	xvfb-run -a .venv/bin/python run_gui.py
else
	.venv/bin/python run_gui.py
endif
