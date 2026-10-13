# Documentation Index

All persistent project documentation lives under this directory.

## CI / CD Pipeline

Two workflows cover all changes:

- **Pull Request Gate** — `.github/workflows/pr_gate.yml` runs on every PR targeting `main`. It runs Ruff lint, pytest with coverage (after lint), and `pip-audit` (in parallel with lint/test), then summarizes those results; it does not run a type-check job. In-progress runs are cancelled when a new commit lands on the PR.
- **Release Pipeline** — `.github/workflows/release.yml` runs on pushes to `main` and via `workflow_dispatch`. It runs lint, pytest, and `pip-audit`, checks them at a validation gate, then builds and verifies the AppImage and uploads the build artifact. Only afterward does it check whether `HEAD` is already tagged, compute and check a unique UTC CalVer tag (`YYYY.MM.DD`, or `YYYY.MM.DD.N` for another release on that UTC date), create and push the tag, rename the asset to `NudityDetector-<generated-tag>-x86_64.AppImage`, and publish the GitHub Release. Do not push a tag to trigger a release.

Tags are **CalVer only**. Legacy non-CalVer tags have been cleaned up.

## Documentation Conventions

When behavior, API contracts, deployment steps, or architecture change, update the relevant doc under this `docs/` tree in the same change. Code and docs must stay in sync.

For authoritative rules on verification, review, conventions, and context efficiency, see [openspec/config.yaml](../openspec/config.yaml) (when present in this repo).
