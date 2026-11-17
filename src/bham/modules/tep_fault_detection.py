"""ماژول ۵: تشخیص خطای فرآیند بر اساس داده واقعی TEP.

این ماژول از داده بنچ‌مارک Tennessee Eastman Process استفاده می‌کند تا
قابلیت تشخیص ناهنجاری/خطا در سیگنال‌های فرآیندی را اعتبارسنجی کند.

الگوریتم‌ها:
  - PCA + Q-statistic (T² و SPE) برای تشخیص ناهنجاری (MSPC)
  - Random Forest برای طبقه‌بندی نوع خطا
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


@dataclass
class FaultDetectionResult:
    fault_id: int
    is_anomaly: bool
    t2_statistic: float
    spe_statistic: float
    predicted_fault: int
    confidence: float


class TEPFaultDetector:
    """تشخیص خطای فرآیند بر اساس PCA + RF روی داده TEP."""

    def __init__(self, n_components: int = 15, n_estimators: int = 200, random_state: int = 42):
        self.n_components = n_components
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=n_components, random_state=random_state)
        self.clf = RandomForestClassifier(
            n_estimators=n_estimators, random_state=random_state, n_jobs=-1,
            class_weight="balanced"
        )
        self._t2_threshold: float = 0.0
        self._spe_threshold: float = 0.0
        self._fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray, test_size: float = 0.2, random_state: int = 42):
        Xs = self.scaler.fit_transform(X)
        Xp = self.pca.fit_transform(Xs)
        # آستانه‌های کنترل (تقریبی): میانگین + 3×انحراف معیار
        t2 = np.sum(Xp ** 2, axis=1)
        spe = np.sum((Xs - self.pca.inverse_transform(Xp)) ** 2, axis=1)
        self._t2_threshold = float(np.percentile(t2, 99))
        self._spe_threshold = float(np.percentile(spe, 99))

        X_tr, X_te, y_tr, y_te = train_test_split(
            Xp, y, test_size=test_size, random_state=random_state, stratify=y
        )
        self.clf.fit(X_tr, y_tr)
        self._fitted = True
        y_pred = self.clf.predict(X_te)
        report = classification_report(y_te, y_pred, output_dict=True, zero_division=0)
        cm = confusion_matrix(y_te, y_pred).tolist()
        return {
            "train_size": X_tr.shape[0],
            "test_size": X_te.shape[0],
            "n_components": self.n_components,
            "t2_threshold": round(self._t2_threshold, 2),
            "spe_threshold": round(self._spe_threshold, 2),
            "explained_variance_ratio": self.pca.explained_variance_ratio_.tolist(),
            "classification_report": report,
            "confusion_matrix": cm,
        }

    def detect(self, X: np.ndarray) -> list[FaultDetectionResult]:
        if not self._fitted:
            raise RuntimeError("model not fitted; call fit() first")
        Xs = self.scaler.transform(X)
        Xp = self.pca.transform(Xs)
        Xr = self.pca.inverse_transform(Xp)
        t2 = np.sum(Xp ** 2, axis=1)
        spe = np.sum((Xs - Xr) ** 2, axis=1)
        preds = self.clf.predict(Xp)
        proba = self.clf.predict_proba(Xp)
        results = []
        for i in range(X.shape[0]):
            is_anom = bool(t2[i] > self._t2_threshold or spe[i] > self._spe_threshold)
            conf = float(np.max(proba[i]))
            results.append(FaultDetectionResult(
                fault_id=int(preds[i]),
                is_anomaly=is_anom,
                t2_statistic=round(float(t2[i]), 2),
                spe_statistic=round(float(spe[i]), 4),
                predicted_fault=int(preds[i]),
                confidence=round(conf, 4),
            ))
        return results

    def fault_detection_rate(self, X: np.ndarray, y: np.ndarray,
                              warmup: int = 160) -> dict:
        """محاسبه نرخ تشخیص خطا (FDR) روی داده آزمون TEP.

        y: برچسب واقعی (0 = نرمال، k = خطا k).
        warmup: تعداد نمونه اول که نرمال فرض می‌شوند (160 در TEP).
        """
        results = self.detect(X)
        fdr = {}
        for fault_id in np.unique(y):
            if fault_id == 0:
                continue
            mask = (y == fault_id)[warmup:]
            if mask.sum() == 0:
                continue
            detected = sum(1 for r, t in zip(results, y)
                           if t == fault_id and (r.is_anomaly or r.predicted_fault == fault_id))
            total = int(mask.sum())
            fdr[f"fault_{int(fault_id):02d}"] = round(detected / max(total, 1), 4)
        # نرخ هشدار کاذب (FAR) روی نمونه‌های نرمال
        normal_mask = (y == 0)
        far = sum(1 for r, t in zip(results, y) if t == 0 and r.is_anomaly) / max(int(normal_mask.sum()), 1)
        return {"FDR_per_fault": fdr, "FAR_normal": round(far, 4)}
