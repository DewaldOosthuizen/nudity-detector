"""Regression tests for session version migration (issue #98).

Covers the session-version migration hook in src.core.models and the
version-aware SessionState.from_dict loader in src.reporting.report_manager.
"""

import sys
from unittest.mock import MagicMock

sys.modules.setdefault("nudenet", MagicMock())

import src.core.models as models
from src.core import constants
from src.core.models import ReportEntry, ScanConfig, SessionState
from src.reporting.report_manager import ReportManager

# ---------------------------------------------------------------------------
# AC-2: the v1 -> v2 migration hook is registered and is a payload no-op
# ---------------------------------------------------------------------------


def test_migration_hook_noop():
    """MIGRATIONS and _migrate_v1_to_v2 are module-level names in src.core.models."""
    assert 1 in models.MIGRATIONS
    assert models._migrate_v1_to_v2 is models.MIGRATIONS[1]
    assert models._migrate_v1_to_v2({}) == {}


# ---------------------------------------------------------------------------
# AC-3: unsupported session versions raise descriptive ValueErrors
# ---------------------------------------------------------------------------


def test_unsupported_versions_raise():
    """Non-integer, bool, and below-chain-start versions raise descriptive ValueError."""
    base_data = {
        "version": 1,
        "saved_at": "2024-01-01T00:00:00",
        "scan_config": {"source_folder": "/x"},
        "results": [],
    }

    for bad_version in ("x", True, 0):
        data = dict(base_data)
        data["version"] = bad_version
        try:
            SessionState.from_dict(data)
        except ValueError as exc:
            assert str(bad_version) in str(exc), (
                f"ValueError did not name stored version {bad_version!r}"
            )
        else:
            raise AssertionError(f"expected ValueError for version {bad_version!r}")


# ---------------------------------------------------------------------------
# AC-1 / AC-4: stored version is validated and applied before the object is built
# ---------------------------------------------------------------------------


def test_v1_session_loads_through_migration_hook():
    """A v1 session saves, then loads, as the current format version."""
    report_path = "/tmp/test_issue98_session_report.xlsx"

    config = ScanConfig(
        source_folder="/round/trip",
        model_name="helloz_nsfw",
        threshold_percent=75.0,
        theme_mode="system",
    )
    entry = ReportEntry(
        file="/round/trip/img.jpg",
        media_type="image",
        model_name="helloz_nsfw",
        threshold_percent=75.0,
        confidence_percent=0.9,
        nudity_detected=True,
        detected_classes="[]",
        thumbnail="",
        date_classified="2025-01-01",
    )
    state = SessionState(version=1, scan_config=config, results=[entry])

    ReportManager.save_session(state, report_path)
    loaded = ReportManager.load_session(report_path)

    assert loaded.version == constants.SESSION_VERSION
    assert loaded.scan_config.source_folder == "/round/trip"
    assert loaded.scan_config.model_name == "helloz_nsfw"
    assert len(loaded.results) == 1
    assert loaded.results[0].file == "/round/trip/img.jpg"


def test_v1_payload_roundtrips_and_reports_current_version():
    """SessionState.from_dict applies the migration chain and reports the current version."""
    payload = {
        "version": 1,
        "saved_at": "2024-01-01T00:00:00",
        "scan_config": {"source_folder": "/x"},
        "results": [],
    }
    state = SessionState.from_dict(payload)

    assert state.version == constants.SESSION_VERSION
    assert state.scan_config.source_folder == "/x"
    assert state.results == []


def test_unknown_version_raises():
    """A newer unsupported version raises ValueError, not a built object."""
    payload = {
        "version": 999,
        "saved_at": "2024-01-01T00:00:00",
        "scan_config": {"source_folder": "/x"},
        "results": [],
    }
    try:
        SessionState.from_dict(payload)
    except ValueError as exc:
        assert "999" in str(exc)
        assert "no migration path" in str(exc)
    else:
        raise AssertionError("expected ValueError for version 999")
