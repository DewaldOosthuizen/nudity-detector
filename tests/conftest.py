"""Shared pytest fixtures for the nudity-detector test suite."""
import pytest


@pytest.fixture
def tmp_report_dir(tmp_path):
    """Temporary report directory backed by pytest's tmp_path."""
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    return str(report_dir)


@pytest.fixture
def fake_report_entry():
    """Factory fixture that returns a callable producing fake report entry dicts."""
    def _factory(
        file="/tmp/test_image.jpg",
        media_type="image",
        model="nudenet",
        threshold_percent=60.0,
        confidence_percent=85.0,
        nudity_detected=True,
        detected_classes="[]",
        thumbnail="",
        date_classified="2024-01-01 00:00:00",
    ):
        return {
            "file": file,
            "media_type": media_type,
            "model": model,
            "threshold_percent": threshold_percent,
            "confidence_percent": confidence_percent,
            "nudity_detected": nudity_detected,
            "detected_classes": detected_classes,
            "thumbnail": thumbnail,
            "date_classified": date_classified,
        }
    return _factory
