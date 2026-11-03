# Release Process

Releases are managed by `.github/workflows/release.yml`. Automatic releases on
pushes to `main` are temporarily paused to conserve GitHub Actions minutes used
by the AppImage build; the push trigger is commented out in the workflow. Start
a release manually with `workflow_dispatch`. A manual run validates the selected
commit, builds and verifies the AppImage, then generates and pushes its UTC
CalVer tag before publishing. Do not create or push a version tag to trigger a
release.

---

## Versioning convention

The workflow generates tags using UTC CalVer: `YYYY.MM.DD`. The first release
on a UTC date uses that date alone; subsequent releases on the same date use a
numeric suffix, such as `YYYY.MM.DD.1`, then `.2`, and so on. Contributors do
not choose, create, or push these tags.

---

## How to trigger a release

### 1. Start a release

In GitHub Actions, select the `Release` workflow and choose **Run workflow**
(`workflow_dispatch`) for the intended commit. Pushes to `main` do not start a
release while automatic triggering is paused. The workflow validates the
selected commit; a manually pushed tag does not start a release.

### 2. Workflow operation order

The workflow runs lint, tests, and `pip-audit` validation, then checks their
results at the validation gate. After that gate passes, it builds the AppImage,
verifies the AppImage and bundle, and uploads the unversioned build artifact.
The release job downloads that artifact, checks whether `HEAD` is already
tagged, computes the next UTC CalVer tag, checks that the tag is unique on
`origin`, and creates and pushes it. It then renames the AppImage and publishes
the GitHub Release with the asset attached. If `HEAD` is already tagged, the
workflow skips release publication.

### 3. Monitor the workflow

```bash
gh run list --workflow=release.yml --limit 5
gh run watch   # interactive tail of the latest run
```

Or open the Actions tab on GitHub:
`https://github.com/DewaldOosthuizen/nudity-detector/actions/workflows/release.yml`

### 4. Verify the release

Once the workflow completes:

```bash
TAG="<generated-tag>"
gh release view "$TAG"
```

Or visit:
`https://github.com/DewaldOosthuizen/nudity-detector/releases/tag/<generated-tag>`

The release page will contain:
- Auto-generated release notes (commits since the previous tag)
- The AppImage asset: `NudityDetector-<generated-tag>-x86_64.AppImage`

---

## What the workflow does

Defined in `.github/workflows/release.yml`. It is manually triggered with
`workflow_dispatch`; the automatic push-to-`main` trigger is commented out
while AppImage build minutes are being conserved. A pushed version tag does not
trigger a release.

| Step | Action |
|------|--------|
| Validation | Run `ruff check src/ tests/`, `pytest --cov --cov-report=term-missing tests/`, and `pip-audit -r requirements.txt`; the test job depends on lint and the audit runs in parallel. |
| Validation gate | Require all three validation jobs to succeed before proceeding. |
| Build and verify | Install build dependencies, run `bash scripts/build_linux.sh` with `APPIMAGE_EXTRACT_AND_RUN=1`, verify `dist/NudityDetector-x86_64.AppImage` and `dist/nudity-detector/`, then upload the unversioned artifact. |
| Tag | Check whether `HEAD` is already tagged; compute a unique UTC `YYYY.MM.DD` or `YYYY.MM.DD.N` tag and push it. |
| Rename and publish | Rename the artifact to `NudityDetector-<generated-tag>-x86_64.AppImage` and publish a non-draft, non-prerelease GitHub Release with generated notes. |

---

## Rollback / delete a bad release

If a release was published with a defect:

```bash
# Replace this value with the generated tag for the bad release.
TAG="<generated-tag>"

# Delete the GitHub Release but retain its generated tag so the workflow's
# next CalVer tag advances rather than reusing this one.
gh release delete "$TAG" --yes
```

After correcting the issue, start a new `workflow_dispatch` run for the
intended commit. The workflow generates the next tag (using the next numeric
suffix if this is still the same UTC date); do not create or push a tag manually.

> Do not manually reuse or recreate a generated release tag.

---

## Local build (without CI)

To produce an AppImage locally without starting a release:

```bash
bash scripts/build_linux.sh
# Output: dist/NudityDetector-x86_64.AppImage
```

See the `## Building a Linux Package` section in the top-level README for
prerequisites and runtime requirements.
