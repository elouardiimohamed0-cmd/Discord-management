FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .
RUN mkdir -p assets/players assets/backgrounds assets/fonts

EXPOSE 8000

CMD ["python", "bot.py"]
