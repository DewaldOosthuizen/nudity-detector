# Release Process

Releases are fully automated via the `.github/workflows/release.yml` workflow.
A push of a version tag is the only manual step required.

---

## Versioning convention

This project uses [Semantic Versioning](https://semver.org/):

    MAJOR.MINOR.PATCH[-prerelease]

| Segment | When to increment |
|---------|-------------------|
| MAJOR | Backwards-incompatible change (removed feature, changed config format) |
| MINOR | New feature, backwards-compatible |
| PATCH | Bug fix, backwards-compatible |
| prerelease | Optional suffix — `rc1`, `beta.1`, `alpha.2`, etc. Tags with a hyphen are automatically marked as pre-releases on GitHub. |

Examples: `v1.0.0`, `v1.1.0`, `v2.0.0`, `v1.2.0-rc1`, `v1.2.0-beta.2`

---

## How to trigger a release

### 1. Ensure main is ready

All changes to be included in the release must be merged to `main` and all CI
checks must be green.

```bash
git checkout main
git pull origin main
```

### 2. Decide the version number

Follow the versioning convention above. Check existing tags to avoid conflicts:

```bash
git tag --sort=-version:refname | head -10
```

### 3. Create and push the tag

```bash
# Stable release
git tag v1.2.0
git push origin v1.2.0

# Pre-release (rc, beta, alpha — any hyphenated suffix)
git tag v1.2.0-rc1
git push origin v1.2.0-rc1
```

Pushing the tag is the only action required. The `Release` workflow starts
automatically.

### 4. Monitor the workflow

```bash
gh run list --workflow=release.yml --limit 5
gh run watch   # interactive tail of the latest run
```

Or open the Actions tab on GitHub:
`https://github.com/DewaldOosthuizen/nudity-detector/actions/workflows/release.yml`

### 5. Verify the release

Once the workflow completes:

```bash
gh release view v1.2.0
```

Or visit:
`https://github.com/DewaldOosthuizen/nudity-detector/releases/tag/v1.2.0`

The release page will contain:
- Auto-generated release notes (commits since the previous tag)
- The AppImage asset: `NudityDetector-v1.2.0-x86_64.AppImage`

---

## What the workflow does

Defined in `.github/workflows/release.yml`. Triggered on any tag matching
`v[0-9]+.[0-9]+.[0-9]*`.

| Step | Action |
|------|--------|
| Checkout | Full source checkout |
| Set up Python 3.12 | Action-managed interpreter |
| Install system deps | GTK4, libadwaita, linuxdeploy deps (apt) |
| Install Python deps | `pip install -r requirements.txt && pip install pyinstaller` |
| Build AppImage | `bash scripts/build_linux.sh` with `APPIMAGE_EXTRACT_AND_RUN=1` (no FUSE in CI) |
| Verify artifacts | Assert `dist/NudityDetector-x86_64.AppImage` exists; print sizes |
| Rename artifact | `NudityDetector-x86_64.AppImage` → `NudityDetector-<tag>-x86_64.AppImage` |
| Publish release | `softprops/action-gh-release@v2` — creates release, uploads AppImage, generates notes |

Tags containing a hyphen (e.g. `v1.2.0-rc1`) are automatically published as
GitHub pre-releases. Stable tags (e.g. `v1.2.0`) are published as full releases.

---

## Rollback / delete a bad release

If a release was published with a defect:

```bash
# Delete the GitHub Release (keeps the tag)
gh release delete v1.2.0 --yes

# Delete the tag locally and remotely
git tag -d v1.2.0
git push origin :refs/tags/v1.2.0
```

Then fix the issue, commit to `main`, and re-tag with the same or a new version.

> Do not reuse a version number once a release has been publicly distributed.
> Prefer a patch bump (v1.2.1) over reusing v1.2.0 after deletion.

---

## Local build (without CI)

To produce an AppImage locally before tagging:

```bash
bash scripts/build_linux.sh
# Output: dist/NudityDetector-x86_64.AppImage
```

See the `## Building a Linux Package` section in the top-level README for
prerequisites and runtime requirements.
