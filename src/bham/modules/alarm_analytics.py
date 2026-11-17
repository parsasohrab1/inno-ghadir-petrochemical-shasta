"""ماژول ۱: تحلیل و اولویت‌بندی هوشمند آلارم.

الگوریتم‌ها:
  - DBSCAN برای خوشه‌بندی زمانی آلارم‌ها (شناسایی چترینگ، طوفان آلارم)
  - Isolation Forest برای تشخیص آلارم‌های ناهنجار
  - شاخص‌های EEMUA 191: نرخ آلارم، چترینگ، آلارم‌های ثابت‌مانده
  - خوشه‌بندی هم‌زمانی (شبکه‌ای) برای کشف علت مشترک
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


@dataclass
class AlarmMetrics:
    """شاخص‌های مدیریت آلارم بر اساس EEMUA 191 / ISA 18.2."""
    total_alarms: int
    unique_tags: int
    alarms_per_hour: float
    chattering_tags: int
    stale_alarms: int
    flood_events: int
    top_10_share_pct: float  # سهم ۱۰ تگ پرتکرار

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AlarmCluster:
    cluster_id: int
    n_alarms: int
    start: str
    end: str
    tags: list[str]
    likely_root_tag: str
    priority_score: float
    is_flood: bool


class AlarmAnalytics:
    """تحلیلگر هوشمند آلارم."""

    def __init__(self,
                 dbscan_eps_sec: float = 30,
                 chatter_threshold: int = 5,
                 isolation_contamination: float = 0.05,
                 flood_window_min: int = 10,
                 flood_threshold: int = 10):
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

    # ---- شاخص‌ها ----
    def metrics(self, df: pd.DataFrame) -> AlarmMetrics:
        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        total = len(df)
        unique_tags = int(df["tag"].nunique()) if total else 0

        # حالت خالی
        if total == 0:
            return AlarmMetrics(
                total_alarms=0, unique_tags=0, alarms_per_hour=0.0,
                chattering_tags=0, stale_alarms=0, flood_events=0,
                top_10_share_pct=0.0,
            )

        span_h = max((df["timestamp"].max() - df["timestamp"].min()).total_seconds() / 3600.0, 1.0)
        aph = total / span_h

        # چترینگ: تگ‌هایی که در پنجره کوتاه چندین آلارم دارند
        def _chatter_count(g: pd.DataFrame) -> int:
            if len(g) < 2:
                return 0
            diffs = g["timestamp"].sort_values().diff().dt.total_seconds().dropna()
            return int((diffs < self.dbscan_eps_sec).sum())
        chatter = df.groupby("tag", group_keys=False).apply(_chatter_count)
        chattering_tags = int((chatter >= self.chatter_threshold).sum())

        # آلارم ثابت‌مانده (وضعیت Active بیش از حد)
        stale = int((df["status"] == "Active").sum())

        # طوفان آلارم: پنجره‌ای که تعداد آلارم از حد گذر کند
        df_sorted = df.sort_values("timestamp")
        rolled = (
            df_sorted.set_index("timestamp")["tag"]
            .rolling(f"{self.flood_window_min}min").count()
        )
        floods = int((rolled >= self.flood_threshold).sum() // self.flood_threshold)  # تخمین رویدادها

        # سهم ۱۰ تگ پرتکرار
        top10 = df["tag"].value_counts().head(10).sum()
        top10_share = float(top10 / total * 100) if total else 0.0

        return AlarmMetrics(
            total_alarms=total,
            unique_tags=unique_tags,
            alarms_per_hour=round(aph, 2),
            chattering_tags=chattering_tags,
            stale_alarms=stale,
            flood_events=floods,
            top_10_share_pct=round(top10_share, 2),
        )

    # ---- خوشه‌بندی زمانی با DBSCAN ----
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
            # علت محتمل: تگ با بیشترین اولویت و قدیمی‌ترین زمان آلارم
            prio_map = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
            g_sorted = g.assign(_p=g["priority"].map(prio_map).fillna(1)) \
                        .sort_values(["_p", "timestamp"], ascending=[False, True])
            root = g_sorted["tag"].iloc[0]
            # امتیاز اولویت: تعداد × اولویت میانگین
            avg_prio = g_sorted["_p"].mean()
            prio_score = float(len(g) * avg_prio)
            is_flood = len(g) >= self.flood_threshold
            results.append(AlarmCluster(
                cluster_id=int(cid),
                n_alarms=len(g),
                start=str(g["timestamp"].min()),
                end=str(g["timestamp"].max()),
                tags=tags,
                likely_root_tag=root,
                priority_score=round(prio_score, 2),
                is_flood=bool(is_flood),
            ))
        return sorted(results, key=lambda c: c.priority_score, reverse=True)

    # ---- تشخیص ناهنجاری با Isolation Forest ----
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
        preds = self._iso.predict(X)  # 1 normal, -1 anomaly
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

    # ---- پیشنهاد بازنگری حدود آلارم ----
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
            # اگر انحراف معیاری بزرگ است، شاید نیاز به بازنگری حد بالا/پایین
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
