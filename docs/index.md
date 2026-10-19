# Documentation Index

All persistent project documentation lives under this directory.

## Reading Guide

| Document | Description |
|----------|-------------|
| [getting-started.md](getting-started.md) | Installation, prerequisites, running the app, supported formats, output, building |
| [configuration.md](configuration.md) | Full `app_config.json` reference — all 19 keys, migration, validation |
| [architecture.md](architecture.md) | Architecture overview — layers, modules, data flow, testing strategy |
| [contributing.md](contributing.md) | Branch naming, commit style, PR process, coding standards |
| [development.md](development.md) | Running checks, dependency management, codegraph workflow |
| [releasing.md](releasing.md) | Release process, versioning convention, rollback |
| [agent-guide.md](agent-guide.md) | AI agent rules, standards, verification, repository-specific rules |
| [add/README.md](add/README.md) | Architectural Decision Documents index |
| [diagrams/README.md](diagrams/README.md) | Mermaid diagram suite |

## Quick Links

- **New contributor?** Start with [getting-started.md](getting-started.md), then [contributing.md](contributing.md).
- **Changing code?** Read [agent-guide.md](agent-guide.md) for standards, then [development.md](development.md) for checks.
- **Modifying config?** See [configuration.md](configuration.md) for the full reference.
- **Designing a feature?** Check [add/README.md](add/README.md) for existing ADDs, then write one before building.
- **Releasing?** See [releasing.md](releasing.md).

## CI / CD Pipeline

Two workflows cover all changes:

- **Pull Request Gate** — `.github/workflows/pr_gate.yml` runs on every PR targeting `main`. It runs Ruff lint, pytest with coverage (after lint), and `pip-audit` (in parallel with lint/test), then summarizes those results; it does not run a type-check job. In-progress runs are cancelled when a new commit lands on the PR.
- **Release Pipeline** — `.github/workflows/release.yml` runs on pushes to `main` and via `workflow_dispatch`. It runs lint, pytest, and `pip-audit`, checks them at a validation gate, then builds and verifies the AppImage and uploads the build artifact. Only afterward does it check whether `HEAD` is already tagged, compute and check a unique UTC CalVer tag (`YYYY.MM.DD`, or `YYYY.MM.DD.N` for another release on that UTC date), create and push the tag, rename the asset to `NudityDetector-<generated-tag>-x86_64.AppImage`, and publish the GitHub Release. Do not push a tag to trigger a release.

Tags are **CalVer only**. Legacy non-CalVer tags have been cleaned up.

### GitHub Actions pinning and updates

Pin each action to a verified full commit SHA and keep the exact upstream release version in an inline comment. Verify the SHA against that specific release tag when adding or updating a pin; do not verify only against a moving major tag.

Dependabot proposes monthly GitHub Actions updates. Review every proposed version-to-SHA mapping and require the repository PR validation gates to pass before merging. Only the release-publishing job receives `contents: write`.

## Documentation Conventions

When behavior, API contracts, deployment steps, or architecture change, update the relevant doc under this `docs/` tree in the same change. Code and docs must stay in sync.

For authoritative rules on verification, review, conventions, and context efficiency, see [agent-guide.md](agent-guide.md) and [openspec/config.yaml](../openspec/config.yaml) (when present in this repo).

- Streamed scan progress: bounded producer/consumer discovery; see [architecture.md](architecture.md) "Scan Progress and Discovery (Issue #109)".
