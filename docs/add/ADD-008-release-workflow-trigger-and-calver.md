# ADD-008 — Release Workflow Trigger and CalVer

| Field | Value |
|-------|-------|
| Status | Accepted |
| Created | 2026-10-13 13:22 |
| Author | Dewald Oosthuizen |
| Supersedes | Release workflow guidance in ADD-004 |

---

## Context

The release documentation must describe the behavior implemented in
`.github/workflows/release.yml`. That workflow runs on pushes to `main` and on
manual `workflow_dispatch`; it does not run when a contributor pushes a
version tag. It validates and builds the selected commit before generating and
pushing a UTC CalVer tag, then renames and publishes the AppImage.

This record supersedes only ADD-004's release-trigger and release-operation
guidance. ADD-004's accepted PyInstaller one-dir and AppImage packaging
architecture remains in force and is carried forward here.

---

## Decision

### Packaging decision carried forward from ADD-004

The application must be distributable as a single AppImage for x86-64 Linux,
without requiring users to install Python or the Python dependencies. The
packaging pipeline remains a two-stage build:

1. PyInstaller runs in `onedir` mode, producing `dist/nudity-detector/` with
the executable and its Python dependencies. One-dir is preferred to one-file
because one-file extracts to `/tmp` at every launch, which can trigger security
policies and slow startup for a large bundle. A `.pth` file exposes the system
PyGObject site-packages to the isolated build virtual environment.
2. `linuxdeploy --plugin gtk` gathers GTK4 libraries, GSettings schemas, and
icon themes into the AppDir; `appimagetool` creates the single executable
AppImage. `scripts/AppRun` configures the runtime library, typelib, schema, and
data paths before launching the PyInstaller bundle.

This carries forward ADD-004's accepted choices: PyInstaller one-dir is Stage 1
and AppImage packaging is Stage 2. The packaging alternatives and rationale
remain:

| Option | Rationale | Verdict |
|--------|-----------|---------|
| PyInstaller one-file | Extracts to `/tmp` on each launch, slowing startup and potentially triggering security policies | Rejected |
| PyInstaller one-dir | Keeps dependencies alongside the executable, avoids per-launch extraction, and starts faster | Accepted — Stage 1 |
| AppImage (`appimagetool`) | Provides one portable file after all dependencies have been gathered into the AppDir | Accepted — Stage 2 |
| Flatpak | Requires a Flatpak runtime on the target and a more complex manifest | Deferred |
| Snap | Requires snapd and is not portable across distributions without it | Rejected |
| Docker | Requires Docker on the end-user machine and does not suit a desktop GUI application | Rejected |
| Nix/Nixpkg | Fully reproducible, but has a steep learning curve and is not applicable to the current team | Rejected |

The packaging consequences also remain unchanged: the AppImage targets Ubuntu
20.04+ and major GNOME-based distributions; local builds can download and cache
the required tools without CI; NudeNet model weights are not bundled and are
downloaded on first run; and `APPIMAGE_EXTRACT_AND_RUN=1` supports runners
without FUSE. GTK4 and libadwaita must be available on the build host, full
portability depends on the target system's GTK4 packaging, build tools are
downloaded from GitHub at build time, and first launch requires internet access
unless the model cache is pre-staged.

### Release trigger and operation order

The release workflow runs on pushes to `main` and on manual
`workflow_dispatch`. A pushed version tag is not a release trigger. The
workflow is authoritative for these steps and their order:

1. Validate the selected commit with Ruff lint, pytest with coverage, and
   `pip-audit`. The test job depends on lint; the dependency audit runs in
   parallel. A validation gate requires all three checks to succeed.
2. Build the AppImage with `scripts/build_linux.sh`, verify
   `dist/NudityDetector-x86_64.AppImage` and `dist/nudity-detector/`, and upload
   the unversioned build artifact.
3. Download the artifact and check whether `HEAD` is already tagged with the
   latest matching CalVer tag; if so, skip release publication.
4. Compute and validate a UTC CalVer tag in `YYYY.MM.DD` format. The first
   release on a UTC date uses that base tag; additional releases that date use
   an incrementing numeric suffix (`YYYY.MM.DD.1`, `.2`, and so on). Verify
   the generated tag is not already on `origin`, then create and push it.
5. Rename the AppImage to
   `NudityDetector-<generated-tag>-x86_64.AppImage` and publish a non-draft,
   non-prerelease GitHub Release with generated release notes and the asset.

Contributors must not create or push a tag to trigger a release. Release
version tags are generated and pushed by the workflow only after validation,
build, and artifact verification have succeeded.

---

## Options Considered

| Option | Description | Verdict |
|--------|-------------|---------|
| Continue manual SemVer tag pushes | Contributors choose and push `v*` tags; this disagrees with the workflow's triggers and generated UTC CalVer | Rejected |
| Compute and push a tag before validation/build | Makes a release tag exist even when validation or packaging fails | Rejected |
| Trigger only on `main` pushes | Automates releases after main changes but provides no manual dispatch path | Rejected |
| Push to `main` and manual `workflow_dispatch`; generate UTC CalVer after build verification | Matches the workflow's actual trigger, gate, build, tag, rename, and publish sequence | Accepted |

The packaging options and rationale carried forward from ADD-004 are documented
in the packaging decision above; this ADD changes release orchestration, not the
accepted packaging stages.

---

## Consequences

**Positive:**

- Documentation matches the workflow's actual triggers and validation/build/
tag/publication order.
- A failed validation or build does not create a new release tag.
- The UTC CalVer tag and versioned AppImage asset are generated consistently
  by the workflow rather than manually chosen by contributors.
- The existing accepted one-dir plus AppImage packaging decision, rationale,
  alternatives, and trade-offs remain preserved from ADD-004.

**Negative / Trade-offs:**

- Every push to `main` can start the release workflow, including pushes that
  are not intended as a distinct release; duplicate `HEAD` tags are skipped.
- Releases on the same UTC date require numeric suffixes.
- A manual dispatch validates and releases its selected commit, which may not
  be the current tip of `main`; the workflow emits a warning if that commit is
  not an ancestor of `origin/main` but continues.
- The build still depends on host GTK4/libadwaita packages and external
  linuxdeploy/appimagetool downloads, as recorded in ADD-004.
