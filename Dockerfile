# 1. 使用 Python 3.10 slim 作為基底
FROM python:3.10-slim

# 2. 設定環境變數，避免 `apt-get` 交互式卡住
ENV DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

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

# 4. 安裝 Playwright 並下載 Chromium
RUN pip install --no-cache-dir playwright
RUN playwright install --with-deps chromium

# 5. 確保 Playwright 有權限訪問安裝的瀏覽器
RUN mkdir -p /root/.cache/ms-playwright && chmod -R 777 /root/.cache/ms-playwright

# 6. 設定工作目錄
WORKDIR /app

# 7. 複製專案檔案
COPY . /app

# 8. 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 9. 預設執行命令
CMD ["python", "google_trends_scraper.py"]