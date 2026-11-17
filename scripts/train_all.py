"""آموزش همه ماژول‌های BHAM روی داده مصنوعی و داده واقعی و خروجی نتایج.

اجرا:
    python scripts/train_all.py

این اسکریپت:
  1) ماژول آلارم را روی data/synthetic/alarms.csv آموزش می‌دهد
  2) ماژول لایه‌های حفاظتی را روی data/synthetic/barriers.csv
  3) ماژول پیش‌بینی توالی را روی data/synthetic/sequences.csv
  4) ماژول ریسک پویا را روی data/synthetic/risk_signals.csv
  5) ماژول تشخیص خطای TEP را روی data/real/processed/tep_train.csv و tep_test.csv
و خروجی‌ها (مدل‌ها، معیارها، نمودارها) را در models/ و reports/ ذخیره می‌کند.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# اطمینان از اینکه src در مسیر است
HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "src"))

import numpy as np
import pandas as pd

from bham import (
    AlarmAnalytics, BarrierHealthMonitor, SequencePredictor,
    DynamicRiskEstimator, TEPFaultDetector,
    DATA_SYN, DATA_REAL, MODELS_DIR, REPORTS_DIR,
)
import joblib  # type: ignore


def header(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def train_alarm_module():
    header("ماژول ۱: تحلیل و اولویت‌بندی آلارم")
    df = pd.read_csv(DATA_SYN / "alarms.csv", parse_dates=["timestamp"])
    print(f"loaded {len(df):,} alarm records")
    model = AlarmAnalytics()
    metrics = model.metrics(df)
    print(f"alarms/hour = {metrics.alarms_per_hour}")
    print(f"chattering tags = {metrics.chattering_tags}")
    print(f"stale alarms = {metrics.stale_alarms}")
    print(f"flood events = {metrics.flood_events}")
    print(f"top-10 share = {metrics.top_10_share_pct}%")

    clusters = model.cluster(df.head(5000))
    print(f"clusters found = {len(clusters)}, floods = {sum(c.is_flood for c in clusters)}")

    model.fit(df)
    anomalies = model.detect_anomalies(df.sample(min(5000, len(df))))
    n_anom = int(anomalies["anomaly"].sum())
    print(f"anomalies detected = {n_anom}")

    recs = model.recommend_thresholds(df)
    print(f"threshold recommendations = {len(recs)}")

    joblib.dump(model, MODELS_DIR / "alarm_analytics.joblib")
    report = {
        "metrics": metrics.to_dict(),
        "n_clusters": len(clusters),
        "n_floods": int(sum(c.is_flood for c in clusters)),
        "n_anomalies": n_anom,
        "top_recommendations": recs[:5],
        "top_clusters": [
            {"cluster_id": c.cluster_id, "n_alarms": c.n_alarms, "root": c.likely_root_tag,
             "priority": c.priority_score, "is_flood": c.is_flood}
            for c in clusters[:5]
        ],
    }
    (REPORTS_DIR / "alarm_module_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"report saved -> {REPORTS_DIR/'alarm_module_report.json'}")
    return report


def train_barrier_module():
    header("ماژول ۲: پایش سلامت لایه‌های حفاظتی")
    df = pd.read_csv(DATA_SYN / "barriers.csv", parse_dates=["timestamp"])
    print(f"loaded {len(df):,} barrier records")
    # برای سرعت، نمونه‌گیری روزانه
    df_s = df.groupby(["unit", "layer"]).head(500).reset_index(drop=True)
    model = BarrierHealthMonitor()
    layers = model.compute_layer_health(df_s)
    unit_risk = model.aggregate_unit_risk(layers)
    print(f"layers assessed = {len(layers)}")
    for r in layers[:5]:
        print(f"  {r.unit:18s} | {r.layer:18s} | health={r.health_score:.3f} | risk={r.risk_level}")
    print(f"unit risk: {unit_risk}")

    weak = model.detect_simultaneous_weakness(df_s)
    print(f"simultaneous-weakness events = {len(weak)}")

    schedule = model.optimize_test_intervals(df_s)
    print(f"test-interval recommendations = {len(schedule)}")

    joblib.dump(model, MODELS_DIR / "barrier_health.joblib")
    report = {
        "layers": [r.__dict__ for r in layers],
        "unit_risk": unit_risk,
        "simultaneous_weakness": weak[:10],
        "schedule": schedule.to_dict(orient="records"),
    }
    (REPORTS_DIR / "barrier_module_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"report saved -> {REPORTS_DIR/'barrier_module_report.json'}")
    return report


def train_sequence_module():
    header("ماژول ۳: پیش‌بینی توالی منجر به توقف")
    df = pd.read_csv(DATA_SYN / "sequences.csv")
    print(f"loaded {len(df):,} sequences, positive rate = {df['shutdown_risk'].mean():.3f}")
    model = SequencePredictor()
    fit_info = model.fit(df)
    print(f"train={fit_info['train_size']}, test={fit_info['test_size']}, AUC={fit_info['roc_auc']}")
    print(f"precision(1)={fit_info['classification_report']['1']['precision']:.3f} "
          f"recall(1)={fit_info['classification_report']['1']['recall']:.3f} "
          f"f1(1)={fit_info['classification_report']['1']['f1-score']:.3f}")

    preds = model.predict(df.sample(min(500, len(df))))
    high_risk = sum(1 for p in preds if p.risk_level in ("High", "Critical"))
    print(f"predicted high-risk sequences = {high_risk}/{len(preds)}")

    feats = model.feature_importances(top_k=10)
    print("top features:")
    for f in feats:
        print(f"  {f['feature']:25s} {f['importance']:.4f}")

    joblib.dump(model, MODELS_DIR / "sequence_predictor.joblib")
    report = {
        "fit_info": fit_info,
        "predictions_sample": [p.__dict__ for p in preds[:10]],
        "high_risk_count": high_risk,
        "feature_importances": feats,
    }
    (REPORTS_DIR / "sequence_module_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"report saved -> {REPORTS_DIR/'sequence_module_report.json'}")
    return report


def train_risk_module():
    header("ماژول ۴: برآورد ریسک پویا و بهینه‌سازی تست")
    df = pd.read_csv(DATA_SYN / "risk_signals.csv", parse_dates=["timestamp"])
    print(f"loaded {len(df):,} records, failure rate = {df['failure'].mean():.4f}")
    # نمونه‌گیری برای سرعت
    df_s = df.groupby("unit").head(2000).reset_index(drop=True)
    model = DynamicRiskEstimator()
    fit_info = model.fit(df_s)
    print(f"train={fit_info['train_size']}, test={fit_info['test_size']}, AUC={fit_info['roc_auc']}")
    print(f"precision(1)={fit_info['classification_report']['1']['precision']:.3f} "
          f"recall(1)={fit_info['classification_report']['1']['recall']:.3f}")

    preds = model.predict(df_s.tail(2000))
    risk_levels = {}
    for p in preds:
        risk_levels[p.risk_level] = risk_levels.get(p.risk_level, 0) + 1
    print(f"risk distribution: {risk_levels}")

    schedule = model.optimize_test_schedule(df_s.tail(2000))
    print(f"test-schedule recommendations: {len(schedule)} rows")

    feats = model.feature_importances(top_k=10)
    print("top features:")
    for f in feats:
        print(f"  {f['feature']:25s} {f['importance']:.4f}")

    joblib.dump(model, MODELS_DIR / "dynamic_risk.joblib")
    report = {
        "fit_info": fit_info,
        "risk_distribution": risk_levels,
        "predictions_sample": [p.__dict__ for p in preds[:10]],
        "feature_importances": feats,
        "schedule_sample": schedule.head(10).to_dict(orient="records"),
    }
    (REPORTS_DIR / "risk_module_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"report saved -> {REPORTS_DIR/'risk_module_report.json'}")
    return report


def train_tep_module():
    header("ماژول ۵: تشخیص خطای فرآیند (داده واقعی TEP)")
    train_path = DATA_REAL / "tep_train.csv"
    test_path = DATA_REAL / "tep_test.csv"
    if not train_path.exists() or not test_path.exists():
        print(f"[skip] TEP data not found at {train_path}")
        return None
    df_tr = pd.read_csv(train_path)
    df_te = pd.read_csv(test_path)
    print(f"train: {df_tr.shape}, test: {df_te.shape}")
    feature_cols = [c for c in df_tr.columns if c.startswith(("xmeas_", "xmv_"))]
    X_tr = df_tr[feature_cols].to_numpy()
    y_tr = df_tr["fault_id"].to_numpy()
    X_te = df_te[feature_cols].to_numpy()
    y_te = df_te["fault_id"].to_numpy()

    model = TEPFaultDetector(n_components=15)
    fit_info = model.fit(X_tr, y_tr)
    ev = fit_info["explained_variance_ratio"]
    print(f"PCA components: {model.n_components}, total var: {sum(ev):.3f}")
    print(f"t2_threshold: {fit_info['t2_threshold']:.2f}, spe_threshold: {fit_info['spe_threshold']:.4f}")
    rep = fit_info["classification_report"]
    if "weighted avg" in rep:
        print(f"weighted avg precision={rep['weighted avg']['precision']:.3f} "
              f"recall={rep['weighted avg']['recall']:.3f} f1={rep['weighted avg']['f1-score']:.3f}")

    fdr = model.fault_detection_rate(X_te, y_te, warmup=160)
    fdrs = fdr["FDR_per_fault"]
    avg_fdr = sum(fdrs.values()) / max(len(fdrs), 1)
    print(f"avg FDR across faults: {avg_fdr:.3f}")
    print(f"FAR on normal samples: {fdr['FAR_normal']:.4f}")

    joblib.dump(model, MODELS_DIR / "tep_fault_detector.joblib")
    report = {
        "fit_info": fit_info,
        "FDR_per_fault": fdrs,
        "avg_FDR": round(avg_fdr, 4),
        "FAR_normal": fdr["FAR_normal"],
        "n_train_samples": int(len(X_tr)),
        "n_test_samples": int(len(X_te)),
        "n_features": len(feature_cols),
    }
    (REPORTS_DIR / "tep_fault_module_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"report saved -> {REPORTS_DIR/'tep_fault_module_report.json'}")
    return report


def main():
    print("BHAM training pipeline starting...")
    summary = {}
    summary["alarm"] = train_alarm_module()
    summary["barrier"] = train_barrier_module()
    summary["sequence"] = train_sequence_module()
    summary["risk"] = train_risk_module()
    summary["tep"] = train_tep_module()
    (REPORTS_DIR / "training_summary.json").write_text(
        json.dumps({"modules": list(summary.keys()),
                    "status": "completed"},
                   indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\n" + "=" * 70)
    print("  همه ماژول‌ها آموزش دیدند. خروجی‌ها در models/ و reports/ ذخیره شد.")
    print("=" * 70)


if __name__ == "__main__":
    main()
