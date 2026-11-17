"""پیکربندی مرکزی سامانه هوشمند مدیریت آلارم و پایش سلامت لایه‌های حفاظتی (BHAM)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# مسیرها
DATA_SYN = REPO_ROOT / "data" / "synthetic"
DATA_REAL = REPO_ROOT / "data" / "real" / "processed"
MODELS_DIR = REPO_ROOT / "models"
REPORTS_DIR = REPO_ROOT / "reports"
for d in (MODELS_DIR, REPORTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# اولویت‌ها
ALARM_PRIORITIES = ("Low", "Medium", "High", "Critical")
PRIORITY_WEIGHT = {"Low": 1.0, "Medium": 2.0, "High": 4.0, "Critical": 8.0}

# لایه‌های حفاظتی (IEC 61511 / IEC 61508)
PROTECTION_LAYERS = ("BPCS-Control", "SIS-Interlock", "ESD-Shutdown", "Relief-Valve", "Procedural")

# واحدهای فرآیندی نمونه پتروشیمی غدیر
PROCESS_UNITS = ("Olefins-Unit", "Aromatics-Unit", "Utility-Unit", "Storage-Tank-Farm", "Polymer-Unit")


@dataclass
class ModuleConfig:
    name: str
    algorithm: str
    version: str
    params: dict = field(default_factory=dict)


# الگوریتم‌های مشخص‌شده برای هر ماژول
MODULE_CONFIGS = {
    "alarm_analytics": ModuleConfig(
        name="Alarm Analytics & Prioritization",
        algorithm="DBSCAN clustering + Isolation Forest + TF-IDF on sequences",
        version="1.0.0",
        params={"dbscan_eps_sec": 30, "chatter_threshold": 5, "isolation_contamination": 0.05},
    ),
    "barrier_health": ModuleConfig(
        name="Barrier Health & Bypass Management",
        algorithm="Weighted aggregation + Exponential decay + HMM-like state model",
        version="1.0.0",
        params={"decay_lambda": 0.0008, "bypass_penalty": 0.15, "min_health": 0.4},
    ),
    "sequence_prediction": ModuleConfig(
        name="Sequence Prediction (Shutdown/Unsafe)",
        algorithm="Random Forest classifier + Markov chain for next-event",
        version="1.0.0",
        params={"n_estimators": 200, "max_depth": 12, "markov_order": 2},
    ),
    "dynamic_risk": ModuleConfig(
        name="Dynamic Risk Estimation & Test Optimization",
        algorithm="XGBoost survival + Weibull AFT + Poisson process",
        version="1.0.0",
        params={"n_estimators": 300, "max_depth": 6, "learning_rate": 0.05},
    ),
}
