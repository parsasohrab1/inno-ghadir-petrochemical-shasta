"""تست‌های ماژول پایش سلامت لایه‌های حفاظتی (ماژول ۲)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from bham.modules.barrier_health import BarrierHealthMonitor, LayerHealth, _risk_label


@pytest.fixture
def sample_barriers():
    ts = pd.date_range("2024-03-20", periods=24, freq="h")
    rows = []
    for unit in ["Olefins-Unit", "Aromatics-Unit"]:
        for layer in ["BPCS-Control", "SIS-Interlock", "ESD-Shutdown", "Relief-Valve", "Procedural"]:
            for t in ts[:2]:
                rows.append({
                    "timestamp": t,
                    "unit": unit,
                    "layer": layer,
                    "health_score": 0.85,
                    "bypass_active": False,
                    "bypass_duration_h": 0.0,
                    "last_test_result": 1,
                    "days_since_test": 30,
                    "sensor_drift": 0.01,
                    "response_delay_s": 2.0,
                })
    return pd.DataFrame(rows)


def test_compute_layer_health_returns_layer_objects(sample_barriers):
    m = BarrierHealthMonitor()
    rows = m.compute_layer_health(sample_barriers)
    assert len(rows) == 10  # 2 units × 5 layers
    assert all(isinstance(r, LayerHealth) for r in rows)
    for r in rows:
        assert 0 <= r.health_score <= 1
        assert r.risk_level in ("Low", "Medium", "High", "Critical")


def test_bypass_reduces_health():
    df = pd.DataFrame([{
        "timestamp": pd.Timestamp("2024-03-20"),
        "unit": "U", "layer": "SIS-Interlock",
        "health_score": 0.9, "bypass_active": False,
        "last_test_result": 1, "days_since_test": 10,
        "sensor_drift": 0.0, "response_delay_s": 1.0,
    }])
    df_bp = df.copy()
    df_bp["bypass_active"] = True
    h1 = BarrierHealthMonitor().compute_layer_health(df)[0].health_score
    h2 = BarrierHealthMonitor().compute_layer_health(df_bp)[0].health_score
    assert h2 < h1, "بایپس باید سلامت را کاهش دهد"


def test_aggregate_unit_risk_in_range(sample_barriers):
    m = BarrierHealthMonitor()
    rows = m.compute_layer_health(sample_barriers)
    ur = m.aggregate_unit_risk(rows)
    assert len(ur) == 2
    assert all(0 <= v <= 1 for v in ur.values())


def test_simultaneous_weakness():
    ts = pd.Timestamp("2024-03-20")
    df = pd.DataFrame([
        {"timestamp": ts, "unit": "U", "layer": "BPCS-Control",
         "health_score": 0.4, "bypass_active": True, "last_test_result": 1,
         "days_since_test": 100, "sensor_drift": 0.05, "response_delay_s": 3.0},
        {"timestamp": ts, "unit": "U", "layer": "SIS-Interlock",
         "health_score": 0.3, "bypass_active": True, "last_test_result": 0,
         "days_since_test": 400, "sensor_drift": 0.08, "response_delay_s": 5.0},
        {"timestamp": ts, "unit": "U", "layer": "ESD-Shutdown",
         "health_score": 0.9, "bypass_active": False, "last_test_result": 1,
         "days_since_test": 30, "sensor_drift": 0.0, "response_delay_s": 1.0},
    ])
    weak = BarrierHealthMonitor(simultaneous_bypass_threshold=2).detect_simultaneous_weakness(df)
    assert len(weak) >= 1
    assert weak[0]["weak_count"] >= 2


def test_optimize_test_intervals_returns_df(sample_barriers):
    df = pd.concat([sample_barriers] * 3, ignore_index=True)
    sched = BarrierHealthMonitor().optimize_test_intervals(df)
    assert isinstance(sched, pd.DataFrame)
    assert "recommended_interval_days" in sched.columns
    assert "priority" in sched.columns
    assert len(sched) > 0


def test_risk_label_thresholds():
    assert _risk_label(0.95) == "Low"
    assert _risk_label(0.70) == "Medium"
    assert _risk_label(0.50) == "High"
    assert _risk_label(0.20) == "Critical"


def test_recommendation_text():
    df = pd.DataFrame([{
        "timestamp": pd.Timestamp("2024-03-20"),
        "unit": "U", "layer": "SIS-Interlock",
        "health_score": 0.9, "bypass_active": True,
        "last_test_result": 1, "days_since_test": 10,
        "sensor_drift": 0.0, "response_delay_s": 1.0,
    }])
    rows = BarrierHealthMonitor().compute_layer_health(df)
    assert "بایپس" in rows[0].recommendation
