#!/usr/bin/env bash
# =============================================================================
# build_linux.sh — Build a Linux distributable for Nudity Detector
#
# Produces two artifacts in dist/:
#   1. dist/nudity-detector/          — PyInstaller one-dir bundle
#   2. dist/NudityDetector-x86_64.AppImage — portable AppImage
#
# Requirements (install before running):
#   sudo apt-get install python3 python3-pip python3-venv patchelf \
#       python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 \
#       libgtk-4-dev libadwaita-1-dev
#
# The script downloads appimagetool and linuxdeploy into scripts/ on first run.
# FUSE must be available for AppImage self-extraction, or set:
#   export APPIMAGE_EXTRACT_AND_RUN=1
# =============================================================================

set -euo pipefail

# ── Directories ───────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="${PROJECT_ROOT}/dist"
BUILD_DIR="${PROJECT_ROOT}/build"
APPDIR="${BUILD_DIR}/AppDir"
VENV_DIR="${BUILD_DIR}/.build-venv"
TOOLS_DIR="${SCRIPT_DIR}"          # build tools live alongside this script

# ── Tool URLs ─────────────────────────────────────────────────────────────────
APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
LINUXDEPLOY_URL="https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage"
LINUXDEPLOY_GTK_PLUGIN_URL="https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gtk/master/linuxdeploy-plugin-gtk.sh"

APPIMAGETOOL="${TOOLS_DIR}/appimagetool-x86_64.AppImage"
LINUXDEPLOY="${TOOLS_DIR}/linuxdeploy-x86_64.AppImage"
LINUXDEPLOY_GTK="${TOOLS_DIR}/linuxdeploy-plugin-gtk.sh"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ── Step counter ──────────────────────────────────────────────────────────────
STEP=0
step() { (( STEP++ )) || true; echo -e "\n${BLUE}── Step ${STEP}: $* ──${NC}"; }

# =============================================================================
# 1. Prerequisites check
# =============================================================================
step "Checking prerequisites"

for cmd in python3 pip3 patchelf curl; do
    if ! command -v "$cmd" &>/dev/null; then
        error "'$cmd' is not installed. See the requirements at the top of this script."
    fi
done

# Verify GTK4 typelibs are available on the host (needed for bundling)
TYPELIB_DIR=""
for candidate in /usr/lib/girepository-1.0 /usr/lib/x86_64-linux-gnu/girepository-1.0; do
    if [[ -f "${candidate}/Gtk-4.0.typelib" ]]; then
        TYPELIB_DIR="$candidate"
        break
    fi
done
if [[ -z "$TYPELIB_DIR" ]]; then
    error "Gtk-4.0.typelib not found. Install: sudo apt-get install gir1.2-gtk-4.0"
fi
success "All prerequisites satisfied (typelibs at ${TYPELIB_DIR})"

# =============================================================================
# 2. Download build tools (once)
# =============================================================================
step "Downloading build tools (if not cached)"

download_tool() {
    local url="$1" dest="$2" mode="$3"
    if [[ ! -f "$dest" ]]; then
        info "Downloading $(basename "$dest") …"
        curl -fsSL --progress-bar -o "$dest" "$url"
        chmod "$mode" "$dest"
        success "Downloaded $(basename "$dest")"
    else
        info "$(basename "$dest") already cached — skipping download"
    fi
}

download_tool "$APPIMAGETOOL_URL"          "$APPIMAGETOOL"   "755"
download_tool "$LINUXDEPLOY_URL"           "$LINUXDEPLOY"    "755"
download_tool "$LINUXDEPLOY_GTK_PLUGIN_URL" "$LINUXDEPLOY_GTK" "755"

# =============================================================================
# 3. Prepare build virtual environment
# =============================================================================
step "Preparing build virtual environment"

if [[ ! -d "$VENV_DIR" ]]; then
    info "Creating build venv at ${VENV_DIR}"
    python3 -m venv "$VENV_DIR"
fi

# Activate
# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

# Expose system gi (PyGObject) to the build venv – gi cannot be pip-installed
VENV_SITE_PACKAGES="$(python3 -c 'import site; print(site.getsitepackages()[0])')"
GI_SYSTEM_PATH="$(/usr/bin/python3 -c 'import gi, pathlib; print(pathlib.Path(gi.__file__).resolve().parent.parent)' 2>/dev/null || true)"
if [[ -n "$GI_SYSTEM_PATH" ]]; then
    PTH_FILE="${VENV_SITE_PACKAGES}/system-gi.pth"
    if [[ ! -f "$PTH_FILE" ]]; then
        echo "$GI_SYSTEM_PATH" > "$PTH_FILE"
        info "Linked system gi at ${GI_SYSTEM_PATH}"
    fi
else
    warn "Could not locate system gi – GTK4 GUI may not bundle correctly."
fi

info "Installing pip dependencies …"
pip install --quiet --upgrade pip
pip install --quiet -r "${PROJECT_ROOT}/requirements.txt"
pip install --quiet pyinstaller

success "Build venv ready"

# =============================================================================
# 4. PyInstaller build
# =============================================================================
step "Building PyInstaller one-dir bundle"

# Clean previous PyInstaller artefacts but keep the venv
rm -rf "${DIST_DIR}/nudity-detector" "${BUILD_DIR}/nudity-detector"

cd "$PROJECT_ROOT"
pyinstaller \
    --distpath "${DIST_DIR}" \
    --workpath "${BUILD_DIR}" \
    --noconfirm \
    "${SCRIPT_DIR}/nudity-detector.spec"

success "PyInstaller bundle → ${DIST_DIR}/nudity-detector/"

# =============================================================================
# 5. Copy GTK4 typelibs into the bundle
# =============================================================================
step "Copying GTK4/Adw typelibs into bundle"

BUNDLE_TYPELIB_DIR="${DIST_DIR}/nudity-detector/_gi_typelibs"
mkdir -p "$BUNDLE_TYPELIB_DIR"

REQUIRED_TYPELIBS=(
    Gtk-4.0
    Adw-1
    GLib-2.0
    GObject-2.0
    Gio-2.0
    Gdk-4.0
    GdkPixbuf-2.0
    Pango-1.0
    PangoCairo-1.0
    cairo-1.0
    HarfBuzz-0.0
    freetype2-2.0
    fontconfig-2.0
)

for typelib in "${REQUIRED_TYPELIBS[@]}"; do
    src="${TYPELIB_DIR}/${typelib}.typelib"
    if [[ -f "$src" ]]; then
        cp "$src" "$BUNDLE_TYPELIB_DIR/"
    else
        warn "Typelib not found (non-fatal): ${src}"
    fi
done

success "Typelibs copied to bundle"

# =============================================================================
# 6. Assemble AppDir
# =============================================================================
step "Assembling AppDir"

rm -rf "$APPDIR"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/lib"
mkdir -p "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

# Bundle binary → AppDir/usr/bin/nudity-detector-bin/
info "Copying PyInstaller bundle into AppDir …"
cp -r "${DIST_DIR}/nudity-detector" "${APPDIR}/usr/bin/nudity-detector-bin"

# Desktop file
cp "${SCRIPT_DIR}/nudity-detector.desktop" "${APPDIR}/nudity-detector.desktop"
cp "${SCRIPT_DIR}/nudity-detector.desktop" "${APPDIR}/usr/share/applications/nudity-detector.desktop"

# AppRun entry point
cp "${SCRIPT_DIR}/AppRun" "${APPDIR}/AppRun"
chmod +x "${APPDIR}/AppRun"

# ── Icon ──────────────────────────────────────────────────────────────────────
CUSTOM_ICON="${SCRIPT_DIR}/nudity-detector.png"
SYSTEM_ICON=""
# Look for a suitable fallback system icon
for candidate in \
        /usr/share/icons/hicolor/256x256/apps/org.gnome.Utilities.png \
        /usr/share/icons/hicolor/256x256/apps/utilities-system-monitor.png \
        /usr/share/pixmaps/gnome-system-monitor.png; do
    if [[ -f "$candidate" ]]; then
        SYSTEM_ICON="$candidate"
        break
    fi
done

if [[ -f "$CUSTOM_ICON" ]]; then
    info "Using custom icon: ${CUSTOM_ICON}"
    cp "$CUSTOM_ICON" "${APPDIR}/nudity-detector.png"
    cp "$CUSTOM_ICON" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/nudity-detector.png"
elif [[ -n "$SYSTEM_ICON" ]]; then
    warn "No custom icon found at scripts/nudity-detector.png — using system fallback."
    cp "$SYSTEM_ICON" "${APPDIR}/nudity-detector.png"
    cp "$SYSTEM_ICON" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/nudity-detector.png"
else
    warn "No icon found. AppImage will be created without an icon."
    # appimagetool requires at least a placeholder
    convert -size 256x256 xc:transparent "${APPDIR}/nudity-detector.png" 2>/dev/null \
        || touch "${APPDIR}/nudity-detector.png"
fi

success "AppDir assembled at ${APPDIR}"

# =============================================================================
# 7. linuxdeploy GTK plugin — gather GTK4 libraries, schemas and themes
# =============================================================================
step "Running linuxdeploy --plugin gtk to bundle GTK4 libraries"

# linuxdeploy must be able to find the plugin script on PATH
export PATH="${TOOLS_DIR}:${PATH}"
# Tell the GTK plugin we are targeting GTK4 (default is GTK3)
export DEPLOY_GTK_VERSION=4

# Allow FUSE-less execution of the downloaded AppImages
export APPIMAGE_EXTRACT_AND_RUN=1

"$LINUXDEPLOY" \
    --appdir "$APPDIR" \
    --plugin gtk \
    --output appimage \
    --desktop-file "${APPDIR}/nudity-detector.desktop" \
    --icon-file "${APPDIR}/nudity-detector.png" || true
# Note: we do NOT let linuxdeploy create the final AppImage (--output appimage
# is listed for linuxdeploy context; actual image creation is done by
# appimagetool below for more control).  The "--output appimage" flag may
# cause linuxdeploy to also invoke appimagetool – that's fine, we overwrite.

success "linuxdeploy gtk plugin finished"

# =============================================================================
# 8. Compile GSettings schemas inside the bundle
# =============================================================================
step "Compiling GSettings schemas"

SCHEMA_DIR="${APPDIR}/usr/share/glib-2.0/schemas"
if [[ -d "$SCHEMA_DIR" ]]; then
    glib-compile-schemas "$SCHEMA_DIR" && success "Schemas compiled" || warn "glib-compile-schemas failed (non-fatal)"
else
    warn "No schema dir found at ${SCHEMA_DIR} — skipping"
fi

# =============================================================================
# 9. Create AppImage with appimagetool
# =============================================================================
step "Creating AppImage with appimagetool"

APPIMAGE_OUTPUT="${DIST_DIR}/NudityDetector-x86_64.AppImage"
rm -f "$APPIMAGE_OUTPUT"

ARCH=x86_64 "$APPIMAGETOOL" --no-appstream "$APPDIR" "$APPIMAGE_OUTPUT"
chmod +x "$APPIMAGE_OUTPUT"

success "AppImage → ${APPIMAGE_OUTPUT}"

# =============================================================================
# 10. Summary
# =============================================================================
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            Build complete — artifacts in dist/                ║${NC}"
echo -e "${GREEN}╠═══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}  PyInstaller bundle : dist/nudity-detector/              ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  AppImage           : dist/NudityDetector-x86_64.AppImage ${GREEN}║${NC}"
echo -e "${GREEN}╠═══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}  Run the bundle directly:                                ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}    ./dist/nudity-detector/nudity-detector                 ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Run the AppImage:                                        ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}    ./dist/NudityDetector-x86_64.AppImage                  ${GREEN}║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
warn "Note: GTK4 and libadwaita must be installed on the target system."
warn "Note: NudeNet model files are downloaded on first run (requires internet)."
