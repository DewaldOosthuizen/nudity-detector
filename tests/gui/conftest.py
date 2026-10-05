"""GUI-test-session guard: fail loudly if real PyGObject is in play.

``tests/conftest.py`` refuses to fake a genuine ``gi`` package — overwriting a
third-party library's attributes from a fixture would break ``send2trash`` and make
the suite order-dependent. The consequence is that, if something imports real
PyGObject before the stubs are installed, the gui tests would subclass and construct
genuine GTK types while still reporting success.

That assumption ("the root conftest runs before any ``src`` import and therefore
wins the race") is load-bearing, so it is verified here rather than trusted: this
module runs at gui-collection time, after every test module has been imported, and
fails the session if a real ``gi`` is present.
"""
import sys

from tests.conftest import REAL_GI_DETECTED, _is_real_gi


def pytest_collection_modifyitems(session, config, items):
    """Fail the gui test session when genuine PyGObject is loaded.

    Args:
        session: The pytest session (unused).
        config: The pytest config (unused).
        items: Collected test items (unused).

    Raises:
        pytest.ExitCode.TESTS_FAILED: Real PyGObject is active, so the gui tests are
            not testing the stubbed code paths they claim to.
    """
    if not items:
        return
    gi_module = sys.modules.get("gi")
    if _is_real_gi(gi_module):
        origin = getattr(gi_module, "__file__", "unknown")
        detail = ", ".join(REAL_GI_DETECTED) or origin
        raise RuntimeError(
            "Real PyGObject is loaded in the gui test session (from "
            f"{detail}). The gi stubs were not installed, so these tests would "
            "exercise genuine GTK objects instead of the stubbed code paths. "
            "Import order changed — check what pulls in `gi` before tests/conftest.py "
            "installs its stubs."
        )