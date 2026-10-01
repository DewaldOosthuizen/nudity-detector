# DewaldOosthuizen/nudity-detector

## A. Orientation

- README.md — project overview, installation, supported formats, backend setup
- docs/index.md — documentation index and CI/CD pipeline overview
- docs/ARCHITECTURE.md — architecture overview, layered design, data flow, testing strategy
- docs/add/README.md — index of all Architectural Decision Documents (ADDs)
- docs/releasing.md — release process and versioning
- CONTRIBUTING.md — branching, commit style, PR process, local checks
- .github/copilot-instructions.md — repository structure and working guide

## B. Token efficiency

- Query codegraph / understand-anything before opening source files; read only the files that matter.
- Prefer targeted reads (line ranges, symbol lookups) over whole-file or whole-directory reads unless a broader overview is required.
- No graph artifacts are pre-built (`.codegraph/`, `.understand-anything/`, `graphify-out/` are absent); run `codegraph sync .` before first querying.
- Refresh the graph after modifying code.
- Do not paste large outputs, logs, or files into responses; summarise and reference path:line.

Tool commands:
- graphify | `graphify query "<q>"` | `graphify path "<A>" "<B>"` | `graphify explain "<c>"` | `graphify update .`
- codegraph | `codegraph context "<task>" -p .` | `codegraph query "<symbol>" -p .` | `codegraph affected <files> -p .` | `codegraph sync .`
- understand | launch dashboard at `~/.understand-anything-plugin/packages/dashboard`; skill: understand-chat

## C. Engineering standards

- Clean architecture: layered design with dependencies flowing inward toward `src/core/`. The GUI never imports detectors directly — all coordination goes through `src/core/utils.py`.
- All magic values, extensions, model names, and file paths live in `src/core/constants.py`; extend from there, never duplicate.
- Match neighbouring code conventions. Do not refactor unrelated code unless it advances clean architecture.
- Every public class, function, and method gets a docstring covering purpose, parameters, return value, and raised errors.
- Module-level loggers only: `logger = logging.getLogger(__name__)`. No `logging.basicConfig(...)` inside `src/`.
- Every behaviour change ships with tests, including negative-path tests. Every bug fix ships with a regression test. Coverage threshold is 80% (setup.cfg).
- No hacky workarounds, no silent error swallowing, no secrets in code or logs.

## D. Architecture documentation

- Significant decisions are recorded as ADDs in `docs/add/`. Each captures context, options considered, decision, and consequences.
- When a decision is superseded, mark the old ADD as "Superseded" with a forward reference to the replacement; never edit an accepted ADD in place.
- Add a timestamp (yyyy-mm-dd HH:MM) when creating or superseding an ADD.
- Write an ADD before building a non-trivial feature; update it alongside the code. Documentation drift is a defect.

## E. Verification and review

- No `make ci` target exists and no Makefile is present; consider adding a unified `Makefile` with a `ci` target. Before declaring work done, run the CI gate:
  - `ruff check src/ tests/`
  - `pytest --cov --cov-report=term-missing tests/`
  - `pip-audit -r requirements.txt`
- All three must exit 0. No type-checker is configured (mypy deferred per ADD-005).
- During review, run the CI gate as well — do not approve on reading the diff alone. Report real command output, never assumed results.
- Review checklist: tests cover new behaviour and failure paths, public APIs documented, no duplicated logic, no dead code, docs and ADDs updated, no secrets.
- Fix root causes, not symptoms; check sibling code paths for the same flaw.

## F. Repository-specific rules

- Configuration is solely via `config/app_config.json`. `.env.example` is NOT an env-var template (no `python-dotenv` or `os.environ` anywhere in the codebase); it is a reference table for config keys and their defaults.
- Reports are written to `reports/<YYYY-MM-DD_HH-MM-SS>/` containing `nudity_report.xlsx` and `nudity_report_session.json`.
- GUI updates from worker threads must use `GLib.idle_add` (ADD-006); never touch GTK widgets from a non-main thread. In tests, patch `src.gui.*.GLib`, not `gi.repository.GLib`.
- Ruff is the sole linter: `line-length = 160`, E402 ignored globally (GTK `gi.require_version` must precede imports). Config in `pyproject.toml`.
- Tests mirror `src/` layout under `tests/`. GTK/gi modules are stubbed via `sys.modules` before any `src` import; see `tests/conftest.py`.
- If you change dependencies, regenerate pinned requirements from `requirements.in` (`pip-compile`) before rerunning checks.
- Run `codegraph sync .` after any code change.
- Branch from `main` using `feature/<issue>-<topic>`, `fix/<issue>-<topic>`, `chore/<topic>`, or `docs/<topic>`.
- Commit messages: imperative mood, 72-char subject, `Closes #<n>` in footer.
- Open PRs against `main`, request review, do not merge your own PR.
