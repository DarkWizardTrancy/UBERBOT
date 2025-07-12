import asyncio
import os
import logging
import sqlite3
import uvicorn
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, CommandHandler
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

# --- Инициализация базы данных SQLite ---
def init_db():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            message_count INTEGER DEFAULT 0,
            rank TEXT DEFAULT 'Новенький'
        )
    ''')
    conn.commit()
    conn.close()

# --- Функция для получения ранга по количеству сообщений ---
def get_rank(message_count):
    if message_count >= 2400:
        return "Ранг 5"
    elif message_count >= 1200:
        return "Ранг 4"
    elif message_count >= 600:
        return "Ранг 3"
    elif message_count >= 300:
        return "Ранг 2"
    elif message_count >= 150:
        return "Ранг 1"
    else:
        return "Новенький"

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

# --- Функция для подсчёта сообщений пользователей ---
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

    conn = sqlite3.connect('bot.db')
    c = conn.cursor()

    # Проверяем, есть ли пользователь в базе
    c.execute("SELECT message_count FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()

    if result:
        message_count = result[0] + 1
        new_rank = get_rank(message_count)
        c.execute(
            "UPDATE users SET message_count = ?, rank = ?, username = ? WHERE user_id = ?",
            (message_count, new_rank, username, user_id)
        )
    else:
        message_count = 1
        new_rank = get_rank(message_count)
        c.execute(
            "INSERT INTO users (user_id, username, message_count, rank) VALUES (?, ?, ?, ?)",
            (user_id, username, message_count, new_rank)
        )

    conn.commit()
    conn.close()
    logger.info(f"Updated message count for user {user_id} ({username}): {message_count}, rank: {new_rank}")

# --- Функция для команды /site ---
async def site(update: Update, context):
    current_chat_id = str(update.message.chat.id)
    discussion_group_id = os.getenv("DISCUSSION_GROUP_ID")

    if not discussion_group_id or current_chat_id != discussion_group_id:
        logger.info(f"Ignored /site command from chat_id {current_chat_id}, not the expected discussion group {discussion_group_id}")
        return

    try:
        await update.message.reply_text("Наш любимый форум: https://pwismylife.com/")
        logger.info(f"Sent /site response in discussion group {discussion_group_id}")
    except Exception as e:
        logger.error(f"Failed to send /site response in discussion group {discussion_group_id}: {e}")

# --- Функция для команды /servers ---
async def servers(update: Update, context):
    current_chat_id = str(update.message.chat.id)
    discussion_group_id = os.getenv("DISCUSSION_GROUP_ID")

    if not discussion_group_id or current_chat_id != discussion_group_id:
        logger.info(f"Ignored /servers command from chat_id {current_chat_id}, not the expected discussion group {discussion_group_id}")
        return

    try:
        await update.message.reply_text(
            "Сервера достойные для просмотра:\n\n"
            "Edem New Born: https://edem.pw/\n"
            "Asgard PW: https://asgard.pw/\n"
            "Revolution PW: https://revolutionpw.online/\n"
            "ComeBack PW: https://comeback.pw/"
        )
        logger.info(f"Sent /servers response in discussion group {discussion_group_id}")
    except Exception as e:
        logger.error(f"Failed to send /servers response in discussion group {discussion_group_id}: {e}")

# --- Функция для команды /partners ---
async def partners(update: Update, context):
    current_chat_id = str(update.message.chat.id)
    discussion_group_id = os.getenv("DISCUSSION_GROUP_ID")

    if not discussion_group_id or current_chat_id != discussion_group_id:
        logger.info(f"Ignored /partners command from chat_id {current_chat_id}, not the expected discussion group {discussion_group_id}")
        return

    try:
        await update.message.reply_text(
            "Партнерские/Каналы соратников:\n\n"
            "RuFree News: @RuFreeNews\n"
            "ChaoPersik Team: @chaopersikpw\n"
            "GastTV: @gasttv\n"
            "Ubermench PW: @ubermensch_pw"
        )
        logger.info(f"Sent /partners response in discussion group {discussion_group_id}")
    except Exception as e:
        logger.error(f"Failed to send /partners response in discussion group {discussion_group_id}: {e}")

# --- Функция для команды /help ---
async def help_command(update: Update, context):
    current_chat_id = str(update.message.chat.id)
    discussion_group_id = os.getenv("DISCUSSION_GROUP_ID")

    if not discussion_group_id or current_chat_id != discussion_group_id:
        logger.info(f"Ignored /help command from chat_id {current_chat_id}, not the expected discussion group {discussion_group_id}")
        return

    try:
        await update.message.reply_text(
            "📋 Доступные команды:\n"
            "/site - Показать ссылку на наш любимый форум\n"
            "/servers - Показать список рекомендуемых серверов\n"
            "/partners - Показать список партнёрских каналов\n"
            "/help - Показать это сообщение\n"
            "/ping - Проверить статус бота\n"
            "/rank - Показать ваш текущий ранг и количество сообщений"
        )
        logger.info(f"Sent /help response in discussion group {discussion_group_id}")
    except Exception as e:
        logger.error(f"Failed to send /help response in discussion group {discussion_group_id}: {e}")

# --- Функция для команды /ping ---
async def ping(update: Update, context):
    current_chat_id = str(update.message.chat.id)
    discussion_group_id = os.getenv("DISCUSSION_GROUP_ID")

    if not discussion_group_id or current_chat_id != discussion_group_id:
        logger.info(f"Ignored /ping command from chat_id {current_chat_id}, not the expected discussion group {discussion_group_id}")
        return

    try:
        await update.message.reply_text("Бот онлайн! 🟢")
        logger.info(f"Sent /ping response in discussion group {discussion_group_id}")
    except Exception as e:
        logger.error(f"Failed to send /ping response in discussion group {discussion_group_id}: {e}")

# --- Функция для команды /rank ---
async def rank(update: Update, context):
    current_chat_id = str(update.message.chat.id)
    discussion_group_id = os.getenv("DISCUSSION_GROUP_ID")

    if not discussion_group_id or current_chat_id != discussion_group_id:
        logger.info(f"Ignored /rank command from chat_id {current_chat_id}, not the expected discussion group {discussion_group_id}")
        return

    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name

    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT message_count, rank FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()

    if result:
        message_count, rank = result
        response = f"👤 Пользователь: {username}\n📊 Количество сообщений: {message_count}\n🏆 Ранг: {rank}"
    else:
        response = f"👤 Пользователь: {username}\n📊 Количество сообщений: 0\n🏆 Ранг: Новенький"

    try:
        await update.message.reply_text(response)
        logger.info(f"Sent /rank response for user {user_id} in discussion group {discussion_group_id}")
    except Exception as e:
        logger.error(f"Failed to send /rank response in discussion group {discussion_group_id}: {e}")

# --- Эндпоинт для вебхука ---
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
    
    # Инициализация базы данных
    init_db()
    
    application = Application.builder().token(token).build()
    await application.initialize()
    
    # --- Добавляем обработчики ---
    # Используем ~filters.COMMAND, чтобы MessageHandler не перехватывал команды
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_forwarded_post_in_discussion))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, count_messages))
    application.add_handler(CommandHandler("site", site))
    application.add_handler(CommandHandler("servers", servers))
    application.add_handler(CommandHandler("partners", partners))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("rank", rank))
    
    port = int(os.getenv("PORT", 10000))
    logger.info(f"Starting Uvicorn server on host 0.0.0.0 and port {port}")
    config = uvicorn.Config(app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
