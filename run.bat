@echo off
REM ============================================================
REM BHAM — اسکریپت راه‌اندازی داشبورد (بک‌اند + فرانت‌اند)
REM پلتفرم: Windows (CMD / PowerShell)
REM ============================================================
REM کاربرد:
REM   1. فایل را در پوشه ریشه پروژه قرار دهید
REM   2. دابل‌کلیک کنید یا در CMD اجرا کنید: run.bat
REM
REM متوقف‌سازی: Ctrl+C
REM ============================================================
setlocal EnableDelayedExpansion

echo ============================================================
echo   BHAM v2.1.0 - راه‌اندازی داشبورد
echo ============================================================

REM مسیر ریپو (مسیر همین اسکریپت)
cd /d "%~dp0"
echo مسیر پروژه: %CD%

REM ------------------------------------------------------------
REM مرحله ۱: بررسی پایتون
REM ------------------------------------------------------------
echo.
echo ▶ مرحله ۱: بررسی پایتون...
where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo ❌ پایتون نصب نیست. ابتدا پایتون ۳.۱۰+ را از https://python.org نصب کنید.
        echo    حتماً گزینه "Add Python to PATH" را هنگام نصب تیک بزنید.
        pause
        exit /b 1
    )
    set PY=py
) else (
    set PY=python
)
%PY% --version
echo ✓ پایتون OK

REM ------------------------------------------------------------
REM مرحله ۲: ساخت محیط مجازی (اگر نباشد)
REM ------------------------------------------------------------
echo.
echo ▶ مرحله ۲: محیط مجازی پایتون...
if not exist ".venv" (
    echo    ساخت محیط مجازی جدید...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo ❌ خطا در ساخت محیط مجازی.
        pause
        exit /b 1
    )
)
call .venv\Scripts\activate.bat
echo ✓ محیط مجازی فعال شد
set PY=python

REM ------------------------------------------------------------
REM مرحله ۳: نصب وابستگی‌ها
REM ------------------------------------------------------------
echo.
echo ▶ مرحله ۳: نصب وابستگی‌ها...
%PY% -m pip install --upgrade pip --quiet
%PY% -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ❌ خطا در نصب وابستگی‌ها.
    pause
    exit /b 1
)
echo ✓ وابستگی‌ها نصب شدند

REM ------------------------------------------------------------
REM مرحله ۴: تولید داده مصنوعی (اگر نباشد)
REM ------------------------------------------------------------
echo.
echo ▶ مرحله ۴: داده مصنوعی...
if not exist "data\synthetic\alarms.csv" (
    echo    تولید داده مصنوعی...
    %PY% scripts\generate_synthetic_data.py
    echo ✓ داده مصنوعی تولید شد
) else (
    echo ✓ داده مصنوعی از قبل موجود است
)

REM ------------------------------------------------------------
REM مرحله ۵: آموزش مدل‌ها (اگر نباشند)
REM ------------------------------------------------------------
echo.
echo ▶ مرحله ۵: مدل‌های آموزش‌دیده...
if not exist "models\sequence_predictor.joblib" (
    echo    آموزش مدل‌ها (چند دقیقه طول می‌کشد)...
    %PY% scripts\train_and_evaluate_all.py
    echo ✓ مدل‌ها آموزش دیدند
) else (
    echo ✓ مدل‌ها از قبل موجودند
)

REM ------------------------------------------------------------
REM مرحله ۶: ساخت گواهینامه SSL خودامضا (برای HTTPS)
REM ------------------------------------------------------------
echo.
echo ▶ مرحله ۶: گواهینامه SSL (برای HTTPS)...
if not exist "certs" mkdir certs
where openssl >nul 2>nul
if errorlevel 1 (
    echo    ⚠️ openssl یافت نشد — فقط HTTP روی پورت 8000 اجرا می‌شود
    echo    برای HTTPS، OpenSSL را نصب کنید یا از Git Bash استفاده کنید
    set HAS_SSL=0
) else (
    if not exist "certs\cert.pem" (
        echo    ساخت گواهینامه خودامضا...
        openssl req -x509 -newkey rsa:2048 -keyout certs\key.pem -out certs\cert.pem -days 365 -nodes -subj "/C=IR/ST=Tehran/L=Tehran/O=BHAM/OU=Dev/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>nul
        echo ✓ گواهینامه ساخته شد
        set HAS_SSL=1
    ) else (
        echo ✓ گواهینامه از قبل موجود است
        set HAS_SSL=1
    )
)

REM ------------------------------------------------------------
REM مرحله ۷: اجرای سرور (بک‌اند + فرانت)
REM ------------------------------------------------------------
echo.
echo ============================================================
echo   🚀 راه‌اندازی کامل شد!
echo ============================================================
echo.
echo   📊 داشبورد (HTTP):  http://localhost:8000/
echo   📚 مستندات API:     http://localhost:8000/docs
echo   ❤️  Health check:    http://localhost:8000/api/v1/health
if "!HAS_SSL!"=="1" (
    echo   📊 داشبورد (HTTPS): https://localhost:8443/
    echo   ⚠️  اگر مرورگر خطای SSL داد: روی «Advanced» → «Proceed» کلیک کنید
)
echo.
echo   برای توقف: Ctrl+C
echo ============================================================
echo.

REM باز کردن خودکار مرورگر پس از ۳ ثانیه
start "" cmd /c "timeout /t 3 >nul && start http://localhost:8000/"

REM اجرای سرور HTTPS در background (اگر SSL موجود باشد)
if "!HAS_SSL!"=="1" (
    start "BHAM-HTTPS" cmd /c "%PY% -m uvicorn api.server:app --host 0.0.0.0 --port 8443 --ssl-keyfile certs\key.pem --ssl-certfile certs\cert.pem"
    echo ✓ سرور HTTPS روی پورت 8443 اجرا شد
)

REM اجرای سرور HTTP در foreground (با reload برای توسعه)
%PY% -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload

pause
