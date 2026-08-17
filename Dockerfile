FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py weather.py cities.py storage.py .

# Токен передаётся через переменную окружения TELEGRAM_BOT_TOKEN
# (см. docker-compose.yml или docker run -e TELEGRAM_BOT_TOKEN=...)
CMD ["python", "bot.py"]
