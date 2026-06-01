"""Tests for issue #33 - path traversal validation in open_file / open_file_location."""
import os
import pathlib
import sys
from unittest.mock import patch, MagicMock

import pytest

from src.core.utils import open_file, open_file_location, _validate_path_within_root


# ---------------------------------------------------------------------------
# _validate_path_within_root
# ---------------------------------------------------------------------------

def test_validate_path_within_root_returns_resolved_path(tmp_path):
    child = tmp_path / "images" / "photo.jpg"
    child.parent.mkdir(parents=True)
    child.touch()
    result = _validate_path_within_root(str(child), str(tmp_path))
    assert result == child.resolve()


def test_validate_path_within_root_raises_for_escape(tmp_path):
    outside = tmp_path.parent / "outside.jpg"
    with pytest.raises(ValueError):
        _validate_path_within_root(str(outside), str(tmp_path))


def test_validate_path_within_root_raises_for_dotdot(tmp_path):
    escape_path = str(tmp_path / ".." / "escape.jpg")
    with pytest.raises(ValueError):
        _validate_path_within_root(escape_path, str(tmp_path))


def test_validate_path_within_root_raises_for_symlink_escape(tmp_path):
    outside = tmp_path.parent / "secret.jpg"
    outside.touch()
    link = tmp_path / "link.jpg"
    link.symlink_to(outside)
    with pytest.raises(ValueError):
        _validate_path_within_root(str(link), str(tmp_path))
    outside.unlink()


# ---------------------------------------------------------------------------
# open_file with scan_root
# ---------------------------------------------------------------------------

def test_open_file_inside_root_calls_subprocess(tmp_path):
    child = tmp_path / "photo.jpg"
    child.touch()
    with patch("src.core.utils.subprocess.run") as mock_run, \
         patch("src.core.utils.sys.platform", "linux"):
        success, msg = open_file(str(child), scan_root=str(tmp_path))
    assert success is True
    assert msg == ""
    mock_run.assert_called_once()


def test_open_file_outside_root_blocked(tmp_path):
    outside = tmp_path.parent / "evil.jpg"
    outside.touch()
    try:
        with patch("src.core.utils.subprocess.run") as mock_run:
            success, msg = open_file(str(outside), scan_root=str(tmp_path))
        assert success is False
        assert msg != ""
        mock_run.assert_not_called()
    finally:
        outside.unlink()


def test_open_file_empty_scan_root_backward_compat(tmp_path):
    child = tmp_path / "photo.jpg"
    child.touch()
    with patch("src.core.utils.subprocess.run") as mock_run, \
         patch("src.core.utils.sys.platform", "linux"):
        success, msg = open_file(str(child))
    assert success is True
    mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# open_file_location with scan_root
# ---------------------------------------------------------------------------

def test_open_file_location_outside_root_blocked(tmp_path):
    outside = tmp_path.parent / "evil_dir" / "photo.jpg"
    outside.parent.mkdir(exist_ok=True)
    outside.touch()
    try:
        with patch("src.core.utils.subprocess.run") as mock_run:
            success, msg = open_file_location(str(outside), scan_root=str(tmp_path))
        assert success is False
        assert msg != ""
        mock_run.assert_not_called()
    finally:
        outside.unlink()
        outside.parent.rmdir()


def test_open_file_location_inside_root_calls_subprocess(tmp_path):
    child = tmp_path / "images" / "photo.jpg"
    child.parent.mkdir()
    child.touch()
    with patch("src.core.utils.subprocess.run") as mock_run, \
         patch("src.core.utils.sys.platform", "linux"):
        success, msg = open_file_location(str(child), scan_root=str(tmp_path))
    assert success is True
    mock_run.assert_called_once()
