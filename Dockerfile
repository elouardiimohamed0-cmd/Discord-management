FROM mcr.microsoft.com/playwright/python:v1.41.2-jammy

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ensure browser version matches the Python package (safety net)
RUN playwright install chromium

# Copy app
COPY . .
RUN mkdir -p assets/players assets/backgrounds assets/fonts

EXPOSE 8000

CMD ["python", "bot.py"]
