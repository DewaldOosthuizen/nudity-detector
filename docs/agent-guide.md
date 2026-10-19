# Agent Guide

Rules, guardrails, and workflow expectations for AI agents working in this repository.
This is NOT project documentation; it tells an agent HOW TO BEHAVE. For project facts,
setup, configuration, and pipelines, see the linked docs first.

---

## Token Efficiency

Query graph tools before opening raw source files; read only the files that matter.

- graphify: `graphify query "<q>" | graphify path "<A>" "<B>" | graphify explain "<c>" | graphify update .`
- codegraph: `codegraph context "<task>" -p . | codegraph query "<symbol>" -p . | codegraph affected <files> -p . | codegraph sync .`
- understand: launch dashboard at `~/.understand-anything-plugin/packages/dashboard`; for prose questions load the `understand-chat` skill.

No analysis artifacts are present yet — run `codegraph sync .` or `graphify update .` to populate them before relying on query results.

- Prefer targeted reads (line ranges, symbol lookups) over whole-file or whole-directory reads unless a broad overview is required.
- Refresh the graph after modifying code — `codegraph sync .` (and `graphify update .` for graphify tools).
- Do not paste large outputs, logs, or files into responses; summarise and reference `path:line`.

---

## Engineering Standards

- Follow clean architecture: separation of concerns, dependency direction toward abstractions, single responsibility; reuse existing modules before adding new ones when a suitable one exists.
- Match the conventions of neighbouring code. Do not refactor unrelated code unless it advances clean architecture.
- Every public class, function, and method has a docstring/doc comment covering purpose, parameters, return value, and raised errors (native documentation style).
- Every behaviour change ships with tests, including negative-path tests for validation and authorization. Every bug fix ships with a regression test.
- No hacky workarounds, no silent error swallowing, no secrets in code or logs.

---

## Architecture Documentation

- Significant decisions are recorded as Architectural Decision Documents (ADDs) under `docs/add/` (see `docs/add/README.md`). Short, one decision per document, immutable once Accepted. To change a decision, write a new ADD that supersedes the old (forward-reference the predecessor); never edit an accepted ADD. Add a timestamp `(yyyy-mm-dd HH:MM)` when creating or superseding.
- Feature and system designs are ADDs (typically 5-15 pages). Write one before a non-trivial feature and update it alongside the code.
- Follow the existing numbering and templates under `docs/add/`.
- Update the relevant ADD, `docs/architecture.md`, and `docs/index.md` in the same change as code — documentation drift is a defect.

---

## Verification and Review

- Before declaring work done, run the CI gate and confirm it passes (see [development.md](../development.md) for exact commands): `ruff check src/ tests/`, `pytest --cov=src --cov-report=term-missing tests/` (80% threshold enforced via `setup.cfg`), `pip-audit -r requirements.txt`.
- No type checker is configured (mypy deferred — see `docs/add/ADD-005`).
- There is no `make ci` target and no Makefile; add one running the three gate commands above if none exists.
- When reviewing, run the CI gate — do not approve on the diff alone. Report real command output, never assumed results.
- Review checklist: tests cover new behaviour and failure paths, public APIs documented, no duplicated logic, no dead code, docs/ADDs updated, no secrets, and no new dependency without regenerating `requirements.txt` from `requirements.in` via `pip-compile`.
- Fix root causes, not symptoms; check sibling code paths for the same flaw.

---

## Repository-Specific Rules

- Configuration is solely via `config/app_config.json` — no env-var overrides (no `python-dotenv` / `os.environ` anywhere). `.env.example` is a plain-text reference table, not a template (see [configuration.md](../configuration.md)).
- Reports are written to `reports/<YYYY-MM-DD_HH-MM-SS>/` containing `nudity_report.xlsx` and `nudity_report_session.json`; source files are never moved or copied.
- GUI updates from worker threads must use `GLib.idle_add`; in tests patch `src/gui/*.GLib`, never `gi.repository.GLib`, and set `glib_mock.Error = Exception` (see `docs/add/ADD-006`).
- Ruff is the sole linter: `line-length = 160`, `E402` ignored (GTK `gi.require_version` ordering); config in `pyproject.toml` (see `docs/add/ADD-005`).
- If dependencies change, regenerate pinned `requirements.txt` from `requirements.in` via `pip-compile`, then reinstall before running checks.
- Run `codegraph sync .` after any code change.
- Branch from `main` with `feature/<issue>-<topic>`, `fix/<issue>-<topic>`, `chore/<topic>`, or `docs/<topic>`; open PRs against `main`, request review, never merge your own.
- Commit messages: imperative mood, 72-char subject, `Closes #<n>` in the footer.
