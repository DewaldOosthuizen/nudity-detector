from pathlib import Path

from scripts.install_local_desktop import APPLICATION_ID, ICON_NAME, install_local_desktop


def test_appimage_desktop_template_matches_the_gtk_application_identity():
    desktop_path = Path(__file__).resolve().parents[1] / "scripts" / "nudity-detector.desktop"
    desktop = desktop_path.read_text(encoding="utf-8")

    assert "Exec=AppRun\n" in desktop
    assert f"Icon={ICON_NAME}\n" in desktop
    assert f"StartupWMClass={APPLICATION_ID}\n" in desktop


def test_local_desktop_install_uses_application_identity_and_branded_icon(tmp_path):
    project_root = tmp_path / "nudity detector"
    data_home = tmp_path / "xdg data"
    (project_root / ".venv" / "bin").mkdir(parents=True)
    (project_root / "scripts").mkdir()
    (project_root / "run_gui.py").write_text("# GUI entry point\n", encoding="utf-8")
    (project_root / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
    icon_bytes = (Path(__file__).resolve().parents[1] / "scripts" / f"{ICON_NAME}.png").read_bytes()
    (project_root / "scripts" / f"{ICON_NAME}.png").write_bytes(icon_bytes)
    (project_root / "scripts" / "nudity-detector.desktop").write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Nudity Detector\n"
        "Exec=AppRun\n"
        f"Icon={ICON_NAME}\n"
        f"StartupWMClass={APPLICATION_ID}\n",
        encoding="utf-8",
    )

    desktop_path, installed_icon_path = install_local_desktop(project_root, data_home)

    assert desktop_path == data_home / "applications" / f"{APPLICATION_ID}.desktop"
    assert installed_icon_path == data_home / "icons" / "hicolor" / "256x256" / "apps" / f"{ICON_NAME}.png"
    desktop = desktop_path.read_text(encoding="utf-8")
    assert f'Exec="{project_root / ".venv" / "bin" / "python"}" "{project_root / "run_gui.py"}"' in desktop
    assert f"Icon={ICON_NAME}\n" in desktop
    assert f"StartupWMClass={APPLICATION_ID}\n" in desktop
    assert installed_icon_path.read_bytes() == icon_bytes
