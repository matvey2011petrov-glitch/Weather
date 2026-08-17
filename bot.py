"""
Telegram-бот "Погода".

Возможности:
  1. Подписка на ежедневную рассылку погоды: /start -> кнопка "Начать" ->
     выбор города кнопками -> выбор времени кнопками -> готово.
     Погода приходит каждый день в выбранное МЕСТНОЕ время города.
  2. Разовая проверка погоды: /weather <город> или просто написать
     название города текстом.
  3. /status — посмотреть текущую подписку.
  4. /stop — отписаться от рассылки.

Источник данных о погоде: Open-Meteo (без API-ключа).
Хранилище подписок: JSON-файл (storage.py).

Запуск:
    export TELEGRAM_BOT_TOKEN="ваш_токен_от_BotFather"
    python bot.py
"""

import logging
import os
from datetime import time as dt_time
from zoneinfo import ZoneInfo

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import storage
from cities import CITIES, CITIES_BY_NAME, TIME_SLOTS
from weather import find_city, get_current_weather, format_weather_message, location_from_geocoding

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Клавиатуры
# ---------------------------------------------------------------------------

def build_city_keyboard() -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(city["name"], callback_data=f"city:{city['name']}") for city in CITIES]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


def build_time_keyboard() -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(t, callback_data=f"time:{t}") for t in TIME_SLOTS]
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(rows)


def build_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("▶️ Начать", callback_data="start_onboarding")]])


# ---------------------------------------------------------------------------
# Планирование ежедневной рассылки
# ---------------------------------------------------------------------------

def job_name_for(user_id: int) -> str:
    return f"weather_{user_id}"


def schedule_daily_job(job_queue, user_id: int, chat_id: int, city_name: str, time_str: str) -> bool:
    """Ставит (или переставляет) ежедневную задачу рассылки погоды."""
    city = CITIES_BY_NAME.get(city_name)
    if city is None:
        logger.warning("Неизвестный город при планировании задачи: %s", city_name)
        return False

    hour, minute = (int(part) for part in time_str.split(":"))
    tz = ZoneInfo(city["timezone"])

    name = job_name_for(user_id)
    for job in job_queue.get_jobs_by_name(name):
        job.schedule_removal()

    job_queue.run_daily(
        send_scheduled_weather,
        time=dt_time(hour=hour, minute=minute, tzinfo=tz),
        name=name,
        chat_id=chat_id,
        data={"city": city_name, "latitude": city["latitude"], "longitude": city["longitude"]},
    )
    return True


async def send_scheduled_weather(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    data = job.data
    try:
        current = get_current_weather(data["latitude"], data["longitude"])
        message = format_weather_message(data["city"], current)
        await context.bot.send_message(chat_id=job.chat_id, text=message)
    except requests.RequestException:
        logger.exception("Не удалось получить погоду для рассылки (chat_id=%s)", job.chat_id)
    except Exception:
        logger.exception("Неожиданная ошибка в задаче рассылки (chat_id=%s)", job.chat_id)


# ---------------------------------------------------------------------------
# Онбординг: /start -> город -> время
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    existing = await storage.get_subscription(user_id)

    if existing:
        text = (
            f"Ты уже подписан на рассылку погоды 🙂\n"
            f"Город: {existing['city']}\n"
            f"Время: {existing['time']} (по местному времени города)\n\n"
            f"Хочешь изменить город или время — жми «Начать» ниже.\n"
            f"Отписаться можно командой /stop."
        )
    else:
        text = (
            "Привет! Я присылаю погоду в выбранном городе каждый день "
            "в удобное тебе время.\n\n"
            "Нажми «Начать», чтобы выбрать город и время рассылки."
        )

    await update.message.reply_text(text, reply_markup=build_start_keyboard())


async def on_start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("pending_city", None)
    await query.edit_message_text(
        "Выбери город, для которого присылать погоду:",
        reply_markup=build_city_keyboard(),
    )


async def on_city_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    city_name = query.data.split(":", 1)[1]
    if city_name not in CITIES_BY_NAME:
        await query.edit_message_text("Такого города нет в списке, попробуй ещё раз: /start")
        return

    context.user_data["pending_city"] = city_name
    await query.edit_message_text(
        f"Город: {city_name}\n\nТеперь выбери время ежедневной рассылки (по местному времени города):",
        reply_markup=build_time_keyboard(),
    )


async def on_time_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    time_str = query.data.split(":", 1)[1]
    city_name = context.user_data.get("pending_city")

    if not city_name:
        await query.edit_message_text(
            "Сначала нужно выбрать город — начни заново: /start"
        )
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    await storage.save_subscription(user_id, chat_id, city_name, time_str)
    ok = schedule_daily_job(context.application.job_queue, user_id, chat_id, city_name, time_str)
    context.user_data.pop("pending_city", None)

    if not ok:
        await query.edit_message_text("Не получилось поставить рассылку, попробуй /start ещё раз.")
        return

    await query.edit_message_text(
        f"Готово! ✅\n\n"
        f"Буду присылать погоду в городе {city_name} каждый день в {time_str} "
        f"(по местному времени города).\n\n"
        f"Посмотреть настройки — /status\n"
        f"Отписаться — /stop"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    existing = await storage.get_subscription(user_id)
    if not existing:
        await update.message.reply_text("Ты пока не подписан на рассылку. Используй /start, чтобы подписаться.")
        return
    await update.message.reply_text(
        f"Текущая подписка:\nГород: {existing['city']}\nВремя: {existing['time']}\n\n"
        f"Изменить — /start\nОтписаться — /stop"
    )


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    existing = await storage.get_subscription(user_id)

    if not existing:
        await update.message.reply_text("У тебя и так нет активной подписки.")
        return

    for job in context.application.job_queue.get_jobs_by_name(job_name_for(user_id)):
        job.schedule_removal()
    await storage.delete_subscription(user_id)

    await update.message.reply_text(
        "Подписка отменена, рассылка погоды больше не будет приходить. "
        "Подписаться заново можно через /start."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Команды:\n"
        "/start — подписаться на ежедневную рассылку погоды (город + время выбираются кнопками)\n"
        "/status — посмотреть текущую подписку\n"
        "/stop — отписаться от рассылки\n"
        "/weather <город> — узнать погоду прямо сейчас, разово\n\n"
        "Также можно просто написать название города текстом — пришлю погоду сейчас."
    )


# ---------------------------------------------------------------------------
# Разовая проверка погоды (/weather <город> или просто текст)
# ---------------------------------------------------------------------------

async def weather_for_city(update: Update, city_name: str) -> None:
    if not city_name or not city_name.strip():
        await update.message.reply_text("Укажи название города, например: /weather Москва")
        return

    try:
        city_info = find_city(city_name.strip())
        if city_info is None:
            await update.message.reply_text(
                f"Не нашёл город «{city_name}». Проверь написание и попробуй ещё раз."
            )
            return

        current = get_current_weather(city_info["latitude"], city_info["longitude"])
        message = format_weather_message(location_from_geocoding(city_info), current)
        await update.message.reply_text(message)

    except requests.RequestException:
        logger.exception("Ошибка запроса к Open-Meteo")
        await update.message.reply_text("Не удалось получить данные о погоде. Попробуй ещё раз чуть позже.")
    except Exception:
        logger.exception("Неожиданная ошибка")
        await update.message.reply_text("Что-то пошло не так. Попробуй ещё раз.")


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    city_name = " ".join(context.args) if context.args else ""
    await weather_for_city(update, city_name)


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Любое обычное текстовое сообщение вне сценария подписки трактуем как название города
    await weather_for_city(update, update.message.text)


# ---------------------------------------------------------------------------
# Восстановление подписок при запуске
# ---------------------------------------------------------------------------

async def restore_subscriptions(application: Application) -> None:
    subscriptions = storage.load_all()
    restored = 0
    for user_id_str, sub in subscriptions.items():
        try:
            user_id = int(user_id_str)
        except ValueError:
            continue
        ok = schedule_daily_job(
            application.job_queue, user_id, sub["chat_id"], sub["city"], sub["time"]
        )
        if ok:
            restored += 1
    logger.info("Восстановлено подписок при старте: %d из %d", restored, len(subscriptions))


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "Не задан TELEGRAM_BOT_TOKEN. "
            "Установи переменную окружения с токеном от @BotFather."
        )

    application = Application.builder().token(token).post_init(restore_subscriptions).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("weather", weather_command))

    application.add_handler(CallbackQueryHandler(on_start_onboarding, pattern=r"^start_onboarding$"))
    application.add_handler(CallbackQueryHandler(on_city_chosen, pattern=r"^city:"))
    application.add_handler(CallbackQueryHandler(on_time_chosen, pattern=r"^time:"))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    logger.info("Бот запущен, ожидаю сообщения...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
