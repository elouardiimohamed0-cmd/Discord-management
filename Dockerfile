FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libgconf-2-4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libgbm-dev \
    libnss3-dev \
    libxss1 \
    libasound2 \
    fonts-noto-color-emoji \
    fonts-noto \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers to persistent path
ENV PLAYWRIGHT_BROWSERS_PATH=/app/ms-playwright
RUN mkdir -p /app/ms-playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy app
COPY . .

# Create directories
RUN mkdir -p assets/players assets/backgrounds assets/fonts

# Expose health check port
EXPOSE 8080

# Run
CMD ["python", "bot.py"]
