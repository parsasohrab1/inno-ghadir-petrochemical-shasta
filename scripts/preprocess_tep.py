"""پیش‌پردازش داده واقعی TEP و تبدیل به CSV.

ساختار فایل‌های dXX.dat (Rieth et al. 2017):
  - هر فایل ماتریسی با shape (n_vars, n_samples) است
  - 52 متغیر فرآیندی (XMEAS 1..41 + XMV 1..11)
  - فایل‌های dXX.dat: 500 نمونه خطا-آزاد یا خطا-دار (آموزش)
  - فایل‌های dXX_te.dat: 960 نمونه آزمون (160 نمونه خطا-آزاد + 800 نمونه با خطا)

خروجی: data/real/processed/tep_train.csv و tep_test.csv با برچسب خطا.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
RAW = REPO / "data" / "real" / "raw_tep"
PROC = REPO / "data" / "real" / "processed"
PROC.mkdir(parents=True, exist_ok=True)

# نام ۵۲ متغیر TEP: ۴۱ متغیر اندازه‌گیری + ۱۱ متغیر دستکاری
VAR_NAMES = [f"xmeas_{i:02d}" for i in range(1, 42)] + [f"xmv_{i:02d}" for i in range(1, 12)]
assert len(VAR_NAMES) == 52


def load_dat(path: Path) -> np.ndarray:
    """فایل .dat را به آرایه (n_samples, 52) تبدیل می‌کند."""
    arr = np.loadtxt(path)
    if arr.ndim != 2:
        raise ValueError(f"{path}: expected 2D, got {arr.ndim}D")
    # اگر شکل (52, N) بود، ترانهاده کن
    if arr.shape[0] == 52 and arr.shape[1] != 52:
        return arr.T
    if arr.shape[1] == 52:
        return arr
    # حالت .dat خط‌شکن با ستون‌های چندگانه
    return arr.reshape(-1, 52)


def main() -> None:
    train_rows = []
    test_rows = []
    train_labels = []
    test_labels = []

    for fault_id in range(0, 22):
        train_path = RAW / f"d{fault_id:02d}.dat"
        test_path = RAW / f"d{fault_id:02d}_te.dat"
        if not train_path.exists() or not test_path.exists():
            print(f"[skip] fault {fault_id}: missing file")
            continue
        tr = load_dat(train_path)
        te = load_dat(test_path)
        train_rows.append(tr)
        train_labels.append(np.full(tr.shape[0], fault_id, dtype=int))
        test_rows.append(te)
        # در داده آزمون ۱۶۰ نمونه اول خطا-آزاد، ۸۰۰ نمونه بعدی خطا-دار
        te_lbl = np.zeros(te.shape[0], dtype=int)
        te_lbl[160:] = fault_id
        test_labels.append(te_lbl)
        print(f"[ok] fault {fault_id:02d}: train={tr.shape}, test={te.shape}")

    X_train = np.vstack(train_rows)
    y_train = np.concatenate(train_labels)
    X_test = np.vstack(test_rows)
    y_test = np.concatenate(test_labels)

    df_train = pd.DataFrame(X_train, columns=VAR_NAMES)
    df_train["fault_id"] = y_train
    df_test = pd.DataFrame(X_test, columns=VAR_NAMES)
    df_test["fault_id"] = y_test

    out_train = PROC / "tep_train.csv"
    out_test = PROC / "tep_test.csv"
    df_train.to_csv(out_train, index=False)
    df_test.to_csv(out_test, index=False)

    print(f"\n[done] TEP train: {df_train.shape} -> {out_train}")
    print(f"[done] TEP test:  {df_test.shape} -> {out_test}")
    print(f"[done] fault distribution (train): {np.bincount(y_train).tolist()}")
    print(f"[done] fault distribution (test):  {np.bincount(y_test).tolist()}")

    # یادداشت منبع
    src = REPO / "data" / "real" / "SOURCE.md"
    src.write_text(
        "# Tennessee Eastman Process — منبع داده واقعی\n\n"
        "## منبع\n"
        "- مخزن: https://github.com/camaramm/tennessee-eastman-profBraatz (شاخه master)\n"
        "- فایل‌های خام (.dat): data/real/raw_tep/d00.dat .. d21.dat و d00_te.dat .. d21_te.dat\n"
        "- مرجع علمی: Rieth et al. (2017), \"Additional Tennessee Eastman Process Simulation "
        "Data for Anomaly Detection Evaluation\", Harvard Dataverse DOI:10.7910/DVN/6C3JR1\n\n"
        "## ساختار\n"
        "- 52 متغیر فرآیندی (41 اندازه‌گیری XMEAS + 11 متغیر دستکاری XMV)\n"
        "- 22 سناریو: خطای 0 (نرمال) تا خطای 21\n"
        "- آموزش: 500 نمونه برای هر خطا\n"
        "- آزمون: 960 نمونه برای هر خطا (160 نمونه نرمال + 800 نمونه خطا-دار)\n"
        "- فایل‌های پردازش‌شده: data/real/processed/tep_train.csv, tep_test.csv\n\n"
        "## مرتبط با پتروشیمی غدیر\n"
        "TEP یک بنچ‌مارک استاندارد دانشگاهی برای تشخیص خطا و ایمنی فرآیند است. ساختار چند-"
        "متغیره و الگوهای خطای آن مشابه خطوط الفین/آروماتیک مجتمع غدیر است و برای ارزیابی\n"
        "ماژول‌های دوم و سوم BHAM (پایش لایه‌های حفاظتی و پیش‌بینی توالی) به‌کار می‌رود.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
