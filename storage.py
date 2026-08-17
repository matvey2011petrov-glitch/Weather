"""
Простое JSON-хранилище подписок пользователей.

Формат subscriptions.json:
{
  "<user_id>": {
    "chat_id": 123456789,
    "city": "Москва",
    "time": "08:00"
  },
  ...
}

Подходит для небольшого числа пользователей. Если бот вырастет и записи
станут частыми и параллельными — стоит перейти на SQLite.
"""

import asyncio
import json
import os

STORAGE_PATH = os.environ.get("SUBSCRIPTIONS_FILE", "subscriptions.json")

_lock = asyncio.Lock()


def _read_raw() -> dict:
    if not os.path.exists(STORAGE_PATH):
        return {}
    with open(STORAGE_PATH, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return {}
        return json.loads(content)


def _write_raw(data: dict) -> None:
    tmp_path = STORAGE_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, STORAGE_PATH)  # атомарная замена файла


def load_all() -> dict:
    """Синхронное чтение всех подписок (используется при старте бота)."""
    return _read_raw()


async def save_subscription(user_id: int, chat_id: int, city: str, time_str: str) -> None:
    async with _lock:
        data = _read_raw()
        data[str(user_id)] = {"chat_id": chat_id, "city": city, "time": time_str}
        _write_raw(data)


async def delete_subscription(user_id: int) -> None:
    async with _lock:
        data = _read_raw()
        data.pop(str(user_id), None)
        _write_raw(data)


async def get_subscription(user_id: int) -> dict | None:
    async with _lock:
        data = _read_raw()
        return data.get(str(user_id))
