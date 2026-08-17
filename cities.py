"""
Фиксированный список городов для кнопок выбора при подписке на рассылку.
Координаты и IANA-таймзона нужны, чтобы:
  - запрашивать погоду у Open-Meteo (широта/долгота);
  - планировать ежедневную рассылку по МЕСТНОМУ времени города,
    а не по времени сервера (таймзона).
"""

CITIES = [
    {"name": "Москва", "latitude": 55.7558, "longitude": 37.6173, "timezone": "Europe/Moscow"},
    {"name": "Санкт-Петербург", "latitude": 59.9343, "longitude": 30.3351, "timezone": "Europe/Moscow"},
    {"name": "Новосибирск", "latitude": 55.0084, "longitude": 82.9357, "timezone": "Asia/Novosibirsk"},
    {"name": "Екатеринбург", "latitude": 56.8389, "longitude": 60.6057, "timezone": "Asia/Yekaterinburg"},
    {"name": "Казань", "latitude": 55.8304, "longitude": 49.0661, "timezone": "Europe/Moscow"},
    {"name": "Нижний Новгород", "latitude": 56.2965, "longitude": 43.9361, "timezone": "Europe/Moscow"},
    {"name": "Челябинск", "latitude": 55.1644, "longitude": 61.4368, "timezone": "Asia/Yekaterinburg"},
    {"name": "Самара", "latitude": 53.2001, "longitude": 50.1500, "timezone": "Europe/Samara"},
    {"name": "Омск", "latitude": 54.9885, "longitude": 73.3242, "timezone": "Asia/Omsk"},
    {"name": "Ростов-на-Дону", "latitude": 47.2357, "longitude": 39.7015, "timezone": "Europe/Moscow"},
]

CITIES_BY_NAME = {city["name"]: city for city in CITIES}

# Готовые варианты времени для кнопок (местное время выбранного города)
TIME_SLOTS = ["07:00", "08:00", "09:00", "12:00", "18:00", "21:00"]
