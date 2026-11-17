# Dockerfile برای سامانه BHAM
FROM python:3.12-slim

WORKDIR /app

# نصب وابستگی‌های سیستم
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# کپی پروژه
COPY . /app/

# نصب پکیج
RUN pip install --no-cache-dir -e ".[dev]"

# پورت API
EXPOSE 8000

# اجرای اولیه: تولید داده، دانلود TEP، آموزش مدل‌ها، سپس سرو API
# برای استقرار ساده‌تر، مدل‌ها از قبل آموزش دیده شوند و در image کپی شوند.
RUN python scripts/generate_synthetic_data.py || true
RUN python scripts/download_tep.py || true
RUN python scripts/preprocess_tep.py || true
RUN python scripts/train_all.py || true

CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
