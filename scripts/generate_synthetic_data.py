"""تولید داده مصنوعی برای سامانه هوشمند مدیریت آلارم و پایش سلامت
لایه‌های حفاظتی ایمنی فرآیند (BHAM) - پتروشیمی غدیر.

این ماژول چهار مجموعه داده می‌سازد که هرکدام برای یکی از ماژول‌های AI است:
  1) alarms.csv        — لاگ آلارم‌ها و رخدادها (DCS / SIS / ESD)
  2) barriers.csv      — وضعیت لایه‌های حفاظتی، بایپس‌ها و نتایج تست دوره‌ای
  3) sequences.csv     — توالی‌های رخداد منتهی به توقف/ناایمن
  4) risk_signals.csv  — سیگنال‌های عملیاتی و خرابی برای ریسک پویا

نویسنده: تیم پتروپالاتوس
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(seed=1405)

# مسیرها
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
DATA_DIR = REPO_ROOT / "data" / "synthetic"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# واحدهای فرآیندی پتروشیمی غدیر (شبیه‌سازی شده)
UNITS = ["Olefins-Unit", "Aromatics-Unit", "Utility-Unit", "Storage-Tank-Farm", "Polymer-Unit"]
TAG_PREFIXES = ["FT", "PT", "TT", "LT", "FV", "PV", "TV", "LS", "PS", "ZT"]

# ۵۴ آلارم نمونه روی تگ‌های مختلف
ALARM_TAGS = [f"{p}{i:03d}_{u[:3].upper()}" for u in UNITS for p in TAG_PREFIXES for i in range(1, 3)][:120]


def _ts(start: pd.Timestamp, periods: int, freq: str = "min") -> pd.DatetimeIndex:
    return pd.date_range(start=start, periods=periods, freq=freq)


# تبدیل تاریخ شمسی تقریبی به میلادی: ۱۴۰۳/۰۱/۰۱ ≈ ۲۰۲۴-۰۳-۲۰
# (پانداس از تاریخ‌های شمسی پشتیبانی نمی‌کند؛ در لاگ‌ها برچسب شمسی جداگانه ذخیره می‌شود)
SHAMSI_START_GREG = "2024-03-20"


def generate_alarms(n: int = 25000, start: str = "1403-01-01") -> pd.DataFrame:
    """لاگ آلارم با ویژگی‌های واقع‌گرایانه:
       چترینگ (chattering)، آلارم‌های ثابت‌مانده، آلارم‌های همزمان، علت مشترک."""
    starts = pd.to_datetime(SHAMSI_START_GREG, utc=False)
    times = np.asarray(starts + pd.to_timedelta(RNG.integers(0, n, size=n), unit="min"))
    tags = np.array(RNG.choice(ALARM_TAGS, size=n), dtype=object)
    priorities = np.array(RNG.choice(["Low", "Medium", "High", "Critical"], size=n, p=[0.55, 0.30, 0.12, 0.03]), dtype=object)
    statuses = np.array(RNG.choice(["Active", "Acknowledged", "Cleared"], size=n, p=[0.20, 0.20, 0.60]), dtype=object)

    # تزریق الگوهای شناخته‌شده برای ارزیابی الگوریتم‌ها
    # ۱) چترینگ: یک تگ، چندین آلارم پشت سر هم
    chat_idx = np.sort(RNG.choice(n, size=400, replace=False))
    times[chat_idx] = times[chat_idx[0]]
    tags[chat_idx] = "PT007_OLF"

    # ۲) آلارم ثابت‌مانده (stale)
    stale_idx = np.sort(RNG.choice(n, size=80, replace=False))
    statuses[stale_idx] = "Active"
    priorities[stale_idx] = "Medium"

    # ۳) علت مشترک: همزمانی چند آلارم
    root_idx = np.sort(RNG.choice(n, size=30, replace=False))
    for ri in root_idx:
        siblings = np.clip(ri + RNG.integers(1, 6, size=4), 0, n - 1)
        times[siblings] = times[ri]

    df = pd.DataFrame({
        "timestamp": times,
        "tag": tags,
        "priority": priorities,
        "status": statuses,
        "unit": [t.split("_")[-1] for t in tags],
        "value": np.round(RNG.normal(50, 10, n), 2),
        "setpoint": np.round(RNG.normal(50, 5, n), 2),
    }).sort_values("timestamp").reset_index(drop=True)
    df["ack_delay_sec"] = RNG.integers(1, 600, size=n)
    df["clear_delay_sec"] = RNG.integers(5, 1800, size=n)
    df["operator"] = RNG.choice(["OP-A", "OP-B", "OP-C", "OP-D"], size=n)
    return df


def generate_barriers(periods: int = 8760) -> pd.DataFrame:
    """وضعیت لایه‌های حفاظتی (BPCS, SIS, ESD, Relief, Procedural)."""
    layers = ["BPCS-Control", "SIS-Interlock", "ESD-Shutdown", "Relief-Valve", "Procedural"]
    rows = []
    ts = _ts(pd.Timestamp(SHAMSI_START_GREG), periods, freq="h")
    for unit in UNITS:
        for layer in layers:
            base_health = RNG.uniform(0.78, 0.99)
            for i, t in enumerate(ts):
                # افت سلامت به مرور زمان + نویز
                drift = -0.0008 * i
                noise = RNG.normal(0, 0.01)
                health = float(np.clip(base_health + drift + noise, 0.4, 1.0))
                bypass = bool(RNG.random() < (0.02 if layer != "Procedural" else 0.05))
                test_result = int(RNG.choice([1, 1, 1, 0], p=[0.7, 0.1, 0.1, 0.1]))
                rows.append({
                    "timestamp": t,
                    "unit": unit,
                    "layer": layer,
                    "health_score": round(health, 4),
                    "bypass_active": bypass,
                    "bypass_duration_h": float(RNG.integers(0, 8)) if bypass else 0.0,
                    "last_test_result": test_result,
                    "days_since_test": int(RNG.integers(1, 365)),
                    "sensor_drift": round(float(RNG.normal(0, 0.02)), 4),
                    "response_delay_s": round(float(RNG.normal(2.0, 0.6)), 3),
                })
    return pd.DataFrame(rows)


def generate_sequences(n: int = 4000) -> pd.DataFrame:
    """توالی‌های رخداد که برخی منجر به توقف/ناایمن می‌شوند (برای یادگیری الگو)."""
    event_types = ["Temp-High", "Pressure-Low", "Level-High", "Flow-Low",
                   "Vibration-High", "Composition-Off", "Bypass-On", "Alarm-Storm"]
    rows = []
    for _ in range(n):
        seq_len = int(RNG.integers(4, 12))
        seq = RNG.choice(event_types, size=seq_len)
        # برچسب: اگر شامل الگوی مشخص (Bypass-On → Alarm-Storm → Temp-High) شد، خطرناک
        seq_str = "|".join(seq)
        is_shutdown = int(
            ("Bypass-On" in seq_str and "Alarm-Storm" in seq_str and "Temp-High" in seq_str)
            or ("Pressure-Low" in seq_str and "Vibration-High" in seq_str)
            or RNG.random() < 0.05  # نویز
        )
        rows.append({
            "sequence_id": f"SEQ-{len(rows):05d}",
            "events": seq_str,
            "length": seq_len,
            "unit": RNG.choice(UNITS),
            "shutdown_risk": is_shutdown,
            "lead_time_min": int(RNG.integers(5, 120)) if is_shutdown else 0,
        })
    return pd.DataFrame(rows)


def generate_risk_signals(periods: int = 8760) -> pd.DataFrame:
    """سیگنال‌های عملیاتی + خرابی (برای ریسک پویا و بهینه‌سازی تست).

    failure به‌صورت وابسته به دما، فشار و لرزش تولید می‌شود تا الگوریتم‌های ML
    بتوانند رابطه را یاد بگیرند (ROC-AUC قابل دستیابی ≥ ۰.۸۵).
    """
    ts = _ts(pd.Timestamp(SHAMSI_START_GREG), periods, freq="h")
    rows = []
    for unit in UNITS:
        temp = np.clip(RNG.normal(150, 8, periods) + np.sin(np.arange(periods) / 24) * 3, 100, 220)
        press = np.clip(RNG.normal(35, 2, periods) + np.cos(np.arange(periods) / 48) * 1, 20, 60)
        flow = np.clip(RNG.normal(180, 12, periods), 100, 300)
        vibration = np.clip(RNG.normal(2.0, 0.4, periods) + (temp - 150) / 100, 0.1, 6.0)
        op_hours = RNG.integers(0, 2000, periods)
        # hazard واقعی: دما بالا + فشار پایین + لرزش بالا + ساعات کار زیاد = خرابی بیشتر
        hazard = (
            (temp - 150) / 30            # دما: ضریب قوی
            + (35 - press) / 10           # فشار: معکوس
            + (vibration - 2.0) / 0.5     # لرزش: ضریب قوی
            + (op_hours - 1000) / 1500    # فرسودگی
            + RNG.normal(0, 0.3, periods)  # نویز
        )
        # احتمال خرابی با sigmoid، با میانگین نهایی ~۲.۵٪
        fail_prob = 1 / (1 + np.exp(-(hazard - 3.0)))  # shift برای کنترل rate
        # نمونه‌گیری با احتمال محاسبه‌شده (واقعاً وابسته به سیگنال‌ها)
        failures = (RNG.random(periods) < fail_prob).astype(int)
        for i, t in enumerate(ts):
            rows.append({
                "timestamp": t,
                "unit": unit,
                "temperature_c": round(float(temp[i]), 2),
                "pressure_bar": round(float(press[i]), 2),
                "flow_kg_h": round(float(flow[i]), 2),
                "vibration_mm_s": round(float(vibration[i]), 3),
                "failure": int(failures[i]),
                "operating_hours": int(op_hours[i]),
            })
    return pd.DataFrame(rows)


def main() -> None:
    print("[synthetic] generating datasets...")
    alarms = generate_alarms()
    barriers = generate_barriers()
    sequences = generate_sequences()
    risk = generate_risk_signals()
    alarms.to_csv(DATA_DIR / "alarms.csv", index=False)
    barriers.to_csv(DATA_DIR / "barriers.csv", index=False)
    sequences.to_csv(DATA_DIR / "sequences.csv", index=False)
    risk.to_csv(DATA_DIR / "risk_signals.csv", index=False)
    print(f"[synthetic] alarms:    {len(alarms):>7,} rows -> {DATA_DIR/'alarms.csv'}")
    print(f"[synthetic] barriers:  {len(barriers):>7,} rows -> {DATA_DIR/'barriers.csv'}")
    print(f"[synthetic] sequences: {len(sequences):>7,} rows -> {DATA_DIR/'sequences.csv'}")
    print(f"[synthetic] risk:      {len(risk):>7,} rows -> {DATA_DIR/'risk_signals.csv'}")


if __name__ == "__main__":
    main()
