"""تست‌های ماژول پیش‌بینی توالی (ماژول ۳)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from bham.modules.sequence_prediction import SequencePredictor, SequencePrediction


@pytest.fixture
def sample_sequences():
    rng = np.random.default_rng(0)
    events = ["Temp-High", "Pressure-Low", "Level-High", "Flow-Low",
              "Vibration-High", "Composition-Off", "Bypass-On", "Alarm-Storm"]
    rows = []
    for i in range(200):
        seq_len = rng.integers(4, 10)
        seq = rng.choice(events, size=seq_len)
        seq_str = "|".join(seq)
        is_shutdown = int("Bypass-On" in seq_str and "Alarm-Storm" in seq_str and "Temp-High" in seq_str)
        rows.append({
            "sequence_id": f"S-{i:04d}",
            "events": seq_str,
            "length": seq_len,
            "unit": "Olefins-Unit",
            "shutdown_risk": is_shutdown,
            "lead_time_min": rng.integers(5, 60) if is_shutdown else 0,
        })
    return pd.DataFrame(rows)


def test_fit_returns_metrics(sample_sequences):
    m = SequencePredictor(n_estimators=50, max_depth=6)
    info = m.fit(sample_sequences)
    assert "train_size" in info
    assert "test_size" in info
    assert "roc_auc" in info
    assert 0 <= info["roc_auc"] <= 1
    assert info["train_size"] + info["test_size"] == len(sample_sequences)


def test_predict_returns_predictions(sample_sequences):
    m = SequencePredictor(n_estimators=50, max_depth=6)
    m.fit(sample_sequences)
    preds = m.predict(sample_sequences.sample(50))
    assert all(isinstance(p, SequencePrediction) for p in preds)
    assert len(preds) == 50
    for p in preds:
        assert 0 <= p.shutdown_probability <= 1
        assert p.risk_level in ("Low", "Medium", "High", "Critical")
        assert isinstance(p.predicted_next_event, str)


def test_dangerous_pattern_detected(sample_sequences):
    """توالی خطرناک باید احتمال توقف بالاتر از توالی عادی داشته باشد."""
    m = SequencePredictor(n_estimators=50, max_depth=6)
    m.fit(sample_sequences)
    dangerous = pd.DataFrame([{
        "sequence_id": "D1",
        "events": "Bypass-On|Alarm-Storm|Temp-High|Vibration-High",
        "length": 4, "unit": "U", "shutdown_risk": 1, "lead_time_min": 10,
    }])
    safe = pd.DataFrame([{
        "sequence_id": "S1",
        "events": "Flow-Low|Level-High",
        "length": 2, "unit": "U", "shutdown_risk": 0, "lead_time_min": 0,
    }])
    d_pred = m.predict(dangerous)[0]
    s_pred = m.predict(safe)[0]
    assert d_pred.shutdown_probability > s_pred.shutdown_probability


def test_feature_importances(sample_sequences):
    m = SequencePredictor(n_estimators=50, max_depth=6)
    m.fit(sample_sequences)
    feats = m.feature_importances(top_k=5)
    assert len(feats) > 0
    assert all("feature" in f and "importance" in f for f in feats)


def test_predict_before_fit_raises():
    m = SequencePredictor()
    with pytest.raises(RuntimeError):
        m.predict(pd.DataFrame({"sequence_id": ["x"], "events": ["A|B"]}))


def test_picklable(sample_sequences):
    """مدل باید picklable باشد (برای joblib)."""
    import pickle
    m = SequencePredictor(n_estimators=20, max_depth=4)
    m.fit(sample_sequences)
    blob = pickle.dumps(m)
    m2 = pickle.loads(blob)
    preds = m2.predict(sample_sequences.sample(5))
    assert len(preds) == 5
