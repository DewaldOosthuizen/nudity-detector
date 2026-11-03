#!/usr/bin/env python3
"""Install the local development launcher and branded icon for the current user."""

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core import constants  # noqa: E402

APPLICATION_ID = constants.APP_ID
ICON_NAME = constants.APP_ICON_NAME


def _quote_exec_argument(argument: str) -> str:
    """Quote one path for the freedesktop ``Exec`` field format."""
    escaped = argument.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("$", "\\$").replace("`", "\\`").replace("%", "%%")
    return f'"{escaped}"'


def install_local_desktop(project_root: Path, data_home: Path) -> tuple[Path, Path]:
    """Install a desktop entry and icon for running this checkout locally.

    Args:
        project_root: Root of the checkout containing ``.venv``, ``run_gui.py``,
            and the desktop/icon assets under ``scripts``.
        data_home: Freedesktop user data directory, normally ``~/.local/share``.

    Returns:
        The installed desktop-entry and icon paths.

    Raises:
        FileNotFoundError: If a required local launcher or branding asset is absent.
        ValueError: If the packaged desktop template does not contain exactly one
            ``Exec`` entry.
        subprocess.CalledProcessError: If the available GTK icon-cache updater fails.
    """
    project_root = project_root.resolve()
    python_executable = project_root / ".venv" / "bin" / "python"
    gui_entrypoint = project_root / "run_gui.py"
    desktop_template = project_root / "scripts" / "nudity-detector.desktop"
    icon_source = project_root / "scripts" / f"{ICON_NAME}.png"

    for required_path in (python_executable, gui_entrypoint, desktop_template, icon_source):
        if not required_path.is_file():
            raise FileNotFoundError(f"Required local desktop asset not found: {required_path}")

    lines = desktop_template.read_text(encoding="utf-8").splitlines()
    exec_indices = [index for index, line in enumerate(lines) if line.startswith("Exec=")]
    if len(exec_indices) != 1:
        raise ValueError(f"Expected exactly one Exec entry in {desktop_template}")

    exec_command = " ".join(_quote_exec_argument(str(path)) for path in (python_executable, gui_entrypoint))
    lines[exec_indices[0]] = f"Exec={exec_command}"

    applications_dir = data_home / "applications"
    icons_dir = data_home / "icons" / "hicolor" / "256x256" / "apps"
    desktop_path = applications_dir / f"{APPLICATION_ID}.desktop"
    installed_icon_path = icons_dir / f"{ICON_NAME}.png"

    applications_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)
    desktop_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    shutil.copy2(icon_source, installed_icon_path)

    icon_cache_updater = shutil.which("gtk-update-icon-cache")
    if icon_cache_updater:
        subprocess.run(
            [icon_cache_updater, "--force", "--ignore-theme-index", str(data_home / "icons" / "hicolor")],
            check=True,
        )

    return desktop_path, installed_icon_path


def main() -> None:
    """Install local desktop integration under the current user's data directory."""
    desktop_path, icon_path = install_local_desktop(PROJECT_ROOT, Path.home() / ".local" / "share")
    print(f"Installed desktop entry: {desktop_path}")
    print(f"Installed application icon: {icon_path}")


if __name__ == "__main__":
    main()
