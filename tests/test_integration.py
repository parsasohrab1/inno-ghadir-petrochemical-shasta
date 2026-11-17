"""تست‌های یکپارچگی: خط لوله end-to-end و پیکربندی."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import bham
from bham import (
    AlarmAnalytics, BarrierHealthMonitor, SequencePredictor,
    DynamicRiskEstimator, TEPFaultDetector,
    DATA_SYN, DATA_REAL, MODULE_CONFIGS, PROTECTION_LAYERS,
)


def test_package_version():
    assert bham.__version__ == "1.0.0"
    assert "BHAM" in bham.__product__


def test_module_configs_present():
    assert set(MODULE_CONFIGS.keys()) == {
        "alarm_analytics", "barrier_health",
        "sequence_prediction", "dynamic_risk"
    }
    for cfg in MODULE_CONFIGS.values():
        assert cfg.algorithm
        assert cfg.version


def test_protection_layers_complete():
    expected = {"BPCS-Control", "SIS-Interlock", "ESD-Shutdown", "Relief-Valve", "Procedural"}
    assert set(PROTECTION_LAYERS) == expected


def test_data_directories_exist():
    assert DATA_SYN.exists(), "synthetic data directory missing"
    assert DATA_REAL.exists(), "real data directory exists (even if empty)"


@pytest.mark.skipif(not (DATA_SYN / "alarms.csv").exists(),
                    reason="synthetic data not generated")
def test_pipeline_end_to_end_synthetic():
    """اجرای تمام ماژول‌ها روی داده مصنوعی در یک خط لوله."""
    # ماژول ۱: آلارم
    alarms = pd.read_csv(DATA_SYN / "alarms.csv", parse_dates=["timestamp"]).head(2000)
    m1 = AlarmAnalytics()
    metrics = m1.metrics(alarms)
    assert metrics.total_alarms > 0

    # ماژول ۲: لایه‌های حفاظتی
    barriers = pd.read_csv(DATA_SYN / "barriers.csv", parse_dates=["timestamp"]).head(5000)
    m2 = BarrierHealthMonitor()
    layers = m2.compute_layer_health(barriers)
    assert len(layers) > 0

    # ماژول ۳: توالی
    seqs = pd.read_csv(DATA_SYN / "sequences.csv").head(200)
    m3 = SequencePredictor(n_estimators=30, max_depth=4)
    info = m3.fit(seqs)
    assert info["train_size"] > 0
    preds = m3.predict(seqs.head(20))
    assert len(preds) == 20

    # ماژول ۴: ریسک پویا
    risk = pd.read_csv(DATA_SYN / "risk_signals.csv", parse_dates=["timestamp"]).head(500)
    m4 = DynamicRiskEstimator(n_estimators=30, max_depth=3)
    m4.fit(risk)
    rpreds = m4.predict(risk.head(20))
    assert len(rpreds) == 20


@pytest.mark.skipif(not (DATA_REAL / "tep_train.csv").exists(),
                    reason="TEP real data not available")
def test_pipeline_end_to_end_real():
    """خط لوله روی داده واقعی TEP."""
    import numpy as np
    df_tr = pd.read_csv(DATA_REAL / "tep_train.csv")
    feat_cols = [c for c in df_tr.columns if c.startswith(("xmeas_", "xmv_"))]
    X = df_tr[feat_cols].to_numpy()[:2000]
    y = df_tr["fault_id"].to_numpy()[:2000]
    m = TEPFaultDetector(n_components=10)
    info = m.fit(X, y)
    assert info["train_size"] > 0
    res = m.detect(X[:10])
    assert len(res) == 10


def test_all_modules_picklable():
    """تمام مدل‌ها باید picklable باشند برای ذخیره/بارگذاری."""
    import pickle
    for m in [AlarmAnalytics(), BarrierHealthMonitor(),
              SequencePredictor(n_estimators=5),
              DynamicRiskEstimator(n_estimators=5),
              TEPFaultDetector(n_components=3)]:
        blob = pickle.dumps(m)
        assert len(blob) > 0
