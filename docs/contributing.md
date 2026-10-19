# Contributing to Nudity Detector

Thank you for contributing. This guide keeps changes small, reviewable, and consistent with the current repository workflow.

---

## Table of Contents

1. [Code of Conduct](#1-code-of-conduct)
2. [Picking Up an Issue](#2-picking-up-an-issue)
3. [Branch Naming](#3-branch-naming)
4. [Commit Message Style](#4-commit-message-style)
5. [Pull Request Process](#5-pull-request-process)
6. [Coding Standards](#6-coding-standards)

---

## 1. Code of Conduct

Be respectful, constructive, and collaborative. Contributions that are disrespectful, dismissive, or harmful will not be accepted.

---

## 2. Picking Up an Issue

**Before you write a single line of code:**

1. Browse the [GitHub Issues](../../issues) tab and find an issue you want to work on.
2. **Assign the issue to yourself** before starting any work. Go to the issue page, Assignees (right sidebar), assign yourself. This signals to all other contributors that the issue is claimed.
3. Leave a comment on the issue stating you are picking it up and your intended approach — especially for larger changes.
4. Only then create your branch and begin work.

If you were assigned an issue but can no longer work on it, unassign yourself and leave a comment so someone else can pick it up.

---

## 3. Branch Naming

| Prefix | Pattern | When to use |
|--------|---------|-------------|
| `feature/` | `feature/<issue-id>-<topic>` | New feature or capability |
| `fix/` | `fix/<issue-id>-<topic>` | Bug fix |
| `chore/` | `chore/<topic>` | Tooling, deps, CI, config updates |
| `docs/` | `docs/<topic>` | Documentation only |

Examples:

- `feature/42-add-batch-scan-mode`
- `fix/17-fix-gtk-crash-on-startup`
- `docs/update-contributing-guide`

Always branch from `main`.

---

## 4. Commit Message Style

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

## 5. Pull Request Process

1. Ensure all local checks pass (see [development.md](development.md)).
2. Open the PR against `main`.
3. Use a scoped, descriptive title: `fix: resolve #17 - GTK crash on startup`.
4. In the PR body:
   - Link the issue: `Closes #<n>`
   - Describe the user-visible change.
   - Include screenshots or terminal output when the change affects UI or tooling behaviour.
5. Request a review. Do not merge your own PR without a review.
6. Address review feedback with follow-up commits — do not force-push a reviewed branch unless asked.

---

## 6. Coding Standards

- Follow PEP 8 and keep functions small and explicit.
- Use module-level loggers: `logger = logging.getLogger(__name__)`.
- Do not add `logging.basicConfig(...)` inside library modules under `src/`.
- Reuse the existing `src/` and `tests/` layout — do not create parallel patterns.
- When patching GLib references in tests, patch via `src.gui.*.GLib`; set `glib_mock.Error = Exception`.
- Add or update tests whenever behaviour changes. Coverage must remain at or above the CI threshold (80%).

For the full CI gate commands and dependency management workflow, see [development.md](development.md).
