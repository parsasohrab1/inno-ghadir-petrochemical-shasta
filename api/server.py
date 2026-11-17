"""سرور FastAPI برای سامانه BHAM.

تمام endpointهای REST API و بارگذاری مدل‌ها در startup.

اجرا:
    uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from bham import (
    AlarmAnalytics, BarrierHealthMonitor, SequencePredictor,
    DynamicRiskEstimator, TEPFaultDetector,
    QualityOptimizer, ProductionOptimizer, OEE_TARGETS,
    DATA_SYN, DATA_REAL, MODELS_DIR, REPORTS_DIR, __version__,
    EEMUA_TARGETS,
)
import joblib

app = FastAPI(
    title="BHAM API — سامانه هوشمند مدیریت آلارم و پایش سلامت لایه‌های حفاظتی",
    description="REST API برای هفت ماژول AI + تشخیص خطای TEP + بهینه‌سازی کیفیت و خط تولید",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------
# مدل‌های Pydantic برای ورودی
# ------------------------------------------------------------

class AlarmRow(BaseModel):
    timestamp: str
    tag: str
    priority: str
    status: str
    unit: str | None = None
    value: float = 0.0
    setpoint: float = 0.0
    ack_delay_sec: int = 0
    clear_delay_sec: int = 0
    operator: str | None = None


class AlarmAnalysisRequest(BaseModel):
    alarms: list[AlarmRow] = Field(..., min_length=1)


class BarrierRow(BaseModel):
    timestamp: str
    unit: str
    layer: str
    health_score: float
    bypass_active: bool = False
    bypass_duration_h: float = 0.0
    last_test_result: int = 1
    days_since_test: int = 0
    sensor_drift: float = 0.0
    response_delay_s: float = 2.0


class BarrierHealthRequest(BaseModel):
    barriers: list[BarrierRow] = Field(..., min_length=1)


class SequenceRow(BaseModel):
    sequence_id: str
    events: str  # جدا شده با |
    length: int = 0
    unit: str | None = None
    lead_time_min: int = 0


class SequencePredictRequest(BaseModel):
    sequences: list[SequenceRow] = Field(..., min_length=1)


class RiskSignalRow(BaseModel):
    timestamp: str
    unit: str
    temperature_c: float
    pressure_bar: float
    flow_kg_h: float
    vibration_mm_s: float
    operating_hours: int
    failure: int = 0


class RiskEstimateRequest(BaseModel):
    signals: list[RiskSignalRow] = Field(..., min_length=1)


class TEPDetectRequest(BaseModel):
    features: list[list[float]] = Field(..., min_length=1)


class RationalizeRequest(BaseModel):
    """درخواست Alarm Rationalization (ISA-18.2)."""
    alarms: list[AlarmRow] = Field(..., min_length=1)
    target_distribution: dict[str, float] | None = None


class ShelveRequest(BaseModel):
    """درخواست Alarm Shelving (IEC 62682)."""
    tag: str
    duration_min: int = Field(..., ge=1, le=14400)  # حداکثر ۱۰ روز
    reason: str
    shelved_by: str = "operator"
    auto_reshelf: bool = True
    expires_at: str | None = None
    safety_impact: str = "None"


class ShelveBatchRequest(BaseModel):
    """شلف کردن گروهی."""
    items: list[ShelveRequest] = Field(..., min_length=1)


class StateBasedRequest(BaseModel):
    """درخواست state-based suppression."""
    alarms: list[AlarmRow] = Field(..., min_length=1)
    process_state: str  # Start-up / Shutdown / Maintenance / Normal


class LOPARequest(BaseModel):
    """درخواست تحلیل LOPA."""
    barriers: list[BarrierRow] = Field(..., min_length=1)
    hazard: str = "loss_of_containment"
    unmitigated_freq_per_year: float = 0.1


# ------------------------------------------------------------
# مدل‌های Pydantic برای ماژول‌های جدید کیفیت و تولید (v2.1)
# ------------------------------------------------------------

class QualityRow(BaseModel):
    """یک ردیف داده کیفیت/فرآیند."""
    timestamp: str | None = None
    unit: str | None = None
    value: float
    variable: str | None = None  # نام متغیر (اگر چند متغیره)
    target: float | None = None
    usl: float | None = None
    lsl: float | None = None
    setpoint: float | None = None
    fault_id: int | None = None


class QualitySpec(BaseModel):
    """spec یک متغیر کیفی."""
    target: float
    usl: float
    lsl: float
    description: str = ""
    unit: str = ""
    impact: str = "Medium"


class QualityReportRequest(BaseModel):
    """درخواست گزارش کامل کیفیت محصول."""
    data: dict[str, list[float]] = Field(..., description="نام متغیر -> لیست مقادیر")
    specs: dict[str, QualitySpec] = Field(..., description="spec هر متغیر")
    fault_col: str | None = Field(None, description="نام ستون خطا (اختیاری)")


class QualityFaultImpactRequest(BaseModel):
    """درخواست تحلیل اثر خطا بر کیفیت."""
    values: list[float] = Field(..., min_length=2)
    fault_ids: list[int] = Field(..., min_length=2)
    fault_descriptions: dict[int, str] | None = None
    quality_variable_name: str = "xmeas_40"


class OEEInput(BaseModel):
    """ورودی محاسبه OEE."""
    unit: str
    planned_time_h: float = Field(..., gt=0)
    downtime_h: float = Field(..., ge=0)
    total_count: int = Field(..., gt=0)
    good_count: int = Field(..., ge=0)
    ideal_cycle_time_min: float = 5.0


class UnitProductionData(BaseModel):
    """داده تولید یک واحد برای bottleneck analysis."""
    unit: str
    equipment: str
    utilization_pct: float
    throughput_tph: float
    capacity_tph: float
    quality_pct: float = 99.0
    performance_pct: float = 95.0


class BottleneckRequest(BaseModel):
    """درخواست شناسایی bottleneck."""
    units: list[UnitProductionData] = Field(..., min_length=1)


class YieldInput(BaseModel):
    """ورودی تحلیل بازده."""
    unit: str
    feed_kg_h: float = Field(..., gt=0)
    product_kg_h: float = Field(..., gt=0)
    downtime_loss_kg_h: float = 0.0
    quality_loss_kg_h: float = 0.0
    energy_loss_kg_h: float = 0.0


class ProductionReportRequest(BaseModel):
    """درخواست گزارش جامع تولید."""
    oee_input: OEEInput
    units_data: list[UnitProductionData] = Field(default_factory=list)
    yields_data: list[YieldInput] = Field(default_factory=list)


class SPCRequest(BaseModel):
    """درخواست تحلیل SPC یک متغیر."""
    values: list[float] = Field(..., min_length=2)
    usl: float
    lsl: float
    target: float | None = None
    variable: str = "variable"


class SetpointOptimizeRequest(BaseModel):
    """درخواست بهینه‌سازی setpoint."""
    values: list[float] = Field(..., min_length=10)
    target: float
    usl: float
    lsl: float
    quality_col: str = "quality"
    manipulated_vars: list[str] | None = None


# ------------------------------------------------------------
# بارگذاری مدل‌ها در startup
# ------------------------------------------------------------

_state: dict[str, Any] = {}


@app.on_event("startup")
def load_models() -> None:
    """بارگذاری مدل‌های ذخیره‌شده؛ اگر موجود نبودند، نمونه جدید می‌سازد."""
    paths = {
        "alarm": MODELS_DIR / "alarm_analytics.joblib",
        "barrier": MODELS_DIR / "barrier_health.joblib",
        "sequence": MODELS_DIR / "sequence_predictor.joblib",
        "risk": MODELS_DIR / "dynamic_risk.joblib",
        "tep": MODELS_DIR / "tep_fault_detector.joblib",
    }
    for key, p in paths.items():
        try:
            _state[key] = joblib.load(p)
            print(f"[startup] loaded {key} model from {p}")
        except Exception as e:
            print(f"[startup] {key} model not loaded ({e}); will lazy-init")
            _state[key] = None

    # خلاصه گزارش‌ها
    summary = {}
    for rp in REPORTS_DIR.glob("*_report.json"):
        try:
            summary[rp.stem] = json.loads(rp.read_text(encoding="utf-8"))
        except Exception:
            pass
    _state["reports"] = summary


def _get_or_create(key: str, factory):
    if _state.get(key) is None:
        _state[key] = factory()
    return _state[key]


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _alarm_df(req: AlarmAnalysisRequest) -> pd.DataFrame:
    return pd.DataFrame([r.model_dump() for r in req.alarms])


def _barrier_df(req: BarrierHealthRequest) -> pd.DataFrame:
    return pd.DataFrame([r.model_dump() for r in req.barriers])


def _seq_df(req: SequencePredictRequest) -> pd.DataFrame:
    return pd.DataFrame([r.model_dump() for r in req.sequences])


def _risk_df(req: RiskEstimateRequest) -> pd.DataFrame:
    return pd.DataFrame([r.model_dump() for r in req.signals])


# ------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------

@app.get("/api/v1/health")
def health():
    """بررسی سلامت سرویس."""
    return {
        "status": "ok",
        "version": __version__,
        "product": "BHAM",
        "modules_loaded": {k: bool(v) for k, v in _state.items() if k != "reports"},
    }


@app.get("/api/v1/metrics/summary")
def metrics_summary():
    """خلاصه KPIهای کلان از گزارش‌های آموزش."""
    return {"reports": _state.get("reports", {})}


@app.post("/api/v1/alarms/analyze")
def analyze_alarms(req: AlarmAnalysisRequest):
    """تحلیل آلارم: شاخص‌های کامل EEMUA/ISA + خوشه‌بندی + ناهنجاری + پیشنهاد آستانه."""
    df = _alarm_df(req)
    model: AlarmAnalytics = _get_or_create("alarm", AlarmAnalytics)
    metrics = model.metrics(df)
    clusters = model.cluster(df)
    try:
        if not model._fitted:
            model.fit(df)
        anomalies = model.detect_anomalies(df)
        n_anom = int(anomalies["anomaly"].sum())
    except Exception:
        n_anom = 0
    recs = model.recommend_thresholds(df)
    compliance = model.compliance_report(df)
    return {
        "status": "ok",
        "data": {
            "metrics": metrics.to_dict(),
            "compliance": compliance,
            "n_clusters": len(clusters),
            "n_anomalies": n_anom,
            "top_clusters": [
                {
                    "cluster_id": c.cluster_id,
                    "n_alarms": c.n_alarms,
                    "root": c.likely_root_tag,
                    "priority_score": c.priority_score,
                    "is_flood": c.is_flood,
                    "rationale": c.alarm_rationale,
                    "start": c.start, "end": c.end,
                    "duration_sec": c.duration_sec,
                    "unique_tags": c.unique_tags,
                } for c in clusters[:10]
            ],
            "threshold_recommendations": recs[:5],
        },
        "errors": [],
    }


@app.post("/api/v1/alarms/kpi/eemua")
def alarm_kpi_eemua(req: AlarmAnalysisRequest):
    """شاخص‌های استاندارد EEMUA 191 / ISA-18.2 با اهداف و gaps."""
    df = _alarm_df(req)
    model: AlarmAnalytics = _get_or_create("alarm", AlarmAnalytics)
    compliance = model.compliance_report(df)
    return {
        "status": "ok",
        "data": compliance,
        "errors": [],
    }


@app.post("/api/v1/alarms/rationalize")
def alarm_rationalize(req: RationalizeRequest):
    """Alarm Rationalization (ISA-18.2 Lifecycle — مرحله Rationalization)."""
    df = _alarm_df(req)
    model: AlarmAnalytics = _get_or_create("alarm", AlarmAnalytics)
    records = model.rationalize(df, req.target_distribution)
    return {
        "status": "ok",
        "data": {
            "rationalization_records": [r.__dict__ for r in records[:50]],
            "total_records": len(records),
            "actions_summary": _rationalization_summary(records),
        },
        "errors": [],
    }


def _rationalization_summary(records) -> dict:
    actions = {}
    for r in records:
        actions[r.recommended_action] = actions.get(r.recommended_action, 0) + 1
    return actions


@app.post("/api/v1/alarms/shelve")
def alarm_shelve(req: ShelveRequest):
    """Alarm Shelving (الزام IEC 62682)."""
    model: AlarmAnalytics = _get_or_create("alarm", AlarmAnalytics)
    rec = model.shelve(
        tag=req.tag, duration_min=req.duration_min, reason=req.reason,
        shelved_by=req.shelved_by, auto_reshelf=req.auto_reshelf,
        expires_at=req.expires_at, safety_impact=req.safety_impact,
    )
    return {
        "status": "ok",
        "data": rec.__dict__,
        "errors": [],
    }


@app.post("/api/v1/alarms/shelve/batch")
def alarm_shelve_batch(req: ShelveBatchRequest):
    """شلف کردن گروهی آلارم‌ها."""
    model: AlarmAnalytics = _get_or_create("alarm", AlarmAnalytics)
    results = []
    for item in req.items:
        rec = model.shelve(
            tag=item.tag, duration_min=item.duration_min, reason=item.reason,
            shelved_by=item.shelved_by, auto_reshelf=item.auto_reshelf,
            expires_at=item.expires_at, safety_impact=item.safety_impact,
        )
        results.append(rec.__dict__)
    return {
        "status": "ok",
        "data": {"shelved": results, "count": len(results)},
        "errors": [],
    }


@app.delete("/api/v1/alarms/shelve/{tag}")
def alarm_unshelve(tag: str):
    """بازگرداندن آلارم از shelved."""
    model: AlarmAnalytics = _get_or_create("alarm", AlarmAnalytics)
    ok = model.unshelve(tag)
    return {
        "status": "ok" if ok else "not_found",
        "data": {"tag": tag, "unshelved": ok},
        "errors": [] if ok else [{"type": "NotFound", "message": f"tag {tag} not shelved"}],
    }


@app.get("/api/v1/alarms/shelved")
def alarm_list_shelved():
    """فهرست آلارم‌های shelved."""
    model: AlarmAnalytics = _get_or_create("alarm", AlarmAnalytics)
    records = model.list_shelved()
    return {
        "status": "ok",
        "data": {"shelved": [r.__dict__ for r in records], "count": len(records)},
        "errors": [],
    }


@app.post("/api/v1/alarms/state-based-suppression")
def alarm_state_based(req: StateBasedRequest):
    """پیشنهاد خاموش آلارم بر اساس حالت فرآیند (State-Based Alarming)."""
    df = _alarm_df(req)
    model: AlarmAnalytics = _get_or_create("alarm", AlarmAnalytics)
    suppressions = model.state_based_suppression(df, req.process_state)
    return {
        "status": "ok",
        "data": {
            "process_state": req.process_state,
            "suppressions": [s.__dict__ for s in suppressions],
            "suppressed_count": sum(1 for s in suppressions if s.suppressed),
        },
        "errors": [],
    }


@app.post("/api/v1/barriers/health")
def barrier_health(req: BarrierHealthRequest):
    """محاسبه سلامت لایه‌های حفاظتی، SIL و ریسک واحد (IEC 61511)."""
    df = _barrier_df(req)
    model: BarrierHealthMonitor = _get_or_create("barrier", BarrierHealthMonitor)
    layers = model.compute_layer_health(df)
    unit_risk = model.aggregate_unit_risk(layers)
    weak = model.detect_simultaneous_weakness(df)
    schedule = model.optimize_test_intervals(df)
    return {
        "status": "ok",
        "data": {
            "layers": [r.__dict__ for r in layers],
            "unit_risk": unit_risk,
            "simultaneous_weakness": weak[:10],
            "schedule": schedule.to_dict(orient="records"),
            "sil_summary": _sil_summary(layers),
        },
        "errors": [],
    }


def _sil_summary(layers) -> dict:
    """خلاصه وضعیت SIL لایه‌ها."""
    total = len(layers)
    compliant = sum(1 for l in layers if l.sil_gap == "OK")
    below = sum(1 for l in layers if l.sil_gap == "Below-target")
    bypass_active = sum(1 for l in layers if l.bypass_active)
    bypass_violations = sum(1 for l in layers if l.bypass_active and not l.bypass_compliance)
    return {
        "total_layers": total,
        "sil_compliant": compliant,
        "sil_below_target": below,
        "bypass_active_count": bypass_active,
        "bypass_violations": bypass_violations,
        "compliance_pct": round(compliant / max(total, 1) * 100, 1),
    }


@app.post("/api/v1/barriers/lopa")
def barrier_lopa(req: LOPARequest):
    """تحلیل LOPA (Layer of Protection Analysis) برای ارزیابی کفایت لایه‌ها."""
    df = _barrier_df(req)
    model: BarrierHealthMonitor = _get_or_create("barrier", BarrierHealthMonitor)
    lopa_results = model.lopa_analysis(
        df, hazard=req.hazard,
        unmitigated_freq_per_year=req.unmitigated_freq_per_year,
    )
    return {
        "status": "ok",
        "data": {
            "hazard": req.hazard,
            "tolerable_risk": model.tolerable_risk,
            "results": [r.__dict__ for r in lopa_results],
        },
        "errors": [],
    }


@app.post("/api/v1/barriers/bypass-events")
def barrier_bypass_events(req: BarrierHealthRequest):
    """استخراج و گزارش رویدادهای بایپس با انطباق SIL."""
    df = _barrier_df(req)
    model: BarrierHealthMonitor = _get_or_create("barrier", BarrierHealthMonitor)
    events = model.bypass_events(df)
    violations = [e for e in events if not e.within_limit]
    return {
        "status": "ok",
        "data": {
            "events": [e.__dict__ for e in events],
            "total_events": len(events),
            "violations": len(violations),
            "compliant": len(events) - len(violations),
        },
        "errors": [],
    }


@app.post("/api/v1/sequences/predict")
def predict_sequences(req: SequencePredictRequest):
    """پیش‌بینی احتمال توقف برای توالی‌ها."""
    df = _seq_df(req)
    if "shutdown_risk" not in df.columns:
        df["shutdown_risk"] = 0
    model: SequencePredictor = _get_or_create("sequence", lambda: SequencePredictor(n_estimators=50))
    if not model._fitted:
        model.fit(df)
    preds = model.predict(df)
    return {
        "status": "ok",
        "data": {
            "predictions": [p.__dict__ for p in preds],
            "feature_importances": model.feature_importances(top_k=10),
        },
        "errors": [],
    }


@app.post("/api/v1/risk/estimate")
def estimate_risk(req: RiskEstimateRequest):
    """برآورد ریسک پویا برای سیگنال‌های فرآیند."""
    df = _risk_df(req)
    model: DynamicRiskEstimator = _get_or_create("risk", lambda: DynamicRiskEstimator(n_estimators=50))
    if not model._fitted:
        model.fit(df)
    preds = model.predict(df)
    return {
        "status": "ok",
        "data": {
            "estimates": [p.__dict__ for p in preds],
            "feature_importances": model.feature_importances(top_k=10),
        },
        "errors": [],
    }


@app.post("/api/v1/tep/detect")
def detect_tep_faults(req: TEPDetectRequest):
    """تشخیص خطای فرآیند بر اساس داده TEP-like (52 ویژگی)."""
    X = np.array(req.features, dtype=float)
    if X.shape[1] != 52:
        raise HTTPException(400, f"features must have 52 columns, got {X.shape[1]}")
    model: TEPFaultDetector | None = _state.get("tep")
    if model is None:
        raise HTTPException(503, "TEP model not trained; run scripts/train_all.py first")
    res = model.detect(X)
    return {
        "status": "ok",
        "data": {
            "detections": [r.__dict__ for r in res],
            "t2_threshold": model._t2_threshold,
            "spe_threshold": model._spe_threshold,
        },
        "errors": [],
    }


# ============================================================
# ماژول جدید ۶: پایش و بهینه‌سازی کیفیت محصول (Quality Optimization)
# ============================================================

@app.post("/api/v1/quality/spc")
def quality_spc(req: SPCRequest):
    """تحلیل SPC کامل یک متغیر (Western Electric + Cp/Cpk + CUSUM + EWMA)."""
    qo = QualityOptimizer()
    s = pd.Series(req.values, name=req.variable)
    spc = qo.spc_analysis(s, usl=req.usl, lsl=req.lsl, target=req.target)
    return {"status": "ok", "data": spc.__dict__, "errors": []}


@app.post("/api/v1/quality/report")
def quality_report(req: QualityReportRequest):
    """گزارش جامع کیفیت محصول با همه شاخص‌ها (SPC، fault impact، RCA، setpoint)."""
    qo = QualityOptimizer()
    # تبدیل به DataFrame
    df = pd.DataFrame(req.data)
    # افزودن ستون خطا اگر وجود دارد
    fault_col = req.fault_col if (req.fault_col and req.fault_col in df.columns) else None
    # تبدیل QualitySpec به dict
    specs_clean = {k: v.model_dump() for k, v in req.specs.items()}
    report = qo.quality_report(df, specs_clean, fault_col)
    return {"status": "ok", "data": report, "errors": []}


@app.post("/api/v1/quality/fault-impact")
def quality_fault_impact(req: QualityFaultImpactRequest):
    """تحلیل اثر خطاهای فرآیندی بر کیفیت محصول."""
    qo = QualityOptimizer()
    df = pd.DataFrame({
        "value": req.values,
        "fault_id": req.fault_ids,
    })
    impacts = qo.fault_quality_impact(
        df, "fault_id", "value",
        req.fault_descriptions,
    )
    return {
        "status": "ok",
        "data": {
            "impacts": [i.__dict__ for i in impacts],
            "quality_variable": req.quality_variable_name,
            "n_faults_analyzed": len(impacts),
        },
        "errors": [],
    }


@app.post("/api/v1/quality/setpoint-optimize")
def quality_setpoint_optimize(req: SetpointOptimizeRequest):
    """پیشنهاد بهینه‌سازی setpoint بر اساس همبستگی متغیرهای دستکاری با کیفیت."""
    qo = QualityOptimizer()
    df = pd.DataFrame({req.quality_col: req.values})
    # اگر متغیرهای دستکاری ارائه نشده، None بفرست تا خودکار انتخاب شود
    opts = qo.optimize_setpoint(df, req.quality_col, req.target, req.usl, req.lsl, req.manipulated_vars)
    return {
        "status": "ok",
        "data": {
            "optimizations": [o.__dict__ for o in opts],
            "n_suggestions": len(opts),
        },
        "errors": [],
    }


# ============================================================
# ماژول جدید ۷: بهینه‌سازی خط تولید (Production Optimization)
# ============================================================

@app.post("/api/v1/production/oee")
def production_oee(req: OEEInput):
    """محاسبه OEE (Overall Equipment Effectiveness)."""
    po = ProductionOptimizer()
    oee = po.compute_oee(
        unit=req.unit, planned_time_h=req.planned_time_h,
        downtime_h=req.downtime_h, total_count=req.total_count,
        good_count=req.good_count, ideal_cycle_time_min=req.ideal_cycle_time_min,
    )
    return {
        "status": "ok",
        "data": oee.__dict__,
        "targets": OEE_TARGETS,
        "errors": [],
    }


@app.post("/api/v1/production/bottlenecks")
def production_bottlenecks(req: BottleneckRequest):
    """شناسایی گلوگاه خط تولید (Theory of Constraints)."""
    po = ProductionOptimizer()
    units_data = [u.model_dump() if hasattr(u, 'model_dump') else u.__dict__ for u in req.units]
    bottlenecks = po.identify_bottlenecks(units_data)
    return {
        "status": "ok",
        "data": {
            "bottlenecks": [b.__dict__ for b in bottlenecks],
            "n_bottlenecks": sum(1 for b in bottlenecks if b.is_bottleneck),
        },
        "errors": [],
    }


@app.post("/api/v1/production/yield")
def production_yield(req: YieldInput):
    """تحلیل بازده محصول با تفکیک اتلاف‌ها."""
    po = ProductionOptimizer()
    y = po.analyze_yield(
        unit=req.unit, feed_kg_h=req.feed_kg_h, product_kg_h=req.product_kg_h,
        downtime_loss_kg_h=req.downtime_loss_kg_h,
        quality_loss_kg_h=req.quality_loss_kg_h,
        energy_loss_kg_h=req.energy_loss_kg_h,
    )
    return {"status": "ok", "data": y.__dict__, "errors": []}


@app.post("/api/v1/production/report")
def production_report(req: ProductionReportRequest):
    """گزارش جامع تولید با OEE، bottleneck، yield، KPI و optimizations."""
    po = ProductionOptimizer()
    oee_input = req.oee_input.model_dump() if hasattr(req.oee_input, 'model_dump') else req.oee_input
    units_data = [u.model_dump() if hasattr(u, 'model_dump') else u.__dict__ for u in req.units_data]
    yields_data = [y.model_dump() if hasattr(y, 'model_dump') else y.__dict__ for y in req.yields_data]
    report = po.production_report(
        df=None,
        units_data=units_data,
        yields_data=yields_data,
        oee_input=oee_input,
    )
    return {"status": "ok", "data": report, "errors": []}


# ------------------------------------------------------------
# داشبورد (سرو فایل HTML)
# ------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard():
    """سرو داشبورد تک‌فایلی."""
    p = REPO / "frontend" / "dashboard.html"
    if not p.exists():
        return HTMLResponse("<h1>dashboard.html not found</h1>", status_code=404)
    return HTMLResponse(p.read_text(encoding="utf-8"))


# ------------------------------------------------------------
# مدیریت خطای سراسری
# ------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"status": "error", "data": None, "errors": [{"type": type(exc).__name__, "message": str(exc)}]},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)
