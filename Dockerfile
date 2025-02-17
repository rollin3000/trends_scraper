# 1. 使用 Python 3.10 slim 作為基底 (針對 Debian)
FROM python:3.10-slim

# 2. 設定非交互模式，避免 apt-get 卡住
ENV DEBIAN_FRONTEND=noninteractive

# 3. 安裝 Playwright 所需的系統套件
RUN apt-get update && apt-get install -y \
    libnss3 \
    libxss1 \
    libglib2.0-0 \
    libatk1.0-0 \
    libexpat1 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libdrm2 \
    libxkbcommon0 \
    libasound2 \
    fonts-liberation \
    wget \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 4. 安裝 Python Playwright
RUN pip install --no-cache-dir playwright

# 5. 確保 Playwright 下載完整的 Chromium
ENV PLAYWRIGHT_BROWSERS_PATH=0
RUN playwright install --with-deps chromium

# 6. **[修正] 確保 Playwright 目錄存在後再修改權限**
RUN mkdir -p /root/.cache/ms-playwright && chmod -R 777 /root/.cache/ms-playwright

# 7. 設定工作目錄，確保 COPY 之前設置
WORKDIR /app

# 8. 複製專案檔案
COPY . /app

# 9. 安裝其他 Python 依賴 (如果有 requirements.txt)
RUN pip install --no-cache-dir -r requirements.txt

# 10. 預設執行命令
CMD ["python", "google_trends_scraper.py"]