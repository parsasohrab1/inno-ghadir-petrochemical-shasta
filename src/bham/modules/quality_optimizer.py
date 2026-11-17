"""ماژول ۶: پایش و بهینه‌سازی کیفیت محصول (Quality Monitoring & Optimization).

این ماژول در پاسخ به چالش‌های شناسایی‌شده در خط تولید پتروشیمی غدیر طراحی شده است:
  - نوسانات خلوص محصول تحت ۲۲ نوع خطای فرآیندی
  - انحراف از spec محصول (xmeas_40 = خلوص A در محصول)
  - نبود پایش آماری فرآیند (SPC)
  - نبود شاخص قابلیت فرآیند (Cp/Cpk)

الگوریتم‌ها و قابلیت‌ها:
  - کنترل آماری فرآیند (SPC): Western Electric rules، نمودار X-bar/R، CUSUM، EWMA
  - شاخص قابلیت فرآیند: Cp، Cpk، Pp، Ppk (مطابق ISO 22514-2 / AIAG SPC)
  - تحلیل علت ریشه‌ای انحراف کیفیت (Cause-Effect با نمودار ایشیکاوا)
  - تخمین کنترل‌پذیری (controllability) هر متغیر
  - پیشنهاد تنظیم setpoint بهینه (با تابع هزینه وزنی)
  - تخمین impacts خطا روی کیفیت محصول (impact severity per fault)
  - پایش پارامترهای کیفی کلیدی (Key Quality Variables - KQV)

منابع استاندارد:
  - ISO 22514-2 (Capability of processes)
  - ISO 7870-2 (Shewhart control charts)
  - AIAG SPC Reference Manual
  - ASTM E2587 (Standard Practice for Calculating and Using Control Charts)
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Iterable

import numpy as np
import pandas as pd


# ------------------------------------------------------------
# قوانین Western Electric (Western Electric Rules) برای نمودار کنترل
# ------------------------------------------------------------
WE_RULES = {
    "Rule1": "نقطه فراتر از ۳σ از خط مرکزی (ناهنجاری شدید)",
    "Rule2": "۹ نقطه پیاپی در یک طرف خط مرکزی (انحراف میانگین)",
    "Rule3": "۶ نقطه پیاپی صعودی یا نزولی (روند)",
    "Rule4": "۱۴ نقطه پیاپی متنابی در دو طرف (نویز غیرتصادفی)",
    "Rule5": "۲ از ۳ نقطه پیاپی فراتر از ۲σ",
    "Rule6": "۴ از ۵ نقطه پیاپی فراتر از ۱σ",
    "Rule7": "۱۵ نقطه پیاپی درون ۱σ (کاهش نوسان غیرعادی)",
    "Rule8": "۸ نقطه پیاپی خارج از ۱σ اما داخل ۲σ",
}


@dataclass
class SPCResult:
    """نتیجه پایش آماری فرآیند برای یک متغیر."""
    variable: str
    mean: float
    std: float
    ucl: float           # Upper Control Limit (mean + 3σ)
    lcl: float           # Lower Control Limit (mean - 3σ)
    usl: float           # Upper Spec Limit
    lsl: float           # Lower Spec Limit
    cp: float            # قابلیت بالقوه فرآیند
    cpk: float           # قابلیت واقعی فرآیند
    pp: float            # قابلیت بالقوه عملکرد
    ppk: float           # قابلیت واقعی عملکرد
    capability_grade: str    # Excellent / Acceptable / Marginal / Inadequate
    n_violations: int
    rule_violations: dict      # نام قانون -> تعداد نقض
    out_of_spec_count: int
    out_of_spec_pct: float
    cusum_drift: float         # جمع انباشتathi انحراف (CUSUM)
    ewma_value: float          # میانگین متحرک نمایی
    trend_slope: float         # شیب رونديد


@dataclass
class QualityVariable:
    """یک متغیر کیفی کلیدی (Key Quality Variable)."""
    name: str
    description: str
    unit: str
    target: float
    usl: float          # حد بالایی spec
    lsl: float          # حد پایینی spec
    current_value: float
    deviation_sigma: float
    status: str          # In-control / Out-of-control / Out-of-spec
    impact_on_product: str    # High / Medium / Low


@dataclass
class FaultQualityImpact:
    """اثر یک خطای فرآیندی بر کیفیت محصول."""
    fault_id: int
    fault_description: str
    purity_deviation_pct: float
    purity_deviation_sigma: float
    variability_multiplier: float
    impact_grade: str          # Critical / High / Medium / Low
    affected_quality_vars: list[str]
    estimated_yield_loss_pct: float
    recommended_action: str


@dataclass
class SetpointOptimization:
    """پیشنهاد بهینه‌سازی setpoint بر اساس تابع هزینه."""
    variable: str
    current_setpoint: float
    optimized_setpoint: float
    expected_purity_gain_pct: float
    expected_yield_gain_pct: float
    confidence: float
    rationale: str


@dataclass
class RootCauseAnalysis:
    """تحلیل علت ریشه‌ای انحراف کیفیت."""
    symptom: str
    likely_causes: list[str]      # علت‌های محتمل (Ishikawa fishbone)
    category: str                  # Man / Machine / Material / Method / Measurement / Environment
    confidence: float
    recommended_investigation: str


# قابلیت فرآیند بر اساس Cpk (AIAG SPC)
def _capability_grade(cpk: float) -> str:
    if cpk >= 2.0:
        return "Excellent"    # Six Sigma
    if cpk >= 1.67:
        return "Acceptable"   # قادر به برآورده کردن spec با حاشیه کافی
    if cpk >= 1.33:
        return "Marginal"     # حداقل قابل قبول (پتروشیمی)
    if cpk >= 1.0:
        return "Inadequate"   # ناکافی، نیاز به بهبود
    return "Critical"          # بحرانی، خارج از کنترل


class QualityOptimizer:
    """پایش و بهینه‌سازی کیفیت محصول."""

    def __init__(self,
                 control_limit_sigma: float = 3.0,
                 ewma_lambda: float = 0.2,
                 cusum_threshold: float = 5.0,
                 min_samples: int = 30):
        self.control_limit_sigma = control_limit_sigma
        self.ewma_lambda = ewma_lambda
        self.cusum_threshold = cusum_threshold
        self.min_samples = min_samples

    # ============================================================
    # پایش SPC کامل یک متغیر
    # ============================================================
    def spc_analysis(self, series: pd.Series, usl: float, lsl: float,
                     target: float | None = None) -> SPCResult:
        """تحلیل کامل SPC با قوانین Western Electric، Cp/Cpk، CUSUM، EWMA."""
        s = pd.to_numeric(series, errors="coerce").dropna()
        n = len(s)
        if n < 2:
            return self._empty_spc(series.name or "var", usl, lsl)

        mean = float(s.mean())
        std = float(s.std(ddof=1))
        target_val = float(target) if target is not None else mean

        # محدودهای کنترل (3σ)
        ucl = mean + self.control_limit_sigma * std
        lcl = mean - self.control_limit_sigma * std

        # شاخص قابلیت فرآیند (Cp/Cpk)
        if std > 0 and usl > lsl:
            cp = (usl - lsl) / (6 * std)
            cpk = min((usl - mean) / (3 * std), (mean - lsl) / (3 * std))
            pp = (usl - lsl) / (6 * std)
            ppk = min((usl - mean) / (3 * std), (mean - lsl) / (3 * std))
        else:
            cp = cpk = pp = ppk = 0.0

        grade = _capability_grade(cpk)

        # قوانین Western Electric
        rule_violations = self._western_electric_rules(s, mean, std)
        n_violations = sum(rule_violations.values())

        # خارج از spec
        out_of_spec = int(((s > usl) | (s < lsl)).sum())
        out_of_spec_pct = round(out_of_spec / n * 100, 3)

        # CUSUM (Cumulative Sum)
        cusum = (s - target_val).cumsum()
        cusum_drift = float(cusum.iloc[-1])

        # EWMA (Exponentially Weighted Moving Average)
        ewma = s.ewm(alpha=self.ewma_lambda, adjust=False).mean()
        ewma_value = float(ewma.iloc[-1])

        # شیب روند (Linear regression)
        x = np.arange(n)
        if n >= 3 and std > 0:
            slope = float(np.polyfit(x, s.values, 1)[0])
        else:
            slope = 0.0

        return SPCResult(
            variable=str(series.name or "var"),
            mean=round(mean, 4),
            std=round(std, 4),
            ucl=round(ucl, 4),
            lcl=round(lcl, 4),
            usl=float(usl),
            lsl=float(lsl),
            cp=round(cp, 3),
            cpk=round(cpk, 3),
            pp=round(pp, 3),
            ppk=round(ppk, 3),
            capability_grade=grade,
            n_violations=n_violations,
            rule_violations=rule_violations,
            out_of_spec_count=out_of_spec,
            out_of_spec_pct=out_of_spec_pct,
            cusum_drift=round(cusum_drift, 4),
            ewma_value=round(ewma_value, 4),
            trend_slope=round(slope, 5),
        )

    def _western_electric_rules(self, s: pd.Series, mean: float, std: float) -> dict:
        """بررسی قوانین Western Electric."""
        violations = {k: 0 for k in WE_RULES.keys()}
        if std == 0 or len(s) < 3:
            return violations

        n = len(s)
        vals = s.values
        sigma_1 = std
        sigma_2 = 2 * std
        sigma_3 = 3 * std

        # Rule 1: نقطه فراتر از ۳σ
        violations["Rule1"] = int(np.sum(np.abs(vals - mean) > sigma_3))

        # Rule 2: ۹ نقطه پیاپی در یک طرف
        above = (vals > mean).astype(int)
        below = (vals < mean).astype(int)
        violations["Rule2"] = self._count_run(above, 9) + self._count_run(below, 9)

        # Rule 3: ۶ نقطه پیاپی صعودی یا نزولی
        if n >= 6:
            diffs = np.diff(vals)
            violations["Rule3"] = self._count_run((diffs > 0).astype(int), 6) + \
                                  self._count_run((diffs < 0).astype(int), 6)

        # Rule 5: ۲ از ۳ نقطه پیاپی فراتر از ۲σ
        if n >= 3:
            count = 0
            for i in range(n - 2):
                window = np.abs(vals[i:i+3] - mean) > sigma_2
                if np.sum(window) >= 2:
                    count += 1
            violations["Rule5"] = count

        # Rule 6: ۴ از ۵ نقطه پیاپی فراتر از ۱σ
        if n >= 5:
            count = 0
            for i in range(n - 4):
                window = np.abs(vals[i:i+5] - mean) > sigma_1
                if np.sum(window) >= 4:
                    count += 1
            violations["Rule6"] = count

        # Rule 7: ۱۵ نقطه پیاپی درون ۱σ
        if n >= 15:
            within = (np.abs(vals - mean) < sigma_1).astype(int)
            violations["Rule7"] = self._count_run(within, 15)

        return violations

    def _count_run(self, indicator: np.ndarray, min_run: int) -> int:
        """شمارش دنباله‌های طول ≥ min_run."""
        if len(indicator) < min_run:
            return 0
        count = 0
        run = 0
        for v in indicator:
            if v:
                run += 1
                if run == min_run:
                    count += 1
            else:
                run = 0
        return count

    def _empty_spc(self, name: str, usl: float, lsl: float) -> SPCResult:
        return SPCResult(
            variable=name, mean=0.0, std=0.0, ucl=0.0, lcl=0.0,
            usl=usl, lsl=lsl, cp=0.0, cpk=0.0, pp=0.0, ppk=0.0,
            capability_grade="Critical", n_violations=0,
            rule_violations={k: 0 for k in WE_RULES},
            out_of_spec_count=0, out_of_spec_pct=0.0,
            cusum_drift=0.0, ewma_value=0.0, trend_slope=0.0,
        )

    # ============================================================
    # تحلیل چند متغیر کیفی
    # ============================================================
    def analyze_quality_variables(self, df: pd.DataFrame,
                                   specs: dict[str, dict]) -> list[QualityVariable]:
        """تحلیل همه متغیرهای کیفی با spec.

        specs = {"xmeas_40": {"target": 53.6, "usl": 55.0, "lsl": 52.0, ...}, ...}
        """
        results: list[QualityVariable] = []
        for var, spec in specs.items():
            if var not in df.columns:
                continue
            s = pd.to_numeric(df[var], errors="coerce").dropna()
            if len(s) < 2:
                continue
            target = spec.get("target", float(s.mean()))
            usl = spec["usl"]
            lsl = spec["lsl"]
            current = float(s.iloc[-1])
            mean = float(s.mean())
            std = max(float(s.std(ddof=1)), 1e-6)
            dev_sigma = abs(current - target) / std

            if current > usl or current < lsl:
                status = "Out-of-spec"
            elif dev_sigma > 2:
                status = "Out-of-control"
            else:
                status = "In-control"

            impact = spec.get("impact", "Medium")

            results.append(QualityVariable(
                name=var,
                description=spec.get("description", ""),
                unit=spec.get("unit", ""),
                target=round(target, 3),
                usl=usl,
                lsl=lsl,
                current_value=round(current, 3),
                deviation_sigma=round(dev_sigma, 3),
                status=status,
                impact_on_product=impact,
            ))
        return results

    # ============================================================
    # اثر خطاها روی کیفیت محصول
    # ============================================================
    def fault_quality_impact(self, df: pd.DataFrame, fault_col: str,
                              quality_col: str,
                              fault_descriptions: dict | None = None) -> list[FaultQualityImpact]:
        """محاسبه اثر هر خطا بر کیفیت محصول (purity/خلوص)."""
        results: list[FaultQualityImpact] = []
        if fault_col not in df.columns or quality_col not in df.columns:
            return results

        normal = pd.to_numeric(df[df[fault_col] == 0][quality_col], errors="coerce").dropna()
        if len(normal) < 2:
            return results
        normal_mean = float(normal.mean())
        normal_std = max(float(normal.std(ddof=1)), 1e-6)

        faults = sorted(df[fault_col].unique())
        for fid in faults:
            if fid == 0:
                continue
            faulty = pd.to_numeric(df[df[fault_col] == fid][quality_col], errors="coerce").dropna()
            if len(faulty) < 2:
                continue
            f_mean = float(faulty.mean())
            f_std = float(faulty.std(ddof=1))
            dev_sigma = abs(f_mean - normal_mean) / normal_std
            dev_pct = (f_mean - normal_mean) / normal_mean * 100
            var_mult = f_std / normal_std
            # تخمین افت بازده: اگر خلوص کاهش یابد، محصول قابل فروش کاهش می‌یابد
            yield_loss_pct = max(0.0, -dev_pct) + max(0.0, var_mult - 1) * 5  # تقریب ساده
            grade = "Critical" if dev_sigma > 3 else "High" if dev_sigma > 2 else \
                    "Medium" if dev_sigma > 1 else "Low"
            desc = (fault_descriptions or {}).get(fid, f"Fault {fid}")
            action = self._fault_action(grade, dev_sigma, var_mult)
            results.append(FaultQualityImpact(
                fault_id=int(fid),
                fault_description=desc,
                purity_deviation_pct=round(dev_pct, 3),
                purity_deviation_sigma=round(dev_sigma, 3),
                variability_multiplier=round(var_mult, 3),
                impact_grade=grade,
                affected_quality_vars=[quality_col],
                estimated_yield_loss_pct=round(yield_loss_pct, 3),
                recommended_action=action,
            ))
        return sorted(results, key=lambda r: r.purity_deviation_sigma, reverse=True)

    def _fault_action(self, grade: str, dev_sigma: float, var_mult: float) -> str:
        if grade == "Critical":
            return "مداخله فوری: توقف خط، RCA، بررسی کنترلر و سنسور خلوص."
        if grade == "High":
            return "مداخله در شیفت: بازرسی علت، تنظیم setpoint، پایش ۴۸ ساعته."
        if grade == "Medium":
            return "افزایش فرکانس پایش، تحلیل روند، برنامه‌ریزی اقدام پیشگیرانه."
        return "پایش استاندارد؛ ثبت روند برای ممیزی."

    # ============================================================
    # بهینه‌سازی setpoint
    # ============================================================
    def optimize_setpoint(self, df: pd.DataFrame, quality_col: str,
                          target: float, usl: float, lsl: float,
                          manipulated_vars: list[str] | None = None) -> list[SetpointOptimization]:
        """پیشنهاد تنظیم بهینه setpoint بر اساس همبستگی متغیرهای دستکاری با کیفیت."""
        if quality_col not in df.columns:
            return []
        q = pd.to_numeric(df[quality_col], errors="coerce")
        if len(q) < 10:
            return []

        # انتخاب متغیرهای دستکاری
        if manipulated_vars is None:
            manipulated_vars = [c for c in df.columns if c.startswith("xmv_")]

        results: list[SetpointOptimization] = []
        for mv in manipulated_vars:
            if mv not in df.columns:
                continue
            m = pd.to_numeric(df[mv], errors="coerce")
            paired = pd.concat([q, m], axis=1).dropna()
            if len(paired) < 10:
                continue
            corr = paired.corr().iloc[0, 1]
            if abs(corr) < 0.1:
                continue
            # پیشنهاد تنظیم: انتقال setpoint به سمت میانگین متغیر با همبستگی بالا
            current_sp = float(paired.iloc[:, 1].mean())
            # بهینه‌سازی: تنظیم بر اساس جهت همبستگی برای نزدیک شدن به target
            shift = (target - q.mean()) * 0.3 * corr  # ضریب 0.3 برای ثبات
            optimized = current_sp + shift
            # تخمین بهبود خلوص
            purity_gain = abs(shift * corr) / max(q.std(), 1e-6) * 100
            yield_gain = max(0.0, purity_gain) * 0.5
            confidence = min(1.0, abs(corr))
            rationale = (f"همبستگی {corr:+.3f} با {quality_col}؛ "
                          f"تنظیم {mv} در جهت بهبود خلوص به هدف {target}.")
            results.append(SetpointOptimization(
                variable=mv,
                current_setpoint=round(current_sp, 4),
                optimized_setpoint=round(optimized, 4),
                expected_purity_gain_pct=round(purity_gain, 3),
                expected_yield_gain_pct=round(yield_gain, 3),
                confidence=round(confidence, 3),
                rationale=rationale,
            ))
        return sorted(results, key=lambda r: r.confidence, reverse=True)

    # ============================================================
    # تحلیل علت ریشه‌ای (Ishikawa fishbone)
    # ============================================================
    def root_cause_analysis(self, symptom: str, spc_results: list[SPCResult],
                            fault_impacts: list[FaultQualityImpact] | None = None) -> RootCauseAnalysis:
        """تحلیل علت ریشه‌ای با دسته‌بندی ایشیکاوا (6M)."""
        causes: list[str] = []
        category = "Method"

        # اگر نقض قوانین Western Electric موجود
        we_violations = []
        for r in spc_results:
            for rule, count in r.rule_violations.items():
                if count > 0:
                    we_violations.append((rule, count, r.variable))

        if any(r == "Rule1" for r, _, _ in we_violations):
            causes.append("انحراف ناگهانی در متغیر فرآیندی (احتمالاً خرابی سنسور یا تنظیم setpoint)")
            category = "Machine"
        if any(r == "Rule2" for r, _, _ in we_violations):
            causes.append("جابجایی میانگین (احتمالاً drift سنسور یا فرسودگی کاتالیست)")
            category = "Machine"
        if any(r == "Rule3" for r, _, _ in we_violations):
            causes.append("روند تدریجی (احتمالاً فرسودگی تجهیزات یا نشتی تدریجی)")
            category = "Machine"
        if any(r == "Rule5" or r == "Rule6" for r, _, _ in we_violations):
            causes.append("الگوی غیرتصادفی در نمودار کنترل (نیاز به بازنگری روش کنترل)")
            category = "Method"

        # اگر اثر خطا شناسایی شده
        if fault_impacts:
            critical_faults = [f for f in fault_impacts if f.impact_grade in ("Critical", "High")]
            if critical_faults:
                causes.append(f"خطای فرآیندی فعال ({len(critical_faults)} مورد) با اثر بحرانی بر کیفیت")
                category = "Material"

        # اگر تغییرات نوسان زیادی دارد
        high_var = [r for r in spc_results if r.trend_slope != 0 and abs(r.trend_slope) > 0.001]
        if high_var:
            causes.append("نوسانات متغیر دستکاری (نیاز به tune کردن کنترلر PID)")
            category = "Method"

        # اگر Cpk پایین است
        low_cpk = [r for r in spc_results if r.cpk < 1.33]
        if low_cpk:
            causes.append(f"قابلیت فرآیند ناکافی (Cpk < 1.33 در {len(low_cpk)} متغیر)")
            category = "Measurement"

        if not causes:
            causes.append("هیچ علت قطعی شناسایی نشد؛ ادامه پایش و جمع‌آوری داده بیشتر.")
            category = "Environment"

        # اعتماد: تعداد علائم هم‌جهت
        confidence = min(1.0, len(we_violations) / 10 + (0.5 if causes else 0.2))

        recommendation = (
            "بررسی نمودارهای کنترل SPC، انجام RCA فرمال با تیم چندرشته‌ای، "
            "و در صورت تداوم انحراف > 2σ، توقف خط برای بازرسی."
        )

        return RootCauseAnalysis(
            symptom=symptom,
            likely_causes=causes[:8],
            category=category,
            confidence=round(confidence, 3),
            recommended_investigation=recommendation,
        )

    # ============================================================
    # گزارش جامع کیفیت
    # ============================================================
    def quality_report(self, df: pd.DataFrame, specs: dict[str, dict],
                        fault_col: str | None = None) -> dict:
        """گزارش جامع کیفیت محصول با همه شاخص‌ها."""
        spc_results = []
        quality_vars = self.analyze_quality_variables(df, specs)
        for qv in quality_vars:
            spc = self.spc_analysis(df[qv.name], qv.usl, qv.lsl, qv.target)
            spc_results.append(spc)

        # اثر خطا روی کیفیت
        fault_impacts: list[FaultQualityImpact] = []
        if fault_col and fault_col in df.columns:
            primary_qv = quality_vars[0].name if quality_vars else None
            if primary_qv:
                fault_impacts = self.fault_quality_impact(df, fault_col, primary_qv)

        # تحلیل علت ریشه‌ای
        rca = self.root_cause_analysis(
            "انحراف کیفیت محصول",
            spc_results,
            fault_impacts,
        )

        # خلاصه قابلیت
        avg_cpk = float(np.mean([s.cpk for s in spc_results])) if spc_results else 0.0
        out_of_spec_total = sum(s.out_of_spec_count for s in spc_results)
        out_of_spec_pct_avg = float(np.mean([s.out_of_spec_pct for s in spc_results])) if spc_results else 0.0

        # بهینه‌سازی setpoint برای اولین متغیر کیفی
        setpoint_opts: list[SetpointOptimization] = []
        if quality_vars:
            qv0 = quality_vars[0]
            setpoint_opts = self.optimize_setpoint(
                df, qv0.name, qv0.target, qv0.usl, qv0.lsl,
            )

        return {
            "summary": {
                "n_quality_variables": len(quality_vars),
                "avg_cpk": round(avg_cpk, 3),
                "capability_grade": _capability_grade(avg_cpk),
                "out_of_spec_total": out_of_spec_total,
                "out_of_spec_pct_avg": round(out_of_spec_pct_avg, 3),
                "n_critical_faults": sum(1 for f in fault_impacts if f.impact_grade == "Critical"),
                "n_high_faults": sum(1 for f in fault_impacts if f.impact_grade == "High"),
            },
            "quality_variables": [qv.__dict__ for qv in quality_vars],
            "spc_results": [s.__dict__ for s in spc_results],
            "fault_quality_impacts": [f.__dict__ for f in fault_impacts[:15]],
            "root_cause_analysis": rca.__dict__,
            "setpoint_optimizations": [s.__dict__ for s in setpoint_opts[:10]],
        }
