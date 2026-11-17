#!/usr/bin/env bash
# ============================================================
# BHAM — اسکریپت راه‌اندازی داشبورد (بک‌اند + فرانت‌اند)
# پلتفرم‌ها: Linux / macOS / WSL
# ============================================================
# این اسکریپت:
#   ۱) محیط مجازی پایتون می‌سازد (اگر نباشد)
#   ۲) وابستگی‌ها را نصب می‌کند (اگر نباشند)
#   ۳) داده مصنوعی و مدل‌ها را تولید/آموزش می‌دهد (اگر نباشند)
#   ۴) سرور FastAPI را روی http://localhost:8000 اجرا می‌کند
#
# کاربرد:
#   chmod +x run.sh
#   ./run.sh
#
# متوقف‌سازی: Ctrl+C
# ============================================================
set -e

# رنگ‌ها برای خروجی
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  BHAM v2.1.0 — راه‌اندازی داشبورد${NC}"
echo -e "${BLUE}============================================================${NC}"

# مسیر ریپو (مسیر همین اسکریپت)
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO"
echo -e "${YELLOW}📁 مسیر پروژه: $REPO${NC}"

# ------------------------------------------------------------
# مرحله ۱: بررسی پایتون
# ------------------------------------------------------------
echo -e "\n${YELLOW}▶ مرحله ۱: بررسی پایتون...${NC}"
if command -v python3 &>/dev/null; then
    PY=python3
elif command -v python &>/dev/null; then
    PY=python
else
    echo -e "${RED}❌ پایتون نصب نیست. ابتدا پایتون ۳.۱۰+ را نصب کنید:${NC}"
    echo -e "   Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
    echo -e "   macOS (brew):  brew install python"
    exit 1
fi
$PY --version
if ! $PY -c "import sys; assert sys.version_info >= (3,10)" 2>/dev/null; then
    echo -e "${RED}❌ به پایتون ۳.۱۰ یا بالاتر نیاز است.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ پایتون OK${NC}"

# ------------------------------------------------------------
# مرحله ۲: ساخت محیط مجازی (اگر نباشد)
# ------------------------------------------------------------
echo -e "\n${YELLOW}▶ مرحله ۲: محیط مجازی پایتون...${NC}"
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}   ساخت محیط مجازی جدید...${NC}"
    $PY -m venv .venv
fi
# فعال‌سازی محیط مجازی
source .venv/bin/activate
echo -e "${GREEN}✓ محیط مجازی فعال شد${NC}"
# در محیط مجازی همیشه python در دسترس است
PY=python

# ------------------------------------------------------------
# مرحله ۳: نصب وابستگی‌ها
# ------------------------------------------------------------
echo -e "\n${YELLOW}▶ مرحله ۳: نصب وابستگی‌ها...${NC}"
$PY -m pip install --upgrade pip --quiet
$PY -m pip install -r requirements.txt --quiet
echo -e "${GREEN}✓ وابستگی‌ها نصب شدند${NC}"

# ------------------------------------------------------------
# مرحله ۴: تولید داده مصنوعی (اگر نباشد)
# ------------------------------------------------------------
echo -e "\n${YELLOW}▶ مرحله ۴: داده مصنوعی...${NC}"
if [ ! -f "data/synthetic/alarms.csv" ]; then
    echo -e "${YELLOW}   تولید داده مصنوعی...${NC}"
    $PY scripts/generate_synthetic_data.py
    echo -e "${GREEN}✓ داده مصنوعی تولید شد${NC}"
else
    echo -e "${GREEN}✓ داده مصنوعی از قبل موجود است${NC}"
fi

# ------------------------------------------------------------
# مرحله ۵: آموزش مدل‌ها (اگر نباشند)
# ------------------------------------------------------------
echo -e "\n${YELLOW}▶ مرحله ۵: مدل‌های آموزش‌دیده...${NC}"
if [ ! -f "models/sequence_predictor.joblib" ] || [ ! -f "models/dynamic_risk.joblib" ]; then
    echo -e "${YELLOW}   آموزش مدل‌ها (این کار چند دقیقه طول می‌کشد)...${NC}"
    $PY scripts/train_and_evaluate_all.py
    echo -e "${GREEN}✓ مدل‌ها آموزش دیدند${NC}"
else
    echo -e "${GREEN}✓ مدل‌ها از قبل موجودند${NC}"
fi

# ------------------------------------------------------------
# مرحله ۶: ساخت گواهینامه SSL خودامضا (برای HTTPS)
# ------------------------------------------------------------
echo -e "\n${YELLOW}▶ مرحله ۶: گواهینامه SSL (برای HTTPS)...${NC}"
mkdir -p certs
if [ ! -f "certs/cert.pem" ] || [ ! -f "certs/key.pem" ]; then
    echo -e "${YELLOW}   ساخت گواهینامه خودامضا...${NC}"
    openssl req -x509 -newkey rsa:2048 -keyout certs/key.pem -out certs/cert.pem \
        -days 365 -nodes \
        -subj "/C=IR/ST=Tehran/L=Tehran/O=BHAM/OU=Dev/CN=localhost" \
        -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>/dev/null
    echo -e "${GREEN}✓ گواهینامه ساخته شد (certs/cert.pem)${NC}"
else
    echo -e "${GREEN}✓ گواهینامه از قبل موجود است${NC}"
fi

# ------------------------------------------------------------
# مرحله ۷: اجرای سرور (بک‌اند + فرانت)
# ------------------------------------------------------------
echo -e "\n${BLUE}============================================================${NC}"
echo -e "${GREEN}  🚀 راه‌اندازی کامل شد!${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""
echo -e "${GREEN}  📊 داشبورد (HTTP):  http://localhost:8000/${NC}"
echo -e "${GREEN}  📊 داشبورد (HTTPS): https://localhost:8443/${NC}"
echo -e "${GREEN}  📚 مستندات API:     http://localhost:8000/docs${NC}"
echo -e "${GREEN}  ❤️  Health check:    http://localhost:8000/api/v1/health${NC}"
echo ""
echo -e "${YELLOW}  ⚠️  اگر مرورگر خطای SSL داد: روی «Advanced» → «Proceed to localhost» کلیک کنید${NC}"
echo -e "${YELLOW}     (گواهینامه خودامضاست، امن اما توسط CA امضا نشده)${NC}"
echo ""
echo -e "${YELLOW}  برای توقف: Ctrl+C${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# اجرای سرور HTTPS در background
$PY -m uvicorn api.server:app --host 0.0.0.0 --port 8443 \
    --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem &
HTTPS_PID=$!
echo -e "${GREEN}✓ سرور HTTPS روی پورت 8443 اجرا شد (PID: $HTTPS_PID)${NC}"

# اجرای سرور HTTP در foreground (با reload برای توسعه)
echo -e "${GREEN}✓ سرور HTTP روی پورت 8000 اجرا شد${NC}"
echo ""
$PY -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
HTTP_EXIT=$?

# پس از خروج سرور HTTP، سرور HTTPS را هم متوقف کن
kill $HTTPS_PID 2>/dev/null
exit $HTTP_EXIT
