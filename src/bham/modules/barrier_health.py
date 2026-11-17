"""ماژول ۲: پایش سلامت لایه‌های حفاظتی و مدیریت بایپس.

الگوریتم‌ها:
  - تجمیع وزنی شاخص‌های هر لایه (IEC 61511)
  - کاهش نمایی برای اثر گذشت زمان از آخرین تست
  - جریمه بایپس و غیرفعال‌سازی همزمان
  - شناسایی تجمع ضعف‌ها (ماتریس وابستگی لایه‌ها)
  - تخمین PFD (Probability of Failure on Demand) با فرض Poisson
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass
class LayerHealth:
    unit: str
    layer: str
    health_score: float          # 0..1
    bypass_penalty: float        # 0..1
    pfd_estimate: float         # probability of failure on demand
    risk_level: str              # Low / Medium / High / Critical
    recommendation: str


def _risk_label(score: float) -> str:
    if score >= 0.85:
        return "Low"
    if score >= 0.65:
        return "Medium"
    if score >= 0.45:
        return "High"
    return "Critical"


class BarrierHealthMonitor:
    """پایش پویای سلامت لایه‌های حفاظتی."""

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
                 simultaneous_bypass_threshold: int = 2):
        self.decay_lambda = decay_lambda
        self.bypass_penalty = bypass_penalty
        self.min_health = min_health
        self.sim_threshold = simultaneous_bypass_threshold

    def compute_layer_health(self, df: pd.DataFrame) -> list[LayerHealth]:
        """محاسبه سلامت هر لایه در یک لحظه یا میانگین بازه."""
        results: list[LayerHealth] = []
        for (unit, layer), g in df.groupby(["unit", "layer"]):
            base = float(g["health_score"].mean())
            bypass_active = bool(g["bypass_active"].any())
            days_since = float(g["days_since_test"].mean())
            test_ok_rate = float(g["last_test_result"].mean())  # کسر تست‌های ناموفق
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

            # تخمین PFD با مدل Poisson ساده: PFD ≈ λ * test_interval
            # با فرض نرخ خرابی λ متناسب با افت سلامت
            lam = max(0.0, 1.0 - health) / 24  # هر ساعت یک تقریب
            pfd = float(np.clip(lam * days_since / 30.0, 1e-6, 1e-1))

            risk = _risk_label(health)
            rec = self._recommendation(layer, bypass_active, days_since, test_ok_rate, health)
            results.append(LayerHealth(
                unit=unit, layer=layer,
                health_score=round(health, 4),
                bypass_penalty=round(self.bypass_penalty if bypass_active else 0.0, 4),
                pfd_estimate=round(pfd, 6),
                risk_level=risk,
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
                        test_ok: float, health: float) -> str:
        if bypass:
            return f"بایپس فعال برای لایه {layer}؛ بازگرداندن به خدمت یا compensating measure الزامی است."
        if days > 365:
            return f"بازرسی دوره‌ای {layer} به تأخیر افتاده ({days:.0f} روز)؛ برنامه‌ریزی فوری تست."
        if test_ok < 0.8:
            return f"نرخ عدم موفقیت تست {layer} بالاست؛ تحلیل RCA و بازنگری طراحی."
        if health < 0.6:
            return f"سلامت {layer} ضعیف است؛ بازرسی اضافی و آنالیز روندها."
        return f"لایه {layer} در وضعیت قابل‌قبول است؛ ادامه پایش دوره‌ای."

    # ---- بهینه‌سازی فواصل تست (Risk-Based Inspection) ----
    def optimize_test_intervals(self, df: pd.DataFrame, base_interval_days: int = 365) -> pd.DataFrame:
        """پیشنهاد فاصله تست بر اساس ریسک پویا."""
        rows = []
        for (unit, layer), g in df.groupby(["unit", "layer"]):
            base_health = float(g["health_score"].mean())
            test_ok = float(g["last_test_result"].mean())
            days_since = float(g["days_since_test"].mean())
            risk = (1.0 - base_health) * (1.5 - test_ok)
            # فاصله جدید = فاصله پایه × ضریب ریسک (ریسک بالا = فاصله کوتاه‌تر)
            factor = max(0.3, min(2.0, 1.0 - risk))
            new_interval = int(base_interval_days * factor)
            priority = "Immediate" if risk > 0.4 else ("High" if risk > 0.25 else "Normal")
            rows.append({
                "unit": unit, "layer": layer,
                "current_interval_days": base_interval_days,
                "recommended_interval_days": new_interval,
                "days_since_test": int(days_since),
                "health_score": round(base_health, 4),
                "risk_score": round(risk, 4),
                "priority": priority,
            })
        return pd.DataFrame(rows).sort_values("risk_score", ascending=False).reset_index(drop=True)
