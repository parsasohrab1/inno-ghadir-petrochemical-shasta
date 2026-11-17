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
        algorithm="DBSCAN clustering + Isolation Forest + TF-IDF + EEMUA 191/ISA-18.2 KPIs + Rationalization + Shelving",
        version="2.0.0",
        params={"dbscan_eps_sec": 30, "chatter_threshold": 5, "isolation_contamination": 0.05},
    ),
    "barrier_health": ModuleConfig(
        name="Barrier Health & Bypass Management",
        algorithm="Weighted aggregation + Exponential decay + PFD/SIL (IEC 61511) + LOPA",
        version="2.0.0",
        params={"decay_lambda": 0.0008, "bypass_penalty": 0.15, "min_health": 0.4},
    ),
    "sequence_prediction": ModuleConfig(
        name="Sequence Prediction (Shutdown/Unsafe) — Multi-horizon",
        algorithm="Random Forest + Markov chain + 1h/24h/72h horizon forecasting",
        version="2.0.0",
        params={"n_estimators": 200, "max_depth": 12, "markov_order": 2},
    ),
    "dynamic_risk": ModuleConfig(
        name="Dynamic Risk Estimation & Test Optimization",
        algorithm="XGBoost survival + Weibull AFT + Poisson process",
        version="2.0.0",
        params={"n_estimators": 300, "max_depth": 6, "learning_rate": 0.05},
    ),
    "quality_optimizer": ModuleConfig(
        name="Product Quality Monitoring & Optimization",
        algorithm="SPC (Western Electric) + Cp/Cpk (ISO 22514-2) + CUSUM + EWMA + Ishikawa RCA",
        version="2.1.0",
        params={"control_limit_sigma": 3.0, "ewma_lambda": 0.2, "cusum_threshold": 5.0},
    ),
    "production_optimizer": ModuleConfig(
        name="Production Line Optimization (OEE/Yield/Bottleneck)",
        algorithm="OEE (Nakajima) + Theory of Constraints + Yield analysis + Cost-Benefit ROI",
        version="2.1.0",
        params={"ideal_cycle_time_min": 5.0, "target_yield_pct": 95.0, "product_value_usd_per_ton": 800.0},
    ),
}
