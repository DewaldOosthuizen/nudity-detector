# ADD-005 — Ruff as the Sole Linting Tool

| Field      | Value                  |
|------------|------------------------|
| Status     | Accepted               |
| Date       | 2025-06-02             |
| Author     | Dewald Oosthuizen      |
| Relates to | —                      |

---

## Context

The project had no linting configuration when the test suite was brought to a
fully-green state. Static analysis was run informally by individual contributors.
Running `ruff check src/ tests/` on the codebase revealed 115 violations across
five rule categories. A linting tool needed to be selected, configured, and
integrated into CI before further development continued.

---

## Decision

Use **ruff** as the sole linting tool. It replaces `flake8`, `isort`, and
`pylint` with a single binary.

Configuration lives in `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py312"
line-length = 160

[tool.ruff.lint]
select = ["E", "F", "I"]  # pycodestyle + Pyflakes + isort
ignore = ["E402"]          # GTK gi.require_version() must precede imports
```

**Why E402 is suppressed globally:**  
Every `src/gui/*.py` file must call `gi.require_version('Gtk', '4.0')` before
`from gi.repository import ...`. This is a mandatory GTK4 constraint, not a
style violation. Suppressing E402 globally avoids adding `# noqa: E402`
to every GTK import line across the codebase.

**Why line-length is 160:**  
The codebase contains GTK4 callback chains, f-string labels, and
`Gtk.Label(label=...)` constructors that are long by nature. The ruff default
of 88 would require a mechanical reformat of every existing method call. 160
catches genuinely unreadable lines while not fighting the GTK style.

The local developer workflow:

```bash
pip install -r requirements-dev.txt   # includes ruff>=0.5.0
ruff check src/ tests/                # check
ruff check src/ tests/ --fix          # auto-fix safe violations
```

CI workflow (`.github/workflows/lint.yml`) runs `ruff check src/ tests/` on
every push and pull request.

---

## Options Considered

| Option | Description | Verdict |
|--------|-------------|---------|
| flake8 + isort + pylint | Established trio — but three tools to configure and maintain; slower | Rejected |
| ruff (current) | Replaces all three; single config in pyproject.toml; 10–100× faster | **Accepted** |
| mypy (type checking) | Complementary to ruff — useful for type safety | Deferred (no type annotations in current codebase) |
| No linting | Status quo — 115 violations accumulating | Rejected |

---

## Consequences

**Positive:**
- Single tool, single config file — no `setup.cfg` / `.flake8` / `.isort.cfg` split.
- `ruff --fix` auto-resolves the majority of violations (unused imports,
  unused variables, import ordering) without manual edits.
- Ruff integrates with all major editors via LSP.
- The CI lint job adds ~10 seconds to every push (pip install + ruff run).

**Negative / Trade-offs:**
- Ruff does not perform type inference — it cannot catch type errors that mypy
  or Pyright would catch. Type checking remains a future gap.
- The E402 global suppression means a genuinely misplaced import (not a GTK
  pattern) in `src/gui/` would go undetected by this rule. Code review is
  the fallback.
- `line-length = 160` is generous. Long lines that are not GTK-related
  should still be refactored during review — the lint rule is a safety net,
  not a style guide.
