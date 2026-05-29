"""Tests for src/reporting/report_manager.py"""
from src.reporting.report_manager import ReportManager


def test_get_report_path_default():
    path = ReportManager.get_report_path()
    assert path.endswith("nudity_report.xlsx")


def test_get_session_path():
    path = ReportManager.get_session_path("/some/dir/nudity_report.xlsx")
    assert path.endswith("_session.json")
    assert ".xlsx" not in path


def test_validate_report_dir_empty_string():
    valid, msg = ReportManager.validate_report_dir("")
    assert valid is False
    assert "empty" in msg.lower()


def test_validate_report_dir_writable(tmp_path):
    valid, msg = ReportManager.validate_report_dir(str(tmp_path))
    assert valid is True
    assert msg == ""


def test_validate_report_dir_system_protected():
    valid, msg = ReportManager.validate_report_dir("/")
    assert valid is False
    assert "system directory" in msg.lower()


def test_load_entries_nonexistent_file():
    entries = ReportManager.load_entries("/nonexistent/path/report.xlsx")
    assert entries == []
