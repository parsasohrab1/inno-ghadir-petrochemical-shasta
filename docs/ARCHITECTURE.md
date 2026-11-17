# معماری فنی BHAM
## Technical Architecture

## ۱. نمای کلی

```
┌────────────────────────────────────────────────────────────────────┐
│                       لایه نمایش (Dashboard)                       │
│              frontend/dashboard.html  (HTML تک‌فایلی)               │
└────────────────────────────────┬───────────────────────────────────┘
                                 │ HTTP/JSON
┌────────────────────────────────▼───────────────────────────────────┐
│                   لایه سرویس (FastAPI REST)                         │
│                          api/server.py                              │
└────┬──────────┬──────────┬──────────┬──────────┬─────────────────┘
     │          │          │          │          │
┌────▼───┐ ┌───▼────┐ ┌───▼────┐ ┌───▼────┐ ┌───▼────┐
│  ماژول  │ │  ماژول  │ │  ماژول  │ │  ماژول  │ │  ماژول  │
│   آلارم │ │ لایه‌ها │ │ توالی  │ │ ریسک   │ │  TEP   │
│   ۱     │ │   ۲    │ │   ۳    │ │   ۴    │ │   ۵    │
└────┬───┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
     │         │          │          │          │
     ▼         ▼          ▼          ▼          ▼
┌────────────────────────────────────────────────────────────────────┐
│                          لایه داده                                 │
│  data/synthetic/   data/real/processed/   data/raw/                │
│  alarms.csv        tep_train.csv         TEP .dat                  │
│  barriers.csv      tep_test.csv                                    │
│  sequences.csv                                                     │
│  risk_signals.csv                                                   │
└────────────────────────────────────────────────────────────────────┘
```

## ۲. پشته فناوری

| لایه | فناوری | دلیل انتخاب |
|---|---|---|
| زبان اصلی | Python 3.12 | اکوسیستم علم داده، کتابخانه‌های آماده |
| محاسبات علمی | numpy, pandas, scipy | استاندارد صنعت |
| یادگیری ماشین | scikit-learn, xgboost, lightgbm | الگوریتم‌های کلاسیک، تفسیرپذیر |
| تحلیل آماری | statsmodels | تحلیل بقا، AFT |
| API | FastAPI + Pydantic | سرعت، اسناد خودکار OpenAPI |
| داشبورد | HTML5 + Vanilla JS + CSS3 | بدون build step، portable |
| ذخیره مدل | joblib/pickle | استاندارد sklearn |
| تست | pytest + pytest-cov | استاندارد پایتون |
| نسخه‌گذاری | git | استاندارد |

## ۳. ساختار پوشه‌ها

```
inno-ghadir-petrochemical-shasta/
├── src/bham/                  # پکیج اصلی
│   ├── __init__.py
│   ├── config.py              # پیکربندی مرکزی
│   └── modules/               # ماژول‌های AI
│       ├── alarm_analytics.py
│       ├── barrier_health.py
│       ├── sequence_prediction.py
│       ├── dynamic_risk.py
│       └── tep_fault_detection.py
├── api/                       # سرویس REST
│   └── server.py
├── frontend/                  # داشبورد
│   └── dashboard.html
├── scripts/                   # اسکریپت‌های عملیاتی
│   ├── generate_synthetic_data.py
│   ├── download_tep.py
│   ├── preprocess_tep.py
│   ├── train_all.py
│   └── assess_trl.py
├── tests/                     # تست‌های pytest
├── data/                      # داده‌ها
│   ├── synthetic/
│   ├── real/
│   └── raw/
├── models/                    # مدل‌های ذخیره‌شده
├── reports/                   # گزارش‌ها
├── docs/                      # مستندات
├── configs/                   # پیکربندی
├── deployment/                # استقرار
├── pyproject.toml
├── pytest.ini
└── README.md
```

## ۴. الگوریتم‌ها به تفکیک ماژول

### ماژول ۱: آلارم
- **DBSCAN** (eps = 30 ثانیه) برای خوشه‌بندی زمانی.
- **Isolation Forest** (contamination = 0.05) برای ناهنجاری.
- شاخص‌های EEMUA 191 و ISA 18.2.
- تحلیل آماری μ ± 3σ برای پیشنهاد آستانه.

### ماژول ۲: لایه‌های حفاظتی
- تجمیع وزنی با وزن IEC 61511: BPCS=0.15, SIS=0.30, ESD=0.30, Relief=0.15, Procedural=0.10.
- کاهش نمایی `decay = exp(-λ × days_since_test)` با λ = 0.0008.
- PFD با فرض Poisson: `PFD ≈ λ × Δt`.
- تشخیص تجمع ضعف (≥ ۲ لایه همزمان).

### ماژول ۳: پیش‌بینی توالی
- **TF-IDF** با n-gram 1-2 روی رویدادها.
- ویژگی‌های آماری: طول، تنوع، شاخص‌های الگوی خطرناک.
- **Random Forest** (200 درخت) با class_weight balanced.
- زنجیره مارکوف مرتبه ۲ برای رویداد بعدی.

### ماژول ۴: ریسک پویا
- ویژگی‌های مهندسی: temp/pressure ratio, thermal stress, wear factor.
- **XGBoost** (300 درخت، max_depth=6).
- **Weibull AFT** برای MTBF: `scale_eff = base × (1 - 0.4 × stress)`.
- ریسک = P × (1 + 0.3 × stress).

### ماژول ۵: تشخیص خطای TEP
- **PCA** با 15 مؤلفه (توضیح ۸۷٪ واریانس).
- آماره **T²** (Hotelling) و **SPE/Q** برای ناهنجاری.
- **Random Forest** برای طبقه‌بندی 22 نوع خطا.
- ارزیابی FDR/FAR طبق پروتکل TEP استاندارد.

## ۵. جریان داده

```
1. تولید داده مصنوعی (scripts/generate_synthetic_data.py)
2. دانلود داده واقعی TEP (scripts/download_tep.py)
3. پیش‌پردازش TEP (scripts/preprocess_tep.py)
4. آموزش همه مدل‌ها (scripts/train_all.py)
5. ذخیره مدل‌ها در models/
6. سرویس API بارگذاری مدل‌ها در startup
7. داشبورد از طریق API داده می‌خواند
```

## ۶. ملاحظات مقیاس‌پذیری

- ماژول‌ها مستقل هستند؛ می‌توان هرکدام را در پروسه جداگانه اجرا کرد.
- مدل‌ها stateless پس از load؛ می‌توان چند worker اجرا کرد.
- برای مقیاس بزرگ‌تر: انتقال به Redis برای کش، PostgreSQL برای لاگ، Celery برای صف.

## ۷. ملاحظات امنیتی

- احراز هویت توکنی برای همه endpointها (فاز پایلوت).
- رمزگذاری TLS برای ترافیک.
- ایزوله کردن شبکه سرویس از DCS/SIS با دیوار آتش.
- انطباق با IEC 62443 برای سیستم‌های صنعتی.
- لاگ کامل دسترسی‌ها برای حسابرسی.
