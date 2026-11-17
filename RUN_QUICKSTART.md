# راهنمای سریع اجرای داشبورد BHAM

این راهنما نحوه اجرای داشبورد (بک‌اند + فرانت) روی ماشین محلی شما را توضیح می‌دهد.

---

## 🚀 اجرای سریع (یک دستور)

### روی Linux / macOS / WSL

```bash
./run.sh
```

### روی ویندوز (CMD یا دابل‌کلیک)

```
run.bat
```

اسکریپت به‌طور خودکار:
1. محیط مجازی پایتون `.venv` می‌سازد
2. وابستگی‌ها را نصب می‌کند
3. داده مصنوعی را تولید می‌کند (اگر نباشد)
4. مدل‌های ML را آموزش می‌دهد (اگر نباشند)
5. سرور را روی `http://localhost:8000` اجرا می‌کند

پس از اجرا، مرورگر را به آدرس زیر ببرید:

| آدرس | توضیح |
|---|---|
| **http://localhost:8000/** | 📊 داشبورد اصلی (رابط گرافیکی فارسی RTL) |
| **http://localhost:8000/docs** | 📚 مستندات تعاملی Swagger UI |
| **http://localhost:8000/api/v1/health** | ❤️ بررسی سلامت سرور و ماژول‌ها |

---

## 📋 پیش‌نیازها

| مورد | نسخه | نحوه نصب |
|---|---|---|
| **پایتون** | ۳.۱۰+ | https://python.org (ویندوز: تیک "Add to PATH") |
| **Git** | هر نسخه | https://git-scm.com |
| **فضای دیسک** | ~۵۰۰ مگابایت | برای مدل‌ها و وابستگی‌ها |

### نصب پایتون روی توزیع‌های لینوکس

```bash
# Ubuntu / Debian / WSL
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# Fedora / RHEL
sudo dnf install -y python3 python3-pip
```

---

## 🔧 اجرای دستی (گام‌به‌گام)

اگر می‌خواهید مراحل را به‌صورت دستی اجرا کنید:

### ۱) کلون ریپو

```bash
git clone https://github.com/parsasohrab1/inno-ghadir-petrochemical-shasta.git
cd inno-ghadir-petrochemical-shasta
```

### ۲) ساخت محیط مجازی و نصب وابستگی‌ها

```bash
# Linux / macOS / WSL
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```bat
:: Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### ۳) تولید داده و آموزش مدل‌ها (فقط بار اول)

```bash
python scripts/generate_synthetic_data.py
python scripts/train_and_evaluate_all.py
```

### ۴) اجرای سرور

```bash
# Backend (FastAPI) + Frontend (dashboard HTML) در یک سرور
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

سپس مرورگر را به `http://localhost:8000` ببرید.

---

## 🏗️ معماری

```
┌─────────────────────────────────────────────────┐
│  مرورگر کاربر (Client)                          │
│  http://localhost:8000/                         │
└────────────────────┬────────────────────────────┘
                     │ HTTP / JSON
                     ▼
┌─────────────────────────────────────────────────┐
│  FastAPI Server  (api/server.py)                │
│  ├── /                  → dashboard.html (RTL)  │
│  ├── /docs              → Swagger UI            │
│  └── /api/v1/*          → 23 REST endpoint      │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  مدل‌های ML  (models/*.joblib)                  │
│  ├── alarm_analytics.joblib                     │
│  ├── sequence_predictor.joblib  (ROC-AUC=0.97) │
│  ├── dynamic_risk.joblib        (ROC-AUC=0.69)  │
│  ├── tep_fault_detector.joblib  (FDR=0.41)      │
│  └── ...                                        │
└─────────────────────────────────────────────────┘
```

**نکته:** بک‌اند و فرانت در **یک سرور واحد** سرو می‌شوند — نیازی به اجرای دو سرور جداگانه نیست. سرور FastAPI داشبورد HTML را در مسیر `/` و API را در مسیر `/api/v1/*` ارائه می‌دهد.

---

## 🧪 تست عملکرد داشبورد

پس از اجرای سرور، این دستورها را در ترمینال دیگری اجرا کنید:

```bash
# ۱) بررسی سلامت
curl http://localhost:8000/api/v1/health

# ۲) تحلیل آلارم
curl -X POST http://localhost:8000/api/v1/alarms/analyze \
  -H "Content-Type: application/json" \
  -d '{"alarms":[{"timestamp":"2024-01-01T00:00:00","tag":"TI-101","priority":"High","status":"active","value":150.0,"setpoint":140.0}]}'

# ۳) تخمین ریسک پویا
curl -X POST http://localhost:8000/api/v1/risk/estimate \
  -H "Content-Type: application/json" \
  -d '{"signals":[{"timestamp":"2024-01-01T00:00:00","unit":"Aromatics-Unit","temperature_c":180,"pressure_bar":30,"flow_kg_h":180,"vibration_mm_s":3.5,"operating_hours":1500}]}'
```

یا به‌سادگی به `http://localhost:8000/docs` بروید و endpointها را به‌صورت تعاملی تست کنید.

---

## 🛑 متوقف‌سازی سرور

در ترمینالی که سرور در حال اجراست، `Ctrl+C` را فشار دهید.

---

## ❓ رفع مشکل

### مشکل: `python: command not found` (لینوکس)
```bash
# از python3 استفاده کنید یا alias بسازید
sudo apt install python-is-python3
```

### مشکل: `pip: command not found`
```bash
sudo apt install python3-pip
# یا
python3 -m ensurepip --upgrade
```

### مشکل: پورت ۸۰۰۰ اشغال است
```bash
# پیدا کردن و کشتن پروسه
lsof -i :8000          # Linux/macOS
netstat -ano | findstr :8000   # Windows
```
یا از پورت دیگر استفاده کنید:
```bash
python -m uvicorn api.server:app --host 0.0.0.0 --port 8080
```

### مشکل: `ModuleNotFoundError: No module named 'bham'`
مطمئن شوید از مسیر ریشه ریپو اجرا می‌کنید و محیط مجازی فعال است:
```bash
cd inno-ghadir-petrochemical-shasta
source .venv/bin/activate   # Linux
# یا
.venv\Scripts\activate      # Windows
```

### مشکل: مدل‌ها بارگذاری نمی‌شوند
اگر `models/*.joblib` وجود ندارند، ابتدا آموزش را اجرا کنید:
```bash
python scripts/generate_synthetic_data.py
python scripts/train_and_evaluate_all.py
```

---

## 📁 فایل‌های کلیدی

| فایل | توضیح |
|---|---|
| `run.sh` | اسکریپت اجرای کامل (Linux/macOS/WSL) |
| `run.bat` | اسکریپت اجرای کامل (Windows) |
| `requirements.txt` | وابستگی‌های پایتون |
| `api/server.py` | سرور FastAPI (بک‌اند + سرو فرانت) |
| `frontend/dashboard.html` | داشبورد HTML (فرانت) |
| `scripts/generate_synthetic_data.py` | تولید داده مصنوعی |
| `scripts/train_and_evaluate_all.py` | آموزش و ارزیابی همه مدل‌ها |

---

## ✅ تأیید موفقیت

اگر همه چیز درست باشد، باید ببینید:

```
INFO:     Started server process [XXXX]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

و با باز کردن `http://localhost:8000/api/v1/health`:

```json
{
    "status": "ok",
    "version": "2.1.0",
    "product": "BHAM",
    "modules_loaded": {
        "alarm": true,
        "barrier": true,
        "sequence": true,
        "risk": true,
        "tep": true
    }
}
```
