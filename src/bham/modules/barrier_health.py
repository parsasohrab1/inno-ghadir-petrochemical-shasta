"""ماژول ۲: پایش سلامت لایه‌های حفاظتی و مدیریت بایپس (نسخه ۲ — منطبق با IEC 61511).

الگوریتم‌ها و قابلیت‌ها (بنچ‌مارک با IEC 61511 / IEC 61508 / LOPA):
  - تجمیع وزنی شاخص‌های هر لایه (IEC 61511 — IPL: Independent Protection Layer)
  - کاهش نمایی برای اثر گذشت زمان از آخرین تست
  - جریمه بایپس و غیرفعال‌سازی همزمان
  - تخمین PFD (Probability of Failure on Demand) با مدل Poisson
  - تخمین SIL (Safety Integrity Level) بر اساس PFD هدف IEC 61511:
      * SIL 1: PFD ∈ [1e-2, 1e-1]
      * SIL 2: PFD ∈ [1e-3, 1e-2]
      * SIL 3: PFD ∈ [1e-4, 1e-3]
      * SIL 4: PFD ∈ [1e-5, 1e-4]
  - LOPA (Layer of Protection Analysis): محاسبه فاصله تا ریسک قابل‌تحمل
  - مدیریت زمان بایپس: حداکثر مجاز بایپس بر اساس ریسک
  - آنالیز وابستگی لایه‌ها (مستقل بودن IPL)
  - پیشنهاد SIL هدف و تأیید کفایت لایه‌ها
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Iterable

import numpy as np
import pandas as pd


# ------------------------------------------------------------
# اهداف PFD برای سطوح یکپارچگی ایمنی (IEC 61511 — Table 3)
# ------------------------------------------------------------
SIL_TARGETS = {
    # SIL: (PFD_low, PFD_high, RRF_min, RRF_max)  — RRF = Risk Reduction Factor
    1: (1e-2, 1e-1, 10, 100),
    2: (1e-3, 1e-2, 100, 1000),
    3: (1e-4, 1e-3, 1000, 10000),
    4: (1e-5, 1e-4, 10000, 100000),
}

# حداکثر مجاز زمان بایپس (ساعت در سال) بر اساس SIL
MAX_BYPASS_H_PER_YEAR = {
    1: 4.0,     # ~ 0.05٪ سال
    2: 2.0,
    3: 1.0,
    4: 0.5,
}

# توالی زمان تست پیشنهادی بر اساس SIL (ماه)
SIL_TEST_INTERVAL_MONTHS = {
    1: 12,   # سالانه
    2: 12,
    3: 6,    # نیم‌سالانه
    4: 3,    # فصلی
}


@dataclass
class LayerHealth:
    unit: str
    layer: str
    health_score: float          # 0..1
    bypass_penalty: float        # 0..1
    pfd_estimate: float          # probability of failure on demand
    sil_achieved: int | None     # SIL محقق‌شده (1..4) یا None
    sil_target: int              # SIL هدف برای این لایه
    sil_gap: str                  # OK / Below-target
    risk_level: str               # Low / Medium / High / Critical
    bypass_active: bool
    bypass_hours_year: float      # ساعت بایپس در سال تخمینی
    bypass_compliance: bool       # انطباق با حداکثر مجاز
    recommendation: str


@dataclass
class LOPAResult:
    """تحلیل لایه‌های حفاظتی (Layer of Protection Analysis)."""
    unit: str
    hazard: str
    unmitigated_risk: float        # ریسک بدون لایه حفاظتی
    mitigated_risk: float          # ریسک با لایه‌های موجود
    risk_reduction_factor: float   # ضریب کاهش ریسک کل
    required_rrf: float            # RRF لازم برای رسیدن به ریسک قابل‌تحمل
    tolerable_risk: float          # ریسک قابل‌تحمل هدف
    layers_used: list[str]
    layers_compliant: int          # تعداد لایه‌های مستقل موافق
    gap: str                        # Compliant / Insufficient-layers / Excessive-PFD
    recommendation: str


@dataclass
class BypassEvent:
    """رویداد بایپس یک لایه حفاظتی."""
    unit: str
    layer: str
    start: str
    end: str | None
    duration_h: float
    reason: str
    authorized_by: str
    sil_target: int
    within_limit: bool


def _risk_label(score: float) -> str:
    if score >= 0.85:
        return "Low"
    if score >= 0.65:
        return "Medium"
    if score >= 0.45:
        return "High"
    return "Critical"


def _sil_from_pfd(pfd: float) -> int | None:
    """تعیین SIL محقق‌شده بر اساس PFD (IEC 61511)."""
    if pfd >= 1e-2:
        return 0  # زیر SIL 1
    for sil, (low, high, _, _) in SIL_TARGETS.items():
        if low <= pfd < high:
            return sil
    if pfd < 1e-5:
        return 4
    return None


def _sil_target_for_layer(layer: str) -> int:
    """SIL هدف بر اساس نوع لایه (IEC 61511 / LOPA معمول)."""
    targets = {
        "BPCS-Control": 1,
        "SIS-Interlock": 2,
        "ESD-Shutdown": 3,
        "Relief-Valve": 2,   # معمولاً passive، تخمین SIL 2
        "Procedural": 1,
    }
    return targets.get(layer, 1)


class BarrierHealthMonitor:
    """پایش پویای سلامت لایه‌های حفاظتی (IEC 61511)."""

    LAYER_WEIGHTS = {
        "BPCS-Control": 0.15,
        "SIS-Interlock": 0.30,
        "ESD-Shutdown": 0.30,
        "Relief-Valve": 0.15,
        "Procedural": 0.10,
    }

    def __init__(self,
                 decay_lambda: float = 0.0008,
                 bypass_penalty: float = 0.15,
                 min_health: float = 0.40,
                 simultaneous_bypass_threshold: int = 2,
                 tolerable_risk: float = 1e-5):
        self.decay_lambda = decay_lambda
        self.bypass_penalty = bypass_penalty
        self.min_health = min_health
        self.sim_threshold = simultaneous_bypass_threshold
        self.tolerable_risk = tolerable_risk

    def compute_layer_health(self, df: pd.DataFrame) -> list[LayerHealth]:
        """محاسبه سلامت هر لایه در یک لحظه یا میانگین بازه."""
        results: list[LayerHealth] = []
        for (unit, layer), g in df.groupby(["unit", "layer"]):
            base = float(g["health_score"].mean())
            bypass_active = bool(g["bypass_active"].any())
            days_since = float(g["days_since_test"].mean())
            test_ok_rate = float(g["last_test_result"].mean())
            drift = abs(float(g["sensor_drift"].mean()))
            resp_delay = float(g["response_delay_s"].mean())

            # کاهش نمایی سلامت با گذشت زمان از آخرین تست موفق
            decay = float(np.exp(-self.decay_lambda * days_since))
            health = base * (0.5 + 0.5 * decay) * (0.7 + 0.3 * test_ok_rate)
            health -= drift * 2.0
            health -= max(0.0, (resp_delay - 2.0)) * 0.05
            if bypass_active:
                health -= self.bypass_penalty
            health = float(np.clip(health, self.min_health, 1.0))

            # تخمین PFD با مدل Poisson
            lam = max(0.0, 1.0 - health) / 24
            pfd = float(np.clip(lam * days_since / 30.0, 1e-6, 1e-1))

            # تعیین SIL
            sil_achieved = _sil_from_pfd(pfd)
            sil_target = _sil_target_for_layer(layer)
            sil_gap = "OK" if (sil_achieved is not None and sil_achieved >= sil_target) else "Below-target"

            # زمان بایپس در سال (تخمین از bypass_duration_h اگر موجود)
            bypass_h_year = float(g.get("bypass_duration_h", pd.Series([0.0])).sum()) if bypass_active else 0.0
            max_bypass = MAX_BYPASS_H_PER_YEAR.get(sil_target, 4.0)
            bypass_compliance = bypass_h_year <= max_bypass

            risk = _risk_label(health)
            rec = self._recommendation(layer, bypass_active, days_since, test_ok_rate, health,
                                       sil_achieved, sil_target, bypass_compliance)
            results.append(LayerHealth(
                unit=unit, layer=layer,
                health_score=round(health, 4),
                bypass_penalty=round(self.bypass_penalty if bypass_active else 0.0, 4),
                pfd_estimate=round(pfd, 6),
                sil_achieved=sil_achieved,
                sil_target=sil_target,
                sil_gap=sil_gap,
                risk_level=risk,
                bypass_active=bypass_active,
                bypass_hours_year=round(bypass_h_year, 2),
                bypass_compliance=bypass_compliance,
                recommendation=rec,
            ))
        return results

    def aggregate_unit_risk(self, rows: list[LayerHealth]) -> dict[str, float]:
        """ریسک کل واحد به‌عنوان میانگین وزنی ۱ - سلامت."""
        by_unit: dict[str, list[LayerHealth]] = {}
        for r in rows:
            by_unit.setdefault(r.unit, []).append(r)
        out: dict[str, float] = {}
        for unit, items in by_unit.items():
            num = sum((1.0 - r.health_score) * self.LAYER_WEIGHTS.get(r.layer, 0.2) for r in items)
            den = sum(self.LAYER_WEIGHTS.get(r.layer, 0.2) for r in items)
            out[unit] = round(num / max(den, 1e-6), 4)
        return out

    def detect_simultaneous_weakness(self, df: pd.DataFrame) -> list[dict]:
        """شناسایی زمان‌هایی که چند لایه همزمان بایپس/ضعیف هستند."""
        df = df.copy()
        df["weak"] = ((df["bypass_active"]) | (df["health_score"] < 0.7)).astype(int)
        weak_groups = []
        for ts, g in df.groupby("timestamp"):
            n_weak = int(g["weak"].sum())
            if n_weak >= self.sim_threshold:
                weak_groups.append({
                    "timestamp": str(ts),
                    "unit": g["unit"].iloc[0] if "unit" in g else "unknown",
                    "weak_layers": g[g["weak"] == 1]["layer"].tolist(),
                    "weak_count": n_weak,
                    "severity": "Critical" if n_weak >= 3 else "High",
                })
        return weak_groups[:50]

    def _recommendation(self, layer: str, bypass: bool, days: float,
                        test_ok: float, health: float,
                        sil_achieved: int | None, sil_target: int,
                        bypass_compliance: bool) -> str:
        if bypass and not bypass_compliance:
            return (f"بایپس {layer} فراتر از حد مجاز SIL {sil_target}؛ "
                    f"بازگرداندن به خدمت یا compensating measure الزامی است.")
        if bypass:
            return f"بایپس فعال برای لایه {layer}؛ بازگرداندن به خدمت یا compensating measure الزامی است."
        if sil_achieved is not None and sil_achieved < sil_target:
            return (f"لایه {layer} به SIL هدف ({sil_target}) نمی‌رسد "
                    f"(محقق‌شده: SIL {sil_achieved})؛ بازنگری طراحی یا افزایش تست لازم است.")
        if days > 365:
            return f"بازرسی دوره‌ای {layer} به تأخیر افتاده ({days:.0f} روز)؛ برنامه‌ریزی فوری تست."
        if test_ok < 0.8:
            return f"نرخ عدم موفقیت تست {layer} بالاست؛ تحلیل RCA و بازنگری طراحی."
        if health < 0.6:
            return f"سلامت {layer} ضعیف است؛ بازرسی اضافی و آنالیز روندها."
        return f"لایه {layer} در وضعیت قابل‌قبول است؛ ادامه پایش دوره‌ای."

    # ============================================================
    # بهینه‌سازی فواصل تست (Risk-Based Inspection)
    # ============================================================
    def optimize_test_intervals(self, df: pd.DataFrame, base_interval_days: int = 365) -> pd.DataFrame:
        """پیشنهاد فاصله تست بر اساس ریسک پویا و SIL هدف."""
        rows = []
        for (unit, layer), g in df.groupby(["unit", "layer"]):
            base_health = float(g["health_score"].mean())
            test_ok = float(g["last_test_result"].mean())
            days_since = float(g["days_since_test"].mean())
            risk = (1.0 - base_health) * (1.5 - test_ok)
            sil_target = _sil_target_for_layer(layer)
            # فاصله پایه بر اساس SIL
            sil_base_days = SIL_TEST_INTERVAL_MONTHS.get(sil_target, 12) * 30
            # فاصله جدید = فاصله SIL × ضریب ریسک (ریسک بالا = فاصله کوتاه‌تر)
            factor = max(0.3, min(2.0, 1.0 - risk))
            new_interval = int(sil_base_days * factor)
            priority = "Immediate" if risk > 0.4 else ("High" if risk > 0.25 else "Normal")
            rows.append({
                "unit": unit, "layer": layer,
                "sil_target": sil_target,
                "current_interval_days": base_interval_days,
                "recommended_interval_days": new_interval,
                "days_since_test": int(days_since),
                "health_score": round(base_health, 4),
                "risk_score": round(risk, 4),
                "priority": priority,
            })
        return pd.DataFrame(rows).sort_values("risk_score", ascending=False).reset_index(drop=True)

    # ============================================================
    # LOPA — Layer of Protection Analysis
    # ============================================================
    def lopa_analysis(self, df: pd.DataFrame, hazard: str = "loss_of_containment",
                      unmitigated_freq_per_year: float = 1e-1) -> list[LOPAResult]:
        """تحلیل LOPA برای هر واحد: آیا لایه‌های حفاظتی کافی هستند؟"""
        results: list[LOPAResult] = []
        layers_health = self.compute_layer_health(df)
        by_unit: dict[str, list[LayerHealth]] = {}
        for r in layers_health:
            by_unit.setdefault(r.unit, []).append(r)
        for unit, items in by_unit.items():
            # RRF کل = حاصل‌ضرب RRF لایه‌های مستقل
            # RRF_layer = 1 / PFD
            total_rrf = 1.0
            layers_used = []
            compliant = 0
            for r in items:
                if r.pfd_estimate <= 0:
                    continue
                rrf_layer = 1.0 / r.pfd_estimate
                # فقط لایه‌های مستقل (PFD < 0.1 یعنی RRF > 10) شمارش می‌شوند
                if rrf_layer >= 10 and not r.bypass_active:
                    total_rrf *= rrf_layer
                    layers_used.append(r.layer)
                    if r.sil_achieved is not None and r.sil_achieved >= r.sil_target:
                        compliant += 1
            mitigated = unmitigated_freq_per_year / max(total_rrf, 1.0)
            required_rrf = unmitigated_freq_per_year / self.tolerable_risk
            if mitigated <= self.tolerable_risk:
                gap = "Compliant"
                rec = "لایه‌های حفاظتی کافی برای ریسک قابل‌تحمل."
            elif total_rrf < required_rrf * 0.5:
                gap = "Insufficient-layers"
                rec = (f"افزودن لایه حفاظتی مستقل یا افزایش SIL مورد نیاز است "
                       f"(RRF لازم: {required_rrf:.0f}، موجود: {total_rrf:.0f}).")
            else:
                gap = "Excessive-PFD"
                rec = "بررسی بازنگری PFD یا کاهش بایپس برای بهبود RRF."
            results.append(LOPAResult(
                unit=unit, hazard=hazard,
                unmitigated_risk=round(unmitigated_freq_per_year, 6),
                mitigated_risk=round(mitigated, 6),
                risk_reduction_factor=round(total_rrf, 1),
                required_rrf=round(required_rrf, 1),
                tolerable_risk=self.tolerable_risk,
                layers_used=layers_used,
                layers_compliant=compliant,
                gap=gap,
                recommendation=rec,
            ))
        return results

    # ============================================================
    # مدیریت رویداد بایپس
    # ============================================================
    def bypass_events(self, df: pd.DataFrame) -> list[BypassEvent]:
        """استخراج رویدادهای بایپس با محاسبه مدت زمان و انطباق با SIL."""
        events: list[BypassEvent] = []
        df = df.copy()
        if "bypass_active" not in df.columns:
            return events
        for (unit, layer), g in df.groupby(["unit", "layer"]):
            sil_target = _sil_target_for_layer(layer)
            max_bypass = MAX_BYPASS_H_PER_YEAR.get(sil_target, 4.0)
            bypass_rows = g[g["bypass_active"]]
            if len(bypass_rows) == 0:
                continue
            dur = float(bypass_rows.get("bypass_duration_h", pd.Series([0.0])).sum())
            reason = str(bypass_rows.get("bypass_reason", "Unknown").iloc[0]) if "bypass_reason" in bypass_rows.columns else "Unknown"
            authorized = str(bypass_rows.get("authorized_by", "Unknown").iloc[0]) if "authorized_by" in bypass_rows.columns else "Unknown"
            start_ts = bypass_rows["timestamp"].min() if "timestamp" in bypass_rows.columns else "Unknown"
            end_ts = bypass_rows["timestamp"].max() if "timestamp" in bypass_rows.columns else None
            events.append(BypassEvent(
                unit=unit, layer=layer,
                start=str(start_ts), end=str(end_ts) if end_ts else None,
                duration_h=round(dur, 2),
                reason=reason, authorized_by=authorized,
                sil_target=sil_target,
                within_limit=dur <= max_bypass,
            ))
        return events
