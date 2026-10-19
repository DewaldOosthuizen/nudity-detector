"""Child-process detector factory for the NudeNet backend."""

from .inference_pool import Detector


def create_nudenet_detector() -> Detector:
    """Load NudeNet inside a child process so inference can be terminated safely."""
    from nudenet import NudeDetector

    return NudeDetector()
