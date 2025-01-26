# 使用 Python Slim 作為基礎映像
FROM python:3.10-slim

# 安裝必要的系統依賴和 Playwright 所需的依賴
RUN apt-get update && apt-get install -y \
    wget \
    curl \
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
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 添加 Playwright 官方的依賴安裝腳本（解決兼容性問題）
RUN wget -qO- https://github.com/microsoft/playwright/raw/main/utils/docker/Dockerfile.bionic | bash

# 安裝 Playwright
RUN pip install --no-cache-dir playwright

# 安裝 Chromium 瀏覽器（Playwright 自帶的）
RUN playwright install chromium

# 設置工作目錄
WORKDIR /app

# 創建輸出目錄並設置權限
RUN mkdir -p /app/output && chmod -R 777 /app/output

# 複製專案文件到容器
COPY . .

# 安裝 Python 依賴（如果有）
RUN pip install --no-cache-dir -r requirements.txt

# 預設執行命令
CMD ["python", "google_trends_scraper.py"]