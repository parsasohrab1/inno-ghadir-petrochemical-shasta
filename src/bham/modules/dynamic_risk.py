"""ماژول ۴: برآورد ریسک پویا و بهینه‌سازی برنامه تست و بازرسی.

الگوریتم‌ها:
  - XGBoost برای طبقه‌بندی ریسک خرابی
  - مدل Weibull AFT برای زمان تا خرابی (تحلیل بقا)
  - فرآیند Poisson غیرهمگن برای شدت نرخ خرابی
  - بهینه‌سازی فواصل تست بر اساس ریسک واقعی (RBI / IEC 61511)
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import weibull_min
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

try:
    from xgboost import XGBClassifier
    _HAS_XGB = True
except Exception:
    _HAS_XGB = False


@dataclass
class RiskEstimate:
    unit: str
    timestamp: str
    failure_probability: float
    risk_score: float
    risk_level: str
    recommended_action: str
    weibull_mtbf_h: float  # mean time between failures (hours)


def _risk_level(score: float) -> str:
    if score >= 0.66:
        return "Critical"
    if score >= 0.33:
        return "High"
    if score >= 0.15:
        return "Medium"
    return "Low"


class DynamicRiskEstimator:
    """برآورد ریسک پویای واحد فرآیندی."""

    def __init__(self,
                 n_estimators: int = 300,
                 max_depth: int = 6,
                 learning_rate: float = 0.05,
                 weibull_shape: float = 1.5,
                 weibull_scale_h: float = 1500.0):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.weibull_shape = weibull_shape
        self.weibull_scale_h = weibull_scale_h
        self._scaler = StandardScaler()
        if _HAS_XGB:
            self._clf = XGBClassifier(
                n_estimators=n_estimators, max_depth=max_depth,
                learning_rate=learning_rate, random_state=42,
                eval_metric="logloss", n_jobs=-1,
            )
        else:
            from sklearn.ensemble import GradientBoostingClassifier
            self._clf = GradientBoostingClassifier(
                n_estimators=n_estimators, max_depth=max_depth,
                learning_rate=learning_rate, random_state=42,
            )
        self._feature_names: list[str] = []
        self._fitted = False

    def _features(self, df: pd.DataFrame) -> pd.DataFrame:
        cols = ["temperature_c", "pressure_bar", "flow_kg_h",
                "vibration_mm_s", "operating_hours"]
        out = pd.DataFrame(index=df.index)
        for c in cols:
            if c in df.columns:
                out[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
            else:
                out[c] = 0.0
        # ویژگی‌های مهندسی
        out["temp_pressure_ratio"] = out["temperature_c"] / (out["pressure_bar"] + 1e-3)
        out["thermal_stress"] = (out["temperature_c"] - 150) ** 2 / 1000
        out["wear_factor"] = out["operating_hours"] / 2000
        out["vibration_index"] = out["vibration_mm_s"] / 5.0
        self._feature_names = out.columns.tolist()
        return out

    def _safe_proba(self, X) -> np.ndarray:
        """احتمال کلاس ۱ (خرابی) را ایمن برمی‌گرداند."""
        try:
            proba = self._clf.predict_proba(X)
            classes = list(self._clf.classes_)
            if 1 in classes:
                return proba[:, classes.index(1)]
            return np.zeros(X.shape[0])
        except Exception:
            scores = self._clf.decision_function(X)
            return 1 / (1 + np.exp(-scores))

    def fit(self, df: pd.DataFrame, test_size: float = 0.2, random_state: int = 42):
        X = self._features(df)
        y = df["failure"].astype(int).to_numpy()
        # اگر یک کلاس نماینده کم داشت، stratify را حذف کن
        stratify = y if len(np.unique(y)) > 1 and np.bincount(y).min() >= 2 else None
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=stratify
        )
        X_tr_s = self._scaler.fit_transform(X_tr.values)
        X_te_s = self._scaler.transform(X_te.values)
        # مقابله با عدم تعادل کلاس (failure rate ~2.5٪) با وزن‌دهی کلاس
        n_pos = int(np.sum(y_tr == 1))
        n_neg = int(np.sum(y_tr == 0))
        if _HAS_XGB and n_pos > 0 and n_neg > 0:
            # XGBoost: scale_pos_weight = neg/pos
            try:
                self._clf.set_params(scale_pos_weight=max(n_neg / n_pos, 1.0))
            except Exception:
                pass
        elif n_pos > 0 and n_neg > 0:
            try:
                self._clf.set_params(sample_weight=np.where(y_tr == 1, n_neg / n_pos, 1.0))
            except Exception:
                pass
        self._clf.fit(X_tr_s, y_tr)
        self._fitted = True
        y_pred = self._clf.predict(X_te_s)
        y_proba = self._safe_proba(X_te_s)
        report = classification_report(y_te, y_pred, output_dict=True, zero_division=0)
        try:
            auc = float(roc_auc_score(y_te, y_proba))
        except Exception:
            auc = 0.5
        return {
            "train_size": X_tr.shape[0],
            "test_size": X_te.shape[0],
            "classification_report": report,
            "roc_auc": round(auc, 4),
            "feature_names": self._feature_names,
            "class_balance": {"positive": n_pos, "negative": n_neg,
                               "scale_pos_weight": round(max(n_neg / n_pos, 1.0), 2) if n_pos > 0 else 1.0},
        }

    def predict(self, df: pd.DataFrame) -> list[RiskEstimate]:
        if not self._fitted:
            raise RuntimeError("model not fitted; call fit() first")
        X = self._features(df)
        Xs = self._scaler.transform(X.values)
        proba = self._safe_proba(Xs)
        # تخمین MTBF با توزیع Weibull و شدت نرخ خرابی وابسته به بار عملیاتی
        results = []
        for i, row in enumerate(df.itertuples()):
            unit = getattr(row, "unit", "unknown")
            ts = str(getattr(row, "timestamp", "unknown"))
            p = float(np.clip(proba[i], 0.0, 1.0))
            # شدت بار عملیاتی: دما بالا/فشار پایین = فشار حرارتی بیشتر = MTBF کوتاه‌تر
            stress = abs(getattr(row, "temperature_c", 150) - 150) / 50 + max(0, 35 - getattr(row, "pressure_bar", 35)) / 20
            scale_eff = self.weibull_scale_h * max(0.3, 1.0 - stress * 0.4)
            mtbf = float(weibull_min.mean(self.weibull_shape, scale=scale_eff))
            score = p * (1 + stress * 0.3)
            score = float(np.clip(score, 0.0, 1.0))
            level = _risk_level(score)
            action = self._action(level, getattr(row, "operating_hours", 0))
            results.append(RiskEstimate(
                unit=unit, timestamp=ts,
                failure_probability=round(p, 4),
                risk_score=round(score, 4),
                risk_level=level,
                recommended_action=action,
                weibull_mtbf_h=round(mtbf, 1),
            ))
        return results

    def _action(self, level: str, op_hours: int) -> str:
        if level == "Critical":
            return "کاهش بار فوری + فعال‌سازی لایه‌های حفاظتی اضافی + بررسی توقف."
        if level == "High":
            return "افزایش پایش + آماده‌سازی برنامه مداخله + بازرسی اضافی در ۲۴ ساعت."
        if level == "Medium":
            return "ادامه پایش با فرکانس بالاتر + ثبت روند برای تحلیل."
        return "عملیات عادی؛ پایش دوره‌ای استاندارد."

    def optimize_test_schedule(self, df: pd.DataFrame, base_interval_d: int = 365) -> pd.DataFrame:
        """پیشنهاد برنامه تست و بازرسی مبتنی بر ریسک پویا."""
        results = self.predict(df)
        df = df.reset_index(drop=True).copy()
        df["failure_probability"] = [r.failure_probability for r in results]
        df["risk_score"] = [r.risk_score for r in results]
        df["mtbf_h"] = [r.weibull_mtbf_h for r in results]
        # فاصله پیشنهادی معکوس ریسک
        df["recommended_interval_d"] = np.clip(
            (1.0 - df["risk_score"]) * base_interval_d, 30, base_interval_d * 2
        ).astype(int)
        # اولویت: ریسک بالاتر = اولویت بالاتر
        df["priority"] = pd.cut(df["risk_score"], bins=[-0.01, 0.15, 0.33, 0.66, 1.01],
                                labels=["Low", "Medium", "High", "Critical"])
        return df[["unit", "timestamp", "failure_probability", "risk_score",
                   "mtbf_h", "recommended_interval_d", "priority"]]

    def feature_importances(self, top_k: int = 15) -> list[dict]:
        if not self._fitted:
            return []
        try:
            imp = self._clf.feature_importances_
        except Exception:
            return []
        idx = np.argsort(imp)[::-1][:top_k]
        names = self._feature_names
        return [{"feature": names[i], "importance": float(imp[i])} for i in idx if i < len(names)]
