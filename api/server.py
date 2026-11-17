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
    DATA_SYN, DATA_REAL, MODELS_DIR, REPORTS_DIR, __version__,
)
import joblib

app = FastAPI(
    title="BHAM API — سامانه هوشمند مدیریت آلارم و پایش سلامت لایه‌های حفاظتی",
    description="REST API برای چهار ماژول AI + تشخیص خطای TEP",
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
    """تحلیل آلارم: شاخص‌ها + خوشه‌بندی + ناهنجاری + پیشنهاد آستانه."""
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
    return {
        "status": "ok",
        "data": {
            "metrics": metrics.to_dict(),
            "n_clusters": len(clusters),
            "n_anomalies": n_anom,
            "top_clusters": [
                {
                    "cluster_id": c.cluster_id,
                    "n_alarms": c.n_alarms,
                    "root": c.likely_root_tag,
                    "priority_score": c.priority_score,
                    "is_flood": c.is_flood,
                    "start": c.start, "end": c.end,
                } for c in clusters[:10]
            ],
            "threshold_recommendations": recs[:5],
        },
        "errors": [],
    }


@app.post("/api/v1/barriers/health")
def barrier_health(req: BarrierHealthRequest):
    """محاسبه سلامت لایه‌های حفاظتی و ریسک واحد."""
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
