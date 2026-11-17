"""تست‌های API سرویس FastAPI."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from api.server import app

client = TestClient(app)


def test_health_endpoint():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "modules_loaded" in body


def test_metrics_summary_endpoint():
    r = client.get("/api/v1/metrics/summary")
    assert r.status_code == 200
    body = r.json()
    assert "reports" in body


def test_analyze_alarms_endpoint():
    payload = {
        "alarms": [
            {"timestamp": "2024-03-20 10:00:00", "tag": "PT001_OLF",
             "priority": "High", "status": "Active", "value": 55, "setpoint": 50,
             "ack_delay_sec": 5, "clear_delay_sec": 60},
            {"timestamp": "2024-03-20 10:00:30", "tag": "PT001_OLF",
             "priority": "High", "status": "Cleared", "value": 55, "setpoint": 50,
             "ack_delay_sec": 5, "clear_delay_sec": 30},
            {"timestamp": "2024-03-20 11:00:00", "tag": "TT002_ARO",
             "priority": "Medium", "status": "Cleared", "value": 80, "setpoint": 75,
             "ack_delay_sec": 30, "clear_delay_sec": 200},
        ]
    }
    r = client.post("/api/v1/alarms/analyze", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "metrics" in body["data"]
    assert body["data"]["metrics"]["total_alarms"] == 3


def test_barrier_health_endpoint():
    payload = {
        "barriers": [
            {"timestamp": "2024-03-20 10:00:00", "unit": "Olefins-Unit",
             "layer": "SIS-Interlock", "health_score": 0.85, "bypass_active": False,
             "last_test_result": 1, "days_since_test": 30, "sensor_drift": 0.01,
             "response_delay_s": 2.0},
            {"timestamp": "2024-03-20 10:00:00", "unit": "Olefins-Unit",
             "layer": "BPCS-Control", "health_score": 0.75, "bypass_active": True,
             "last_test_result": 1, "days_since_test": 100, "sensor_drift": 0.05,
             "response_delay_s": 3.0},
        ]
    }
    r = client.post("/api/v1/barriers/health", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "layers" in body["data"]
    assert "unit_risk" in body["data"]
    assert len(body["data"]["layers"]) == 2


def test_sequence_predict_endpoint():
    # داده کافی برای fit + stratified split: حداقل 4 نمونه از هر کلاس
    seqs = []
    for i in range(10):
        seqs.append({"sequence_id": f"D{i}", "events": "Bypass-On|Alarm-Storm|Temp-High|Vibration-High", "length": 4, "unit": "U", "lead_time_min": 10})
    for i in range(10):
        seqs.append({"sequence_id": f"S{i}", "events": "Flow-Low|Level-High", "length": 2, "unit": "U", "lead_time_min": 0})
    payload = {"sequences": seqs}
    r = client.post("/api/v1/sequences/predict", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "predictions" in body["data"]
    assert len(body["data"]["predictions"]) == 20


def test_risk_estimate_endpoint():
    # داده کافی برای stratified split (حداقل 2 نمونه از هر کلاس)
    sigs = []
    for i in range(10):
        sigs.append({"timestamp": "2024-03-20 10:00:00", "unit": "Olefins-Unit",
                     "temperature_c": 200, "pressure_bar": 28, "flow_kg_h": 130,
                     "vibration_mm_s": 5.5, "operating_hours": 1900, "failure": 1})
    for i in range(10):
        sigs.append({"timestamp": "2024-03-20 10:00:00", "unit": "Olefins-Unit",
                     "temperature_c": 150, "pressure_bar": 35, "flow_kg_h": 180,
                     "vibration_mm_s": 2.0, "operating_hours": 100, "failure": 0})
    payload = {"signals": sigs}
    r = client.post("/api/v1/risk/estimate", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "estimates" in body["data"]
    assert len(body["data"]["estimates"]) == 20


def test_dashboard_root():
    r = client.get("/")
    assert r.status_code in (200, 404)  # اگر dashboard.html ساخته نشده باشد


def test_error_handling_invalid_payload():
    r = client.post("/api/v1/alarms/analyze", json={"alarms": []})
    # pydantic min_length=1 باید 422 برگرداند
    assert r.status_code == 422
