import os
import asyncio
import logging
from typing import Optional

from fastapi import FastAPI, Request, Response
import uvicorn
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters

# --- Настройка логирования ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Инициализация FastAPI приложения ---
app = FastAPI()

# Глобальная переменная для экземпляра Telegram Application
application: Optional[Application] = None

# --- ВАШИ ФУНКЦИИ ОБРАБОТЧИКОВ (ПРИМЕРЫ) ---
# Предполагается, что эти функции определены где-то выше в вашем коде
# Если их нет, вам нужно будет их добавить или удалить вызовы в main().
# Для примера я добавил заглушки.

async def handle_forwarded_post_in_discussion(update: Update, context):
    """Обработчик для пересланных постов из канала."""
    if update.message and update.message.forward_from_chat:
        logger.info(f"Получен пересланный пост из чата: {update.message.forward_from_chat.title}")
    # Ваша логика обработки пересланного поста
    await update.message.reply_text("Спасибо за пересланный пост!")

async def count_messages(update: Update, context):
    """Обработчик для подсчёта сообщений в группе."""
    if update.message:
        logger.info(f"Получено сообщение в группе от {update.message.from_user.id}")
    # Ваша логика подсчета сообщений
    # Например, инкремент счетчика в БД для пользователя

async def handle_random_range(update: Update, context):
    """Обработчик для диапазона рандомайзера в ЛС."""
    if update.message:
        logger.info(f"Получен запрос на диапазон рандома в ЛС от {update.message.from_user.id}")
    # Ваша логика для рандомайзера
    await update.message.reply_text("Пожалуйста, введите диапазон для рандома (например, 1-100).")

async def handle_private_message(update: Update, context):
    """Обработчик для сообщений в личных чатах (общая)."""
    if update.message:
        logger.info(f"Получено приватное сообщение от {update.message.from_user.id}: {update.message.text}")
    # Ваша общая логика для приватных сообщений
    await update.message.reply_text("Привет! Чем могу помочь?")

# Команды
async def site(update: Update, context):
    await update.message.reply_text("Наш сайт: [ссылка на сайт]")

async def servers(update: Update, context):
    await update.message.reply_text("Наши сервера: [информация о серверах]")

async def partners(update: Update, context):
    await update.message.reply_text("Наши партнеры: [список партнеров]")

async def help_command(update: Update, context):
    await update.message.reply_text("Список команд: /site, /servers, /partners, /help, /ping, /rank, /random")

async def ping(update: Update, context):
    await update.message.reply_text("Pong!")

async def rank(update: Update, context):
    user_id = update.message.from_user.id
    discussion_group_id = update.message.chat_id
    try:
        # Здесь должна быть ваша логика получения ранга, например:
        # response = await get_user_rank(user_id, discussion_group_id)
        response = f"Твой ранг в этой группе: Отличный! (ID: {user_id})" # Заглушка
        await update.message.reply_text(response)
        logger.info(f"Sent /rank response for user {user_id} in discussion group {discussion_group_id}")
    except Exception as e:
        logger.error(f"Failed to send /rank response in discussion group {discussion_group_id}: {e}")
        await update.message.reply_text("❌ Ошибка при получении ранга. Попробуй позже.")

async def random_command(update: Update, context):
    await update.message.reply_text("Для случайного числа введите /random <число1>-<число2> (например, /random 1-100) в ЛС.")


# --- Инициализация базы данных (пример заглушки) ---
def init_db():
    logger.info("Database initialized successfully.")
    # Здесь могла бы быть ваша логика инициализации базы данных
    # Например, создание таблиц SQLite или подключение к PostgreSQL

# --- Эндпоинт для проверок работоспособности Render (необязательно, но полезно) ---
@app.get("/")
async def health_check():
    return {"status": "ok", "message": "Bot is running"}

# --- Эндпоинт для вебхука Telegram ---
# Обратите внимание: путь теперь фиксирован на "/webhook"
@app.post("/webhook")
async def webhook(request: Request):
    # Убедитесь, что 'application' инициализировано
    if application is None:
        logger.critical("Telegram Application is not initialized. Cannot process webhook.")
        return Response(status_code=500, content="Telegram Application not ready.")

    json_data = await request.json()
    logger.info(f"Received webhook payload: {json_data.get('update_id', 'N/A')}")

    try:
        update = Update.de_json(json_data, application.bot)
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON into Update object: {e}")
        return Response(status_code=400, content=f"Bad Request: {e}")

    try:
        await application.process_update(update)
        logger.info("Webhook processed successfully.")
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)
        return Response(status_code=500, content=f"Internal Server Error: {e}")


# --- Основная асинхронная функция для запуска бота ---
async def main():
    global application # Используем глобальную переменную application
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.critical("BOT_TOKEN environment variable is not set. Bot cannot start.")
        raise ValueError("BOT_TOKEN environment variable is not set")

    # Инициализация базы данных
    init_db()

    application = Application.builder().token(token).build()
    await application.initialize() # Инициализируем приложение перед добавлением обработчиков
    # Note: application.initialize() is crucial for webhook deployments.
    # It fetches bot info and prepares for updates.

    # --- Добавляем обработчики ---
    application.add_handler(MessageHandler(filters.FORWARDED & filters.ChatType.GROUPS, handle_forwarded_post_in_discussion))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & filters.ChatType.GROUPS, count_messages))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_random_range))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_private_message))
    application.add_handler(CommandHandler("site", site))
    application.add_handler(CommandHandler("servers", servers))
    application.add_handler(CommandHandler("partners", partners))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("rank", rank))
    application.add_handler(CommandHandler("random", random_command))

    # Получаем порт из переменной окружения Render, по умолчанию 10000
    port = int(os.getenv("PORT", 10000))
    logger.info(f"Starting Uvicorn server on host 0.0.0.0 and port {port}")

    # Создаем конфиг Uvicorn и запускаем сервер
    config = uvicorn.Config(app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    await server.serve()

# --- Точка входа для запуска асинхронной функции ---
if __name__ == "__main__": # Исправлено: добавлено двойное подчеркивание
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"Bot failed to start: {e}", exc_info=True)

