"""آموزش و ارزیابی جامع همه الگوریتم‌های BHAM روی داده مصنوعی و واقعی.

این اسکریپت برای هر ماژول:
  ۱) داده را بارگذاری می‌کند (synthetic و/یا real)
  ۲) مدل را آموزش می‌دهد
  ۳) شاخص‌های دقت تخصصی هر ماژول را محاسبه می‌کند
  ۴) مدل را در models/ ذخیره می‌کند
  ۵) گزارش را در reports/ ذخیره می‌کند
  ۶) خلاصه دقت همه الگوریتم‌ها را در reports/accuracy_summary.json می‌نویسد

اجرا:
    python scripts/train_and_evaluate_all.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "src"))

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, mean_squared_error, r2_score,
)

from bham import (
    AlarmAnalytics, BarrierHealthMonitor, SequencePredictor,
    DynamicRiskEstimator, TEPFaultDetector,
    QualityOptimizer, ProductionOptimizer,
    DATA_SYN, DATA_REAL, MODELS_DIR, REPORTS_DIR,
    EEMUA_TARGETS, OEE_TARGETS,
)
import joblib  # type: ignore


# ============================================================
# کمکی: چاپ و جمع‌آوری نتایج
# ============================================================

ACCURACY_SUMMARY: dict = {"modules": [], "generated_at": "", "total_runtime_s": 0.0}
START_TIME = time.time()


def header(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def add_summary(module: str, dataset: str, algorithm: str,
                metrics: dict, n_train: int = 0, n_test: int = 0) -> None:
    """ثبت خلاصه دقت یک ماژول."""
    ACCURACY_SUMMARY["modules"].append({
        "module": module,
        "dataset": dataset,
        "algorithm": algorithm,
        "n_train": n_train,
        "n_test": n_test,
        "metrics": metrics,
    })
    print(f"\n📊 [{module} | {dataset}] دقت:")
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"   {k:35s} = {v:.4f}")
        else:
            print(f"   {k:35s} = {v}")


# ============================================================
# ماژول ۱: تحلیل آلارم (داده مصنوعی)
# ============================================================

def eval_alarm_module():
    header("ماژول ۱: تحلیل و اولویت‌بندی آلارم (داده مصنوعی)")
    df = pd.read_csv(DATA_SYN / "alarms.csv", parse_dates=["timestamp"])
    print(f"loaded {len(df):,} alarm records")

    model = AlarmAnalytics()
    metrics = model.metrics(df)
    model.fit(df)

    # ارزیابی تشخیص ناهنجاری (Isolation Forest)
    sample = df.sample(min(8000, len(df)), random_state=42)
    anomalies = model.detect_anomalies(sample)
    # برچسب واقعی: فرض می‌کنیم اولویت Critical = ناهنجاری واقعی
    y_true = (sample["priority"].isin(["Critical", "High"])).astype(int).values
    y_pred = anomalies["anomaly"].values
    if y_pred.sum() > 0 and y_pred.sum() < len(y_pred):
        auc = float(roc_auc_score(y_true, y_pred))
    else:
        auc = 0.5
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    acc = float(accuracy_score(y_true, y_pred))

    # خوشه‌بندی
    clusters = model.cluster(df.head(5000))
    n_clusters = len(clusters)
    n_floods = sum(c.is_flood for c in clusters)

    # انطباق EEMUA
    compliance = {
        "alarms_per_10min_steady": metrics.alarms_per_10min_steady,
        "alarms_per_10min_peak": metrics.alarms_per_10min_peak,
        "chattering_pct": metrics.chattering_pct,
        "standing_pct": metrics.standing_pct,
        "stale_pct": metrics.stale_pct,
        "top_10_share_pct": metrics.top_10_share_pct,
        "compliance_score": metrics.compliance_score,
        "compliance_grade": metrics.compliance_grade,
    }
    eemua_gap = {
        "alarms_per_10min_gap": max(0, metrics.alarms_per_10min_steady - EEMUA_TARGETS["alarms_per_10min_steady"]),
        "chattering_gap_pct": max(0, metrics.chattering_pct - EEMUA_TARGETS["chatter_max_pct"]),
        "stale_gap_pct": max(0, metrics.stale_pct - EEMUA_TARGETS["stale_max_pct"]),
        "top10_gap_pct": max(0, metrics.top_10_share_pct - EEMUA_TARGETS["top10_share_max_pct"]),
    }

    joblib.dump(model, MODELS_DIR / "alarm_analytics.joblib")
    report = {
        "metrics": metrics.to_dict(),
        "n_clusters": n_clusters,
        "n_floods": int(n_floods),
        "n_anomalies": int(anomalies["anomaly"].sum()),
        "compliance": compliance,
        "eemua_gap": eemua_gap,
        "anomaly_detection": {
            "accuracy": acc, "precision": prec, "recall": rec, "f1": f1, "roc_auc": auc,
            "n_samples": int(len(y_true)),
        },
        "top_clusters": [
            {"cluster_id": c.cluster_id, "n_alarms": c.n_alarms, "root": c.likely_root_tag,
             "priority": c.priority_score, "is_flood": c.is_flood}
            for c in clusters[:5]
        ],
    }
    (REPORTS_DIR / "alarm_module_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    add_summary(
        module="۱. تحلیل آلارم",
        dataset="synthetic (alarms.csv)",
        algorithm="Isolation Forest + DBSCAN + Rule-based EEMUA",
        metrics={
            "accuracy": acc, "precision": prec, "recall": rec, "f1_score": f1,
            "roc_auc": auc,
            "compliance_score": metrics.compliance_score,
            "compliance_grade": metrics.compliance_grade,
            "n_clusters": n_clusters, "n_floods": n_floods,
        },
        n_train=len(df), n_test=len(sample),
    )
    return report


# ============================================================
# ماژول ۲: پایش لایه‌های حفاظتی (داده مصنوعی)
# ============================================================

def eval_barrier_module():
    header("ماژول ۲: پایش سلامت لایه‌های حفاظتی (داده مصنوعی)")
    df = pd.read_csv(DATA_SYN / "barriers.csv", parse_dates=["timestamp"])
    print(f"loaded {len(df):,} barrier records")
    df_s = df.groupby(["unit", "layer"]).head(500).reset_index(drop=True)
    print(f"sampled {len(df_s):,} records for training")

    model = BarrierHealthMonitor()
    layers = model.compute_layer_health(df_s)
    unit_risk = model.aggregate_unit_risk(layers)
    weak = model.detect_simultaneous_weakness(df_s)
    schedule = model.optimize_test_intervals(df_s)

    # شاخص‌های دقت: تعداد لایه‌های زیر هدف SIL، میانگین سلامت، تعداد بایپس
    n_layers = len(layers)
    below_sil = sum(1 for l in layers if l.sil_gap == "Below-target")
    bypass_active = sum(1 for l in layers if l.bypass_active)
    avg_health = float(np.mean([l.health_score for l in layers]))
    high_risk_layers = sum(1 for l in layers if l.risk_level == "High")
    # تطبیق با هدف: چند درصد لایه‌ها در هدف SIL هستند
    sil_compliance_pct = (n_layers - below_sil) / max(n_layers, 1) * 100
    bypass_compliance_pct = (n_layers - bypass_active) / max(n_layers, 1) * 100
    # نرخ تشخیص ضعف همزمان
    simultaneous_weakness_rate = len(weak) / max(n_layers, 1)

    joblib.dump(model, MODELS_DIR / "barrier_health.joblib")
    report = {
        "layers": [r.__dict__ for r in layers],
        "unit_risk": unit_risk,
        "simultaneous_weakness": weak[:10],
        "schedule": schedule.to_dict(orient="records"),
        "summary": {
            "n_layers": n_layers,
            "avg_health": round(avg_health, 4),
            "below_sil": below_sil,
            "bypass_active": bypass_active,
            "sil_compliance_pct": round(sil_compliance_pct, 2),
            "bypass_compliance_pct": round(bypass_compliance_pct, 2),
            "high_risk_layers": high_risk_layers,
            "simultaneous_weakness_events": len(weak),
        },
    }
    (REPORTS_DIR / "barrier_module_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    add_summary(
        module="۲. پایش لایه‌های حفاظتی",
        dataset="synthetic (barriers.csv)",
        algorithm="Weighted Health Index + LOPA + SIL Verification (IEC 61511)",
        metrics={
            "avg_health_score": avg_health,
            "sil_compliance_pct": sil_compliance_pct,
            "bypass_compliance_pct": bypass_compliance_pct,
            "high_risk_layers_pct": high_risk_layers / max(n_layers, 1) * 100,
            "simultaneous_weakness_rate": simultaneous_weakness_rate,
            "n_layers_assessed": n_layers,
        },
        n_train=len(df_s), n_test=n_layers,
    )
    return report


# ============================================================
# ماژول ۳: پیش‌بینی توالی (داده مصنوعی)
# ============================================================

def eval_sequence_module():
    header("ماژول ۳: پیش‌بینی توالی منجر به توقف (داده مصنوعی)")
    df = pd.read_csv(DATA_SYN / "sequences.csv")
    pos_rate = df["shutdown_risk"].mean()
    print(f"loaded {len(df):,} sequences, positive rate = {pos_rate:.3f}")

    model = SequencePredictor()
    fit_info = model.fit(df)

    # ارزیابی کامل
    rep = fit_info["classification_report"]
    auc = fit_info["roc_auc"]
    cls_1 = rep.get("1", {})
    cls_0 = rep.get("0", {})
    weighted = rep.get("weighted avg", {})

    # پیش‌بینی روی نمونه
    preds = model.predict(df.sample(min(500, len(df)), random_state=42))
    high_risk = sum(1 for p in preds if p.risk_level in ("High", "Critical"))

    feats = model.feature_importances(top_k=10)

    joblib.dump(model, MODELS_DIR / "sequence_predictor.joblib")
    report = {
        "fit_info": fit_info,
        "predictions_sample": [p.__dict__ for p in preds[:10]],
        "high_risk_count": high_risk,
        "feature_importances": feats,
        "accuracy_metrics": {
            "roc_auc": auc,
            "precision_class_0": cls_0.get("precision", 0),
            "recall_class_0": cls_0.get("recall", 0),
            "f1_class_0": cls_0.get("f1-score", 0),
            "precision_class_1": cls_1.get("precision", 0),
            "recall_class_1": cls_1.get("recall", 0),
            "f1_class_1": cls_1.get("f1-score", 0),
            "weighted_precision": weighted.get("precision", 0),
            "weighted_recall": weighted.get("recall", 0),
            "weighted_f1": weighted.get("f1-score", 0),
        },
    }
    (REPORTS_DIR / "sequence_module_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    add_summary(
        module="۳. پیش‌بینی توالی",
        dataset="synthetic (sequences.csv)",
        algorithm="Random Forest + Markov Chain (multi-horizon)",
        metrics={
            "roc_auc": auc,
            "accuracy": fit_info.get("accuracy", 0),
            "precision_class_1": cls_1.get("precision", 0),
            "recall_class_1": cls_1.get("recall", 0),
            "f1_class_1": cls_1.get("f1-score", 0),
            "weighted_f1": weighted.get("f1-score", 0),
            "high_risk_detected": high_risk,
        },
        n_train=fit_info["train_size"], n_test=fit_info["test_size"],
    )
    return report


# ============================================================
# ماژول ۴: ریسک پویا (داده مصنوعی)
# ============================================================

def eval_risk_module():
    header("ماژول ۴: برآورد ریسک پویا (داده مصنوعی)")
    df = pd.read_csv(DATA_SYN / "risk_signals.csv", parse_dates=["timestamp"])
    print(f"loaded {len(df):,} records, failure rate = {df['failure'].mean():.4f}")
    df_s = df.groupby("unit").head(2000).reset_index(drop=True)
    print(f"sampled {len(df_s):,} records for training")

    model = DynamicRiskEstimator()
    fit_info = model.fit(df_s)

    rep = fit_info["classification_report"]
    auc = fit_info["roc_auc"]
    cls_1 = rep.get("1", {})
    weighted = rep.get("weighted avg", {})

    preds = model.predict(df_s.tail(2000))
    risk_levels = {}
    for p in preds:
        risk_levels[p.risk_level] = risk_levels.get(p.risk_level, 0) + 1

    schedule = model.optimize_test_schedule(df_s.tail(2000))
    feats = model.feature_importances(top_k=10)

    # تخمین C-index ( Concordance) به عنوان proxy: AUC معادل C-index برای binary
    c_index = auc

    joblib.dump(model, MODELS_DIR / "dynamic_risk.joblib")
    report = {
        "fit_info": fit_info,
        "risk_distribution": risk_levels,
        "predictions_sample": [p.__dict__ for p in preds[:10]],
        "feature_importances": feats,
        "schedule_sample": schedule.head(10).to_dict(orient="records"),
        "accuracy_metrics": {
            "roc_auc": auc,
            "c_index": c_index,
            "precision_class_1": cls_1.get("precision", 0),
            "recall_class_1": cls_1.get("recall", 0),
            "f1_class_1": cls_1.get("f1-score", 0),
            "weighted_precision": weighted.get("precision", 0),
            "weighted_recall": weighted.get("recall", 0),
            "weighted_f1": weighted.get("f1-score", 0),
        },
    }
    (REPORTS_DIR / "risk_module_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    add_summary(
        module="۴. ریسک پویا",
        dataset="synthetic (risk_signals.csv)",
        algorithm="XGBoost + Weibull AFT + Poisson process",
        metrics={
            "roc_auc": auc,
            "c_index": c_index,
            "precision_class_1": cls_1.get("precision", 0),
            "recall_class_1": cls_1.get("recall", 0),
            "f1_class_1": cls_1.get("f1-score", 0),
            "weighted_f1": weighted.get("f1-score", 0),
        },
        n_train=fit_info["train_size"], n_test=fit_info["test_size"],
    )
    return report


# ============================================================
# ماژول ۵: تشخیص خطای TEP (داده واقعی)
# ============================================================

def eval_tep_module():
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
    weighted = rep.get("weighted avg", {})
    print(f"weighted avg precision={weighted.get('precision',0):.3f} "
          f"recall={weighted.get('recall',0):.3f} f1={weighted.get('f1-score',0):.3f}")

    fdr = model.fault_detection_rate(X_te, y_te, warmup=160)
    fdrs = fdr["FDR_per_fault"]
    avg_fdr = sum(fdrs.values()) / max(len(fdrs), 1)
    far_normal = fdr["FAR_normal"]
    print(f"avg FDR across faults: {avg_fdr:.3f}")
    print(f"FAR on normal samples: {far_normal:.4f}")

    # دقت تشخیص multiclass (از detect)
    results = model.detect(X_te)
    y_pred = np.array([r.predicted_fault for r in results])
    acc = float(accuracy_score(y_te, y_pred))
    weighted_prec = weighted.get("precision", 0)
    weighted_rec = weighted.get("recall", 0)
    weighted_f1 = weighted.get("f1-score", 0)

    joblib.dump(model, MODELS_DIR / "tep_fault_detector.joblib")
    report = {
        "fit_info": fit_info,
        "FDR_per_fault": fdrs,
        "avg_FDR": round(avg_fdr, 4),
        "FAR_normal": far_normal,
        "n_train_samples": int(len(X_tr)),
        "n_test_samples": int(len(X_te)),
        "n_features": len(feature_cols),
        "accuracy": acc,
        "weighted_precision": weighted_prec,
        "weighted_recall": weighted_rec,
        "weighted_f1": weighted_f1,
        "pca_explained_variance": round(float(sum(ev)), 4),
    }
    (REPORTS_DIR / "tep_fault_module_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    add_summary(
        module="۵. تشخیص خطای TEP",
        dataset="real (Tennessee Eastman Process)",
        algorithm="PCA + T² + SPE/Q-statistic (multivariate SPC)",
        metrics={
            "avg_FDR": avg_fdr,
            "FAR_normal": far_normal,
            "accuracy": acc,
            "weighted_precision": weighted_prec,
            "weighted_recall": weighted_rec,
            "weighted_f1": weighted_f1,
            "pca_explained_variance": float(sum(ev)),
        },
        n_train=len(X_tr), n_test=len(X_te),
    )
    return report


# ============================================================
# ماژول ۶: پایش کیفیت محصول (داده واقعی TEP)
# ============================================================

def eval_quality_module():
    header("ماژول ۶: پایش و بهینه‌سازی کیفیت محصول (داده واقعی TEP)")
    df = pd.read_csv(DATA_REAL / "tep_train.csv")
    print(f"loaded TEP train: {df.shape}")

    qo = QualityOptimizer()

    # spec های واقعی پتروشیمی برای متغیرهای کیفی TEP
    # بر اساس نمونه‌برداری از داده
    specs = {}
    for col in ["xmeas_40", "xmeas_41", "xmeas_09", "xmeas_17", "xmeas_07", "xmeas_08"]:
        if col in df.columns:
            s = df[col]
            mean = float(s.mean())
            std = float(s.std())
            specs[col] = {
                "target": round(mean, 3),
                "usl": round(mean + 3 * std, 3),
                "lsl": round(mean - 3 * std, 3),
                "description": f"متغیر فرآیندی {col}",
                "unit": "—",
                "impact": "High" if col in ("xmeas_40", "xmeas_41") else "Medium",
            }

    # گزارش کامل کیفیت با ستون خطا
    report = qo.quality_report(df, specs, fault_col="fault_id")

    # شاخص‌های دقت/ارزیابی
    spc_results = report.get("spc_results", [])
    avg_cpk = float(np.mean([s["cpk"] for s in spc_results])) if spc_results else 0.0
    n_out_of_spec = sum(s["out_of_spec_count"] for s in spc_results)
    n_total_violations = sum(s["n_violations"] for s in spc_results)
    fault_impacts = report.get("fault_quality_impacts", [])
    n_critical = sum(1 for f in fault_impacts if f["impact_grade"] == "Critical")
    n_high = sum(1 for f in fault_impacts if f["impact_grade"] == "High")

    # ذخیره مدل (stateless ولی برای پایداری)
    joblib.dump(qo, MODELS_DIR / "quality_optimizer.joblib")
    (REPORTS_DIR / "quality_module_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    add_summary(
        module="۶. پایش کیفیت محصول",
        dataset="real (TEP — 22 fault types)",
        algorithm="SPC (Western Electric 8 rules) + Cp/Cpk (ISO 22514-2) + CUSUM + EWMA + Ishikawa RCA",
        metrics={
            "avg_cpk": avg_cpk,
            "n_out_of_spec_samples": n_out_of_spec,
            "n_spc_violations": n_total_violations,
            "n_quality_variables": len(specs),
            "n_faults_analyzed": len(fault_impacts),
            "n_critical_fault_impacts": n_critical,
            "n_high_fault_impacts": n_high,
        },
        n_train=len(df), n_test=len(df),
    )
    return report


# ============================================================
# ماژول ۷: بهینه‌سازی خط تولید (داده مصنوعی + واقعی)
# ============================================================

def eval_production_module():
    header("ماژول ۷: بهینه‌سازی خط تولید (داده مصنوعی risk_signals)")
    df = pd.read_csv(DATA_SYN / "risk_signals.csv", parse_dates=["timestamp"])
    print(f"loaded risk_signals: {len(df):,} records, {df['unit'].nunique()} units")

    po = ProductionOptimizer()

    # محاسبه KPI از داده operational
    kpis = po.compute_kpis(df)

    # داده bottleneck (مصنوعی بر اساس KPI ها)
    units_data = []
    for k in kpis:
        cap = max(k.throughput_tph * 1.3, 1.0)
        units_data.append({
            "unit": k.unit,
            "equipment": k.unit.replace("-Unit", "-Main"),
            "utilization_pct": round(min(k.utilization_pct * 1.1, 99), 1),
            "throughput_tph": k.throughput_tph,
            "capacity_tph": round(cap, 2),
            "quality_pct": round(100 - k.quality_loss_pct, 2),
            "performance_pct": round(k.utilization_pct, 2),
        })
    bottlenecks = po.identify_bottlenecks(units_data)

    # محاسبه OEE برای هر واحد از KPI
    oee_results = []
    yields = []
    for k in kpis:
        avail = k.availability_pct / 100
        perf = k.utilization_pct / 100
        qual = 1 - k.quality_loss_pct / 100
        total_count = 10000
        good_count = int(total_count * qual)
        oee = po.compute_oee(
            unit=k.unit, planned_time_h=720,
            downtime_h=720 * (1 - avail),
            total_count=total_count, good_count=good_count,
            ideal_cycle_time_min=60 / max(k.throughput_tph * 60, 0.01),
        )
        oee_results.append(oee)
        # yield
        feed = k.throughput_tph * 1000
        product = feed * qual * 0.95
        yields.append(po.analyze_yield(
            unit=k.unit, feed_kg_h=feed, product_kg_h=product,
            downtime_loss_kg_h=feed * 0.02, quality_loss_kg_h=feed * 0.015,
        ))

    # بهینه‌سازی با ROI
    all_opts = []
    for oee, y in zip(oee_results, yields):
        opts = po.suggest_optimizations(oee, kpis, [y])
        all_opts.extend(opts)

    # شاخص‌های ارزیابی
    avg_oee = float(np.mean([o.oee for o in oee_results]))
    avg_yield = float(np.mean([y.yield_pct for y in yields]))
    total_loss_usd_h = float(sum(y.estimated_loss_value_usd_h for y in yields))
    n_bottlenecks = sum(1 for b in bottlenecks if b.is_bottleneck)
    best_roi = max((o.roi for o in all_opts), default=0.0)
    n_optimizations = len(all_opts)
    # رتبه عملکرد
    if avg_oee >= 0.85: oee_grade = "World-class"
    elif avg_oee >= 0.60: oee_grade = "Fair"
    elif avg_oee >= 0.40: oee_grade = "Poor"
    else: oee_grade = "Critical"

    joblib.dump(po, MODELS_DIR / "production_optimizer.joblib")
    report = {
        "kpis": [k.__dict__ for k in kpis],
        "oee_results": [o.__dict__ for o in oee_results],
        "bottlenecks": [b.__dict__ for b in bottlenecks],
        "yields": [y.__dict__ for y in yields],
        "optimizations": [o.__dict__ for o in all_opts[:20]],
        "summary": {
            "avg_oee": round(avg_oee, 4),
            "oee_grade": oee_grade,
            "avg_yield_pct": round(avg_yield, 2),
            "total_loss_usd_h": round(total_loss_usd_h, 2),
            "n_bottlenecks": n_bottlenecks,
            "n_optimization_opportunities": n_optimizations,
            "best_roi": round(best_roi, 2),
        },
    }
    (REPORTS_DIR / "production_module_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    add_summary(
        module="۷. بهینه‌سازی خط تولید",
        dataset="synthetic (risk_signals.csv)",
        algorithm="OEE (Nakajima) + Theory of Constraints + Yield + ROI",
        metrics={
            "avg_oee": avg_oee,
            "oee_grade": oee_grade,
            "avg_yield_pct": avg_yield,
            "n_bottlenecks_identified": n_bottlenecks,
            "total_loss_usd_h": total_loss_usd_h,
            "n_optimization_opportunities": n_optimizations,
            "best_roi": best_roi,
        },
        n_train=len(df), n_test=len(kpis),
    )
    return report


# ============================================================
# جمع‌بندی و ذخیره خلاصه
# ============================================================

def save_accuracy_summary():
    """ذخیره خلاصه دقت همه الگوریتم‌ها."""
    ACCURACY_SUMMARY["generated_at"] = pd.Timestamp.now().isoformat()
    ACCURACY_SUMMARY["total_runtime_s"] = round(time.time() - START_TIME, 2)
    ACCURACY_SUMMARY["n_modules"] = len(ACCURACY_SUMMARY["modules"])
    (REPORTS_DIR / "accuracy_summary.json").write_text(
        json.dumps(ACCURACY_SUMMARY, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8"
    )
    print("\n" + "=" * 72)
    print("  خلاصه دقت همه الگوریتم‌ها")
    print("=" * 72)
    print(f"{'ماژول':<35} {'داده':<25} {'دقت کلیدی':<15}")
    print("-" * 80)
    for m in ACCURACY_SUMMARY["modules"]:
        metrics = m["metrics"]
        # انتخاب شاخص کلیدی
        key_metric = "—"
        key_val = "—"
        if "roc_auc" in metrics:
            key_metric, key_val = "ROC-AUC", f"{metrics['roc_auc']:.4f}"
        elif "avg_FDR" in metrics:
            key_metric, key_val = "avg FDR", f"{metrics['avg_FDR']:.4f}"
        elif "accuracy" in metrics:
            key_metric, key_val = "accuracy", f"{metrics['accuracy']:.4f}"
        elif "avg_oee" in metrics:
            key_metric, key_val = "avg OEE", f"{metrics['avg_oee']:.4f}"
        elif "avg_health_score" in metrics:
            key_metric, key_val = "avg health", f"{metrics['avg_health_score']:.4f}"
        elif "avg_cpk" in metrics:
            key_metric, key_val = "avg Cpk", f"{metrics['avg_cpk']:.4f}"
        elif "compliance_score" in metrics:
            key_metric, key_val = "compliance", f"{metrics['compliance_score']:.1f}/100"
        print(f"{m['module']:<35} {m['dataset']:<25} {key_metric}={key_val}")
    print("-" * 80)
    print(f"\n📊 گزارش کامل ذخیره شد: {REPORTS_DIR / 'accuracy_summary.json'}")


def main():
    print("=" * 72)
    print("  BHAM v2.1.0 — آموزش و ارزیابی جامع همه الگوریتم‌ها")
    print("  داده مصنوعی + داده واقعی (TEP)")
    print("=" * 72)

    # اجرای همه ماژول‌ها
    eval_alarm_module()
    eval_barrier_module()
    eval_sequence_module()
    eval_risk_module()
    eval_tep_module()
    eval_quality_module()
    eval_production_module()

    # ذخیره خلاصه
    save_accuracy_summary()

    (REPORTS_DIR / "training_summary.json").write_text(
        json.dumps({
            "modules": [m["module"] for m in ACCURACY_SUMMARY["modules"]],
            "status": "completed",
            "version": "2.1.0",
            "n_algorithms": len(ACCURACY_SUMMARY["modules"]),
            "datasets_used": ["synthetic", "real-TEP"],
        }, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("\n" + "=" * 72)
    print(f"  ✅ همه الگوریتم‌ها آموزش و ارزیابی شدند در {ACCURACY_SUMMARY['total_runtime_s']} ثانیه")
    print(f"  📁 مدل‌ها: {MODELS_DIR}")
    print(f"  📁 گزارش‌ها: {REPORTS_DIR}")
    print("=" * 72)


if __name__ == "__main__":
    main()
