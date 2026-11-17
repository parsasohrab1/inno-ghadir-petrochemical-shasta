"""تست‌های ماژول تحلیل آلارم (ماژول ۱)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from bham.modules.alarm_analytics import AlarmAnalytics, AlarmMetrics


@pytest.fixture
def sample_alarms():
    ts = pd.date_range("2024-03-20", periods=100, freq="min")
    return pd.DataFrame({
        "timestamp": ts,
        "tag": ["PT001_OLF"] * 50 + ["TT002_ARO"] * 30 + ["FT003_OLP"] * 20,
        "priority": ["High"] * 50 + ["Medium"] * 30 + ["Low"] * 20,
        "status": ["Active"] * 20 + ["Cleared"] * 80,
        "unit": ["OLF"] * 100,
        "value": np.random.default_rng(0).normal(50, 5, 100),
        "setpoint": [50.0] * 100,
        "ack_delay_sec": np.random.default_rng(0).integers(1, 60, 100),
        "clear_delay_sec": np.random.default_rng(0).integers(5, 300, 100),
        "operator": ["OP-A"] * 100,
    })


def test_metrics_basic(sample_alarms):
    m = AlarmAnalytics().metrics(sample_alarms)
    assert isinstance(m, AlarmMetrics)
    assert m.total_alarms == 100
    assert m.unique_tags == 3
    assert m.alarms_per_hour > 0
    assert 0 <= m.top_10_share_pct <= 100


def test_cluster_groups_chattering(sample_alarms):
    # تزریق چترینگ: ۱۰ آلارم با تگ یکسان در یک لحظه کاملاً مجزا از بقیه
    df = sample_alarms.copy()
    base_ts = pd.Timestamp("2024-04-01 12:00:00")  # خارج از بازه نمونه
    df.loc[0:9, "timestamp"] = [base_ts + pd.Timedelta(seconds=i) for i in range(10)]
    df.loc[0:9, "tag"] = "PT999_OLF"
    df.loc[0:9, "priority"] = "Critical"
    clusters = AlarmAnalytics(dbscan_eps_sec=60).cluster(df)
    assert len(clusters) >= 1
    # خوشه‌ای که شامل PT999_OLF است باید ریشه آن PT999_OLF باشد
    pt_clusters = [c for c in clusters if "PT999_OLF" in c.tags]
    assert len(pt_clusters) >= 1, "خوشه چترینگ PT999 پیدا نشد"
    root_cluster = max(pt_clusters, key=lambda c: c.n_alarms)
    assert root_cluster.n_alarms >= 5
    assert root_cluster.likely_root_tag == "PT999_OLF"
    assert root_cluster.priority_score > 0


def test_anomaly_detection(sample_alarms):
    m = AlarmAnalytics()
    m.fit(sample_alarms)
    out = m.detect_anomalies(sample_alarms)
    assert "anomaly" in out.columns
    assert "anomaly_score" in out.columns
    assert len(out) == len(sample_alarms)
    assert set(out["anomaly"].unique()) <= {0, 1}


def test_threshold_recommendations(sample_alarms):
    recs = AlarmAnalytics().recommend_thresholds(sample_alarms)
    assert isinstance(recs, list)
    assert all("tag" in r and "suggested_high" in r for r in recs)


def test_not_fitted_raises():
    m = AlarmAnalytics()
    with pytest.raises(RuntimeError):
        m.detect_anomalies(pd.DataFrame({"timestamp": [], "tag": [], "priority": []}))


def test_empty_metrics():
    df = pd.DataFrame({
        "timestamp": pd.to_datetime([]),
        "tag": pd.Series([], dtype=object),
        "priority": pd.Series([], dtype=object),
        "status": pd.Series([], dtype=object),
        "value": pd.Series([], dtype=float),
        "setpoint": pd.Series([], dtype=float),
        "ack_delay_sec": pd.Series([], dtype=float),
        "clear_delay_sec": pd.Series([], dtype=float),
    })
    m = AlarmAnalytics().metrics(df)
    assert m.total_alarms == 0
    assert m.unique_tags == 0
