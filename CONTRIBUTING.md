# Contributing to Nudity Detector

Thanks for contributing. This guide keeps changes small, reviewable, and
consistent with the current repository workflow.

## Before you start

1. Fork the repository and create a topic branch from `main`.
2. Use a descriptive branch name with one of these prefixes:
   - `feature/<short-description>`
   - `fix/<short-description>`
   - `chore/<short-description>`
3. Keep each pull request focused on a single issue or improvement.

## Development setup

The project targets Python 3.11+ and is primarily developed on Linux because
the GUI depends on GTK4 and libadwaita.

1. Clone your fork and enter the repository:

   ```bash
   git clone https://github.com/<your-user>/nudity-detector.git
   cd nudity-detector
   ```

2. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install system GTK dependencies if you plan to run the GUI:

   ```bash
   sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
   ```

4. Install development dependencies:

   ```bash
   pip install -r requirements-dev.txt
   ```

5. If you are using a virtual environment for GUI work, expose the system GTK
   bindings inside it:

   ```bash
   VENV_SITE_PACKAGES="$(.venv/bin/python3 -c 'import site; print(site.getsitepackages()[0])')"
   GI_SYSTEM_PATH="$(/usr/bin/python3 -c 'import gi, pathlib; print(pathlib.Path(gi.__file__).resolve().parent.parent)')"
   printf '%s\n' "$GI_SYSTEM_PATH" > "$VENV_SITE_PACKAGES/system-gi.pth"
   ```

## Validation commands

Run these commands before opening a pull request:

```bash
pytest tests/
pytest --cov=src --cov-report=term-missing --cov-fail-under=80 tests/
pip-audit -r requirements.txt
```

If you changed dependencies, regenerate pinned requirements from
`requirements.in`, then rerun the tests.

## Coding standards

- Follow PEP 8 and keep functions small and explicit.
- Prefer module-level loggers such as `logger = logging.getLogger(__name__)`.
- Do not add `logging.basicConfig(...)` inside library modules under `src/`.
- Reuse the existing `src/` and `tests/` layout instead of creating parallel
  patterns.
- Add or update tests whenever behavior changes.

## Pull request checklist

Before submitting a PR, make sure:

- Tests pass locally.
- Coverage remains at or above the CI threshold.
- `pip-audit -r requirements.txt` succeeds when dependencies changed.
- Documentation and examples stay accurate.
- `codegraph sync .` has been run after code changes so repository graph data
  stays current for contributors using the graph tooling.

## Pull request conventions

- Use a clear, scoped PR title. Recent examples follow
  `fix: resolve #<issue> - <summary>`.
- Link the issue in the PR body and describe the user-visible impact.
- Include screenshots or terminal output when the change affects UI or tooling
  behavior.
