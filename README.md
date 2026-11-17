# BHAM — سامانه هوشمند مدیریت آلارم و پایش سلامت لایه‌های حفاظتی ایمنی فرآیند

<div dir="rtl">

![TRL](reports/trl_assessment.png)

**پروژه:** هوشمندسازی مدیریت آلارم و پایش سلامت لایه‌های حفاظتی ایمنی فرآیند
**مشتری:** شرکت پتروشیمی غدیر
**توسعه‌دهنده:** شرکت پتروپالاتوس
**شماره نامه:** 14050817001
**سطح بلوغ فناوری:** TRL 5 ✅
**نسخه:** 2.1.0 (افزودن ماژول‌های کیفیت محصول و بهینه‌سازی خط تولید)

---

## فهرست

- [معرفی](#معرفی)
- [ویژگی‌ها](#ویژگی‌ها)
- [معماری سیستم](#معماری-سیستم)
- [نصب و راه‌اندازی](#نصب-و-راه‌اندازی)
- [اجرای سریع (Quickstart)](#اجرای-سریع-quickstart)
- [تولید داده مصنوعی](#تولید-داده-مصنوعی)
- [داده واقعی TEP](#داده-واقعی-tep)
- [آموزش مدل‌ها](#آموزش-مدل‌ها)
- [سرویس API](#سرویس-api)
- [داشبورد](#داشبورد)
- [تست‌ها و پوشش](#تست‌ها-و-پوشش)
- [ارزیابی TRL](#ارزیابی-trl)
- [ساختار پوشه‌ها](#ساختار-پوشه‌ها)
- [مستندات](#مستندات)
- [استقرار](#استقرار)
- [مسیر توسعه](#مسیر-توسعه)
- [مجوز](#مجوز)

---

## معرفی

BHAM یک سامانه هوشمند مبتنی بر هوش مصنوعی برای پایش ایمنی فرآیند در پتروشیمی غدیر است. این سامانه با یکپارچه‌سازی داده‌های آلارم، رخدادها، بایپس‌ها، نتایج تست دوره‌ای و شرایط عملیاتی، چهار قابلیت کلیدی فراهم می‌کند:

1. **تحلیل و اولویت‌بندی هوشمند آلارم** — کاهش سیل آلارم، شناسایی چترینگ، طوفان آلارم و علت‌های مشترک.
2. **پایش سلامت لایه‌های حفاظتی** — محاسبه شاخص سلامت BPCS/SIS/ESD/Relief/Procedural و تشخیص تجمع ضعف.
3. **پیش‌بینی توالی‌های منجر به توقف** — شناسایی الگوهای خطرناک پیش از وقوع.
4. **برآورد ریسک پویا و بهینه‌سازی برنامه تست** — RBI مبتنی بر ریسک واقعی.

این محصول با پایبندی به استانداردهای ISA 18.2، EEMUA 191، IEC 61511 و IEC 61508 توسعه یافته و روی داده واقعی بنچ‌مارک Tennessee Eastman Process (TEP) اعتبارسنجی شده است.

## ویژگی‌ها

### قابلیت‌های اصلی (نسخه ۲.۰.۰ — بهینه‌شده با بنچ‌مارک بین‌المللی)

- ✅ **۴ ماژول AI مستقل** با الگوریتم‌های تخصصی (DBSCAN، Isolation Forest، Random Forest، XGBoost، Weibull AFT، PCA، Markov Chain).
- ✅ **ماژول پنجم تشخیص خطای فرآیند** روی بنچ‌مارک واقعی TEP با ۱۰٬۵۸۰ نمونه آموزش و ۲۱٬۱۲۰ نمونه آزمون.
- ✅ **REST API کامل** با FastAPI (۱۵ endpoint) برای یکپارچه‌سازی با سیستم‌های دیگر.
- ✅ **داشبورد واکنش‌گرا** تک‌فایلی (HTML/CSS/JS بدون وابستگی خارجی) با پشتیبانی RTL و فارسی.
- ✅ **تست خودکار** با pytest (۱۱۴ تست)، پوشش ۹۳٪.
- ✅ **تولید داده مصنوعی** با الگوهای واقع‌گرایانه (چترینگ، علت مشترک، طوفان آلارم، توالی خطرناک).
- ✅ **مستندات کامل** SRS، BRS، TRL، معماری فنی، بنچ‌مارک.
- ✅ **قابلیت بازتولید** با seed ثابت و نسخه‌گذاری وابستگی.
- ✅ **سطح بلوغ فناوری TRL 5** (اعتبارسنجی در محیط مرتبط).

### قابلیت‌های جدید نسخه ۲ (منطبق با استانداردهای بین‌المللی)

**ماژول آلارم — منطبق با EEMUA 191 / ISA-18.2 / IEC 62682:**
- 📊 ۲۰ شاخص کامل EEMUA: نرخ پایدار/اوج (per 10 min)، چترینگ (هر دو معیار 1min/9min)، standing، stale، flood با شروع/پایان، توزیع اولویت، bad-actors، ack_compliance، بار اپراتور.
- 🎯 **Alarm Rationalization** خودکار (مرحله C چرخه ISA-18.2) با ۴ اقدام: Keep / Reprioritize / Retune / Remove.
- 🔇 **Alarm Shelving** (الزام IEC 62682) با ثبت دلیل، انقضا، و safety impact.
- 🔄 **State-Based Suppression** برای حالت‌های Start-up / Shutdown / Maintenance.
- 📈 **امتیاز انطباق خودکار** (0-100) با گرید A-D و گزارش شکاف‌ها.

**ماژول لایه‌های حفاظتی — منطبق با IEC 61511:**
- 🛡️ **تخمین SIL** (1-4) محقق‌شده بر اساس PFD (IEC 61511 Table 3).
- 🎯 **SIL هدف** بر اساس نوع لایه (BPCS=1, SIS=2, ESD=3).
- ⚖️ **LOPA** (Layer of Protection Analysis) با محاسبه RRF و مقایسه با RRF لازم برای ریسک قابل‌تحمل.
- ⏱️ **مدیریت زمان بایپس** با حداکثر مجاز بر اساس SIL (`MAX_BYPASS_H_PER_YEAR`).
- 📅 **فواصل تست بر اساس SIL** (SIL 3 = نیم‌سالانه، SIL 4 = فصلی).

**ماژول پیش‌بینی توالی:**
- ⏰ **Horizon چندمرحله‌ای**: احتمال توقف در ۱ ساعت، ۲۴ ساعت و ۷۲ ساعت آینده.
- 🎯 **تخمین lead-time** تا توقف و فیلد اعتماد (confidence).
- 💡 **توصیه مداخله** بر اساس horizon پیش‌بینی.

برای جزئیات بنچ‌مارک با محصولات تجاری (PAS, Honeywell, ABB, AspenTech, GE, Yokogawa, Siemens, Rockwell) به [docs/BENCHMARK.md](docs/BENCHMARK.md) مراجعه کنید.

### قابلیت‌های جدید نسخه ۲.۱ (بهینه‌سازی کیفیت محصول و خط تولید)

پس از تحلیل چالش‌های خط تولید و کیفیت محصول پتروشیمی غدیر (نرخ خرابی ۲.۵٪، نبود SPC، نبود OEE، نبود bottleneck analysis)، دو ماژول جدید اضافه شد:

**ماژول ۶: پایش و بهینه‌سازی کیفیت محصول (Quality Optimization) — منطبق با ISO 22514-2 / ISO 7870-2 / AIAG SPC:**
- 📊 **کنترل آماری فرآیند (SPC)** با ۸ قانون Western Electric (Rule1-8).
- 🎯 **شاخص قابلیت فرآیند**: Cp، Cpk، Pp، Ppk + گرید (Excellent/Acceptable/Marginal/Inadequate/Critical).
- 📈 **CUSUM و EWMA** برای تشخیص drift تدریجی و ناهنجاری زودهنگام.
- 🔍 **تحلیل علت ریشه‌ای** (Ishikawa fishbone 6M: Man/Machine/Material/Method/Measurement/Environment).
- ⚠ **اثر خطاها بر کیفیت**: رتبه‌بندی ۲۲ خطای فرآیندی بر اساس انحراف خلوص و اتلاف بازده.
- ⚙ **بهینه‌سازی setpoint**: پیشنهاد تنظیم متغیرهای دستکاری بر اساس همبستگی با کیفیت.

**ماژول ۷: بهینه‌سازی عملکرد خط تولید (Production Line Optimization) — منطبق با ISO 22400-2 / TPM (Nakajima) / Theory of Constraints:**
- 🏭 **OEE** (Overall Equipment Effectiveness) = Availability × Performance × Quality + گرید (World-class/Good/Fair/Poor/Critical).
- 🚧 **شناسایی گلوگاه** (Bottleneck) با Theory of Constraints + تعیین نوع محدودیت (Capacity/Speed/Quality/Availability).
- 📉 **تحلیل بازده** (Yield) با تفکیک اتلاف‌ها (downtime/quality/energy) + ارزش دلاری.
- 📊 **KPI تولید**: MTBF، MTTR، PPH، utilization، cycle time (مطابق SEMI E10).
- 💡 **بهینه‌سازی با ROI**: تحلیل هزینه-فایده با تخمین ROI و payback period برای اولویت‌بندی سرمایه‌گذاری.

برای جزئیات چالش‌های شناسایی‌شده و بهینه‌سازی‌ها به [docs/PRODUCTION_QUALITY.md](docs/PRODUCTION_QUALITY.md) مراجعه کنید.

## معماری سیستم

```
┌────────────────────────────────────────────────────────────┐
│                  داشبورد (frontend/dashboard.html)         │
└──────────────────────────┬─────────────────────────────────┘
                           │ HTTP/JSON
┌──────────────────────────▼─────────────────────────────────┐
│                  سرویس API (api/server.py - FastAPI)        │
└───┬───────────┬───────────┬───────────┬───────────┬────────┘
    │           │           │           │           │
┌───▼──┐  ┌────▼───┐  ┌────▼───┐  ┌────▼───┐  ┌────▼───┐
│ ماژول │  │ ماژول  │  │ ماژول  │  │ ماژول  │  │ ماژول  │
│ آلارم│  │ لایه‌ها│  │ توالی │  │ ریسک  │  │  TEP  │
│  ۱  │  │   ۲   │  │   ۳   │  │   ۴   │  │   ۵   │
└───┬──┘  └────┬───┘  └────┬───┘  └────┬───┘  └────┬───┘
    │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼
┌────────────────────────────────────────────────────────────┐
│              لایه داده (data/synthetic + data/real)         │
└────────────────────────────────────────────────────────────┘
```

برای جزئیات بیشتر به [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) مراجعه کنید.

## نصب و راه‌اندازی

### پیش‌نیازها

- Python 3.10 یا بالاتر (تست شده روی 3.12)
- pip
- git

### نصب وابستگی‌ها

```bash
git clone <repo-url>
cd inno-ghadir-petrochemical-shasta
pip install -e ".[dev]"
```

وابستگی‌های اصلی: numpy, pandas, scikit-learn, scipy, statsmodels, xgboost, lightgbm, fastapi, uvicorn, joblib, pydantic.

## اجرای سریع (Quickstart)

اجرای کامل خط لوله از صفر تا داشبورد:

```bash
# 1) تولید داده مصنوعی
python scripts/generate_synthetic_data.py

# 2) دانلود داده واقعی TEP
python scripts/download_tep.py
# اگر API rate-limited شد، فایل‌ها مستقیم از raw.githubusercontent.com گرفته می‌شوند.
# در صورت نیاز می‌توانید دستی دانلود کنید: data/real/raw_tep/d00.dat .. d21.dat

# 3) پیش‌پردازش TEP
python scripts/preprocess_tep.py

# 4) آموزش همه مدل‌ها
python scripts/train_all.py

# 5) ارزیابی TRL
python scripts/assess_trl.py

# 6) اجرای تست‌ها
PYTHONPATH=src pytest tests/

# 7) راه‌اندازی API و داشبورد
uvicorn api.server:app --host 0.0.0.0 --port 8000
# سپس مرورگر را روی http://localhost:8000 باز کنید
```

## تولید داده مصنوعی

```bash
python scripts/generate_synthetic_data.py
```

این اسکریپت چهار مجموعه داده می‌سازد:

| فایل | توضیح | اندازه نمونه |
|---|---|---|
| `data/synthetic/alarms.csv` | لاگ آلارم با چترینگ، علت مشترک، طوفان | ۲۵٬۰۰۰ رکورد |
| `data/synthetic/barriers.csv` | وضعیت لایه‌های حفاظتی + بایپس + تست دوره‌ای | ۲۱۹٬۰۰۰ رکورد |
| `data/synthetic/sequences.csv` | توالی رخدادها با برچسب خطرناک | ۴٬۰۰۰ رکورد |
| `data/synthetic/risk_signals.csv` | سیگنال‌های عملیاتی + خرابی | ۴۳٬۸۰۰ رکورد |

الگوریتم‌های تزریق الگو:
- چترینگ: ۴۰۰ آلارم پشت سر هم برای یک تگ.
- آلارم ثابت‌مانده: ۸۰ آلارم Active.
- علت مشترک: ۳۰ گروه همزمانی.
- توالی خطرناک: الگوی `Bypass-On → Alarm-Storm → Temp-High`.

## داده واقعی TEP

[Bench] Tennessee Eastman Process یک بنچ‌مارک استاندارد جهانی برای تشخیص خطا در فرآیندهای شیمیایی است که ساختار آن (۵۲ متغیر فرآیندی + ۲۱ نوع خطا) شبیه خطوط الفین/آروماتیک پتروشیمی غدیر است.

```bash
# دانلود خودکار
python scripts/download_tep.py

# یا دستی از:
# https://github.com/camaramm/tennessee-eastman-profBraatz
# فایل‌های d00.dat تا d21.dat و d00_te.dat تا d21_te.dat
# در پوشه data/real/raw_tep/ قرار دهید.

# پیش‌پردازش به CSV
python scripts/preprocess_tep.py
```

خروجی:
- `data/real/processed/tep_train.csv` — ۱۰٬۵۸۰ نمونه × ۵۳ ستون (۵۲ ویژگی + برچسب خطا).
- `data/real/processed/tep_test.csv` — ۲۱٬۱۲۰ نمونه آزمون.

## آموزش مدل‌ها

```bash
python scripts/train_all.py
```

این اسکریپت هر پنج ماژول را آموزش می‌دهد و خروجی‌ها را ذخیره می‌کند:

- `models/*.joblib` — مدل‌های ذخیره‌شده.
- `reports/*_module_report.json` — گزارش هر ماژول شامل معیارها و نمونه‌های پیش‌بینی.

### معیارهای کلیدی آموزش

| ماژول | معیار | مقدار |
|---|---|---|
| تحلیل آلارم | آلارم/ساعت، چترینگ، طوفان | ۶۰، ۲، ۱۴۸۷ |
| لایه‌های حفاظتی | میانگین سلامت، رویداد پرخطر | ۵۲٪، ۵۰ |
| پیش‌بینی توالی | AUC، F1 کلاس مثبت | ۰.۹۷، ۰.۹۸ |
| ریسک پویا | AUC | ۰.۴۹ (داده نامتوازن) |
| تشخیص خطای TEP | میانگین FDR، FAR | ۰.۴۰۵، ۰.۰۰۰۰ |

> نکته: AUC پایین ماژول ریسک پویا به دلیل نرخ خرابی پایین (۲.۵٪) در داده مصنوعی است. این موضوع در فاز پایلوت (TRL 6) با داده عملیاتی واقعی پتروشیمی غدیر بهبود می‌یابد.

## سرویس API

```bash
uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

### endpointها

| متد | مسیر | توضیح |
|---|---|---|
| GET | `/api/v1/health` | بررسی سلامت سرویس |
| GET | `/api/v1/metrics/summary` | خلاصه KPIهای آموزش |
| POST | `/api/v1/alarms/analyze` | تحلیل لاگ آلارم + compliance report |
| POST | `/api/v1/alarms/kpi/eemua` | شاخص‌های استاندارد EEMUA 191 / ISA-18.2 |
| POST | `/api/v1/alarms/rationalize` | Alarm Rationalization (ISA-18.2 مرحله C) |
| POST | `/api/v1/alarms/shelve` | Alarm Shelving (الزام IEC 62682) |
| POST | `/api/v1/alarms/shelve/batch` | شلف کردن گروهی |
| DELETE | `/api/v1/alarms/shelve/{tag}` | بازگرداندن آلارم از shelved |
| GET | `/api/v1/alarms/shelved` | فهرست آلارم‌های shelved |
| POST | `/api/v1/alarms/state-based-suppression` | خاموش خودکار بر اساس حالت فرآیند |
| POST | `/api/v1/barriers/health` | محاسبه سلامت + SIL لایه‌های حفاظتی (IEC 61511) |
| POST | `/api/v1/barriers/lopa` | تحلیل LOPA (کفایت لایه‌های حفاظتی) |
| POST | `/api/v1/barriers/bypass-events` | استخراج رویدادهای بایپس با انطباق SIL |
| POST | `/api/v1/sequences/predict` | پیش‌بینی احتمال توقف (horizon 1h/24h/72h) |
| POST | `/api/v1/risk/estimate` | برآورد ریسک پویا |
| POST | `/api/v1/tep/detect` | تشخیص خطای TEP |
| POST | `/api/v1/quality/spc` | تحلیل SPC یک متغیر (Western Electric + Cp/Cpk) |
| POST | `/api/v1/quality/report` | گزارش جامع کیفیت محصول (SPC + fault impact + RCA) |
| POST | `/api/v1/quality/fault-impact` | اثر خطاهای فرآیندی بر کیفیت |
| POST | `/api/v1/quality/setpoint-optimize` | بهینه‌سازی setpoint بر اساس همبستگی |
| POST | `/api/v1/production/oee` | محاسبه OEE (Availability × Performance × Quality) |
| POST | `/api/v1/production/bottlenecks` | شناسایی گلوگاه خط تولید (Theory of Constraints) |
| POST | `/api/v1/production/yield` | تحلیل بازده با تفکیک اتلاف‌ها |
| POST | `/api/v1/production/report` | گزارش جامع تولید (OEE + bottleneck + yield + ROI) |

مستندات تعاملی Swagger UI در `/docs` و ReDoc در `/redoc` در دسترس است.

### مثال

```bash
curl -X POST http://localhost:8000/api/v1/sequences/predict \
  -H "Content-Type: application/json" \
  -d '{"sequences":[{"sequence_id":"S1","events":"Bypass-On|Alarm-Storm|Temp-High","length":3}]}'
```

## داشبورد

داشبورد یک فایل HTML تک‌فایلی در `frontend/dashboard.html` است که می‌تواند مستقلاً یا از طریق API سرو شود.

ویژگی‌ها:
- **واکنش‌گرا** برای موبایل، تبلت و دسکتاپ.
- **RTL و فارسی** کامل.
- **حالت دمو** در صورت آفلاین بودن API (با داده‌های نمونه).
- ۶ نما: نمای کلی، تحلیل آلارم، لایه‌های حفاظتی، پیش‌بینی توالی، ریسک پویا، تشخیص خطای TEP.
- نمودارهای میله‌ای، دونات، جدول و کارت‌های KPI.

دسترسی از سرور API: `http://localhost:8000/` (ریشه).

## تست‌ها و پوشش

```bash
PYTHONPATH=src pytest tests/ -v
```

نتیجه فعلی: **۱۱۴ تست، همه موفق، پوشش ۹۳٪**.

گزارش پوشش HTML در `reports/coverage_html/index.html` و XML در `reports/coverage.xml`.

ساختار تست‌ها:
- `tests/test_alarm_analytics.py` — ماژول ۱.
- `tests/test_barrier_health.py` — ماژول ۲.
- `tests/test_sequence_prediction.py` — ماژول ۳.
- `tests/test_dynamic_risk.py` — ماژول ۴.
- `tests/test_tep_fault_detection.py` — ماژول ۵.
- `tests/test_integration.py` — تست‌های یکپارچگی end-to-end.
- `tests/test_api.py` — تست endpointهای API.

## ارزیابی TRL

```bash
python scripts/assess_trl.py
```

خروجی:
- `reports/trl_assessment.json` — ارزیابی تفصیلی هر سطح.
- `reports/trl_assessment.png` — نمودار میله‌ای پیشرفت.

نتیجه فعلی: **TRL 5 تکمیل شده** ✅ — اجزای کلیدی در محیط مرتبط (داده واقعی TEP + داشبورد زنده + API) اعتبارسنجی شده‌اند.

برای جزئیات بیشتر به [docs/TRL_ASSESSMENT.md](docs/TRL_ASSESSMENT.md) مراجعه کنید.

## ساختار پوشه‌ها

```
inno-ghadir-petrochemical-shasta/
├── src/bham/                  # پکیج اصلی
│   ├── __init__.py
│   ├── config.py              # پیکربندی مرکزی
│   └── modules/
│       ├── alarm_analytics.py         # ماژول ۱
│       ├── barrier_health.py          # ماژول ۲
│       ├── sequence_prediction.py     # ماژول ۳
│       ├── dynamic_risk.py            # ماژول ۴
│       └── tep_fault_detection.py     # ماژول ۵ (داده واقعی)
├── api/server.py              # سرویس FastAPI
├── frontend/dashboard.html    # داشبورد
├── scripts/
│   ├── generate_synthetic_data.py
│   ├── download_tep.py
│   ├── preprocess_tep.py
│   ├── train_all.py
│   └── assess_trl.py
├── tests/                     # ۴۹ تست pytest
├── data/
│   ├── synthetic/             # داده مصنوعی
│   ├── real/raw_tep/          # داده خام TEP
│   └── real/processed/        # داده پردازش‌شده
├── models/                    # مدل‌های ذخیره‌شده (.joblib)
├── reports/                   # گزارش‌ها + coverage
├── docs/                      # BRS، SRS، TRL، معماری
├── deployment/                # Docker و استقرار
├── configs/                   # پیکربندی
├── pyproject.toml
├── pytest.ini
└── README.md
```

## مستندات

- [docs/BRS.md](docs/BRS.md) — سند نیازمندی‌های کسب‌وکار
- [docs/SRS.md](docs/SRS.md) — سند نیازمندی‌های نرم‌افزار
- [docs/TRL_ASSESSMENT.md](docs/TRL_ASSESSMENT.md) — ارزیابی سطح بلوغ فناوری
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — معماری فنی
- [data/real/SOURCE.md](data/real/SOURCE.md) — منبع داده واقعی TEP

## استقرار

### Docker (پیشنهادی)

فایل `deployment/Dockerfile` در حال آماده‌سازی است. در حال حاضر می‌توانید مستقیم اجرا کنید:

```bash
# روی سرور لینوکس
pip install -e ".[dev]"
python scripts/generate_synthetic_data.py
python scripts/download_tep.py
python scripts/preprocess_tep.py
python scripts/train_all.py
uvicorn api.server:app --host 0.0.0.0 --port 8000
```

### systemd (پیشنهادی برای استقرار دائمی)

```ini
[Unit]
Description=BHAM API
After=network.target

[Service]
Type=simple
User=bham
WorkingDirectory=/opt/bham
ExecStart=/opt/bham/venv/bin/uvicorn api.server:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## مسیر توسعه

| فاز | وضعیت | توضیح |
|---|---|---|
| TRL 1-3 | ✅ کامل | اثبات مفهوم هر ماژول |
| TRL 4 | ✅ کامل | یکپارچه‌سازی + تست |
| **TRL 5** | **✅ کامل** | **اعتبارسنجی TEP + API + داشبورد** |
| TRL 6 | ⏳ فاز بعدی | پایلوت آفلاین روی یک واحد |
| TRL 7 | ⏳ آینده | استقرار پایلوت آنلاین |
| TRL 8 | ⏳ آینده | پذیرش نهایی |
| TRL 9 | ⏳ آینده | بهره‌برداری کامل |

## مجوز

این پروژه متعلق به شرکت پتروشیمی غدیر و شرکت پتروپالاتوس است و طبق نامه شماره 14050817001 برای دریافت اعتبار مالیاتی تحقیق و توسعه (قانون جهش تولید دانش‌بنیان، ماده ۱۱) توسعه یافته است.

## تماس

- **شرکت پتروپالاتوس** — فریده شفیعی، مدیرعامل
- **پتروشیمی غدیر** — کامران گنجی، مدیرعامل

---

*این پروژه با هدف ارتقای ایمنی فرآیند و تولید دانش فنی بومی توسعه یافته است.*
</div>
