"""ماژول ۷: بهینه‌سازی عملکرد خط تولید (Production Line Optimization).

این ماژول در پاسخ به چالش‌های شناسایی‌شده در خط تولید پتروشیمی غدیر طراحی شده است:
  - نرخ خرابی تجهیزات ۲.۵٪ (هدف < ۱٪)
  - نوسانات شدید پارامترها (دما ۱۱۷-۱۸۷°C، فشار ۲۶-۴۳ bar)
  - نبود شاخص OEE
  - نبود شناسایی گلوگاه (bottleneck)
  - نبود تخمین بازده محصول (yield)

الگوریتم‌ها و قابلیت‌ها:
  - محاسبه OEE (Overall Equipment Effectiveness): Availability × Performance × Quality
  - تخمین throughput و ظرفیت خط تولید
  - شناسایی گلوگاه (Bottleneck) با Theory of Constraints
  - محاسبه بازده محصول (Yield)
  - پیشنهاد بهبود با تحلیل هزینه-فایده
  - پایش KPI تولید: PPH (Production per Hour)، MTBF، MTTR
  - تخمین تأثیر بهینه‌سازی هر پارامتر بر throughput

منابع استاندارد:
  - ISO 22400-2 (KPIs for operations management)
  - TPM (Total Productive Maintenance) — Nakajima
  - Theory of Constraints (Goldratt)
  - SEMI E10 (Equipment reliability)
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Iterable

import numpy as np
import pandas as pd


# ------------------------------------------------------------
# اهداف استاندارد OEE (World-Class — Nakajima)
# ------------------------------------------------------------
OEE_TARGETS = {
    "availability": 0.90,      # ۹۰٪ در دسترس
    "performance": 0.95,       # ۹۵٪ سرعت
    "quality": 0.99,            # ۹۹٪ کیفیت
    "oee": 0.85,                # ۸۵٪ کلی (world-class)
    "oee_minimum": 0.60,        # حداقل قابل قبول
}


@dataclass
class OEEResult:
    """شاخص اثربخشی کلی تجهیزات برای یک واحد/خط."""
    unit: str
    availability: float          # 0..1
    performance: float           # 0..1
    quality_rate: float          # 0..1
    oee: float                   # 0..1
    oee_pct: float               # درصد
    grade: str                    # World-class / Good / Fair / Poor / Critical
    planned_production_time_h: float
    downtime_h: float
    operating_time_h: float
    ideal_cycle_time_min: float
    total_count: int
    good_count: int
    reject_count: int
    net_operating_time_h: float
    fast_loss_h: float
    gap_to_target_pct: float


@dataclass
class Bottleneck:
    """گلوگاه خط تولید."""
    unit: str
    equipment: str
    utilization_pct: float       # درصد استفاده
    throughput_tph: float        # تن بر ساعت
    is_bottleneck: bool
    constraint_type: str         # Capacity / Speed / Quality / Availability
    impact_on_total_pct: float
    recommendation: str


@dataclass
class YieldAnalysis:
    """تحلیل بازده محصول."""
    unit: str
    feed_kg_h: float
    product_kg_h: float
    yield_pct: float
    yield_target_pct: float
    yield_gap_pct: float
    loss_categories: dict        # توزیع اتلاف
    estimated_loss_value_usd_h: float


@dataclass
class ProductionKPI:
    """KPI‌های تولید یک واحد."""
    unit: str
    production_per_hour: float    # PPH
    mtbf_h: float                  # Mean Time Between Failures
    mttr_h: float                  # Mean Time To Repair
    availability_pct: float
    utilization_pct: float
    cycle_time_min: float
    throughput_tph: float
    downtime_events: int
    quality_loss_pct: float


@dataclass
class ProductionOptimization:
    """پیشنهاد بهینه‌سازی تولید."""
    lever: str                     # اهرم بهبود
    unit: str
    current_value: float
    target_value: float
    expected_oee_gain_pct: float
    expected_throughput_gain_tph: float
    estimated_cost_usd: float
    estimated_benefit_usd_year: float
    roi: float                     # بازگشت سرمایه
    payback_months: float
    priority: str                  # High / Medium / Low


def _oee_grade(oee: float) -> str:
    if oee >= 0.85:
        return "World-class"
    if oee >= 0.75:
        return "Good"
    if oee >= 0.60:
        return "Fair"
    if oee >= 0.40:
        return "Poor"
    return "Critical"


class ProductionOptimizer:
    """بهینه‌سازی عملکرد خط تولید."""

    def __init__(self,
                 ideal_cycle_time_min: float = 5.0,
                 target_yield_pct: float = 95.0,
                 product_value_usd_per_ton: float = 800.0):
        self.ideal_cycle_time_min = ideal_cycle_time_min
        self.target_yield_pct = target_yield_pct
        self.product_value_usd_per_ton = product_value_usd_per_ton

    # ============================================================
    # محاسبه OEE
    # ============================================================
    def compute_oee(self, unit: str, planned_time_h: float, downtime_h: float,
                    total_count: int, good_count: int,
                    ideal_cycle_time_min: float | None = None) -> OEEResult:
        """محاسبه OEE بر اساس تعریف استاندارد Nakajima.

        OEE = Availability × Performance × Quality
        """
        cycle = ideal_cycle_time_min or self.ideal_cycle_time_min
        operating_time = max(planned_time_h - downtime_h, 0.0)
        availability = operating_time / planned_time_h if planned_time_h > 0 else 0.0

        # Performance = (Ideal Cycle Time × Total Count) / Operating Time
        net_operating_time = (cycle * total_count) / 60.0  # convert to hours
        performance = net_operating_time / operating_time if operating_time > 0 else 0.0
        performance = min(performance, 1.0)  # cap at 100%
        fast_loss = operating_time - net_operating_time

        # Quality = Good Count / Total Count
        quality_rate = good_count / total_count if total_count > 0 else 0.0

        oee = availability * performance * quality_rate
        grade = _oee_grade(oee)
        gap = (OEE_TARGETS["oee"] - oee) * 100

        return OEEResult(
            unit=unit,
            availability=round(availability, 4),
            performance=round(performance, 4),
            quality_rate=round(quality_rate, 4),
            oee=round(oee, 4),
            oee_pct=round(oee * 100, 2),
            grade=grade,
            planned_production_time_h=round(planned_time_h, 2),
            downtime_h=round(downtime_h, 2),
            operating_time_h=round(operating_time, 2),
            ideal_cycle_time_min=cycle,
            total_count=total_count,
            good_count=good_count,
            reject_count=total_count - good_count,
            net_operating_time_h=round(net_operating_time, 2),
            fast_loss_h=round(max(fast_loss, 0.0), 2),
            gap_to_target_pct=round(gap, 2),
        )

    # ============================================================
    # شناسایی گلوگاه (Bottleneck)
    # ============================================================
    def identify_bottlenecks(self, units_data: list[dict]) -> list[Bottleneck]:
        """شناسایی گلوگاه بر اساس Theory of Constraints.

        units_data = [{"unit": "...", "equipment": "...", "utilization_pct": 85.0,
                        "throughput_tph": 12.5, "capacity_tph": 15.0, "quality_pct": 99}, ...]
        """
        if not units_data:
            return []
        # مرتب‌سازی بر اساس utilization نزولی
        sorted_units = sorted(units_data, key=lambda u: u.get("utilization_pct", 0), reverse=True)
        max_util = sorted_units[0].get("utilization_pct", 0)
        results: list[Bottleneck] = []
        for u in sorted_units:
            util = u.get("utilization_pct", 0)
            is_bn = util >= max_util * 0.95 and util >= 80
            # تعیین نوع محدودیت
            capacity_tph = u.get("capacity_tph", 0)
            throughput_tph = u.get("throughput_tph", 0)
            quality_pct = u.get("quality_pct", 100)
            if util >= 95:
                ctype = "Capacity"
                rec = "افزایش ظرفیت یا انتقال بار به واحد موازی."
            elif u.get("performance_pct", 100) < 90:
                ctype = "Speed"
                rec = "tune کنترلر، کاهش سرعت چرخه اضافی، بازرسی مکانیکی."
            elif quality_pct < 95:
                ctype = "Quality"
                rec = "بهبود کنترل کیفیت، بازنگری setpoint، بازرسی آنلاین خلوص."
            else:
                ctype = "Availability"
                rec = "کاهش downtime با PM پیشگیرانه و بهبود MTTR."

            # محاسبه اثر بر کل: اگر ۱۰٪ کاهش throughput گلوگاه، کل ۱۰٪ کاهش
            impact = (util / 100) * 10 if is_bn else (util / 100) * 2

            results.append(Bottleneck(
                unit=u.get("unit", "Unknown"),
                equipment=u.get("equipment", "Unknown"),
                utilization_pct=round(util, 2),
                throughput_tph=round(throughput_tph, 2),
                is_bottleneck=is_bn,
                constraint_type=ctype,
                impact_on_total_pct=round(impact, 2),
                recommendation=rec,
            ))
        return results

    # ============================================================
    # تحلیل بازده محصول (Yield)
    # ============================================================
    def analyze_yield(self, unit: str, feed_kg_h: float, product_kg_h: float,
                      downtime_loss_kg_h: float = 0,
                      quality_loss_kg_h: float = 0,
                      energy_loss_kg_h: float = 0) -> YieldAnalysis:
        """تحلیل بازده با تفکیک اتلاف‌ها."""
        total_loss = downtime_loss_kg_h + quality_loss_kg_h + energy_loss_kg_h
        yield_pct = (product_kg_h / feed_kg_h * 100) if feed_kg_h > 0 else 0.0
        gap = self.target_yield_pct - yield_pct

        # توزیع اتلاف (نرمالایز)
        loss_categories = {
            "downtime": round(downtime_loss_kg_h, 2),
            "quality": round(quality_loss_kg_h, 2),
            "energy": round(energy_loss_kg_h, 2),
            "unaccounted": round(max(feed_kg_h - product_kg_h - total_loss, 0), 2),
        }
        # تخمین ارزش اتلاف (USD/h)
        total_loss_kg = sum(loss_categories.values())
        loss_value = total_loss_kg / 1000 * self.product_value_usd_per_ton

        return YieldAnalysis(
            unit=unit,
            feed_kg_h=round(feed_kg_h, 2),
            product_kg_h=round(product_kg_h, 2),
            yield_pct=round(yield_pct, 2),
            yield_target_pct=self.target_yield_pct,
            yield_gap_pct=round(gap, 2),
            loss_categories=loss_categories,
            estimated_loss_value_usd_h=round(loss_value, 2),
        )

    # ============================================================
    # محاسبه KPI‌های تولید از داده‌ها
    # ============================================================
    def compute_kpis(self, df: pd.DataFrame, unit_col: str = "unit") -> list[ProductionKPI]:
        """محاسبه KPI‌های تولید از داده operational."""
        results: list[ProductionKPI] = []
        if unit_col not in df.columns:
            return results
        for unit, g in df.groupby(unit_col):
            n_records = len(g)
            if n_records == 0:
                continue
            # MTBF و MTTR از operating_hours و failure
            if "operating_hours" in g.columns and "failure" in g.columns:
                n_failures = int(g["failure"].sum())
                total_hours = float(g["operating_hours"].max() - g["operating_hours"].min())
                mtbf = total_hours / max(n_failures, 1)
                mttr = 4.0  # فرض ثابت در نبود داده دقیق
                avail_pct = (total_hours - n_failures * mttr) / max(total_hours, 1) * 100
            else:
                mtbf = 0.0; mttr = 0.0; avail_pct = 100.0

            # throughput
            if "flow_kg_h" in g.columns:
                tph = float(g["flow_kg_h"].mean()) / 1000.0  # convert to t/h
                cycle_min = 60 / max(tph, 0.01)
            else:
                tph = 0.0; cycle_min = self.ideal_cycle_time_min

            # utilization
            if "temperature_c" in g.columns:
                # proxy: درصد زمان که فرآیند در محدوده عملکردی است
                in_range = ((g["temperature_c"] > 130) & (g["temperature_c"] < 180)).mean()
                util_pct = float(in_range * 100)
            else:
                util_pct = 80.0

            # quality loss proxy
            if "vibration_mm_s" in g.columns:
                ql_pct = float((g["vibration_mm_s"] > 3.0).mean() * 5)
            else:
                ql_pct = 2.0

            # PPH
            pph = tph * 1000  # kg/h

            results.append(ProductionKPI(
                unit=unit,
                production_per_hour=round(pph, 2),
                mtbf_h=round(mtbf, 2),
                mttr_h=round(mttr, 2),
                availability_pct=round(avail_pct, 2),
                utilization_pct=round(util_pct, 2),
                cycle_time_min=round(cycle_min, 3),
                throughput_tph=round(tph, 3),
                downtime_events=int(g["failure"].sum()) if "failure" in g.columns else 0,
                quality_loss_pct=round(ql_pct, 2),
            ))
        return results

    # ============================================================
    # پیشنهاد بهینه‌سازی با تحلیل هزینه-فایده
    # ============================================================
    def suggest_optimizations(self, oee: OEEResult, kpis: list[ProductionKPI],
                              yields: list[YieldAnalysis]) -> list[ProductionOptimization]:
        """پیشنهاد بهبود بر اساس شکاف‌ها با تخمین ROI."""
        opts: list[ProductionOptimization] = []

        # ۱. بهبود Availability (اگر پایین)
        if oee.availability < OEE_TARGETS["availability"]:
            gain_pct = (OEE_TARGETS["availability"] - oee.availability) * 100
            benefit_year = gain_pct * 0.01 * 8760 * 10 * self.product_value_usd_per_ton * 0.5  # تقریب
            opts.append(ProductionOptimization(
                lever="Availability (PM پیشگیرانه + پیش‌بینی خرابی)",
                unit=oee.unit,
                current_value=round(oee.availability * 100, 2),
                target_value=round(OEE_TARGETS["availability"] * 100, 2),
                expected_oee_gain_pct=round(gain_pct, 2),
                expected_throughput_gain_tph=round(gain_pct * 0.01 * 10, 2),
                estimated_cost_usd=50000,
                estimated_benefit_usd_year=round(benefit_year, 0),
                roi=round(benefit_year / 50000, 2),
                payback_months=round(50000 / max(benefit_year / 12, 1), 1),
                priority="High" if gain_pct > 5 else "Medium",
            ))

        # ۲. بهبود Performance
        if oee.performance < OEE_TARGETS["performance"]:
            gain_pct = (OEE_TARGETS["performance"] - oee.performance) * 100
            benefit_year = gain_pct * 0.01 * 8760 * 10 * self.product_value_usd_per_ton * 0.3
            opts.append(ProductionOptimization(
                lever="Performance (tune PID + کاهش cycle time)",
                unit=oee.unit,
                current_value=round(oee.performance * 100, 2),
                target_value=round(OEE_TARGETS["performance"] * 100, 2),
                expected_oee_gain_pct=round(gain_pct, 2),
                expected_throughput_gain_tph=round(gain_pct * 0.01 * 10, 2),
                estimated_cost_usd=30000,
                estimated_benefit_usd_year=round(benefit_year, 0),
                roi=round(benefit_year / 30000, 2),
                payback_months=round(30000 / max(benefit_year / 12, 1), 1),
                priority="High" if gain_pct > 5 else "Medium",
            ))

        # ۳. بهبود Quality
        if oee.quality_rate < OEE_TARGETS["quality"]:
            gain_pct = (OEE_TARGETS["quality"] - oee.quality_rate) * 100
            benefit_year = gain_pct * 0.01 * 8760 * 10 * self.product_value_usd_per_ton * 0.4
            opts.append(ProductionOptimization(
                lever="Quality (SPC + APC + Real-time optimization)",
                unit=oee.unit,
                current_value=round(oee.quality_rate * 100, 2),
                target_value=round(OEE_TARGETS["quality"] * 100, 2),
                expected_oee_gain_pct=round(gain_pct, 2),
                expected_throughput_gain_tph=round(gain_pct * 0.01 * 10, 2),
                estimated_cost_usd=80000,
                estimated_benefit_usd_year=round(benefit_year, 0),
                roi=round(benefit_year / 80000, 2),
                payback_months=round(80000 / max(benefit_year / 12, 1), 1),
                priority="High" if gain_pct > 3 else "Medium",
            ))

        # ۴. بهبود Yield (اگر زیر هدف)
        for y in yields:
            if y.yield_pct < y.yield_target_pct:
                gap = y.yield_gap_pct
                benefit_year = gap * 0.01 * 8760 * y.feed_kg_h / 1000 * self.product_value_usd_per_ton
                opts.append(ProductionOptimization(
                    lever="Yield (کاهش اتلاف + بازیافت)",
                    unit=y.unit,
                    current_value=y.yield_pct,
                    target_value=y.yield_target_pct,
                    expected_oee_gain_pct=round(gap * 0.1, 2),
                    expected_throughput_gain_tph=round(gap * 0.01 * y.feed_kg_h / 1000, 2),
                    estimated_cost_usd=100000,
                    estimated_benefit_usd_year=round(benefit_year, 0),
                    roi=round(benefit_year / 100000, 2),
                    payback_months=round(100000 / max(benefit_year / 12, 1), 1),
                    priority="High" if gap > 5 else "Medium",
                ))

        # مرتب‌سازی بر اساس ROI
        return sorted(opts, key=lambda o: o.roi, reverse=True)

    # ============================================================
    # گزارش جامع تولید
    # ============================================================
    def production_report(self, df: pd.DataFrame | None = None,
                          units_data: list[dict] | None = None,
                          yields_data: list[dict] | None = None,
                          oee_input: dict | None = None) -> dict:
        """گزارش جامع تولید با OEE، bottleneck، yield، KPI و optimizations."""
        # محاسبه KPI‌ها از داده
        kpis = self.compute_kpis(df) if df is not None else []

        # OEE
        if oee_input:
            oee = self.compute_oee(**oee_input)
        else:
            # تخمین از KPI ها
            if kpis:
                k = kpis[0]
                avail = k.availability_pct / 100
                perf = k.utilization_pct / 100
                qual = 1 - k.quality_loss_pct / 100
                total_count = 1000
                good_count = int(total_count * qual)
                oee = self.compute_oee(
                    unit=k.unit, planned_time_h=720, downtime_h=720 * (1 - avail),
                    total_count=total_count, good_count=good_count,
                )
            else:
                oee = self.compute_oee("default", 720, 100, 1000, 950)

        # Bottleneck
        bottlenecks = self.identify_bottlenecks(units_data or [])

        # Yield
        yields = []
        if yields_data:
            for yd in yields_data:
                yields.append(self.analyze_yield(**yd))
        elif kpis:
            for k in kpis:
                feed = k.throughput_tph * 1000
                product = feed * (self.target_yield_pct / 100) * (1 - k.quality_loss_pct / 100)
                yields.append(self.analyze_yield(
                    unit=k.unit, feed_kg_h=feed, product_kg_h=product,
                    downtime_loss_kg_h=feed * 0.02, quality_loss_kg_h=feed * 0.015,
                ))

        # Optimizations
        opts = self.suggest_optimizations(oee, kpis, yields)

        return {
            "summary": {
                "oee_pct": oee.oee_pct,
                "oee_grade": oee.grade,
                "oee_target_pct": OEE_TARGETS["oee"] * 100,
                "oee_gap_pct": oee.gap_to_target_pct,
                "n_bottlenecks": sum(1 for b in bottlenecks if b.is_bottleneck),
                "avg_yield_pct": float(np.mean([y.yield_pct for y in yields])) if yields else 0.0,
                "total_estimated_loss_usd_h": sum(y.estimated_loss_value_usd_h for y in yields),
                "n_optimization_opportunities": len(opts),
                "best_roi": max((o.roi for o in opts), default=0.0),
            },
            "oee": oee.__dict__,
            "kpis": [k.__dict__ for k in kpis],
            "bottlenecks": [b.__dict__ for b in bottlenecks],
            "yields": [y.__dict__ for y in yields],
            "optimizations": [o.__dict__ for o in opts],
        }
