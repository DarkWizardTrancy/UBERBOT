import asyncio
import os
import logging
import uvicorn
from telegram import Update
from telegram.ext import Application, MessageHandler, filters
from fastapi import FastAPI, Request, Response

# --- Настройка логирования ---
# Устанавливаем базовую конфигурацию логирования.
# Сообщения будут выводиться с указанием времени, имени логгера, уровня и самого сообщения.
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__) # Используем __name__ для логгера, это хорошая практика

# --- Инициализация FastAPI ---
app = FastAPI()

# Глобальная переменная для хранения Application (инстанс бота).
# Это нужно, потому что FastAPI и bot-library работают немного по-разному и Application создается в main().
application = None

# --- Функция для обработки новых постов в канале ---
async def handle_post(update: Update, context):
    logger.info(f"Received an update with ID: {update.update_id}") # Лог: Получено обновление

    # Проверяем, что обновление является новым постом в канале и не является ответом на другое сообщение.
    # Если это просто сообщение в группе или ответ, мы его игнорируем.
    if update.channel_post and not update.channel_post.reply_to_message:
        channel_id = str(update.channel_post.chat.id)
        # Получаем ожидаемый ID канала из переменных окружения.
        expected_channel_id = os.getenv("CHANNEL_ID")

        logger.info(f"Detected channel post from chat ID: {channel_id}. Expected channel ID: {expected_channel_id}") # Лог: Обнаружен пост из канала

        # Проверяем, что сообщение пришло именно из того канала, который мы мониторим.
        if expected_channel_id and channel_id == expected_channel_id:
            message_id = update.channel_post.message_id
            # Получаем ID дискуссионной группы из переменных окружения.
            discussion_group_id = os.getenv("DISCUSSION_GROUP_ID")

            logger.info(f"Post is from the expected channel ({channel_id}). Message ID: {message_id}. Discussion Group ID: {discussion_group_id}") # Лог: Пост из нужного канала

            if discussion_group_id:
                try:
                    # Отправляем комментарий в дискуссионную группу, отвечая на оригинальный пост.
                    await context.bot.send_message(
                        chat_id=discussion_group_id,
                        text="Ждем Edem PW! 🚀",
                        reply_to_message_id=message_id
                    )
                    logger.info(f"Successfully commented on post {message_id} in discussion group {discussion_group_id} from channel {channel_id}") # Лог: Комментарий успешно отправлен
                except Exception as e:
                    # Логируем любую ошибку, которая произошла при попытке отправить сообщение.
                    logger.error(f"Failed to send message to discussion group {discussion_group_id}: {e}")
            else:
                logger.warning("No DISCUSSION_GROUP_ID environment variable set. Cannot send comment.") # Лог: Переменная для группы не установлена
        else:
            logger.info(f"Ignored message from chat_id {channel_id} because it's not the expected channel.") # Лог: Игнорируется пост из другого канала
    else:
        logger.info("Update is not a new channel post (either not a channel post or is a reply). Skipping.") # Лог: Обновление не является новым постом в канале

# --- Эндпоинт для вебхука ---
@app.post("/{token_suffix}")
async def webhook(token_suffix: str, request: Request):
    # Проверяем, что токен в URL совпадает с частью токена нашего бота.
    # Это базовая мера безопасности, чтобы только Telegram мог отправлять запросы.
    # split(":")[-1] берет часть токена после двоеточия.
    expected_token_suffix = os.getenv("BOT_TOKEN", "").split(":")[-1]
    if not expected_token_suffix:
        logger.error("BOT_TOKEN environment variable is not set correctly. Cannot validate webhook.")
        return Response(status_code=500) # В случае ошибки конфига возвращаем 500

    if token_suffix != expected_token_suffix:
        logger.warning(f"Unauthorized webhook attempt with token suffix: {token_suffix}. Expected: {expected_token_suffix}")
        return Response(status_code=403) # 403 Forbidden, если токен не совпадает
    
    # Получаем JSON данные из тела HTTP-запроса.
    json_data = await request.json()
    logger.info(f"Received webhook payload: {json_data.get('update_id', 'N/A')}") # Лог: Получен payload вебхука

    # Преобразуем JSON данные в объект Update, понятный python-telegram-bot.
    # application.bot должен быть инициализирован к этому моменту.
    try:
        update = Update.de_json(json_data, application.bot)
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON into Update object: {e}")
        return Response(status_code=400) # 400 Bad Request, если JSON невалидный для Update

    # Передаем обновление в Application для обработки зарегистрированными обработчиками.
    await application.process_update(update)
    logger.info("Webhook processed successfully.") # Лог: Вебхук успешно обработан
    return Response(status_code=200) # 200 OK, чтобы Telegram знал, что мы получили обновление

# --- Основная асинхронная функция для запуска бота ---
async def main():
    global application # Объявляем, что будем использовать глобальную переменную application

    # Получаем токен бота из переменных окружения.
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.critical("BOT_TOKEN environment variable is not set. Bot cannot start.")
        raise ValueError("BOT_TOKEN environment variable is not set")
    
    # Инициализируем Application (основной объект бота).
    application = Application.builder().token(token).build()
    
    # Инициализируем внутренние компоненты Application.
    await application.initialize()
    
    # Добавляем обработчик для сообщений, которые являются постами в канале.
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, handle_post))
    
    # Запускаем FastAPI сервер с Uvicorn.
    # "0.0.0.0" позволяет серверу слушать все доступные сетевые интерфейсы.
    # Порт берется из переменной окружения PORT, по умолчанию 8000.
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting Uvicorn server on host 0.0.0.0 and port {port}")
    config = uvicorn.Config(app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    await server.serve()

# --- Точка входа в программу ---
if __name__ == "__main__":
    # Запускаем основную асинхронную функцию.
    asyncio.run(main())

