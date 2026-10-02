"""Shared pytest fixtures for the nudity-detector test suite."""
import sys

import pytest


class _BlockRealGI:
    """Prevent the real PyGObject package from being imported during tests.

    GUI test modules install their own MagicMock-based ``gi`` stubs and assume
    the real toolkit is absent (as it is in CI, where PyGObject is not a
    dependency). On developer machines with system ``python3-gi`` installed the
    real package can be pulled in transitively — ``send2trash`` imports
    ``gi.repository.Gio`` on Linux — before those stubs run, which breaks their
    collection. Blocking the real package here makes local runs match CI.
    """

    def find_spec(self, name, path=None, target=None):
        if name == "gi" or name.startswith("gi."):
            raise ImportError("real gi blocked in tests; GUI tests install stubs")
        return None


sys.meta_path.insert(0, _BlockRealGI())


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
        model_name="nudenet",
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
            "model_name": model_name,
            "threshold_percent": threshold_percent,
            "confidence_percent": confidence_percent,
            "nudity_detected": nudity_detected,
            "detected_classes": detected_classes,
            "thumbnail": thumbnail,
            "date_classified": date_classified,
        }
    return _factory
