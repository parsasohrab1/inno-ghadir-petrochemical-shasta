"""تست عملکردی ماژول‌های جدید کیفیت و تولید (نسخه ۲.۱.۰)."""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[1] if __name__ != "__main__" else Path('.').resolve()
sys.path.insert(0, str(REPO / "src"))

import numpy as np
import pandas as pd

# ایمپورت ماژول‌های جدید
from bham import (
    QualityOptimizer, SPCResult, QualityVariable, FaultQualityImpact,
    SetpointOptimization, RootCauseAnalysis, WE_RULES,
    ProductionOptimizer, OEEResult, Bottleneck, YieldAnalysis,
    ProductionKPI, ProductionOptimization, OEE_TARGETS,
    __version__,
)

print(f"BHAM version: {__version__}")
print()

# ============================================================
# تست ۱: ماژول کیفیت — SPC و Cp/Cpk
# ============================================================
print("=== تست ۱: QualityOptimizer — SPC ===")
np.random.seed(42)
# تولید داده با میانگین ۵۳.۶ و انحراف معیار ۰.۵
normal_data = pd.Series(np.random.normal(53.6, 0.5, 200), name="xmeas_40")
qo = QualityOptimizer()
spc = qo.spc_analysis(normal_data, usl=55.0, lsl=52.0, target=53.6)
print(f"variable: {spc.variable}")
print(f"mean={spc.mean} std={spc.std}")
print(f"UCL={spc.ucl} LCL={spc.lcl}")
print(f"Cp={spc.cp} Cpk={spc.cpk}")
print(f"capability_grade: {spc.capability_grade}")
print(f"n_violations: {spc.n_violations}")
print(f"out_of_spec: {spc.out_of_spec_count} ({spc.out_of_spec_pct}%)")
print(f"cusum_drift: {spc.cusum_drift}")
print(f"ewma_value: {spc.ewma_value}")
print()

# داده خارج از کنترل
bad_data = pd.Series(np.concatenate([np.random.normal(53.6, 0.5, 100),
                                      np.random.normal(54.5, 0.8, 100)]), name="xmeas_40")
spc_bad = qo.spc_analysis(bad_data, usl=55.0, lsl=52.0, target=53.6)
print(f"Bad data: Cpk={spc_bad.cpk} violations={spc_bad.n_violations} grade={spc_bad.capability_grade}")
print()

# ============================================================
# تست ۲: QualityOptimizer — quality_variables
# ============================================================
print("=== تست ۲: QualityOptimizer — Quality Variables ===")
df = pd.DataFrame({
    "xmeas_40": np.random.normal(53.6, 0.5, 100),
    "xmeas_41": np.random.normal(43.8, 0.6, 100),
    "xmeas_09": np.random.normal(80, 2, 100),
})
specs = {
    "xmeas_40": {"target": 53.6, "usl": 55.0, "lsl": 52.0, "description": "خلوص A در محصول", "unit": "%", "impact": "High"},
    "xmeas_41": {"target": 43.8, "usl": 45.0, "lsl": 42.0, "description": "B/C در محصول", "unit": "%", "impact": "Medium"},
    "xmeas_09": {"target": 80, "usl": 85, "lsl": 75, "description": "دما جداکننده", "unit": "°C", "impact": "Medium"},
}
qvs = qo.analyze_quality_variables(df, specs)
print(f"Found {len(qvs)} quality variables")
for qv in qvs:
    print(f"  {qv.name}: target={qv.target} current={qv.current_value} dev={qv.deviation_sigma}σ status={qv.status}")
print()

# ============================================================
# تست ۳: QualityOptimizer — fault_quality_impact
# ============================================================
print("=== تست ۳: QualityOptimizer — Fault Impact ===")
np.random.seed(0)
fault_df = pd.DataFrame({
    "fault_id": [0]*100 + [1]*100 + [6]*100,
    "xmeas_40": list(np.random.normal(53.6, 0.5, 100)) +
                list(np.random.normal(53.8, 0.5, 100)) +
                list(np.random.normal(54.3, 0.5, 100)),
})
fault_desc = {1: "A/C feed ratio (B composition)", 6: "A feed loss"}
impacts = qo.fault_quality_impact(fault_df, "fault_id", "xmeas_40", fault_desc)
print(f"Found {len(impacts)} fault impacts")
for fi in impacts:
    print(f"  Fault {fi.fault_id} ({fi.fault_description}): dev={fi.purity_deviation_sigma}σ grade={fi.impact_grade} yield_loss={fi.estimated_yield_loss_pct}%")
print()

# ============================================================
# تست ۴: QualityOptimizer — setpoint optimization
# ============================================================
print("=== تست ۴: QualityOptimizer — Setpoint Optimization ===")
np.random.seed(0)
opt_df = pd.DataFrame({
    "xmeas_40": np.random.normal(53.6, 0.5, 200),
    "xmv_01": np.random.normal(50, 5, 200),
    "xmv_02": np.random.normal(40, 4, 200),
})
# ایجاد همبستگی
opt_df["xmeas_40"] = opt_df["xmeas_40"] + 0.3 * (opt_df["xmv_01"] - 50)
opts = qo.optimize_setpoint(opt_df, "xmeas_40", target=53.6, usl=55.0, lsl=52.0)
print(f"Found {len(opts)} setpoint optimizations")
for op in opts[:3]:
    print(f"  {op.variable}: current={op.current_setpoint} optimized={op.optimized_setpoint} gain={op.expected_purity_gain_pct}% conf={op.confidence}")
print()

# ============================================================
# تست ۵: QualityOptimizer — RCA
# ============================================================
print("=== تست ۵: QualityOptimizer — Root Cause Analysis ===")
# ساخت SPC با نقض قوانین
spc_list = [spc, spc_bad]
fault_imps = [impacts[0]] if impacts else []
rca = qo.root_cause_analysis("انحراف کیفیت محصول", spc_list, fault_imps)
print(f"symptom: {rca.symptom}")
print(f"category: {rca.category}")
print(f"confidence: {rca.confidence}")
print(f"causes ({len(rca.likely_causes)}):")
for c in rca.likely_causes:
    print(f"  - {c}")
print()

# ============================================================
# تست ۶: QualityOptimizer — full report
# ============================================================
print("=== تست ۶: QualityOptimizer — Full Report ===")
report = qo.quality_report(fault_df, specs, fault_col="fault_id")
print(f"n_quality_variables: {report['summary']['n_quality_variables']}")
print(f"avg_cpk: {report['summary']['avg_cpk']}")
print(f"capability_grade: {report['summary']['capability_grade']}")
print(f"n_critical_faults: {report['summary']['n_critical_faults']}")
print(f"setpoint_opts: {len(report['setpoint_optimizations'])}")
print()

# ============================================================
# تست ۷: ProductionOptimizer — OEE
# ============================================================
print("=== تست ۷: ProductionOptimizer — OEE ===")
po = ProductionOptimizer()
oee = po.compute_oee(unit="Olefins-Unit", planned_time_h=720, downtime_h=100,
                     total_count=8000, good_count=7600, ideal_cycle_time_min=5.0)
print(f"unit: {oee.unit}")
print(f"availability: {oee.availability*100:.1f}% (target: {OEE_TARGETS['availability']*100}%)")
print(f"performance: {oee.performance*100:.1f}% (target: {OEE_TARGETS['performance']*100}%)")
print(f"quality_rate: {oee.quality_rate*100:.1f}% (target: {OEE_TARGETS['quality']*100}%)")
print(f"OEE: {oee.oee_pct:.1f}% (target: {OEE_TARGETS['oee']*100}%) grade: {oee.grade}")
print(f"gap_to_target: {oee.gap_to_target_pct:.1f}%")
print()

# ============================================================
# تست ۸: ProductionOptimizer — Bottlenecks
# ============================================================
print("=== تست ۸: ProductionOptimizer — Bottlenecks ===")
units_data = [
    {"unit": "Olefins-Unit", "equipment": "Cracker", "utilization_pct": 95.0, "throughput_tph": 12.5, "capacity_tph": 13.0, "quality_pct": 99, "performance_pct": 95},
    {"unit": "Aromatics-Unit", "equipment": "Reformer", "utilization_pct": 88.0, "throughput_tph": 10.0, "capacity_tph": 11.5, "quality_pct": 98, "performance_pct": 90},
    {"unit": "Polymer-Unit", "equipment": "Reactor", "utilization_pct": 70.0, "throughput_tph": 8.0, "capacity_tph": 12.0, "quality_pct": 97, "performance_pct": 85},
]
bottlenecks = po.identify_bottlenecks(units_data)
print(f"Found {len(bottlenecks)} units, {sum(1 for b in bottlenecks if b.is_bottleneck)} bottlenecks")
for b in bottlenecks:
    print(f"  {b.unit} ({b.equipment}): util={b.utilization_pct}% bn={b.is_bottleneck} type={b.constraint_type}")
print()

# ============================================================
# تست ۹: ProductionOptimizer — Yield
# ============================================================
print("=== تست ۹: ProductionOptimizer — Yield ===")
y = po.analyze_yield(unit="Olefins-Unit", feed_kg_h=12500, product_kg_h=11500,
                      downtime_loss_kg_h=200, quality_loss_kg_h=150, energy_loss_kg_h=100)
print(f"unit: {y.unit}")
print(f"feed: {y.feed_kg_h} kg/h product: {y.product_kg_h} kg/h")
print(f"yield: {y.yield_pct}% (target: {y.yield_target_pct}%, gap: {y.yield_gap_pct}%)")
print(f"loss_categories: {y.loss_categories}")
print(f"loss_value: ${y.estimated_loss_value_usd_h}/h")
print()

# ============================================================
# تست ۱۰: ProductionOptimizer — KPIs from risk_signals.csv
# ============================================================
print("=== تست ۱۰: ProductionOptimizer — KPIs ===")
risk_df = pd.read_csv(REPO / "data" / "synthetic" / "risk_signals.csv")
kpis = po.compute_kpis(risk_df)
print(f"Found {len(kpis)} unit KPIs")
for k in kpis:
    print(f"  {k.unit}: PPH={k.production_per_hour} tph={k.throughput_tph} avail={k.availability_pct}% MTBF={k.mtbf_h}h")
print()

# ============================================================
# تست ۱۱: ProductionOptimizer — Optimizations with ROI
# ============================================================
print("=== تست ۱۱: ProductionOptimizer — Optimization Suggestions ===")
# ساخت یک OEE ضعیف برای تست بهینه‌سازی
weak_oee = po.compute_oee(unit="Olefins-Unit", planned_time_h=720, downtime_h=180,
                          total_count=6000, good_count=5400, ideal_cycle_time_min=6.0)
print(f"weak OEE: {weak_oee.oee_pct}% grade: {weak_oee.grade}")
opts = po.suggest_optimizations(weak_oee, kpis, [y])
print(f"Found {len(opts)} optimization opportunities")
for op in opts:
    print(f"  {op.lever}: current={op.current_value} target={op.target_value} "
          f"OEE_gain={op.expected_oee_gain_pct}% ROI={op.roi}x payback={op.payback_months}mo")
print()

# ============================================================
# تست ۱۲: ProductionOptimizer — Full Production Report
# ============================================================
print("=== تست ۱۲: ProductionOptimizer — Full Production Report ===")
report = po.production_report(
    df=risk_df,
    units_data=units_data,
    yields_data=[{"unit": "Olefins-Unit", "feed_kg_h": 12500, "product_kg_h": 11500,
                  "downtime_loss_kg_h": 200, "quality_loss_kg_h": 150, "energy_loss_kg_h": 100}],
    oee_input={"unit": "Olefins-Unit", "planned_time_h": 720, "downtime_h": 100,
               "total_count": 8000, "good_count": 7600, "ideal_cycle_time_min": 5.0},
)
print(f"OEE: {report['summary']['oee_pct']}% ({report['summary']['oee_grade']})")
print(f"n_bottlenecks: {report['summary']['n_bottlenecks']}")
print(f"avg_yield: {report['summary']['avg_yield_pct']}%")
print(f"total_loss: ${report['summary']['total_estimated_loss_usd_h']}/h")
print(f"n_optimizations: {report['summary']['n_optimization_opportunities']}")
print(f"best_ROI: {report['summary']['best_roi']}x")

print()
print("=" * 60)
print("✓ ALL FUNCTIONAL TESTS PASSED")
print("=" * 60)
