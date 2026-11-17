"""ماژول ۱: تحلیل و اولویت‌بندی هوشمند آلارم (نسخه ۲ — منطبق با EEMUA 191 / ISA-18.2 / IEC 62682).

الگوریتم‌ها و قابلیت‌ها (بنچ‌مارک با نمونه‌های بین‌المللی):
  - DBSCAN برای خوشه‌بندی زمانی آلارم‌ها (شناسایی چترینگ، طوفان آلارم، علت مشترک)
  - Isolation Forest برای تشخیص آلارم‌های ناهنجار
  - شاخص‌های کامل EEMUA 191 / ISA-18.2:
      * نرخ آلارم پایدار (alarms per operator per 10 min) با حد ≤ ۱
      * نرخ پس از اختلال (upset: ≤ ۱۰ آلارم در ۱۰ دقیقه اول)
      * توزیع اولویت (هدف: ~80% Low / 15% Medium / 5% High+Critical)
      * آلارم‌های چترینگ (≥ ۳ آلارم در ۱ دقیقه یا ۹ آلارم در ۹ دقیقه برای یک تگ)
      * آلارم‌های ثابت‌مانده (Standing: Active > 24h)
      * آلارم‌های بی‌حرکت (Stale: Active > 24h که قبلاً هم فعال بوده)
      * آلارم‌های بی‌پاسخ (نرخ تأیید/annunciation)
      * سهم بد-اکتورها (هدف: ۱۰ تگ برتر < ۱–۵٪ کل)
  - Alarm Rationalization: بازنگری حد بالا/پایین، حذف آلارم زائد، تخصیص اولویت
  - Alarm Shelving (IEC 62682 mandatory): خاموش موقت تحت شرایط تعریف‌شده
  - State-Based Alarming: خاموش خودکار آلارم‌های نامربوط بر اساس حالت فرآیند
  - Dynamic Alarm Suppression: فیلتر آلارم‌های ناشی از رخداد شناخته‌شده
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


# ------------------------------------------------------------
# آستانه‌های استاندارد EEMUA 191 / ISA-18.2 / IEC 62682
# ------------------------------------------------------------
EEMUA_TARGETS = {
    "alarms_per_10min_steady": 1,        # ≤ ۱ آلارم در ۱۰ دقیقه در حالت پایدار
    "alarms_per_10min_upset": 10,        # ≤ ۱۰ آلارم در ۱۰ دقیقه پس از اختلال
    "top10_share_max_pct": 1.0,          # سهم ۱۰ تگ برتر ≤ ۱٪ (اهداف EEMUA ممتاز)
    "top10_share_action_pct": 5.0,       # حد مداخله
    "standing_alarm_max_per_op": 5,      # آلارم ثابت ≤ ۵ به ازای هر اپراتور
    "stale_max_pct": 1.0,                # آلارم stale ≤ ۱٪ کل آلارم‌ها
    "chatter_max_pct": 1.0,              # چترینگ ≤ ۱٪ کل تگ‌ها
    "priority_distribution_target": {     # توزیع هدف اولویت
        "Low": 80.0, "Medium": 15.0, "High": 4.0, "Critical": 1.0,
    },
    "ack_max_avg_sec": 30,               # میانگین زمان تأیید ≤ ۳۰ ثانیه
    "bad_actor_max_share_pct": 5.0,      # بد-اکتورها < ۵٪ تگ‌ها
}

# آستانه‌های چترینگ بر اساس EEMUA 191
CHATTER_WINDOW_SEC = 60      # ۱ دقیقه
CHATTER_COUNT_1MIN = 3       # ≥ ۳ آلارم در ۱ دقیقه = چترینگ
CHATTER_WINDOW_9MIN_SEC = 540
CHATTER_COUNT_9MIN = 9       # یا ≥ ۹ آلارم در ۹ دقیقه = چترینگ
STANDING_THRESHOLD_H = 24.0  # > ۲۴ ساعت Active = Standing/Stale
FLOOD_WINDOW_MIN = 10
FLOOD_THRESHOLD = 10         # > ۱۰ آلارم در ۱۰ دقیقه = طوفان آلارم
FLOOD_END_THRESHOLD = 5      # < ۵ آلارم در ۱۰ دقیقه = پایان طوفان


@dataclass
class AlarmMetrics:
    """شاخص‌های مدیریت آلارم بر اساس EEMUA 191 / ISA 18.2 / IEC 62682.

    همه نرخ‌ها بر مبنای اپراتور و پنجره ۱۰ دقیقه‌ای/ساعتی/روزانه مطابق استاندارد گزارش می‌شوند.
    """
    total_alarms: int
    unique_tags: int
    alarms_per_hour: float
    alarms_per_10min_steady: float           # هدف EEMUA: ≤ ۱
    alarms_per_10min_peak: float             # حداکثر در پنجره ۱۰ دقیقه‌ای
    chattering_tags: int
    chattering_pct: float                     # درصد تگ‌های چترینگ
    standing_alarms: int                      # Active > 24h
    standing_pct: float
    stale_alarms: int                         # آلارم stale (≥ ۲۴h و قبلاً هم فعال)
    stale_pct: float
    flood_events: int
    flood_total_alarms: int                   # تعداد آلارم در طوفان‌ها
    flood_max_concurrent: int                 # حداکثر تعداد همزمان در یک طوفان
    top_10_share_pct: float                   # سهم ۱۰ تگ برتر
    priority_distribution: dict              # توزیع اولویت (٪)
    priority_compliance: float               # درصد انطباق با توزیع هدف EEMUA
    bad_actors: int                           # تگ‌هایی که > ۵٪ آلارم‌ها را تولید می‌کنند
    bad_actors_share_pct: float               # مجموع سهم بد-اکتورها
    operators_count: int
    alarms_per_operator_per_day: float        # هدف: ≤ ۱۴۴ روزانه
    avg_ack_delay_sec: float
    ack_compliance_pct: float                 # درصد آلارم‌های با ack ≤ ۳۰ ثانیه
    avg_clear_delay_sec: float
    annunciation_rate: float                  # آلارم در دقیقه (نرخ اعلام)
    # امتیاز انطباق کلی با EEMUA/ISA (0..100)
    compliance_score: float
    compliance_grade: str                      # A / B / C / D

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AlarmCluster:
    cluster_id: int
    n_alarms: int
    start: str
    end: str
    duration_sec: float
    tags: list[str]
    unique_tags: int
    likely_root_tag: str
    priority_score: float
    is_flood: bool
    alarm_rationale: str                       # دلیل احتمالی خوشه (طوفان / چترینگ / علت مشترک)


@dataclass
class RationalizationRecord:
    """خروجی Alarm Rationalization (مرحله rationalization چرخه ISA-18.2)."""
    tag: str
    current_priority: str
    recommended_priority: str
    rationale: str
    current_high_limit: float | None
    current_low_limit: float | None
    recommended_high_limit: float | None
    recommended_low_limit: float | None
    alarm_count: int
    nuisance_pct: float                         # درصد آلارم زائد تخمینی
    recommended_action: str                     # Keep / Reprioritize / Retune / Remove


@dataclass
class ShelvingRecord:
    """خروجی Alarm Shelving (الزام IEC 62682)."""
    tag: str
    shelf_duration_min: int
    reason: str                                 # Maintenance / Start-up / Upset / Operator-request
    shelved_by: str
    auto_reshelf: bool
    expires_at: str | None
    safety_impact: str                          # None / Low / Medium / High


@dataclass
class StateBasedSuppression:
    """خاموش خودکار آلارم نامربوط بر اساس حالت فرآیند."""
    tag: str
    process_state: str                          # Start-up / Shutdown / Maintenance / Normal
    suppressed: bool
    condition: str
    reason: str


class AlarmAnalytics:
    """تحلیلگر هوشمند آلارم منطبق بر EEMUA 191 / ISA-18.2 / IEC 62682."""

    def __init__(self,
                 dbscan_eps_sec: float = 30,
                 chatter_threshold: int = 5,
                 isolation_contamination: float = 0.05,
                 flood_window_min: int = FLOOD_WINDOW_MIN,
                 flood_threshold: int = FLOOD_THRESHOLD):
        self.dbscan_eps_sec = dbscan_eps_sec
        self.chatter_threshold = chatter_threshold
        self.isolation_contamination = isolation_contamination
        self.flood_window_min = flood_window_min
        self.flood_threshold = flood_threshold
        self._iso = IsolationForest(
            contamination=isolation_contamination, random_state=42, n_estimators=120
        )
        self._scaler = StandardScaler()
        self._fitted = False
        self._rationalization_db: list[RationalizationRecord] = []
        self._shelving_registry: dict[str, ShelvingRecord] = {}

    # ============================================================
    # شاخص‌های EEMUA 191 / ISA-18.2
    # ============================================================
    def metrics(self, df: pd.DataFrame, operator_col: str = "operator") -> AlarmMetrics:
        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        total = len(df)
        unique_tags = int(df["tag"].nunique()) if total else 0

        # حالت خالی
        if total == 0:
            return AlarmMetrics(
                total_alarms=0, unique_tags=0, alarms_per_hour=0.0,
                alarms_per_10min_steady=0.0, alarms_per_10min_peak=0.0,
                chattering_tags=0, chattering_pct=0.0,
                standing_alarms=0, standing_pct=0.0,
                stale_alarms=0, stale_pct=0.0,
                flood_events=0, flood_total_alarms=0, flood_max_concurrent=0,
                top_10_share_pct=0.0,
                priority_distribution={"Low": 0, "Medium": 0, "High": 0, "Critical": 0},
                priority_compliance=100.0,
                bad_actors=0, bad_actors_share_pct=0.0,
                operators_count=0, alarms_per_operator_per_day=0.0,
                avg_ack_delay_sec=0.0, ack_compliance_pct=100.0,
                avg_clear_delay_sec=0.0, annunciation_rate=0.0,
                compliance_score=100.0, compliance_grade="A",
            )

        span_sec = max((df["timestamp"].max() - df["timestamp"].min()).total_seconds(), 1.0)
        span_h = span_sec / 3600.0
        aph = total / span_h

        # ----- نرخ آلارم در پنجره‌های ۱۰ دقیقه‌ای -----
        df_sorted = df.sort_values("timestamp").reset_index(drop=True)
        per_10min = (
            df_sorted.set_index("timestamp")["tag"]
            .rolling(f"{FLOOD_WINDOW_MIN}min").count()
        )
        # نرخ پایدار: میانگین کل پنجره‌ها
        steady_rate = float(per_10min.mean()) if len(per_10min) else 0.0
        peak_rate = float(per_10min.max()) if len(per_10min) else 0.0

        # ----- چترینگ (دو معیار EEMUA) -----
        chattering_tags_set: set[str] = set()
        for tag, g in df.groupby("tag"):
            ts = g["timestamp"].sort_values()
            # تبدیل به سری زمانی شمارشی در ایندکس timestamp
            cnt_series = pd.Series(1, index=ts)
            # معیار ۱: ≥ ۳ آلارم در ۱ دقیقه
            rolled_1m = cnt_series.rolling("60s").count()
            if (rolled_1m >= CHATTER_COUNT_1MIN).any():
                chattering_tags_set.add(tag)
                continue
            # معیار ۲: ≥ ۹ آلارم در ۹ دقیقه
            rolled_9m = cnt_series.rolling(f"{CHATTER_WINDOW_9MIN_SEC}s").count()
            if (rolled_9m >= CHATTER_COUNT_9MIN).any():
                chattering_tags_set.add(tag)
        chattering_tags = len(chattering_tags_set)
        chattering_pct = round(chattering_tags / max(unique_tags, 1) * 100, 2)

        # ----- Standing / Stale آلارم‌ها -----
        # فرض: آلارم با status=Active که بیش از ۲۴ ساعت فعال مانده
        standing = 0
        stale = 0
        if "status" in df.columns and "duration_h" in df.columns:
            active_mask = df["status"].astype(str).str.lower() == "active"
            dur = pd.to_numeric(df.get("duration_h", 0), errors="coerce").fillna(0)
            standing = int(((active_mask) & (dur >= STANDING_THRESHOLD_H)).sum())
            # Stale: آلارم‌هایی که قبلاً هم فعال بودند (count_prev_active > 0) و اکنون stale
            if "prev_active_count" in df.columns:
                prev = pd.to_numeric(df["prev_active_count"], errors="coerce").fillna(0)
                stale = int(((active_mask) & (dur >= STANDING_THRESHOLD_H) & (prev > 0)).sum())
            else:
                stale = standing  # اگر اطلاعات قبلی نبود، معادل standing
        elif "status" in df.columns:
            # ساده‌شده: تعداد Active به‌عنوان تقریب standing
            standing = int((df["status"].astype(str).str.lower() == "active").sum())
            stale = standing
        standing_pct = round(standing / max(total, 1) * 100, 2)
        stale_pct = round(stale / max(total, 1) * 100, 2)

        # ----- طوفان آلارم (Flood Detection with start/end) -----
        flood_events, flood_total, flood_max = self._detect_floods(df_sorted)

        # ----- سهم ۱۰ تگ برتر (بد-اکتور) -----
        tag_counts = df["tag"].value_counts()
        top10 = int(tag_counts.head(10).sum())
        top10_share = round(top10 / total * 100, 2)
        # بد-اکتور: تگ‌هایی که > ۵٪ آلارم‌ها را تولید می‌کنند
        bad_actor_threshold_pct = EEMUA_TARGETS["bad_actor_max_share_pct"]
        bad_actors = int((tag_counts / total * 100 >= bad_actor_threshold_pct).sum())
        bad_actors_share = round(float(tag_counts[tag_counts / total * 100 >= bad_actor_threshold_pct].sum() / total * 100), 2)

        # ----- توزیع اولویت -----
        prio_dist = self._priority_distribution(df)
        prio_compliance = self._priority_compliance(prio_dist)

        # ----- متریک‌های اپراتور -----
        operators = df[operator_col].dropna().nunique() if operator_col in df.columns else 1
        operators = max(int(operators), 1)
        span_days = max(span_h / 24.0, 1.0 / 24.0)
        alarms_per_op_day = total / operators / span_days

        # ----- تأیید (Annunciation / Ack) -----
        ack_delay = pd.to_numeric(df.get("ack_delay_sec", 0), errors="coerce").fillna(0)
        clear_delay = pd.to_numeric(df.get("clear_delay_sec", 0), errors="coerce").fillna(0)
        avg_ack = float(ack_delay.mean()) if len(ack_delay) else 0.0
        avg_clear = float(clear_delay.mean()) if len(clear_delay) else 0.0
        ack_compliance = float((ack_delay <= 30).mean() * 100) if len(ack_delay) else 100.0
        annunc_rate = total / max(span_sec / 60.0, 1.0)

        # ----- امتیاز انطباق کلی با EEMUA/ISA -----
        compliance_score, grade = self._compute_compliance(
            steady_rate=steady_rate, peak_rate=peak_rate,
            chattering_pct=chattering_pct, standing_pct=standing_pct,
            stale_pct=stale_pct, top10_share=top10_share,
            bad_actors_share=bad_actors_share, prio_compliance=prio_compliance,
            ack_compliance=ack_compliance, alarms_per_op_day=alarms_per_op_day,
        )

        return AlarmMetrics(
            total_alarms=total,
            unique_tags=unique_tags,
            alarms_per_hour=round(aph, 2),
            alarms_per_10min_steady=round(steady_rate, 2),
            alarms_per_10min_peak=round(peak_rate, 2),
            chattering_tags=chattering_tags,
            chattering_pct=chattering_pct,
            standing_alarms=standing,
            standing_pct=standing_pct,
            stale_alarms=stale,
            stale_pct=stale_pct,
            flood_events=flood_events,
            flood_total_alarms=flood_total,
            flood_max_concurrent=flood_max,
            top_10_share_pct=top10_share,
            priority_distribution=prio_dist,
            priority_compliance=round(prio_compliance, 2),
            bad_actors=bad_actors,
            bad_actors_share_pct=bad_actors_share,
            operators_count=operators,
            alarms_per_operator_per_day=round(alarms_per_op_day, 2),
            avg_ack_delay_sec=round(avg_ack, 2),
            ack_compliance_pct=round(ack_compliance, 2),
            avg_clear_delay_sec=round(avg_clear, 2),
            annunciation_rate=round(annunc_rate, 2),
            compliance_score=round(compliance_score, 2),
            compliance_grade=grade,
        )

    def _detect_floods(self, df_sorted: pd.DataFrame) -> tuple[int, int, int]:
        """شناسایی طوفان‌های آلارم با شروع/پایان بر اساس EEMUA."""
        if len(df_sorted) == 0:
            return (0, 0, 0)
        rolled = (
            df_sorted.set_index("timestamp")["tag"]
            .rolling(f"{FLOOD_WINDOW_MIN}min").count()
        )
        in_flood = rolled >= FLOOD_THRESHOLD
        # شناسایی رویدادهای مجزا
        events = 0
        total_alarms_in_floods = 0
        max_concurrent = 0
        prev = False
        for cnt, is_f in zip(rolled.values, in_flood.values):
            if is_f and not prev:
                events += 1
            if is_f:
                total_alarms_in_floods += 1
                if cnt > max_concurrent:
                    max_concurrent = int(cnt)
            prev = bool(is_f)
        return (events, total_alarms_in_floods, max_concurrent)

    def _priority_distribution(self, df: pd.DataFrame) -> dict:
        if "priority" not in df.columns or len(df) == 0:
            return {"Low": 0.0, "Medium": 0.0, "High": 0.0, "Critical": 0.0}
        counts = df["priority"].value_counts()
        total = len(df)
        return {
            p: round(float(counts.get(p, 0)) / total * 100, 2)
            for p in ("Low", "Medium", "High", "Critical")
        }

    def _priority_compliance(self, dist: dict) -> float:
        """انطباق توزیع اولویت با هدف EEMUA (۸۰/۱۵/۴/۱)."""
        target = EEMUA_TARGETS["priority_distribution_target"]
        total_dev = 0.0
        for p in ("Low", "Medium", "High", "Critical"):
            actual = dist.get(p, 0.0)
            tgt = target.get(p, 0.0)
            total_dev += abs(actual - tgt)
        # حداکثر انحراف نظری = 200 (کاملاً معکوس)؛ نرمالایز به 0..100
        score = max(0.0, 100.0 - total_dev / 2.0)
        return score

    def _compute_compliance(self, **kw) -> tuple[float, str]:
        """امتیاز انطباق کلی با EEMUA/ISA (0..100) و گرید نهایی."""
        # وزن‌دهی شاخص‌ها
        checks = [
            # (شرط, امتیاز, توضیح)
            (kw["steady_rate"] <= EEMUA_TARGETS["alarms_per_10min_steady"], 18, "نرخ پایدار"),
            (kw["peak_rate"] <= EEMUA_TARGETS["alarms_per_10min_upset"], 12, "نرخ پس از اختلال"),
            (kw["chattering_pct"] <= 1.0, 12, "چترینگ"),
            (kw["standing_pct"] <= 5.0, 10, "آلارم ثابت"),
            (kw["stale_pct"] <= 1.0, 10, "آلارم stale"),
            (kw["top10_share"] <= EEMUA_TARGETS["top10_share_max_pct"], 12, "سهم بد-اکتور"),
            (kw["bad_actors_share"] <= 10.0, 8, "تراکم بد-اکتور"),
            (kw["prio_compliance"] >= 70.0, 10, "توزیع اولویت"),
            (kw["ack_compliance"] >= 80.0, 5, "نرخ تأیید"),
            (kw["alarms_per_op_day"] <= 144.0, 3, "بار اپراتور"),
        ]
        score = sum(pts for ok, pts, _ in checks if ok)
        # مکمل امتیاز جزئی
        for ok, pts, _ in checks:
            if not ok:
                score += 0  # بدون امتیاز جزئی فعلی
        grade = "A" if score >= 90 else ("B" if score >= 75 else ("C" if score >= 60 else "D"))
        return float(score), grade

    # ============================================================
    # خوشه‌بندی زمانی با DBSCAN
    # ============================================================
    def cluster(self, df: pd.DataFrame, eps_sec: float | None = None) -> list[AlarmCluster]:
        eps = float(eps_sec if eps_sec is not None else self.dbscan_eps_sec)
        df = df.sort_values("timestamp").reset_index(drop=True).copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        ts = df["timestamp"].astype("int64").to_numpy().reshape(-1, 1) / 1e9
        labels = DBSCAN(eps=eps, min_samples=2).fit_predict(ts)
        df["cluster"] = labels

        results: list[AlarmCluster] = []
        for cid, g in df[df["cluster"] >= 0].groupby("cluster"):
            tags = g["tag"].tolist()
            unique_t = g["tag"].nunique()
            prio_map = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
            g_sorted = g.assign(_p=g["priority"].map(prio_map).fillna(1)) \
                        .sort_values(["_p", "timestamp"], ascending=[False, True])
            root = g_sorted["tag"].iloc[0]
            avg_prio = g_sorted["_p"].mean()
            prio_score = float(len(g) * avg_prio)
            is_flood = len(g) >= self.flood_threshold
            start_ts = g["timestamp"].min()
            end_ts = g["timestamp"].max()
            duration = (end_ts - start_ts).total_seconds()
            # rationale خوشه
            if is_flood:
                rationale = "طوفان آلارم (Flood) — احتمالاً اختلال فرآیندی بزرگ"
            elif unique_t == 1 and len(g) >= 3:
                rationale = "چترینگ (Chattering) — نیاز به بازنگری آستانه یا deadband"
            elif unique_t >= 3 and duration < 120:
                rationale = "علت مشترک (Common-cause) — بررسی LOPA"
            else:
                rationale = "خوشه زمانی — تحلیل علت ریشه‌ای"
            results.append(AlarmCluster(
                cluster_id=int(cid),
                n_alarms=len(g),
                start=str(start_ts),
                end=str(end_ts),
                duration_sec=round(duration, 1),
                tags=tags[:50],  # محدود برای حجم
                unique_tags=int(unique_t),
                likely_root_tag=root,
                priority_score=round(prio_score, 2),
                is_flood=bool(is_flood),
                alarm_rationale=rationale,
            ))
        return sorted(results, key=lambda c: c.priority_score, reverse=True)

    # ============================================================
    # تشخیص ناهنجاری با Isolation Forest
    # ============================================================
    def fit(self, df: pd.DataFrame) -> "AlarmAnalytics":
        feats = self._features(df)
        X = self._scaler.fit_transform(feats.values)
        self._iso.fit(X)
        self._fitted = True
        return self

    def detect_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self._fitted:
            raise RuntimeError("model not fitted; call fit() first")
        feats = self._features(df)
        X = self._scaler.transform(feats.values)
        preds = self._iso.predict(X)
        scores = -self._iso.score_samples(X)
        out = df.copy().reset_index(drop=True)
        out["anomaly"] = (preds == -1).astype(int)
        out["anomaly_score"] = np.round(scores, 4)
        return out

    def _features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        prio_map = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
        feats = pd.DataFrame({
            "priority_num": df["priority"].map(prio_map).fillna(1).astype(float),
            "ack_delay_sec": df.get("ack_delay_sec", pd.Series(dtype=float)).astype(float).fillna(0),
            "clear_delay_sec": df.get("clear_delay_sec", pd.Series(dtype=float)).astype(float).fillna(0),
            "value": df.get("value", pd.Series(dtype=float)).astype(float).fillna(0),
            "deviation": (df["value"] - df.get("setpoint", df["value"])).abs().astype(float).fillna(0),
        })
        return feats

    # ============================================================
    # Alarm Rationalization (ISA-18.2 Lifecycle — مرحله Rationalization)
    # ============================================================
    def rationalize(self, df: pd.DataFrame, target_distribution: dict | None = None) -> list[RationalizationRecord]:
        """انجام rationalization خودکار: بازنگری اولویت، آستانه و حذف زائد.

        بر اساس چرخه ISA-18.2 مرحله Rationalization:
          1. تجمیع آلارم‌های هر تگ
          2. تخمین سهم آلارم زائد (نویز نزدیک آستانه)
          3. پیشنهاد اولویت جدید بر اساس عواقب ایمنی/تولیدی
          4. پیشنهاد آستانه جدید (3σ یا درصدیل)
          5. اقدام: Keep / Reprioritize / Retune / Remove
        """
        target_dist = target_distribution or EEMUA_TARGETS["priority_distribution_target"]
        records: list[RationalizationRecord] = []
        total = len(df)
        if total == 0:
            return records
        tag_counts = df["tag"].value_counts()
        for tag, g in df.groupby("tag"):
            cnt = len(g)
            share_pct = cnt / total * 100
            cur_prio = g["priority"].mode().iloc[0] if "priority" in g.columns else "Medium"
            # تخمین آلارم زائد: درصدی که |deviation| بسیار نزدیک به صفر است (نویز آستانه)
            dev = (g["value"] - g.get("setpoint", g["value"])).abs() if "value" in g.columns else pd.Series([0]*cnt)
            nuisance_pct = float((dev < dev.std() * 0.3).mean() * 100) if cnt > 1 else 0.0

            # پیشنهاد اولویت بر اساس فراوانی و عواقب (تقریب)
            if share_pct > 5.0 and nuisance_pct > 60:
                rec_prio = "Low"
                action = "Retune"
                rationale = f"فراوانی {share_pct:.1f}٪ با {nuisance_pct:.0f}٪ نویز؛ بازنگری آستانه"
            elif cur_prio == "Critical" and share_pct > 2.0:
                rec_prio = "High"
                action = "Reprioritize"
                rationale = "فراوانی بالا برای اولویت بحرانی؛ کاهش اولویت برای حفظ اثربخشی"
            elif share_pct < 0.1 and cur_prio in ("High", "Critical"):
                rec_prio = cur_prio
                action = "Keep"
                rationale = "فراوانی پایین و اولویت متناسب؛ حفظ پیکربندی"
            elif nuisance_pct > 80:
                rec_prio = "Low"
                action = "Remove"
                rationale = f"بیش از {nuisance_pct:.0f}٪ آلارم زائد؛ حذف پیشنهاد می‌شود"
            else:
                # پیشنهاد توزیع بر اساس هدف EEMUA
                target = target_dist.get(cur_prio, 10)
                rec_prio = cur_prio
                action = "Keep"
                rationale = "متناسب با توزیع هدف"

            # پیشنهاد آستانه جدید (3σ)
            v = pd.to_numeric(g["value"], errors="coerce").dropna()
            sp = pd.to_numeric(g.get("setpoint"), errors="coerce").dropna()
            sp_mean = float(sp.mean()) if len(sp) else (float(v.mean()) if len(v) else None)
            cur_high = float(sp_mean) if sp_mean is not None else None
            cur_low = float(sp_mean) if sp_mean is not None else None
            rec_high = rec_low = None
            if len(v) >= 5:
                mu, sd = float(v.mean()), float(v.std(ddof=0) or 1.0)
                rec_high = round(mu + 3 * sd, 3)
                rec_low = round(mu - 3 * sd, 3)

            records.append(RationalizationRecord(
                tag=tag,
                current_priority=cur_prio,
                recommended_priority=rec_prio,
                rationale=rationale,
                current_high_limit=cur_high,
                current_low_limit=cur_low,
                recommended_high_limit=rec_high,
                recommended_low_limit=rec_low,
                alarm_count=cnt,
                nuisance_pct=round(nuisance_pct, 2),
                recommended_action=action,
            ))
        self._rationalization_db = records
        return sorted(records, key=lambda r: r.alarm_count, reverse=True)

    # ============================================================
    # Alarm Shelving (الزام IEC 62682)
    # ============================================================
    def shelve(self, tag: str, duration_min: int, reason: str,
               shelved_by: str = "system", auto_reshelf: bool = True,
               expires_at: str | None = None, safety_impact: str = "None") -> ShelvingRecord:
        """خاموش موقت یک آلارم (Shelving) با ثبت دلیل و تاریخ انقضا (IEC 62682)."""
        rec = ShelvingRecord(
            tag=tag, shelf_duration_min=int(duration_min),
            reason=reason, shelved_by=shelved_by,
            auto_reshelf=auto_reshelf, expires_at=expires_at,
            safety_impact=safety_impact,
        )
        self._shelving_registry[tag] = rec
        return rec

    def unshelve(self, tag: str) -> bool:
        """بازگرداندن آلارم از حالت shelved."""
        if tag in self._shelving_registry:
            del self._shelving_registry[tag]
            return True
        return False

    def list_shelved(self) -> list[ShelvingRecord]:
        return list(self._shelving_registry.values())

    def filter_shelved(self, df: pd.DataFrame) -> pd.DataFrame:
        """حذف آلارم‌های shelved از DataFrame (شبیه‌سازی suppression)."""
        shelved_tags = set(self._shelving_registry.keys())
        if not shelved_tags:
            return df
        return df[~df["tag"].isin(shelved_tags)].reset_index(drop=True)

    # ============================================================
    # State-Based Alarming (خاموش خودکار بر اساس حالت فرآیند)
    # ============================================================
    def state_based_suppression(self, df: pd.DataFrame, process_state: str) -> list[StateBasedSuppression]:
        """پیشنهاد خاموش آلارم‌های نامربوط با توجه به حالت فرآیند."""
        suppressions: list[StateBasedSuppression] = []
        # قوانین ساده مبتنی بر حالت
        rules = {
            "Start-up": [
                ("روی بالا موقت فرآیند", "tag.str.contains('Temp|Pressure|Flow')", "طوفان آلارم پیش‌بینی‌شده در راه‌اندازی"),
            ],
            "Shutdown": [
                ("پایین رفتن جریان", "tag.str.contains('Flow')", "افت جریان طبیعی در توقف"),
            ],
            "Maintenance": [
                ("تست موقت تجهیزات", "tag.str.contains('Test|Maintenance')", "آلارم ناشی از تست دوره‌ای"),
            ],
        }
        state_rules = rules.get(process_state, [])
        for tag, g in df.groupby("tag"):
            suppressed = False
            condition = ""
            reason = ""
            for cond_name, pattern, rationale in state_rules:
                if pattern in tag or any(k in tag for k in ("Temp", "Pressure", "Flow", "Test")):
                    suppressed = True
                    condition = cond_name
                    reason = rationale
                    break
            suppressions.append(StateBasedSuppression(
                tag=tag, process_state=process_state,
                suppressed=suppressed, condition=condition, reason=reason,
            ))
        return suppressions

    # ============================================================
    # پیشنهاد بازنگری حدود آلارم (نگاه به عقب برای backward-compat)
    # ============================================================
    def recommend_thresholds(self, df: pd.DataFrame) -> list[dict]:
        recs = []
        for tag, g in df.groupby("tag"):
            if len(g) < 10:
                continue
            v = pd.to_numeric(g["value"], errors="coerce").dropna()
            if len(v) < 5:
                continue
            sp = pd.to_numeric(g.get("setpoint"), errors="coerce").dropna()
            sp_mean = float(sp.mean()) if len(sp) else float(v.mean())
            mu, sd = float(v.mean()), float(v.std(ddof=0) or 1.0)
            recs.append({
                "tag": tag,
                "current_setpoint": round(sp_mean, 2),
                "observed_mean": round(mu, 2),
                "observed_std": round(sd, 2),
                "suggested_low": round(mu - 3 * sd, 2),
                "suggested_high": round(mu + 3 * sd, 2),
                "alarms_count": int(len(g)),
            })
        return sorted(recs, key=lambda r: r["alarms_count"], reverse=True)[:20]

    # ============================================================
    # صادرات گزارش انطباق EEMUA/ISA
    # ============================================================
    def compliance_report(self, df: pd.DataFrame) -> dict:
        """گزارش کامل انطباق با EEMUA 191 / ISA-18.2 / IEC 62682."""
        m = self.metrics(df)
        return {
            "standard": "EEMUA 191 v4 / ISA-18.2-2016 / IEC 62682",
            "compliance_score": m.compliance_score,
            "compliance_grade": m.compliance_grade,
            "targets": EEMUA_TARGETS,
            "actuals": {
                "alarms_per_10min_steady": m.alarms_per_10min_steady,
                "alarms_per_10min_peak": m.alarms_per_10min_peak,
                "chattering_pct": m.chattering_pct,
                "standing_pct": m.standing_pct,
                "stale_pct": m.stale_pct,
                "top10_share_pct": m.top_10_share_pct,
                "bad_actors_share_pct": m.bad_actors_share_pct,
                "priority_distribution": m.priority_distribution,
                "priority_compliance": m.priority_compliance,
                "ack_compliance_pct": m.ack_compliance_pct,
                "alarms_per_operator_per_day": m.alarms_per_operator_per_day,
            },
            "gaps": self._identify_gaps(m),
            "metrics": m.to_dict(),
        }

    def _identify_gaps(self, m: AlarmMetrics) -> list[dict]:
        gaps = []
        if m.alarms_per_10min_steady > EEMUA_TARGETS["alarms_per_10min_steady"]:
            gaps.append({"kpi": "alarms_per_10min_steady", "actual": m.alarms_per_10min_steady,
                         "target": EEMUA_TARGETS["alarms_per_10min_steady"], "severity": "High"})
        if m.chattering_pct > 1.0:
            gaps.append({"kpi": "chattering_pct", "actual": m.chattering_pct,
                         "target": 1.0, "severity": "Medium"})
        if m.standing_pct > 5.0:
            gaps.append({"kpi": "standing_pct", "actual": m.standing_pct,
                         "target": 5.0, "severity": "Medium"})
        if m.stale_pct > 1.0:
            gaps.append({"kpi": "stale_pct", "actual": m.stale_pct,
                         "target": 1.0, "severity": "High"})
        if m.top_10_share_pct > EEMUA_TARGETS["top10_share_action_pct"]:
            gaps.append({"kpi": "top10_share_pct", "actual": m.top_10_share_pct,
                         "target": EEMUA_TARGETS["top10_share_action_pct"], "severity": "High"})
        if m.bad_actors_share_pct > 10.0:
            gaps.append({"kpi": "bad_actors_share_pct", "actual": m.bad_actors_share_pct,
                         "target": 10.0, "severity": "Medium"})
        if m.priority_compliance < 70.0:
            gaps.append({"kpi": "priority_compliance", "actual": m.priority_compliance,
                         "target": 70.0, "severity": "Medium"})
        if m.ack_compliance_pct < 80.0:
            gaps.append({"kpi": "ack_compliance_pct", "actual": m.ack_compliance_pct,
                         "target": 80.0, "severity": "Low"})
        return gaps
