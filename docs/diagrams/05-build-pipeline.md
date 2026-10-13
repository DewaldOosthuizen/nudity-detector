# 05 — Build Pipeline

The full packaging pipeline from source to distributable AppImage,
covering both local developer builds and the CI release workflow.

## Local build (scripts/build_linux.sh)

```mermaid
flowchart TD
    A([Developer runs\nbash scripts/build_linux.sh]) --> B[Step 1: Check prerequisites\npython3 · pip3 · patchelf · Gtk-4.0.typelib]
    B --> C[Step 2: Download build tools\nappimagetool · linuxdeploy · linuxdeploy-plugin-gtk\ncached in scripts/ after first run]
    C --> D[Step 3: Create build venv\nbuild/.build-venv\nExpose system gi via .pth file]
    D --> E[Step 4: pip install\nrequirements.txt + pyinstaller]
    E --> F[Step 5: PyInstaller\nscripts/nudity-detector.spec\nonedir mode]
    F --> G[dist/nudity-detector/\nexecutable + Python runtime\n+ all pip deps]
    G --> H[Step 6: Copy GTK4 typelibs\nGtk-4.0 · Adw-1 · GLib-2.0\netc. → dist/nudity-detector/_gi_typelibs/]
    H --> I[Step 7: Assemble AppDir\nbuild/AppDir/\nbundle · desktop file · icon · AppRun]
    I --> J[Step 8: linuxdeploy --plugin gtk\nGather GTK4 shared libraries\nGSettings schemas · icon themes]
    J --> K[Step 9: glib-compile-schemas\nCompile GSettings schemas inside AppDir]
    K --> L[Step 10: appimagetool\nARCH=x86_64]
    L --> M([dist/NudityDetector-x86_64.AppImage])
```

## CI release workflow (.github/workflows/release.yml)

```mermaid
flowchart TD
    A([Push to main\nor manual workflow_dispatch]) --> B[Validation jobs\nlint · pytest · pip-audit\ntest needs lint; audit runs in parallel]
    B --> C{Validation gate\nall jobs passed?}
    C -- No --> D([Workflow fails\nno build or release])
    C -- Yes --> E[Build AppImage\nUbuntu runner\nAPPIMAGE_EXTRACT_AND_RUN=1]
    E --> F{Build succeeded?}
    F -- No --> D
    F -- Yes --> G[Verify AppImage and bundle\nupload appimage-build artifact]
    G --> H[Download build artifact\ncheck whether HEAD is already tagged]
    H --> I{HEAD already tagged?}
    I -- Yes --> J([Skip release])
    I -- No --> K[Compute UTC CalVer tag\nYYYY.MM.DD or YYYY.MM.DD.N\ncheck uniqueness on origin]
    K --> L[Create and push generated tag]
    L --> M[Rename asset to\nNudityDetector-<generated-tag>-x86_64.AppImage]
    M --> N[softprops/action-gh-release@v2\nCreate GitHub Release\nattach AppImage]
    N --> O([GitHub Release published])

    style D fill:#7f1d1d,color:#fca5a5
    style O fill:#14532d,color:#86efac
```

The workflow validates and builds the selected commit before generating and
pushing its UTC CalVer tag. Do not push a tag to trigger a release.

## What is bundled vs host-required

| Component | Bundled in AppImage | Notes |
|-----------|--------------------|----|
| Python 3.12 runtime | Yes | PyInstaller embeds interpreter |
| pip dependencies | Yes | Collected by PyInstaller |
| GTK4 shared libraries | Best-effort | `linuxdeploy-plugin-gtk` collects from build host |
| GTK4 GI typelibs | Yes | Explicitly copied by `build_linux.sh` step 6 |
| GSettings schemas + themes | Yes | Collected by `linuxdeploy-plugin-gtk` |
| NudeNet model weights | No | Downloaded on first run — requires internet access |
| libadwaita | Best-effort | Must be installed on build host |
