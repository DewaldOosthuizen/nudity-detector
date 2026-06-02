"""Tests for issue #50 - Replace module-level logging.basicConfig calls."""
import ast
import pathlib

ROOT = pathlib.Path(__file__).parent.parent.parent

NUDENET_PATH = ROOT / 'src' / 'detectors' / 'nudenet.py'
HELLOZ_PATH = ROOT / 'src' / 'detectors' / 'helloz_nsfw.py'
RUN_NUDENET_PATH = ROOT / 'run_nudenet.py'
RUN_HELLOZ_PATH = ROOT / 'run_helloz_nsfw.py'


def _source(path):
    return path.read_text()


def _ast(path):
    return ast.parse(_source(path))


def test_nudenet_no_module_level_basicconfig():
    """src/detectors/nudenet.py must not call logging.basicConfig at module level."""
    source = _source(NUDENET_PATH)
    assert 'logging.basicConfig' not in source


def test_helloz_no_module_level_basicconfig():
    """src/detectors/helloz_nsfw.py must not call logging.basicConfig at module level."""
    source = _source(HELLOZ_PATH)
    assert 'logging.basicConfig' not in source


def test_nudenet_defines_logger():
    """src/detectors/nudenet.py must define logger = logging.getLogger(__name__)."""
    source = _source(NUDENET_PATH)
    assert 'logger = logging.getLogger(__name__)' in source


def test_helloz_defines_logger():
    """src/detectors/helloz_nsfw.py must define logger = logging.getLogger(__name__)."""
    source = _source(HELLOZ_PATH)
    assert 'logger = logging.getLogger(__name__)' in source


def _basicconfig_in_main_guard(path):
    """Return True if basicConfig is called inside if __name__ == '__main__': block."""
    tree = _ast(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            # Check if it's the __name__ == '__main__' guard
            test = node.test
            is_main_guard = (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == '__name__'
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value == '__main__'
            )
            if is_main_guard:
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        func = child.func
                        if (isinstance(func, ast.Attribute)
                                and func.attr == 'basicConfig'):
                            return True
    return False


def test_run_nudenet_basicconfig_in_main_guard():
    """run_nudenet.py must call logging.basicConfig inside if __name__ == '__main__'."""
    assert _basicconfig_in_main_guard(RUN_NUDENET_PATH)


def test_run_helloz_basicconfig_in_main_guard():
    """run_helloz_nsfw.py must call logging.basicConfig inside if __name__ == '__main__'."""
    assert _basicconfig_in_main_guard(RUN_HELLOZ_PATH)
