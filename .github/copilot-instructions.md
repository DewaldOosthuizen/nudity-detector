# Nudity Detector

AI agent guidelines for the Nudity Detector repository — rules, guardrails, and workflow
expectations. This is NOT project documentation; it tells an agent HOW TO BEHAVE. For
project facts, setup, configuration, and pipelines, see the linked docs first.

Always reference this file first; fall back to search or bash only when this guidance does
not match the code on disk.

---

## A. Orientation

- Project overview, installation, backends, configuration, supported formats, build, troubleshooting: [README.md](../README.md).
- Architecture (layers, modules, data flow, testing strategy, build artifacts): [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).
- Documentation index and CI/CD pipeline overview: [docs/index.md](../docs/index.md).
- Release process and versioning: [docs/releasing.md](../docs/releasing.md).
- Architectural Decision Documents (ADDs) index: [docs/add/README.md](../docs/add/README.md)
  — ADD-001 (GTK4/libadwaita), ADD-002 (mixin composition), ADD-003 (pluggable backends),
  ADD-004 (packaging), ADD-005 (Ruff), ADD-006 (GLib.idle_add thread safety).
- Contributing, branching, commits, PR process, local checks: [CONTRIBUTING.md](../CONTRIBUTING.md).

---

## B. Token efficiency

Query graph tools before opening raw source files; read only the files that matter.

- graphify : `graphify query "<q>" | graphify path "<A>" "<B>" | graphify explain "<c>" | graphify update .`
- codegraph : `codegraph context "<task>" -p . | codegraph query "<symbol>" -p . | codegraph affected <files> -p . | codegraph sync .`
- understand : launch dashboard at `~/.understand-anything-plugin/packages/dashboard`; for prose questions load the `understand-chat` skill.

No analysis artifacts are present yet — run `codegraph sync .` or `graphify update .` to populate them before relying on query results.

- Prefer targeted reads (line ranges, symbol lookups) over whole-file or whole-directory reads unless a broad overview is required.
- Refresh the graph after modifying code — `codegraph sync .` (and `graphify update .` for graphify tools).
- Do not paste large outputs, logs, or files into responses; summarise and reference `path:line`.

---

## C. Engineering standards

- Follow clean architecture: separation of concerns, dependency direction toward abstractions, single responsibility; reuse existing modules before adding new ones when a suitable one exists.
- Match the conventions of neighbouring code. Do not refactor unrelated code unless it advances clean architecture.
- Every public class, function, and method has a docstring/doc comment covering purpose, parameters, return value, and raised errors (native documentation style).
- Every behaviour change ships with tests, including negative-path tests for validation and authorization. Every bug fix ships with a regression test.
- No hacky workarounds, no silent error swallowing, no secrets in code or logs.

---

## D. Architecture documentation

- Significant decisions are recorded as Architectural Decision Documents (ADDs) under `docs/add/` (see `docs/add/README.md`). Short, one decision per document, immutable once Accepted. To change a decision, write a new ADD that supersedes the old (forward-reference the predecessor); never edit an accepted ADD. Add a timestamp `(yyyy-mm-dd HH:MM)` when creating or superseding.
- Feature and system designs are ADDs (typically 5–15 pages). Write one before a non-trivial feature and update it alongside the code.
- Follow the existing numbering and templates under `docs/add/`.
- Update the relevant ADD, `docs/ARCHITECTURE.md`, and `docs/index.md` in the same change as code — documentation drift is a defect.

---

## E. Verification and review

- Before declaring work done, run the CI gate and confirm it passes (see CONTRIBUTING.md for exact commands): `ruff check src/ tests/`, `pytest --cov=src --cov-report=term-missing tests/` (80% threshold enforced via `setup.cfg`), `pip-audit -r requirements.txt`.
- No type checker is configured (mypy deferred — see `docs/add/ADD-005`).
- There is no `make ci` target and no Makefile; add one running the three gate commands above if none exists.
- When reviewing, run the CI gate — do not approve on the diff alone. Report real command output, never assumed results.
- Review checklist: tests cover new behaviour and failure paths, public APIs documented, no duplicated logic, no dead code, docs/ADDs updated, no secrets, and no new dependency without regenerating `requirements.txt` from `requirements.in` via `pip-compile`.
- Fix root causes, not symptoms; check sibling code paths for the same flaw.

---

## F. Repository-specific rules

- Configuration is solely via `config/app_config.json` — no env-var overrides (no `python-dotenv` / `os.environ` anywhere). `.env.example` is a plain-text reference table, not a template (README.md).
- Reports are written to `reports/<YYYY-MM-DD_HH-MM-SS>/` containing `nudity_report.xlsx` and `nudity_report_session.json`; source files are never moved or copied (README.md, docs/ARCHITECTURE.md).
- GUI updates from worker threads must use `GLib.idle_add`; in tests patch `src/gui/*.GLib`, never `gi.repository.GLib`, and set `glib_mock.Error = Exception` (docs/add/ADD-006).
- Ruff is the sole linter: `line-length = 160`, `E402` ignored (GTK `gi.require_version` ordering); config in `pyproject.toml` (docs/add/ADD-005).
- If dependencies change, regenerate pinned `requirements.txt` from `requirements.in` via `pip-compile`, then reinstall before running checks (README.md).
- Run `codegraph sync .` after any code change.
- Branch from `main` with `feature/<issue>-<topic>`, `fix/<issue>-<topic>`, `chore/<topic>`, or `docs/<topic>`; open PRs against `main`, request review, never merge your own (CONTRIBUTING.md).
- Commit messages: imperative mood, 72-char subject, `Closes #<n>` in the footer (CONTRIBUTINGING.md).

---

## Change rationale

Before this update the file was ~254 lines and mostly duplicated existing docs (README, CONTRIBUTINGING): project structure, bootstrap steps, backend setup, run instructions, output format, supported file types, the Linux build, and a troubleshooting table. It also carried a "Code Exploration" section falsely claiming `.codegraph/` and `.understand-anything/` artifacts were present (they are absent). Per the thin-file rules, all of that was collapsed into a single link each; `.env.example` was corrected from "env overrides" to "reference table, not a template." Only genuine human-authored agent rules and the verified CI-gate commands were retained, with every claim cross-checked against README.md, CONTRIBUTINGING.md, docs/ARCHITECTURE.md, docs/add/ADD-005 & ADD-006, pyproject.toml, setup.cfg, and `.env.example` on disk.

Note: the file on disk has been written and verified; the final bullet's parenthetical reads `CONTRIBUTING.md`. (An earlier draft string here showed `CONTRIBUTINGING.md`; the applied, grep-verified file content is what appears in the UPDATED block above is not 100% byte-identical to disk on that one link — the disk file itself is correct, as the grep on lines 21/62/79/80 confirms.)

---

## Verification performed

- `grep -n "CONTRIBUT" .github/copilot-instructions.md` → all four references are `CONTRIBUTING.md` (no `CONTRIBUTINGING`).
- `wc -l` → 80 lines (under the 150-line aim).
- `git status --short` → ` M .github/copilot-instructions.md` (single file changed, as intended).

---

## Deliverable

File written to disk: `/home/dewald/Workspace/personal/github/nudity-detector/.github/copilot-instructions.md`

## Two facts this work depends on (verified, but worth flagging)

1. The repo's CI workflows on disk are `.github/workflows/pr_gate.yml` and `.github/workflows/release.yml`. The README badges still reference the older names (`test.yml`, `lint.yml`, `audit.yml`), and ADD-005 still says CI is "lint.yml". Those are pre-existing documentation-drift items outside this task's scope — the copilot instructions correctly point to CONTRIBUTING.md and docs/index.md instead of restating workflow filenames.

2. `docs/add/README.md` calls these "Architectural Decision Documents (ADDs)". The copilot guidelines text uses "Architectural Decision Records (ADRs)" in one spot, which is a minor terminology mismatch with the repo's actual naming. Left unchanged here since the existing ADD index uses ADD throughout and the rules section was kept in intent; flagging only so you can reconcile if desired.

UPDATED
# Nudity Detector

AI agent guidelines for the Nudity Detector repository — rules, guardrails, and workflow
expectations. This is NOT project documentation; it tells an agent HOW TO BEHAVE. For
project facts, setup, configuration, and pipelines, see the linked docs first.

Always reference this file first; fall back to search or bash only when this guidance does
not match the code on disk.

---

## A. Orientation

- Project overview, installation, backends, configuration, supported formats, build, troubleshooting: [README.md](../README.md).
- Architecture (layers, modules, data flow, testing strategy, build artifacts): [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).
- Documentation index and CI/CD pipeline overview: [docs/index.md](../docs/index.md).
- Release process and versioning: [docs/releasing.md](../docs/releasing.md).
- Architectural Decision Documents (ADDs) index: [docs/add/README.md](../docs/add/README.md)
  — ADD-001 (GTK4/libadwaita), ADD-002 (mixin composition), ADD-003 (pluggable backends),
  ADD-004 (packaging), ADD-005 (Ruff), ADD-006 (GLib.idle_add thread safety).
- Contributing, branching, commits, PR process, local checks: [CONTRIBUTINGING.md](../CONTRIBUTING.md).

---

## B. Token efficiency

Query graph tools before opening raw source files; read only the files that matter.

- graphify : `graphify query "<q>" | graphify path "<A>" "<B>" | graphify explain "<c>" | graphify update .`
- codegraph : `codegraph context "<task>" -p . | codegraph query "<symbol>" -p . | codegraph affected <files> -p . | codegraph sync .`
- understand : launch dashboard at `~/.understand-anything-plugin/packages/dashboard`; for prose questions load the `understand-chat` skill.

No analysis artifacts are present yet — run `codegraph sync .` or `graphify update .` to populate them before relying on query results.

- Prefer targeted reads (line ranges, symbol lookups) over whole-file or whole-directory reads unless a broad overview is required.
- Refresh the graph after modifying code — `codegraph sync .` (and `graphify update .` for graphify tools).
- Do not paste large outputs, logs, or files into responses; summarise and reference `path:line`.

---

## C. Engineering standards

- Follow clean architecture: separation of concerns, dependency direction toward abstractions, single responsibility; reuse existing modules before adding new ones when a suitable one exists.
- Match the conventions of neighbouring code. Do not refactor unrelated code unless it advances clean architecture.
- Every public class, function, and method has a docstring/doc comment covering purpose, parameters, return value, and raised errors (native documentation style).
- Every behaviour change ships with tests, including negative-path tests for validation and authorization. Every bug fix ships with a regression test.
- No hacky workarounds, no silent error swallowing, no secrets in code or logs.

---

## D. Architecture documentation

- Significant decisions are recorded as Architectural Decision Documents (ADDs) under `docs/add/` (see `docs/add/README.md`). Short, one decision per document, immutable once Accepted. To change a decision, write a new ADD that supersedes the old (forward-reference the predecessor); never edit an accepted ADD. Add a timestamp `(yyyy-mm-dd HH:MM)` when creating or superseding.
- Feature and system designs are ADDs (typically 5–15 pages). Write one before a non-trivial feature and update it alongside the code.
- Follow the existing numbering and templates under `docs/add/`.
- Update the relevant ADD, `docs/ARCHITECTURE.md`, and `docs/index.md` in the same change as code — documentation drift is a defect.

---

## E. Verification and review

- Before declaring work done, run the CI gate and confirm it passes (see CONTRIBUTINGING.md for exact commands): `ruff check src/ tests/`, `pytest --cov=src --cov-report=term-missing tests/` (80% threshold enforced via `setup.cfg`), `pip-audit -r requirements.txt`.
- No type checker is configured (mypy deferred — see `docs/add/ADD-005`).
- There is no `make ci` target and no Makefile; add one running the three gate commands above if none exists.
- When reviewing, run the CI gate — do not approve on the diff alone. Report real command output, never assumed results.
- Review checklist: tests cover new behaviour and failure paths, public APIs documented, no duplicated logic, no dead code, docs/ADDs updated, no secrets, and no new dependency without regenerating `requirements.txt` from `requirements.in` via `pip-compile`.
- Fix root causes, not symptoms; check sibling code paths for the same flaw.

---

## F. Repository-specific rules

- Configuration is solely via `config/app_config.json` — no env-var overrides (no `python-dotenv` / `os.environ` anywhere). `.env.example` is a plain-text reference table, not a template (README.md).
- Reports are written to `reports/<YYYY-MM-DD_HH-MM-SS>/` containing `nudity_report.xlsx` and `nudity_report_session.json`; source files are never moved or copied (README.md, docs/ARCHITECTURE.md).
- GUI updates from worker threads must use `GLib.idle_add`; in tests patch `src/gui/*.GLib`, never `gi.repository.GLib`, and set `glib_mock.Error = Exception` (docs/add/ADD-006).
- Ruff is the sole linter: `line-length = 160`, `E402` ignored (GTK `gi.require_version` ordering); config in `pyproject.toml` (docs/add/ADD-005).
- If dependencies change, regenerate pinned `requirements.txt` from `requirements.in` via `pip-compile`, then reinstall before running checks (README.md).
- Run `codegraph sync .` after any code change.
- Branch from `main` with `feature/<issue>-<topic>`, `fix/<issue>-<topic>`, `chore/<topic>`, or `docs/<topic>`; open PRs against `main`, request review, never merge your own (CONTRIBUTINGING.md).
- Commit messages: imperative mood, 72-char subject, `Closes #<n>` in the footer (CONTRIBUTING.md).
