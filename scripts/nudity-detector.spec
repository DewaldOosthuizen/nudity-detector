# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Nudity Detector – one-dir (onedir) build.
# Run via: pyinstaller scripts/nudity-detector.spec
# Output: dist/nudity-detector/

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

# ── Project root (one level above this spec file in scripts/) ───────────────
spec_dir = Path(SPECPATH)            # noqa: F821  (SPECPATH injected by PyInstaller)
project_root = spec_dir.parent

# ── Collect complete packages that need all sub-modules & data ───────────────
nudenet_datas, nudenet_binaries, nudenet_hiddenimports = collect_all('nudenet')
vnudenet_datas, vnudenet_binaries, vnudenet_hiddenimports = collect_all('vnudenet')
gi_datas, gi_binaries, gi_hiddenimports = collect_all('gi')
cv2_datas, cv2_binaries, cv2_hiddenimports = collect_all('cv2')

all_datas = (
    nudenet_datas
    + vnudenet_datas
    + gi_datas
    + cv2_datas
    # Bundle the app config so the packaged binary finds it at runtime
    + [(str(project_root / 'config'), 'config')]
)
all_binaries = nudenet_binaries + vnudenet_binaries + gi_binaries + cv2_binaries
all_hiddenimports = (
    nudenet_hiddenimports
    + vnudenet_hiddenimports
    + gi_hiddenimports
    + cv2_hiddenimports
    + [
        # GObject-introspection core
        'gi',
        'gi.repository',
        'gi.repository.GLib',
        'gi.repository.GObject',
        'gi.repository.Gio',
        'gi.repository.Gdk',
        'gi.repository.GdkPixbuf',
        'gi.repository.Gtk',
        'gi.repository.Adw',
        'gi.repository.Pango',
        'gi.repository.PangoCairo',
        'gi.repository.cairo',
        'gi.overrides',
        'gi.overrides.Gtk',
        'gi.overrides.GLib',
        'gi.overrides.Gio',
        # App modules
        'src',
        'src.core',
        'src.core.constants',
        'src.core.models',
        'src.core.utils',
        'src.detectors',
        'src.detectors.nudenet',
        'src.detectors.deepstack',
        'src.processing',
        'src.processing.media_processor',
        'src.reporting',
        'src.reporting.report_manager',
        'src.gui',
        'src.gui.app',
        'src.gui.scanning',
        'src.gui.preview',
        'src.gui.session',
        'src.gui.results',
        'src.gui.dialogs',
        'src.gui.result_item',
        # Common runtime deps
        'openpyxl',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'requests',
        'send2trash',
        'darkdetect',
        'numpy',
        'onnxruntime',
    ]
)

block_cipher = None

a = Analysis(
    [str(project_root / 'run_gui.py')],
    pathex=[str(project_root)],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'PyQt5',
        'PyQt6',
        'wx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,       # onedir: keep libs alongside binary
    name='nudity-detector',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,               # no terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='nudity-detector',      # dist/nudity-detector/
)
