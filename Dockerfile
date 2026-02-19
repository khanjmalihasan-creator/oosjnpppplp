# استفاده از پایتون رسمی
FROM python:3.11-slim

# نصب کتابخانه‌های سیستمی مورد نیاز
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# ایجاد پوشه کار
WORKDIR /app

# کپی فایل‌های مورد نیاز
COPY requirements.txt .
COPY bot.py .
COPY vpn_panel.py .

# نصب کتابخانه‌های پایتون
RUN pip install --no-cache-dir -r requirements.txt

# ایجاد پوشه برای دیتابیس
RUN mkdir -p /data

# اجرای ربات
CMD ["python", "bot.py"]
