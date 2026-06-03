# Contributing to Nudity Detector

Thank you for contributing. This guide keeps changes small, reviewable, and
consistent with the current repository workflow.

---

## Table of Contents

1. [Code of Conduct](#1-code-of-conduct)
2. [Getting Started](#2-getting-started)
3. [Picking Up an Issue](#3-picking-up-an-issue)
4. [Branch Naming](#4-branch-naming)
5. [Development Setup](#5-development-setup)
6. [Running Checks Locally](#6-running-checks-locally)
7. [Commit Message Style](#7-commit-message-style)
8. [Pull Request Process](#8-pull-request-process)
9. [Coding Standards](#9-coding-standards)

---

## 1. Code of Conduct

Be respectful, constructive, and collaborative. Contributions that are
disrespectful, dismissive, or harmful will not be accepted.

---

## 2. Getting Started

1. Fork the repository.
2. Clone your fork locally.
3. Follow the [Development Setup](#5-development-setup) section below.

---

## 3. Picking Up an Issue

**Before you write a single line of code:**

1. Browse the [GitHub Issues](../../issues) tab and find an issue you want to work on.
2. **Assign the issue to yourself** before starting any work.
   Go to the issue page → Assignees (right sidebar) → assign yourself.
   This signals to all other contributors that the issue is claimed.
3. Leave a comment on the issue stating you are picking it up and your
   intended approach — especially for larger changes.
4. Only then create your branch and begin work.

> Why this matters: two contributors working on the same issue in parallel
> wastes effort and creates painful merge conflicts. A self-assignment takes
> five seconds and saves hours.

If you were assigned an issue but can no longer work on it, unassign yourself
and leave a comment so someone else can pick it up.

---

## 4. Branch Naming

| Prefix     | Pattern                         | When to use                                |
|------------|---------------------------------|--------------------------------------------|
| `feature/` | `feature/<issue-id>-<topic>`    | New feature or capability                  |
| `fix/`     | `fix/<issue-id>-<topic>`        | Bug fix                                    |
| `chore/`   | `chore/<topic>`                 | Tooling, deps, CI, config updates          |
| `docs/`    | `docs/<topic>`                  | Documentation only                         |

Examples:
- `feature/42-add-batch-scan-mode`
- `fix/17-fix-gtk-crash-on-startup`
- `docs/update-contributing-guide`

Always branch from `main`.

---

## 5. Development Setup

The project targets **Python 3.11+** and is primarily developed on Linux
because the GUI depends on GTK4 and libadwaita.

```bash
git clone https://github.com/<your-user>/nudity-detector.git
cd nudity-detector
python3 -m venv .venv
source .venv/bin/activate
```

Install system GTK dependencies if you plan to run the GUI:

```bash
sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
```

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

If you are using a virtual environment for GUI work, expose the system GTK
bindings inside it:

```bash
VENV_SITE_PACKAGES="$(.venv/bin/python3 -c 'import site; print(site.getsitepackages()[0])')"
GI_SYSTEM_PATH="$(/usr/bin/python3 -c 'import gi, pathlib; print(pathlib.Path(gi.__file__).resolve().parent.parent)')"
printf '%s\n' "$GI_SYSTEM_PATH" > "$VENV_SITE_PACKAGES/system-gi.pth"
```

---

## 6. Running Checks Locally

Run these commands before pushing. CI runs the same checks and a failing PR
will not be reviewed.

```bash
pytest tests/
pytest --cov=src --cov-report=term-missing --cov-fail-under=80 tests/
pip-audit -r requirements.txt
```

If you changed dependencies, regenerate pinned requirements from
`requirements.in`, then rerun the tests.

After any code change, keep the repository graph current:

```bash
codegraph sync .
```

All commands must exit with code `0` before opening a PR.

---

## 7. Commit Message Style

- Use the **imperative mood** in the subject line: "Add", "Fix", "Remove".
- Limit the subject line to **72 characters**.
- Leave one blank line between the subject and body when a body is needed.
- Reference the related issue in the footer with `Closes #<n>`.

Example:

```
Add batch scan mode for directory processing

Closes #42
```

---

## 8. Pull Request Process

1. Ensure all local checks pass (see [Section 6](#6-running-checks-locally)).
2. Open the PR against `main`.
3. Use a scoped, descriptive title: `fix: resolve #17 - GTK crash on startup`.
4. In the PR body:
   - Link the issue: `Closes #<n>`
   - Describe the user-visible change.
   - Include screenshots or terminal output when the change affects UI or tooling behaviour.
5. Request a review. Do not merge your own PR without a review.
6. Address review feedback with follow-up commits — do not force-push a reviewed branch unless asked.

---

## 9. Coding Standards

- Follow PEP 8 and keep functions small and explicit.
- Use module-level loggers: `logger = logging.getLogger(__name__)`.
- Do not add `logging.basicConfig(...)` inside library modules under `src/`.
- Reuse the existing `src/` and `tests/` layout — do not create parallel patterns.
- When patching GLib references in tests, patch via `src.gui.*.GLib`; set `glib_mock.Error = Exception`.
- Add or update tests whenever behaviour changes. Coverage must remain at or above the CI threshold (80%).
