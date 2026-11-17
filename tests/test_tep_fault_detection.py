"""تست‌های ماژول تشخیص خطای TEP (ماژول ۵ - داده واقعی)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from bham.modules.tep_fault_detection import TEPFaultDetector, FaultDetectionResult
from bham import DATA_REAL


def _make_synthetic_tep(n_per_fault: int = 30, n_faults: int = 4, n_features: int = 10, seed: int = 0):
    rng = np.random.default_rng(seed)
    X, y = [], []
    for fid in range(n_faults):
        mu = np.ones(n_features) * (50 + fid * 5)
        sigma = 2 + fid * 0.5
        X.append(rng.normal(mu, sigma, size=(n_per_fault, n_features)))
        y.append(np.full(n_per_fault, fid))
    X = np.vstack(X)
    y = np.concatenate(y)
    return X, y


def test_fit_returns_metrics():
    X, y = _make_synthetic_tep()
    m = TEPFaultDetector(n_components=5)
    info = m.fit(X, y)
    assert info["train_size"] + info["test_size"] == len(X)
    assert "t2_threshold" in info
    assert "spe_threshold" in info
    assert len(info["explained_variance_ratio"]) == 5


def test_detect_returns_results():
    X, y = _make_synthetic_tep()
    m = TEPFaultDetector(n_components=5)
    m.fit(X, y)
    res = m.detect(X[:10])
    assert all(isinstance(r, FaultDetectionResult) for r in res)
    assert len(res) == 10
    for r in res:
        assert 0 <= r.confidence <= 1
        assert isinstance(r.is_anomaly, bool)
        assert r.t2_statistic >= 0
        assert r.spe_statistic >= 0


def test_anomaly_high_for_off_distribution():
    X, y = _make_synthetic_tep(n_per_fault=40, n_faults=3, n_features=8)
    m = TEPFaultDetector(n_components=4)
    m.fit(X, y)
    # داده فرضی خارج از توزیع
    outlier = np.random.default_rng(99).normal(500, 1, size=(3, 8))
    res = m.detect(outlier)
    n_anom = sum(1 for r in res if r.is_anomaly)
    assert n_anom >= 1, "داده خارج از توزیع باید ناهنجار تشخیص داده شود"


def test_fault_detection_rate():
    X, y = _make_synthetic_tep(n_per_fault=80, n_faults=4, n_features=12)
    # داده آزمون شبیه TEP: 160 نمونه نرمال سپس خطا
    rng = np.random.default_rng(1)
    X_te = np.vstack([X[rng.choice(len(X), 160)], X[rng.choice(len(X), 80)]])
    y_te = np.concatenate([np.zeros(160), np.ones(80)])
    m = TEPFaultDetector(n_components=5)
    m.fit(X, y)
    fdr = m.fault_detection_rate(X_te, y_te, warmup=160)
    assert "FDR_per_fault" in fdr
    assert "FAR_normal" in fdr
    assert 0 <= fdr["FAR_normal"] <= 1


def test_not_fitted_raises():
    m = TEPFaultDetector()
    with pytest.raises(RuntimeError):
        m.detect(np.zeros((5, 10)))


@pytest.mark.skipif(not (DATA_REAL / "tep_train.csv").exists(),
                    reason="TEP real data not downloaded")
def test_real_tep_pipeline_runs():
    """اگر داده واقعی TEP موجود است، خط لوله کامل اجرا شود."""
    df = pd.read_csv(DATA_REAL / "tep_train.csv")
    feat_cols = [c for c in df.columns if c.startswith(("xmeas_", "xmv_"))]
    X = df[feat_cols].to_numpy()[:2000]
    y = df["fault_id"].to_numpy()[:2000]
    m = TEPFaultDetector(n_components=10)
    info = m.fit(X, y)
    assert info["train_size"] > 0
    assert info["test_size"] > 0
    res = m.detect(X[:20])
    assert len(res) == 20


def test_picklable():
    X, y = _make_synthetic_tep()
    m = TEPFaultDetector(n_components=4)
    m.fit(X, y)
    import pickle
    blob = pickle.dumps(m)
    m2 = pickle.loads(blob)
    res = m2.detect(X[:5])
    assert len(res) == 5
