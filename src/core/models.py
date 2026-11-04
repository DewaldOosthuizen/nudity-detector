"""
Data models for the Nudity Detector application.
Provides type-safe, structured data classes for report entries, scan configs, and session state.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List

from . import constants

logger = logging.getLogger(__name__)


@dataclass
class ScanConfig:
    """Configuration for a scan session."""
    source_folder: str = ''
    model_name: str = constants.MODEL_NUDENET
    threshold_percent: float = constants.DEFAULT_THRESHOLD_PERCENT
    theme_mode: str = constants.THEME_SYSTEM

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScanConfig':
        """Create from dictionary."""
        return cls(
            source_folder=data.get('source_folder', ''),
            model_name=data.get('model_name', constants.MODEL_NUDENET),
            threshold_percent=float(data.get('threshold_percent', constants.DEFAULT_THRESHOLD_PERCENT)),
            theme_mode=data.get('theme_mode', constants.THEME_SYSTEM),
        )


@dataclass
class ReportEntry:
    """Single detection result entry."""
    file: str
    media_type: str
    model_name: str
    threshold_percent: float
    confidence_percent: float
    nudity_detected: bool
    detected_classes: str
    thumbnail: str = ''
    date_classified: str = ''

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_row(self) -> List[Any]:
        """Convert to Excel row format."""
        return [
            self.file,
            self.media_type,
            self.model_name,
            self.threshold_percent,
            self.confidence_percent,
            self.nudity_detected,
            self.detected_classes,
            self.thumbnail,
            self.date_classified,
        ]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReportEntry':
        """Create from dictionary."""
        return cls(
            file=data.get('file', ''),
            media_type=data.get('media_type', constants.MEDIA_TYPE_UNKNOWN),
            model_name=data.get('model_name', ''),
            threshold_percent=float(data.get('threshold_percent', constants.DEFAULT_THRESHOLD_PERCENT)),
            confidence_percent=float(data.get('confidence_percent', 0.0)),
            nudity_detected=bool(data.get('nudity_detected', False)),
            detected_classes=data.get('detected_classes', '[]'),
            thumbnail=data.get('thumbnail', ''),
            date_classified=data.get('date_classified', ''),
        )


@dataclass
class SessionState:
    """Complete scan session state."""
    version: int = constants.SESSION_VERSION
    saved_at: str = ''
    scan_config: ScanConfig = field(default_factory=ScanConfig)
    results: List[ReportEntry] = field(default_factory=list)

    def __post_init__(self):
        """Ensure scanconfig is a ScanConfig instance."""
        if isinstance(self.scan_config, dict):
            self.scan_config = ScanConfig.from_dict(self.scan_config)
        if self.saved_at == '':
            self.saved_at = datetime.now().isoformat(timespec='seconds')

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'version': self.version,
            'saved_at': self.saved_at,
            'scan_config': self.scan_config.to_dict(),
            'results': [r.to_dict() for r in self.results],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionState':
        """Create from dictionary, applying any stored session-version migration.

        The stored version is validated and, when it is older than the current
        format version (:data:`src.core.constants.SESSION_VERSION`), every
        registered migrator on the path is applied in ascending order. Each
        applied migrator is logged at WARNING so the user is told a migration
        was performed. Hand-edited or corrupt session files that declare a
        non-integer version, a version below the start of the migration chain,
        or a version newer than the current format raise a descriptive
        ``ValueError`` instead of a confusing ``TypeError`` or ``KeyError``.

        Args:
            data: The session payload dict as read from the session JSON file.

        Returns:
            A SessionState in the current format version, with scan_config and
            results converted from their stored representations.

        Raises:
            ValueError: If ``data`` is not a mapping, if the stored version is
                not an integer, or if no migration path exists to the current
                version.
        """
        if not isinstance(data, dict):
            raise ValueError(
                f"Session payload is not a JSON object: {type(data).__name__}"
            )

        stored_version = data.get('version', constants.SESSION_VERSION)

        # The stored version must be an integer. None, strings, floats and lists
        # would otherwise raise a confusing TypeError from a comparison, or be
        # silently treated as the current version.
        if isinstance(stored_version, bool) or not isinstance(stored_version, int):
            logger.warning(
                "Session file declares a non-integer version %r; refusing to load.",
                stored_version,
            )
            raise ValueError(
                f"Unsupported session version {stored_version!r}: expected an integer, "
                f"got {type(stored_version).__name__}"
            )

        if stored_version > constants.SESSION_VERSION:
            logger.warning(
                "Session file declares version %r, newer than the current format "
                "version %d; refusing to load.",
                stored_version,
                constants.SESSION_VERSION,
            )
            raise ValueError(
                f"Unsupported session version {stored_version!r}: no migration "
                f"path to version {constants.SESSION_VERSION}"
            )

        migrator = stored_version
        while migrator < constants.SESSION_VERSION:
            migrator_fn = MIGRATIONS.get(migrator)
            if migrator_fn is None:
                logger.warning(
                    "Session file declares version %r; no migration path from "
                    "version %d to version %d.",
                    stored_version,
                    migrator,
                    constants.SESSION_VERSION,
                )
                raise ValueError(
                    f"Unsupported session version {stored_version!r}: no migration "
                    f"path from version {migrator} to version {constants.SESSION_VERSION}"
                )
            data = migrator_fn(data)
            logger.warning(
                "Session version migrated from v%d to v%d",
                migrator,
                migrator + 1,
            )
            migrator += 1

        scan_config = ScanConfig.from_dict(data.get('scan_config', {}))
        results = [ReportEntry.from_dict(r) for r in data.get('results', [])]
        return cls(
            version=constants.SESSION_VERSION,
            saved_at=data.get('saved_at', datetime.now().isoformat(timespec='seconds')),
            scan_config=scan_config,
            results=results,
        )


def _migrate_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate a v1 session payload to v2.

    v2 keeps the v1 schema bit-for-bit (same keys, same value types), so this
    migrator is a pure no-op on the payload. It exists solely to register the
    migration hook: when the session format changes again, one new entry such as
    ``2: _migrate_v2_to_v3`` added to :data:`MIGRATIONS` is the whole change, and
    the loader walks the chain automatically. Nothing else in this module
    (:mod:`src.core.models`) or in :mod:`src.reporting.report_manager` (which
    delegates every load to :meth:`SessionState.from_dict`) needs to know about
    the version.
    """
    logger.debug("Session v1 -> v2 migration: no-op (schema unchanged)")
    return data


# Migration registry: source schema version -> migrator that rewrites the payload
# to the next version. Migrate in ascending order; each migrator receives the
# output of the previous one. Add a new entry for every future schema change; the
# loader walks the whole chain automatically.
MIGRATIONS: Dict[int, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    1: _migrate_v1_to_v2,
}


@dataclass
class DetectionResult:
    """Raw detection result from a detection model."""
    file_path: str
    media_type: str
    model_name: str
    raw_data: Any  # Can be list, dict, or any format from the model
    max_confidence: float = 0.0
    nudity_detected: bool = False
    detected_classes: List[str] = field(default_factory=list)

    def _serialize_classes(self) -> str:
        """Serialize detected_classes list to a JSON string."""
        try:
            return json.dumps(self.detected_classes, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(self.detected_classes)

    def to_report_entry(
        self,
        threshold_percent: float = constants.DEFAULT_THRESHOLD_PERCENT,
        thumbnail: str = '',
    ) -> ReportEntry:
        """Convert detection result to report entry."""
        return ReportEntry(
            file=self.file_path,
            media_type=self.media_type,
            model_name=self.model_name,
            threshold_percent=threshold_percent,
            confidence_percent=round(max(0.0, min(self.max_confidence, 1.0)) * 100, 2),
            nudity_detected=self.nudity_detected,
            detected_classes=self._serialize_classes(),
            thumbnail=thumbnail,
            date_classified=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        )
