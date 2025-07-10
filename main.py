import asyncio
import os
import logging
import uvicorn
from telegram import Update
from telegram.ext import Application, MessageHandler, filters
from fastapi import FastAPI, Request, Response

# --- Настройка логирования ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Инициализация FastAPI ---
app = FastAPI()
application = None

# --- НОВАЯ функция для обработки пересланных постов в дискуссионной группе ---
async def handle_forwarded_post_in_discussion(update: Update, context):
    logger.info(f"Received an update in discussion group: {update.update_id}")

    message = update.message
    if not message:
        logger.info("Update is not a message in discussion group. Skipping.")
        return

    # Проверяем, что сообщение пришло из ожидаемой дискуссионной группы
    current_chat_id = str(message.chat.id)
    discussion_group_id = os.getenv("DISCUSSION_GROUP_ID")

    if not discussion_group_id or current_chat_id != discussion_group_id:
        logger.info(f"Ignored message from chat_id {current_chat_id}, not the expected discussion group {discussion_group_id}")
        return

    # Проверяем, что это пересланное сообщение и переслано из канала
    if message.forward_from_chat and message.forward_from_chat.type == "channel":
        forwarded_from_channel_id = str(message.forward_from_chat.id)
        expected_channel_id = os.getenv("CHANNEL_ID")

        logger.info(f"Detected forwarded message from channel {forwarded_from_channel_id} in discussion group. Expected channel: {expected_channel_id}")

        # Проверяем, что оно переслано именно из нашего целевого канала
        if expected_channel_id and forwarded_from_channel_id == expected_channel_id:
            message_to_reply_id = message.message_id # Это ID пересланного сообщения в дискуссионной группе!

            try:
                # Отправляем комментарий в дискуссионную группу, отвечая на пересланный пост
                await context.bot.send_message(
                    chat_id=discussion_group_id,
                    text="Ждем Edem PW! 🚀",
                    reply_to_message_id=message_to_reply_id
                )
                logger.info(f"Successfully commented on forwarded post {message_to_reply_id} in discussion group {discussion_group_id} from channel {forwarded_from_channel_id}")
            except Exception as e:
                logger.error(f"Failed to send message to discussion group {discussion_group_id}: {e}")
        else:
            logger.info(f"Ignored forwarded message from channel {forwarded_from_channel_id}, not the expected source channel.")
    else:
        logger.info("Message in discussion group is not a forwarded message from a channel. Skipping.")

# --- Эндпоинт для вебхука (без изменений) ---
@app.post("/{token_suffix}")
async def webhook(token_suffix: str, request: Request):
    expected_token_suffix = os.getenv("BOT_TOKEN", "").split(":")[-1]
    if not expected_token_suffix:
        logger.error("BOT_TOKEN environment variable is not set correctly. Cannot validate webhook.")
        return Response(status_code=500)

    if token_suffix != expected_token_suffix:
        logger.warning(f"Unauthorized webhook attempt with token suffix: {token_suffix}. Expected: {expected_token_suffix}")
        return Response(status_code=403)
    
    json_data = await request.json()
    logger.info(f"Received webhook payload: {json_data.get('update_id', 'N/A')}")

    try:
        update = Update.de_json(json_data, application.bot)
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON into Update object: {e}")
        return Response(status_code=400)

    await application.process_update(update)
    logger.info("Webhook processed successfully.")
    return Response(status_code=200)

# --- Основная асинхронная функция для запуска бота ---
async def main():
    global application
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.critical("BOT_TOKEN environment variable is not set. Bot cannot start.")
        raise ValueError("BOT_TOKEN environment variable is not set")
    
    application = Application.builder().token(token).build()
    await application.initialize()
    
    # --- ИЗМЕНЕНИЕ ЗДЕСЬ: УДАЛЯЕМ старый обработчик CHANNEL_POST ---
    # application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, handle_post))

    # --- ДОБАВЛЯЕМ НОВЫЙ обработчик для СООБЩЕНИЙ (включая пересланные) в группе ---
    # filters.ALL будет ловить все сообщения. Затем внутри handle_forwarded_post_in_discussion
    # мы будем фильтровать их по chat_id и наличию forward_from_chat.
    application.add_handler(MessageHandler(filters.ALL, handle_forwarded_post_in_discussion))
    
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting Uvicorn server on host 0.0.0.0 and port {port}")
    config = uvicorn.Config(app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())

