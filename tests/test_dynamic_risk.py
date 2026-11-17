"""تست‌های ماژول ریسک پویا (ماژول ۴)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from bham.modules.dynamic_risk import DynamicRiskEstimator, RiskEstimate, _risk_level


@pytest.fixture
def sample_risk_signals():
    rng = np.random.default_rng(0)
    n = 500
    rows = []
    for i in range(n):
        temp = rng.normal(150, 10)
        press = rng.normal(35, 3)
        # خرابی وابسته به بار عملیاتی
        hazard = (temp - 150) / 30 + (35 - press) / 8
        fail_prob = 1 / (1 + np.exp(-(hazard - 1)))
        fail = int(rng.random() < fail_prob * 0.4)
        rows.append({
            "timestamp": pd.Timestamp("2024-03-20") + pd.Timedelta(hours=i),
            "unit": rng.choice(["Olefins-Unit", "Aromatics-Unit"]),
            "temperature_c": round(temp, 2),
            "pressure_bar": round(press, 2),
            "flow_kg_h": round(rng.normal(180, 12), 2),
            "vibration_mm_s": round(rng.normal(2.0, 0.5), 3),
            "operating_hours": int(rng.integers(0, 2000)),
            "failure": fail,
        })
    return pd.DataFrame(rows)


def test_fit_returns_metrics(sample_risk_signals):
    m = DynamicRiskEstimator(n_estimators=50, max_depth=4)
    info = m.fit(sample_risk_signals)
    assert "train_size" in info and "test_size" in info
    assert "roc_auc" in info
    assert info["train_size"] + info["test_size"] == len(sample_risk_signals)


def test_predict_returns_estimates(sample_risk_signals):
    m = DynamicRiskEstimator(n_estimators=50, max_depth=4)
    m.fit(sample_risk_signals)
    preds = m.predict(sample_risk_signals.head(100))
    assert all(isinstance(p, RiskEstimate) for p in preds)
    assert len(preds) == 100
    for p in preds:
        assert 0 <= p.failure_probability <= 1
        assert 0 <= p.risk_score <= 1
        assert p.risk_level in ("Low", "Medium", "High", "Critical")
        assert p.weibull_mtbf_h > 0


def test_optimize_test_schedule(sample_risk_signals):
    m = DynamicRiskEstimator(n_estimators=50, max_depth=4)
    m.fit(sample_risk_signals)
    sched = m.optimize_test_schedule(sample_risk_signals.head(100))
    assert isinstance(sched, pd.DataFrame)
    assert "recommended_interval_d" in sched.columns
    assert "priority" in sched.columns
    assert len(sched) == 100


def test_high_risk_score_increases_with_stress(sample_risk_signals):
    """نمونه پرخطر باید ریسک بالاتر داشته باشد."""
    m = DynamicRiskEstimator(n_estimators=50, max_depth=4)
    m.fit(sample_risk_signals)
    safe = pd.DataFrame([{
        "timestamp": pd.Timestamp("2024-03-20"), "unit": "U",
        "temperature_c": 150, "pressure_bar": 35, "flow_kg_h": 180,
        "vibration_mm_s": 2.0, "operating_hours": 100, "failure": 0,
    }])
    risky = pd.DataFrame([{
        "timestamp": pd.Timestamp("2024-03-20"), "unit": "U",
        "temperature_c": 200, "pressure_bar": 28, "flow_kg_h": 130,
        "vibration_mm_s": 5.5, "operating_hours": 1900, "failure": 1,
    }])
    s = m.predict(safe)[0]
    r = m.predict(risky)[0]
    assert r.risk_score >= s.risk_score


def test_feature_importances(sample_risk_signals):
    m = DynamicRiskEstimator(n_estimators=50, max_depth=4)
    m.fit(sample_risk_signals)
    feats = m.feature_importances(top_k=5)
    assert len(feats) > 0
    assert all("feature" in f and "importance" in f for f in feats)


def test_risk_level_thresholds():
    assert _risk_level(0.8) == "Critical"
    assert _risk_level(0.5) == "High"
    assert _risk_level(0.2) == "Medium"
    assert _risk_level(0.05) == "Low"


def test_not_fitted_raises():
    m = DynamicRiskEstimator()
    with pytest.raises(RuntimeError):
        m.predict(pd.DataFrame([{"temperature_c": 150, "pressure_bar": 35,
                                 "flow_kg_h": 180, "vibration_mm_s": 2.0,
                                 "operating_hours": 100}]))


def test_picklable(sample_risk_signals):
    import pickle
    m = DynamicRiskEstimator(n_estimators=20, max_depth=3)
    m.fit(sample_risk_signals)
    blob = pickle.dumps(m)
    m2 = pickle.loads(blob)
    preds = m2.predict(sample_risk_signals.head(5))
    assert len(preds) == 5
