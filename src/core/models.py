"""
Data models for the Nudity Detector application.
Provides type-safe, structured data classes for report entries, scan configs, and session state.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Any, List, Optional

from . import constants


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
        """Create from dictionary."""
        scan_config = ScanConfig.from_dict(data.get('scan_config', {}))
        results = [ReportEntry.from_dict(r) for r in data.get('results', [])]
        return cls(
            version=data.get('version', constants.SESSION_VERSION),
            saved_at=data.get('saved_at', datetime.now().isoformat(timespec='seconds')),
            scan_config=scan_config,
            results=results,
        )


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
        import json
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
