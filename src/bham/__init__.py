"""نسخه‌گذاری و ورودی‌های عمومی BHAM."""
from __future__ import annotations
__version__ = "1.0.0"
__product__ = "BHAM — Barrier Health & Alarm Manager"

from .config import (  # noqa: F401
    REPO_ROOT, DATA_SYN, DATA_REAL, MODELS_DIR, REPORTS_DIR,
    ALARM_PRIORITIES, PRIORITY_WEIGHT, PROTECTION_LAYERS, PROCESS_UNITS,
    ModuleConfig, MODULE_CONFIGS,
)
from .modules.alarm_analytics import AlarmAnalytics, AlarmMetrics, AlarmCluster  # noqa: F401
from .modules.barrier_health import (  # noqa: F401
    BarrierHealthMonitor, LayerHealth,
)
from .modules.sequence_prediction import SequencePredictor, SequencePrediction  # noqa: F401
from .modules.dynamic_risk import DynamicRiskEstimator, RiskEstimate  # noqa: F401
from .modules.tep_fault_detection import TEPFaultDetector, FaultDetectionResult  # noqa: F401
