import asyncio
from telegram.ext import Application, MessageHandler, filters
from telegram import Update
import os
import logging
import uvicorn
from fastapi import FastAPI, Request, Response

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация FastAPI
app = FastAPI()

# Глобальная переменная для хранения Application
application = None

# Функция для обработки новых постов в канале
async def handle_post(update: Update, context):
    # Проверяем, что сообщение из канала и не является ответом
    if update.channel_post and not update.channel_post.reply_to_message:
        channel_id = update.channel_post.chat.id
        message_id = update.channel_post.message_id
        # Проверяем, есть ли связанная дискуссионная группа
        discussion_group_id = update.channel_post.linked_chat_id
        if discussion_group_id:
            # Отправляем комментарий в дискуссионную группу
            await context.bot.send_message(
                chat_id=discussion_group_id,
                text="Ждем Edem PW! 🚀",
                reply_to_message_id=message_id
            )
            logger.info(f"Commented on post {message_id} in discussion group {discussion_group_id}")
        else:
            logger.warning(f"No linked discussion group found for channel {channel_id}")

# Эндпоинт для вебхука
@app.post("/{token}")
async def webhook(token: str, request: Request):
    # Проверяем, что токен совпадает
    if token != os.getenv("BOT_TOKEN").split(":")[-1]:
        return Response(status_code=403)
    
    # Получаем данные из запроса
    json_data = await request.json()
    update = Update.de_json(json_data, application.bot)
    
    # Обрабатываем обновление
    await application.process_update(update)
    return Response(status_code=200)

# Основная асинхронная функция для запуска бота
async def main():
    global application
    # Получаем токен из переменной окружения
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN environment variable is not set")
    
    # Инициализируем приложение
    application = Application.builder().token(token).build()
    
    # Инициализируем Application
    await application.initialize()
    
    # Добавляем обработчик для сообщений в канале
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, handle_post))
    
    # Запускаем FastAPI сервер
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
