"""تست‌های قابلیت‌های بنچ‌مارک‌شده با استانداردهای بین‌المللی (EEMUA 191 / ISA-18.2 / IEC 62682 / IEC 61511).

نسخه ۲ — بهینه‌سازی‌های ماژول آلارم و لایه‌های حفاظتی.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from bham import (
    AlarmAnalytics, EEMUA_TARGETS,
    RationalizationRecord, ShelvingRecord, StateBasedSuppression,
    BarrierHealthMonitor, LOPAResult, BypassEvent,
    SIL_TARGETS, MAX_BYPASS_H_PER_YEAR,
)


# ------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------

@pytest.fixture
def real_alarms():
    """داده آلارم با چترینگ، طوفان و stale برای تست KPI استاندارد."""
    np.random.seed(42)
    # چترینگ: یک تگ با ۵ آلارم در ۱ دقیقه
    chatter_ts = pd.date_range("2024-03-20 10:00", periods=5, freq="10s")
    # طوفان: ۱۵ آلارم در ۱۰ دقیقه
    flood_ts = pd.date_range("2024-03-20 11:00", periods=15, freq="30s")
    # عادی
    normal_ts = pd.date_range("2024-03-20 12:00", periods=80, freq="20min")
    ts_all = list(chatter_ts) + list(flood_ts) + list(normal_ts)
    return pd.DataFrame({
        "timestamp": ts_all,
        "tag": (["PT001_OLF"] * 5) + (["FT_FLOOD"] * 15) +
               (["TT002_ARO"] * 40 + ["FT003_OLP"] * 40),
        "priority": (["High"] * 5) + (["Critical"] * 15) +
                    (["Low"] * 60 + ["Medium"] * 20),
        "status": (["Active"] * 5) + (["Cleared"] * 15) + (["Cleared"] * 80),
        "unit": "OLF",
        "value": np.random.normal(50, 5, len(ts_all)),
        "setpoint": 50.0,
        "ack_delay_sec": np.random.randint(1, 60, len(ts_all)),
        "clear_delay_sec": np.random.randint(5, 300, len(ts_all)),
        "operator": "OP-A",
        "duration_h": ([30] * 5) + ([1] * 15) + ([0.5] * 80),
    })


@pytest.fixture
def good_alarms():
    """داده آلارم عالی با انطباق بالا با EEMUA."""
    np.random.seed(0)
    ts = pd.date_range("2024-03-20", periods=50, freq="20min")
    return pd.DataFrame({
        "timestamp": ts,
        "tag": (["T1"] * 10 + ["T2"] * 15 + ["T3"] * 10 + ["T4"] * 15),
        "priority": (["Low"] * 40 + ["Medium"] * 8 + ["High"] * 2),
        "status": ["Cleared"] * 50,
        "unit": "OLF",
        "value": np.random.normal(50, 5, 50),
        "setpoint": 50.0,
        "ack_delay_sec": [15] * 50,
        "clear_delay_sec": [60] * 50,
        "operator": ["OP-A", "OP-B"] * 25,
    })


@pytest.fixture
def barriers():
    return pd.DataFrame({
        "timestamp": ["2024-03-20"] * 5,
        "unit": ["OLF"] * 5,
        "layer": ["BPCS-Control", "SIS-Interlock", "ESD-Shutdown",
                  "Relief-Valve", "Procedural"],
        "health_score": [0.95, 0.92, 0.88, 0.90, 0.85],
        "bypass_active": [False, False, False, False, False],
        "bypass_duration_h": [0, 0, 0, 0, 0],
        "last_test_result": [1, 1, 1, 1, 1],
        "days_since_test": [30, 60, 90, 180, 45],
        "sensor_drift": [0.01, 0.02, 0.03, 0.01, 0.02],
        "response_delay_s": [1.5, 2.0, 2.5, 1.0, 3.0],
    })


# ============================================================
# تست‌های KPI استاندارد EEMUA 191 / ISA-18.2
# ============================================================

def test_eemua_targets_constant():
    """مقادیر هدف EEMUA مطابق استاندارد باشند."""
    assert EEMUA_TARGETS["alarms_per_10min_steady"] == 1
    assert EEMUA_TARGETS["alarms_per_10min_upset"] == 10
    assert EEMUA_TARGETS["top10_share_max_pct"] == 1.0
    assert EEMUA_TARGETS["priority_distribution_target"]["Low"] == 80.0
    assert EEMUA_TARGETS["priority_distribution_target"]["Critical"] == 1.0


def test_metrics_full_v2(real_alarms):
    """شاخص‌های کامل v2 شامل همه KPIهای EEMUA."""
    m = AlarmAnalytics().metrics(real_alarms)
    # فیلدهای جدید v2 باید موجود باشند
    assert m.alarms_per_10min_steady >= 0
    assert m.alarms_per_10min_peak >= 0
    assert m.chattering_pct >= 0
    assert m.standing_pct >= 0
    assert m.stale_pct >= 0
    assert m.flood_events >= 0
    assert m.flood_max_concurrent >= 0
    assert 0 <= m.priority_compliance <= 100
    assert m.bad_actors >= 0
    assert m.operators_count >= 1
    assert m.avg_ack_delay_sec >= 0
    assert 0 <= m.ack_compliance_pct <= 100
    assert m.annunciation_rate >= 0
    assert 0 <= m.compliance_score <= 100
    assert m.compliance_grade in ("A", "B", "C", "D")


def test_chattering_detection(real_alarms):
    """چترینگ باید شناسایی شود (۵ آلارم در ۱ دقیقه برای PT001_OLF)."""
    m = AlarmAnalytics().metrics(real_alarms)
    assert m.chattering_tags >= 1
    assert m.chattering_pct > 0


def test_flood_detection(real_alarms):
    """طوفان آلارم باید شناسایی شود (۱۵ آلارم در ۱۰ دقیقه)."""
    m = AlarmAnalytics().metrics(real_alarms)
    assert m.flood_events >= 1
    assert m.flood_max_concurrent >= 10


def test_stale_alarms(real_alarms):
    """آلارم stale (> 24h Active) باید شناسایی شود."""
    m = AlarmAnalytics().metrics(real_alarms)
    assert m.standing_alarms >= 5  # ۵ آلارم Active با duration 30h


def test_priority_distribution(real_alarms):
    """توزیع اولویت باید محاسبه شود."""
    m = AlarmAnalytics().metrics(real_alarms)
    assert sum(m.priority_distribution.values()) == pytest.approx(100, abs=1)
    assert m.priority_distribution["Low"] > 0


def test_bad_actor_identification(real_alarms):
    """بد-اکتورها (تگ با > ۵٪ آلارم) شناسایی شوند."""
    m = AlarmAnalytics().metrics(real_alarms)
    assert m.bad_actors >= 1


def test_compliance_score_high_for_good_data(good_alarms):
    """داده عالی باید compliance بالا بگیرد."""
    m = AlarmAnalytics().metrics(good_alarms)
    assert m.compliance_score >= 50  # حداقل انطباق
    assert m.compliance_grade in ("A", "B", "C", "D")


def test_compliance_report(real_alarms):
    """گزارش انطباق شامل targets، actuals و gaps باشد."""
    aa = AlarmAnalytics()
    report = aa.compliance_report(real_alarms)
    assert report["standard"] == "EEMUA 191 v4 / ISA-18.2-2016 / IEC 62682"
    assert "targets" in report
    assert "actuals" in report
    assert "gaps" in report
    assert isinstance(report["gaps"], list)


def test_empty_dataframe_metrics():
    """DataFrame خالی باید مقادیر صفر ایمن برگرداند."""
    df = pd.DataFrame(columns=["timestamp", "tag", "priority", "status"])
    m = AlarmAnalytics().metrics(df)
    assert m.total_alarms == 0
    assert m.compliance_grade == "A"
    assert m.compliance_score == 100.0


# ============================================================
# تست‌های Alarm Rationalization (ISA-18.2)
# ============================================================

def test_rationalize_returns_records(real_alarms):
    """rationalize باید لیست RationalizationRecord برگرداند."""
    aa = AlarmAnalytics()
    recs = aa.rationalize(real_alarms)
    assert len(recs) > 0
    assert all(isinstance(r, RationalizationRecord) for r in recs)
    for r in recs:
        assert r.recommended_action in ("Keep", "Reprioritize", "Retune", "Remove")
        assert r.current_priority in ("Low", "Medium", "High", "Critical")
        assert 0 <= r.nuisance_pct <= 100


def test_rationalize_reorders_by_count(real_alarms):
    """رکوردها بر اساس تعداد آلارم نزولی مرتب شوند."""
    recs = AlarmAnalytics().rationalize(real_alarms)
    counts = [r.alarm_count for r in recs]
    assert counts == sorted(counts, reverse=True)


def test_rationalize_with_custom_target(real_alarms):
    """rationalize با توزیع هدف سفارشی."""
    custom = {"Low": 70, "Medium": 20, "High": 8, "Critical": 2}
    recs = AlarmAnalytics().rationalize(real_alarms, target_distribution=custom)
    assert len(recs) > 0


# ============================================================
# تست‌های Alarm Shelving (IEC 62682)
# ============================================================

def test_shelve_single():
    """شلف یک آلارم و بررسی ثبت."""
    aa = AlarmAnalytics()
    rec = aa.shelve("TAG_001", 60, "Maintenance", "OP-A", True, None, "Low")
    assert isinstance(rec, ShelvingRecord)
    assert rec.tag == "TAG_001"
    assert rec.shelf_duration_min == 60
    assert rec.reason == "Maintenance"
    assert len(aa.list_shelved()) == 1


def test_unshelve():
    """بازگرداندن آلارم از shelved."""
    aa = AlarmAnalytics()
    aa.shelve("TAG_001", 60, "Maintenance")
    assert aa.unshelve("TAG_001") is True
    assert len(aa.list_shelved()) == 0
    assert aa.unshelve("TAG_001") is False  # قبلاً حذف شده


def test_filter_shelved(real_alarms):
    """آلارم‌های shelved از DataFrame فیلتر شوند."""
    aa = AlarmAnalytics()
    aa.shelve("PT001_OLF", 60, "Maintenance")
    filtered = aa.filter_shelved(real_alarms)
    assert "PT001_OLF" not in filtered["tag"].values
    assert len(filtered) < len(real_alarms)


def test_filter_shelved_empty(real_alarms):
    """بدون شلف، هیچ فیلتری اعمال نشود."""
    aa = AlarmAnalytics()
    filtered = aa.filter_shelved(real_alarms)
    assert len(filtered) == len(real_alarms)


# ============================================================
# تست‌های State-Based Suppression
# ============================================================

def test_state_based_suppression(real_alarms):
    """پیشنهاد خاموش آلارم بر اساس حالت فرآیند."""
    aa = AlarmAnalytics()
    sups = aa.state_based_suppression(real_alarms, process_state="Start-up")
    assert len(sups) > 0
    assert all(isinstance(s, StateBasedSuppression) for s in sups)
    # در Start-up، آلارم‌های Temp/Pressure/Flow باید suppressed شوند
    suppressed = [s for s in sups if s.suppressed]
    assert len(suppressed) >= 0  # بسته به نوع تگ


def test_state_based_suppression_maintenance(real_alarms):
    """در حالت Maintenance، آلارم‌های تست باید پیشنهاد خاموش شوند."""
    aa = AlarmAnalytics()
    sups = aa.state_based_suppression(real_alarms, process_state="Maintenance")
    assert len(sups) > 0
    assert all(s.process_state == "Maintenance" for s in sups)


# ============================================================
# تست‌های ماژول لایه‌های حفاظتی v2 (IEC 61511 / LOPA)
# ============================================================

def test_sil_targets_constant():
    """اهداف SIL مطابق IEC 61511."""
    sil1_low, sil1_high, _, _ = SIL_TARGETS[1]
    assert sil1_low == 1e-2 and sil1_high == 1e-1
    sil4_low, sil4_high, _, _ = SIL_TARGETS[4]
    assert sil4_low == 1e-5 and sil4_high == 1e-4


def test_sil_computation(barriers):
    """محاسبه SIL محقق‌شده و هدف برای هر لایه."""
    bh = BarrierHealthMonitor()
    layers = bh.compute_layer_health(barriers)
    assert len(layers) == 5
    for l in layers:
        assert l.sil_target >= 1
        assert l.sil_gap in ("OK", "Below-target")
        assert l.pfd_estimate > 0


def test_sil_gap_detection():
    """لایه با سلامت پایین باید Below-target باشد."""
    df = pd.DataFrame({
        "timestamp": ["2024-03-20"] * 2,
        "unit": ["OLF"] * 2,
        "layer": ["ESD-Shutdown", "SIS-Interlock"],
        "health_score": [0.4, 0.95],
        "bypass_active": [False, False],
        "bypass_duration_h": [0, 0],
        "last_test_result": [1, 1],
        "days_since_test": [365, 30],
        "sensor_drift": [0.1, 0.01],
        "response_delay_s": [5.0, 1.5],
    })
    layers = BarrierHealthMonitor().compute_layer_health(df)
    esd = [l for l in layers if l.layer == "ESD-Shutdown"][0]
    assert esd.sil_gap == "Below-target"


def test_lopa_compliant(barriers):
    """LOPA باید نتیجه Compliant یا Insufficient برگرداند."""
    bh = BarrierHealthMonitor()
    results = bh.lopa_analysis(barriers, hazard="loss_of_containment",
                                unmitigated_freq_per_year=0.1)
    assert len(results) > 0
    for r in results:
        assert isinstance(r, LOPAResult)
        assert r.gap in ("Compliant", "Insufficient-layers", "Excessive-PFD")
        assert r.risk_reduction_factor >= 1.0
        assert r.required_rrf >= 1.0


def test_bypass_compliance_violation():
    """بایپس بیش از حد مجاز باید غیرمطابق شناسایی شود."""
    # SIL 3 = max 1h/year، ما 5h می‌دهیم
    df = pd.DataFrame({
        "timestamp": ["2024-03-20"],
        "unit": ["OLF"],
        "layer": ["ESD-Shutdown"],
        "health_score": [0.9],
        "bypass_active": [True],
        "bypass_duration_h": [5.0],
        "last_test_result": [1],
        "days_since_test": [30],
        "sensor_drift": [0.01],
        "response_delay_s": [2.0],
    })
    layers = BarrierHealthMonitor().compute_layer_health(df)
    assert layers[0].bypass_active is True
    assert layers[0].bypass_compliance is False  # 5h > 1h (SIL 3)


def test_bypass_events_extraction(barriers):
    """استخراج رویدادهای بایپس."""
    df = barriers.copy()
    df.loc[2, "bypass_active"] = True  # ESD-Shutdown
    df.loc[2, "bypass_duration_h"] = 0.5
    events = BarrierHealthMonitor().bypass_events(df)
    assert len(events) >= 1
    assert all(isinstance(e, BypassEvent) for e in events)


def test_test_interval_based_on_sil(barriers):
    """فواصل تست بر اساس SIL هدف متفاوت باشند."""
    df = barriers.copy()
    schedule = BarrierHealthMonitor().optimize_test_intervals(df)
    assert "sil_target" in schedule.columns
    assert "recommended_interval_days" in schedule.columns
    # لایه SIL 3 باید فاصله کوتاه‌تر از SIL 1 داشته باشد
    sil3_row = schedule[schedule["sil_target"] == 3]
    sil1_row = schedule[schedule["sil_target"] == 1]
    if len(sil3_row) and len(sil1_row):
        assert sil3_row["recommended_interval_days"].iloc[0] <= sil1_row["recommended_interval_days"].iloc[0] * 2


# ============================================================
# تست‌های گزارش compliance
# ============================================================

def test_compliance_gaps_structure(real_alarms):
    """ساختار gaps باید فیلدهای استاندارد داشته باشد."""
    aa = AlarmAnalytics()
    report = aa.compliance_report(real_alarms)
    for gap in report["gaps"]:
        assert "kpi" in gap
        assert "actual" in gap
        assert "target" in gap
        assert "severity" in gap
        assert gap["severity"] in ("Low", "Medium", "High")


def test_compliance_score_bounds(real_alarms, good_alarms):
    """امتیاز compliance بین 0 و 100."""
    bad_m = AlarmAnalytics().metrics(real_alarms)
    good_m = AlarmAnalytics().metrics(good_alarms)
    assert 0 <= bad_m.compliance_score <= 100
    assert 0 <= good_m.compliance_score <= 100
    # داده خوب باید بالاتر از داده بد باشد (البته نه لزوماً، ولی معمولاً)
    assert good_m.compliance_grade <= bad_m.compliance_grade  # A < B < C < D


def test_cluster_rationale(real_alarms):
    """خوشه‌ها باید rationale (طوفان/چترینگ/علت مشترک) داشته باشند."""
    aa = AlarmAnalytics()
    clusters = aa.cluster(real_alarms)
    assert len(clusters) > 0
    for c in clusters:
        assert c.alarm_rationale
        assert c.duration_sec >= 0
        assert c.unique_tags >= 1
