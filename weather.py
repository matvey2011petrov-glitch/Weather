"""
Общая логика получения погоды через Open-Meteo (без API-ключа).
Используется и для разовой проверки погоды, и для ежедневной рассылки.
"""

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Коды погоды WMO -> (текст, emoji)
# https://open-meteo.com/en/docs (см. описание поля weather_code)
WEATHER_CODES = {
    0: ("ясно", "☀️"),
    1: ("преимущественно ясно", "🌤"),
    2: ("переменная облачность", "⛅"),
    3: ("пасмурно", "☁️"),
    45: ("туман", "🌫"),
    48: ("изморозь", "🌫"),
    51: ("морось слабая", "🌦"),
    53: ("морось умеренная", "🌦"),
    55: ("морось сильная", "🌧"),
    56: ("ледяная морось слабая", "🌧"),
    57: ("ледяная морось сильная", "🌧"),
    61: ("дождь слабый", "🌦"),
    63: ("дождь умеренный", "🌧"),
    65: ("дождь сильный", "🌧"),
    66: ("ледяной дождь слабый", "🌧"),
    67: ("ледяной дождь сильный", "🌧"),
    71: ("снег слабый", "🌨"),
    73: ("снег умеренный", "🌨"),
    75: ("снег сильный", "❄️"),
    77: ("снежная крупа", "❄️"),
    80: ("ливень слабый", "🌦"),
    81: ("ливень умеренный", "🌧"),
    82: ("ливень сильный", "⛈"),
    85: ("снегопад слабый", "🌨"),
    86: ("снегопад сильный", "❄️"),
    95: ("гроза", "⛈"),
    96: ("гроза с градом (слабая)", "⛈"),
    99: ("гроза с градом (сильная)", "⛈"),
}


def get_weather_description(code: int) -> tuple[str, str]:
    return WEATHER_CODES.get(int(code), ("неизвестно", "❓"))


def find_city(city_name: str) -> dict | None:
    """Ищет город через геокодинг Open-Meteo. Возвращает первую находку или None.

    Используется для команды /weather с произвольным названием города.
    """
    params = {
        "name": city_name,
        "count": 1,
        "language": "ru",
        "format": "json",
    }
    resp = requests.get(GEOCODING_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results")
    if not results:
        return None
    return results[0]


def get_current_weather(latitude: float, longitude: float) -> dict:
    """Запрашивает текущую погоду для координат."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": (
            "temperature_2m,relative_humidity_2m,apparent_temperature,"
            "precipitation,weather_code,wind_speed_10m"
        ),
        "timezone": "auto",
    }
    resp = requests.get(FORECAST_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()["current"]


def format_weather_message(location: str, current: dict) -> str:
    """Форматирует текст сообщения с погодой для указанной локации."""
    desc, emoji = get_weather_description(current["weather_code"])

    return (
        f"{emoji} Погода в городе {location}\n\n"
        f"Температура: {current['temperature_2m']:.0f}°C "
        f"(ощущается как {current['apparent_temperature']:.0f}°C)\n"
        f"Состояние: {desc}\n"
        f"Влажность: {current['relative_humidity_2m']:.0f}%\n"
        f"Ветер: {current['wind_speed_10m']:.0f} км/ч\n"
        f"Осадки: {current['precipitation']:.1f} мм"
    )


def location_from_geocoding(city_info: dict) -> str:
    """Собирает читаемое название локации из ответа геокодинга Open-Meteo."""
    city_name = city_info.get("name", "")
    country = city_info.get("country", "")
    admin1 = city_info.get("admin1")

    parts = [city_name]
    if admin1 and admin1 != city_name:
        parts.append(admin1)
    if country:
        parts.append(country)
    return ", ".join(parts)
