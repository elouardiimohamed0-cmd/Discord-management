FROM python:3.11-slim

WORKDIR /app

# Install system fonts (required for PIL image generation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    libfreetype6-dev \
    libjpeg-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project
COPY . .

# Run the bot
CMD ["python", "bot.py"]
