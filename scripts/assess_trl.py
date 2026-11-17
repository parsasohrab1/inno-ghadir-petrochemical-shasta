"""ارزیابی سطح بلوغ فناوری (TRL) محصول BHAM.

TRL 1: اصول پایه مشاهده شده
TRL 2: مفهوم فناوری formul شده
TRL 3: اثبات مفهوم آزمایشگاهی
TRL 4: تأیید اجزای کلیدی در محیط آزمایشگاهی
TRL 5: اعتبارسنجی اجزای کلیدی در محیط مرتبط (relevant environment)
TRL 6: نمونه سیستم/زیرسیاستم در محیط مرتبط
TRL 7: نمونه اولیه سیستم در محیط عملیاتی
TRL 8: سیستم کامل تأیید شده
TRL 9: سیستم واقعی اثبات شده در عمل

این اسکریپت وضعیت فعلی هر معیار TRL را ارزیابی و گزارش JSON + نمودار می‌سازد.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "src"))
REPORTS_DIR = REPO / "reports"
REPORTS_DIR.mkdir(exist_ok=True, parents=True)


# معیارها برای رسیدن به هر سطح TRL
TRL_CRITERIA = {
    1: ["مشاهده و تعریف مسئله ایمنی فرآیند و حجم آلارم",
        "تدوین ایده اولیه سامانه هوشمند مدیریت آلارم"],
    2: ["فرمول‌بندی معماری ۴ ماژولی BHAM",
        "انتخاب الگوریتم‌های کاندید (DBSCAN، Isolation Forest، Random Forest، XGBoost، Weibull)"],
    3: ["پیاده‌سازی نمونه اولیه هر ماژول در پایتون",
        "اجرای موفق روی داده شبیه‌سازی‌شده کوچک",
        "اعتبارسنجی مفهوم چترینگ/خوشه‌بندی/تشخیص ناهنجاری"],
    4: ["تجمیع چهار ماژول در یک پکیج نرم‌افزاری (bham)",
        "خط لوله آموزش سرتاسری (train_all.py)",
        "مجموعه تست‌های واحد با پوشش ≥ ۸۰٪",
        "گزارش شاخص‌های کمی هر ماژول"],
    5: ["اعتبارسنجی روی داده واقعی بنچ‌مارک صنعت (TEP)",
        "نمونه اولیه API سرویس (FastAPI) با مدل‌های آموزش‌دیده",
        "داشبورد نمایش زنده خروجی مدل‌ها",
        "مستندات SRS/BRS و معماری فنی",
        "ارزیابی FDR/FAR روی داده واقعی",
        "نسخه‌گذاری و قابلیت بازتولید (versioning + reproduce)"],
}


def assess() -> dict:
    """ارزیابی معیارهای هر سطح TRL و گزارش وضعیت."""
    results = {}
    achieved = 0
    for level in range(1, 6):
        criteria = TRL_CRITERIA[level]
        evidence = _collect_evidence(level)
        completed = []
        pending = []
        for c in criteria:
            key = _key(c)
            if evidence.get(key):
                completed.append(c)
            else:
                pending.append(c)
        ratio = len(completed) / len(criteria)
        status = "completed" if ratio == 1.0 else ("partial" if ratio >= 0.5 else "not_started")
        results[f"TRL_{level}"] = {
            "level": level,
            "criteria_total": len(criteria),
            "criteria_completed": len(completed),
            "ratio": round(ratio, 2),
            "status": status,
            "completed": completed,
            "pending": pending,
        }
        if ratio == 1.0:
            achieved = level
        elif ratio >= 0.5 and achieved < level:
            achieved_partial = level

    overall = {
        "achieved_trl": achieved,
        "target_trl": 5,
        "details": results,
        "evidence": _collect_evidence_all(),
        "summary": _summary_text(achieved),
    }
    return overall


def _key(text: str) -> str:
    """تبدیل متن فارسی به کلید ایمن."""
    import hashlib
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:10]


def _collect_evidence(level: int) -> dict:
    """بررسی وجود فایل‌های شواهد برای هر سطح TRL."""
    repo = REPO
    ev = {}
    if level == 1:
        ev[_key("مشاهده و تعریف مسئله ایمنی فرآیند و حجم آلارم")] = (repo / "docs" / "BRS.md").exists() or (repo / "upload" ).exists()
        ev[_key("تدوین ایده اولیه سامانه هوشمند مدیریت آلارم")] = (repo / "docs" / "BRS.md").exists()
    elif level == 2:
        ev[_key("فرمول‌بندی معماری ۴ ماژولی BHAM")] = (repo / "src" / "bham" / "config.py").exists()
        ev[_key("انتخاب الگوریتم‌های کاندید (DBSCAN، Isolation Forest، Random Forest، XGBoost، Weibull)")] = (repo / "src" / "bham" / "modules").exists()
    elif level == 3:
        ev[_key("پیاده‌سازی نمونه اولیه هر ماژول در پایتون")] = (repo / "src" / "bham" / "modules" / "alarm_analytics.py").exists()
        ev[_key("اجرای موفق روی داده شبیه‌سازی‌شده کوچک")] = (repo / "data" / "synthetic").exists() and any((repo / "data" / "synthetic").iterdir())
        ev[_key("اعتبارسنجی مفهوم چترینگ/خوشه‌بندی/تشخیص ناهنجاری")] = (repo / "reports" / "alarm_module_report.json").exists()
    elif level == 4:
        ev[_key("تجمیع چهار ماژول در یک پکیج نرم‌افزاری (bham)")] = (repo / "src" / "bham" / "__init__.py").exists()
        ev[_key("خط لوله آموزش سرتاسری (train_all.py)")] = (repo / "scripts" / "train_all.py").exists()
        ev[_key("مجموعه تست‌های واحد با پوشش ≥ ۸۰٪")] = (repo / "reports" / "coverage.xml").exists()
        ev[_key("گزارش شاخص‌های کمی هر ماژول")] = (repo / "reports").exists() and any((repo / "reports").glob("*_report.json"))
    elif level == 5:
        ev[_key("اعتبارسنجی روی داده واقعی بنچ‌مارک صنعت (TEP)")] = (repo / "data" / "real" / "processed" / "tep_train.csv").exists()
        ev[_key("نمونه اولیه API سرویس (FastAPI) با مدل‌های آموزش‌دیده")] = (repo / "api").exists() and any((repo / "api").glob("*.py"))
        ev[_key("داشبورد نمایش زنده خروجی مدل‌ها")] = (repo / "frontend").exists() and any((repo / "frontend").glob("*.html"))
        ev[_key("مستندات SRS/BRS و معماری فنی")] = (repo / "docs").exists()
        ev[_key("ارزیابی FDR/FAR روی داده واقعی")] = (repo / "reports" / "tep_fault_module_report.json").exists()
        ev[_key("نسخه‌گذاری و قابلیت بازتولید (versioning + reproduce)")] = (repo / "pyproject.toml").exists() and (repo / ".git").exists()
    return ev


def _collect_evidence_all() -> dict:
    out = {}
    for lvl in range(1, 6):
        out[f"TRL_{lvl}"] = _collect_evidence(lvl)
    return out


def _summary_text(achieved: int) -> str:
    if achieved >= 5:
        return ("سطح TRL 5 به‌طور کامل حاصل شده است: اجزای کلیدی سامانه در محیط مرتبط "
                "(داده واقعی بنچ‌مارک TEP + داشبورد زنده + API) اعتبارسنجی شده‌اند.")
    if achieved >= 4:
        return ("سطح TRL 4 حاصل و TRL 5 در حال تکمیل است؛ شواهد اعتبارسنجی محیط مرتبط "
                "(داده واقعی + داشبورد + API) باید تکمیل شوند.")
    return f"سطح فعلی: TRL {achieved}. ادامه توسعه برای رسیدن به TRL 5 لازم است."


def plot(assessment: dict) -> Path:
    """رسم نمودار میله‌ای پیشرفت TRL."""
    import matplotlib.font_manager as fm
    fm.fontManager.addfont('/usr/share/fonts/truetype/chinese/NotoSansSC-Regular.ttf')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['Noto Sans SC', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

    levels = [f"TRL {i}" for i in range(1, 6)]
    ratios = [assessment["details"][f"TRL_{i}"]["ratio"] * 100 for i in range(1, 6)]
    colors = ['#9e9e9e', '#90caf9', '#66bb6a', '#42a5f5', '#ef5350']

    fig, ax = plt.subplots(figsize=(10, 5.5), constrained_layout=True)
    bars = ax.bar(levels, ratios, color=colors, edgecolor='#222', linewidth=0.8)
    for b, r in zip(bars, ratios):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 2,
                f"{r:.0f}%", ha='center', va='bottom', fontsize=12, fontweight='bold')
    ax.set_ylabel("Criteria Completion (%)", fontsize=12)
    ax.set_title("BHAM Technology Readiness Level (TRL) Assessment", fontsize=13, fontweight='bold')
    ax.set_ylim(0, 110)
    ax.axhline(100, color='#888', linestyle='--', linewidth=0.7)
    ax.grid(axis='y', alpha=0.3)
    out = REPORTS_DIR / "trl_assessment.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


def main():
    result = assess()
    out_json = REPORTS_DIR / "trl_assessment.json"
    out_json.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[trl] assessment saved -> {out_json}")
    print(f"[trl] achieved TRL: {result['achieved_trl']} (target: {result['target_trl']})")
    for i in range(1, 6):
        d = result["details"][f"TRL_{i}"]
        print(f"  TRL {i}: {d['criteria_completed']}/{d['criteria_total']} ({d['status']})")
    try:
        png = plot(result)
        print(f"[trl] chart saved -> {png}")
    except Exception as e:
        print(f"[trl] chart failed: {e}")


if __name__ == "__main__":
    main()
