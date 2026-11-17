"""ماژول ۳: پیش‌بینی توالی‌های منجر به توقف اضطراری یا رخداد ناایمن.

الگوریتم‌ها:
  - Random Forest برای طبقه‌بندی توالی پرخطر
  - TF-IDF روی توالی رویدادها برای استخراج ویژگی
  - زنجیره مارکوف مرتبه ۲ برای پیش‌بینی رویداد بعدی
  - برآورد احتمال توقف در بازه زمانی آینده
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score


class _IntDict(dict):
    """dict that returns 0 for missing keys (picklable replacement for defaultdict(int))."""
    def __missing__(self, key):
        return 0


@dataclass
class SequencePrediction:
    sequence_id: str
    shutdown_probability: float
    predicted_next_event: str
    next_event_probability: float
    lead_time_min: int
    risk_level: str
    # پیش‌بینی چندمرحله‌ای (بنچ‌مارک با Horizon پیش‌بینی محصولات تجاری)
    prob_shutdown_1h: float       # احتمال توقف در ۱ ساعت آینده
    prob_shutdown_24h: float      # احتمال توقف در ۲۴ ساعت آینده
    prob_shutdown_72h: float      # احتمال توقف در ۷۲ ساعت آینده
    lead_time_to_shutdown_min: int  # تخمین زمان تا توقف
    confidence: float              # اعتماد پیش‌بینی (0..1)
    recommended_intervention: str  # اقدام پیشنهادی برای جلوگیری


class SequencePredictor:
    """پیش‌بینی توالی‌های منجر به توقف/ناایمن — نسخه ۲ با horizon چندمرحله‌ای."""

    def __init__(self,
                 n_estimators: int = 200,
                 max_depth: int = 12,
                 markov_order: int = 2,
                 shutdown_prob_threshold: float = 0.5):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.markov_order = markov_order
        self.threshold = shutdown_prob_threshold
        self._tfidf = TfidfVectorizer(
            token_pattern=r"[^|]+", ngram_range=(1, 2)
        )
        self._clf = RandomForestClassifier(
            n_estimators=n_estimators, max_depth=max_depth,
            random_state=42, n_jobs=-1, class_weight="balanced",
        )
        # زنجیره مارکوف: (state) -> {next: count}
        self._markov: dict = {}
        self._fitted = False

    def fit(self, df: pd.DataFrame, test_size: float = 0.2, random_state: int = 42):
        """df باید شامل ستون‌های events (محدود با '|') و shutdown_risk باشد."""
        X_tfidf = self._tfidf.fit_transform(df["events"])
        # ویژگی‌های آماری اضافی
        extra = self._extract_features(df)
        from scipy.sparse import hstack
        X = hstack([X_tfidf, extra]).tocsr()
        y = df["shutdown_risk"].astype(int).to_numpy()
        stratify = y if len(np.unique(y)) > 1 and np.bincount(y).min() >= 2 else None
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=stratify
        )
        self._clf.fit(X_train, y_train)
        self._fitted = True
        # آموزش زنجیره مارکوف
        for events in df["events"]:
            seq = events.split("|")
            order = self.markov_order
            for i in range(len(seq) - order):
                state = tuple(seq[i:i + order])
                if state not in self._markov:
                    self._markov[state] = _IntDict()
                self._markov[state][seq[i + order]] += 1

        # ارزیابی
        y_pred = self._clf.predict(X_test)
        y_proba = self._safe_predict_proba(X_test)
        report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
        try:
            auc = float(roc_auc_score(y_test, y_proba))
        except Exception:
            auc = 0.5
        return {
            "train_size": X_train.shape[0],
            "test_size": X_test.shape[0],
            "classification_report": report,
            "roc_auc": round(auc, 4),
        }

    def _safe_predict_proba(self, X) -> np.ndarray:
        """احتمال کلاس ۱ (توقف) را ایمن برمی‌گرداند؛ اگر مدل تنها یک کلاس دیده باشد، صفر می‌دهد."""
        proba = self._clf.predict_proba(X)
        classes = list(self._clf.classes_)
        if 1 in classes:
            return proba[:, classes.index(1)]
        return np.zeros(X.shape[0])

    def _extract_features(self, df: pd.DataFrame) -> np.ndarray:
        feats = pd.DataFrame({
            "len": df["events"].str.split("|").str.len(),
            "unique_events": df["events"].str.split("|").apply(lambda s: len(set(s))),
            "has_bypass": df["events"].str.contains("Bypass-On").astype(int),
            "has_storm": df["events"].str.contains("Alarm-Storm").astype(int),
            "has_temp_high": df["events"].str.contains("Temp-High").astype(int),
            "has_press_low": df["events"].str.contains("Pressure-Low").astype(int),
            "has_vibration": df["events"].str.contains("Vibration-High").astype(int),
        }).to_numpy(dtype=float)
        return feats

    def predict(self, df: pd.DataFrame) -> list[SequencePrediction]:
        if not self._fitted:
            raise RuntimeError("model not fitted; call fit() first")
        X_tfidf = self._tfidf.transform(df["events"])
        extra = self._extract_features(df)
        from scipy.sparse import hstack
        X = hstack([X_tfidf, extra]).tocsr()
        proba = self._safe_predict_proba(X)
        results = []
        for i, row in enumerate(df.itertuples()):
            seq = row.events.split("|")
            next_event, next_p = self._predict_next(seq)
            p = float(proba[i])
            # تخمین horizon چندمرحله‌ای: فرض ساده‌ی نرخ ثابت رشد احتمال در زمان
            # P(t≤T) = 1 - (1-p)^k که k متناسب با افق زمانی است
            # کالیبراسیون: پنجره ۱ ساعت = p، ۲۴ ساعت = 24×p (محصول ویژگی‌های ثابت)
            # ۷۲ ساعت = 72×p با کاهش اثر (decay)
            p1h = float(np.clip(p * 1.0, 0.0, 1.0))
            p24h = float(np.clip(1 - (1 - p) ** 24, 0.0, 1.0))
            p72h = float(np.clip(1 - (1 - p) ** 72, 0.0, 1.0))
            # تخمین زمان تا توقف: معکوس نرخ
            if p > 0.05:
                lead = int(getattr(row, "lead_time_min", 0) if p > self.threshold else max(1, int(60 / p)))
                lead_to_shutdown = max(lead, int(60 / max(p, 0.01)))
            else:
                lead = 0
                lead_to_shutdown = -1  # غیرقابل پیش‌بینی
            risk = "Critical" if p > 0.7 else "High" if p > 0.4 else "Medium" if p > 0.15 else "Low"
            # اعتماد بر اساس تعداد نمونه‌های مشابه دیده‌شده
            confidence = float(np.clip(next_p if next_event != "Unknown" else 0.5, 0.0, 1.0))
            # اقدام پیشنهادی بر اساس horizon
            intervention = self._recommend_intervention(risk, p1h, p24h, p72h)
            results.append(SequencePrediction(
                sequence_id=row.sequence_id,
                shutdown_probability=round(p, 4),
                predicted_next_event=next_event,
                next_event_probability=round(next_p, 4),
                lead_time_min=lead,
                risk_level=risk,
                prob_shutdown_1h=round(p1h, 4),
                prob_shutdown_24h=round(p24h, 4),
                prob_shutdown_72h=round(p72h, 4),
                lead_time_to_shutdown_min=lead_to_shutdown,
                confidence=round(confidence, 3),
                recommended_intervention=intervention,
            ))
        return results

    def _recommend_intervention(self, risk: str, p1h: float, p24h: float, p72h: float) -> str:
        """اقدام پیشنهادی بر اساس horizon پیش‌بینی."""
        if p1h > 0.5:
            return "مداخله فوری در < ۱ ساعت: کاهش بار، فعال‌سازی بک‌آپ، آماده‌سازی تیم اضطراری."
        if p24h > 0.5:
            return "مداخله در ۲۴ ساعت: بازرسی فوری، کنترل پارامترهای بحرانی، آماده‌سازی shutdown کنترل‌شده."
        if p72h > 0.5:
            return "برنامه‌ریزی مداخله در ۷۲ ساعت: تحلیل روند، تنظیم فرآیند، بازرسی دوره‌ای زودهنگام."
        if risk == "Medium":
            return "افزایش فرکانس پایش و ثبت روند برای تحلیل پیشگیرانه."
        return "عملیات عادی؛ پایش استاندارد ادامه یابد."

    def _predict_next(self, seq: list[str]) -> tuple[str, float]:
        order = self.markov_order
        if len(seq) < order:
            return ("Unknown", 0.0)
        state = tuple(seq[-order:])
        transitions = self._markov.get(state)
        if not transitions:
            return ("Unknown", 0.0)
        total = sum(transitions.values())
        best = max(transitions.items(), key=lambda kv: kv[1])
        return (best[0], best[1] / total)

    def feature_importances(self, top_k: int = 15) -> list[dict]:
        if not self._fitted:
            return []
        names = self._tfidf.get_feature_names_out().tolist() + [
            "len", "unique_events", "has_bypass", "has_storm",
            "has_temp_high", "has_press_low", "has_vibration",
        ]
        imps = self._clf.feature_importances_
        idx = np.argsort(imps)[::-1][:top_k]
        return [{"feature": names[i], "importance": float(imps[i])} for i in idx]
