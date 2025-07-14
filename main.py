import asyncio
import os
import logging
import sqlite3
import random
import uvicorn
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, CommandHandler, ContextTypes
from telegram.error import TelegramError # Добавлено для обработки ошибок вебхука
from fastapi import FastAPI, Request, Response

# --- Настройка логирования ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Инициализация FastAPI ---
app = FastAPI()
application = None # Инициализируем как None, будет установлено в main()

# --- Инициализация базы данных SQLite ---
def init_db():
    try:
        # Убедитесь, что путь '/app/bot.db' доступен для записи в контейнере Render
        conn = sqlite3.connect('/app/bot.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                message_count INTEGER DEFAULT 0,
                rank TEXT DEFAULT 'Странник Эфира'
            )
        ''')
        conn.commit()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    finally:
        if conn:
            conn.close()

# --- Функция для получения ранга по количеству сообщений ---
def get_rank(message_count):
    if message_count >= 2400:
        return "Бессмертный Пангу"
    elif message_count >= 1200:
        return "Повелитель Стихий"
    elif message_count >= 600:
        return "Архонт Света"
    elif message_count >= 300:
        return "Мастер Дао"
    elif message_count >= 150:
        return "Адепт Небес"
    else:
        return "Странник Эфира"

# --- Функция для обработки пересланных постов в дискуссионной группе ---
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

        # Проверяем, что оно переслано из нашего целевого канала
        if expected_channel_id and forwarded_from_channel_id == expected_channel_id:
            message_to_reply_id = message.message_id

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

# --- Функция для подсчёта сообщений пользователей в группе ---
async def count_messages(update: Update, context):
    message = update.message
    if not message or not message.from_user:
        logger.info("Update is not a message or has no user. Skipping message count.")
        return

    current_chat_id = str(message.chat.id)
    discussion_group_id = os.getenv("DISCUSSION_GROUP_ID")

    if not discussion_group_id or current_chat_id != discussion_group_id:
        logger.info(f"Ignored message for counting from chat_id {current_chat_id}, not the expected discussion group {discussion_group_id}")
        return

    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Определяем тип сообщения для логов (улучшено)
    message_type = "unknown"
    if message.text:
        message_type = "text"
    elif message.photo:
        message_type = "photo"
    elif message.sticker:
        message_type = "sticker"
    elif message.video:
        message_type = "video"
    elif message.document:
        message_type = "document"
    elif message.audio:
        message_type = "audio"
    elif message.voice:
        message_type = "voice"
    elif message.video_note:
        message_type = "video_note"
    elif message.new_chat_members: # Добавлено для
