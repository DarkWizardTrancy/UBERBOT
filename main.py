import asyncio
import os
import logging
import sqlite3
import random
import uvicorn
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, CommandHandler, ContextTypes
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
    try:
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

    # Определяем тип сообщения для логов
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

    logger.info(f"Processing message from user {user_id} ({username}), type: {message_type}")

    try:
        conn = sqlite3.connect('/app/bot.db', check_same_thread=False)
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
        logger.info(f"Updated message count for user {user_id} ({username}): {message_count}, rank: {new_rank}")
    except Exception as e:
        logger.error(f"Failed to update message count for user {user_id}: {e}")
    finally:
        conn.close()

# --- Функция для обработки сообщений в личных чатах ---
async def handle_private_message(update: Update, context):
    current_chat_id = str(update.message.chat.id)
    logger.info(f"Received private message from chat_id {current_chat_id}")

    try:
        await update.message.reply_text(
            "Привет! 🎲 Ты можешь воспользоваться нашим рандомайзером по команде /random"
        )
        logger.info(f"Sent randomizer prompt to user in chat_id {current_chat_id}")
    except Exception as e:
        logger.error(f"Failed to send randomizer prompt in chat_id {current_chat_id}: {e}")

# --- Функция для команды /random ---
async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_chat_id = str(update.message.chat.id)
    if update.message.chat.type != "private":
        logger.info(f"Ignored /random command from chat_id {current_chat_id}, not a private chat")
        return

    try:
        await update.message.reply_text(
            "🎲 Введи диапазон чисел в формате <start>-<end>, например, '1-3'"
        )
        context.user_data["awaiting_random_range"] = True
        logger.info(f"Prompted user for random range in chat_id {current_chat_id}")
    except Exception as e:
        logger.error(f"Failed to send random range prompt in chat_id {current_chat_id}: {e}")

# --- Функция для обработки диапазона рандомайзера ---
async def handle_random_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_random_range", False):
        return

    current_chat_id = str(update.message.chat.id)
    if update.message.chat.type != "private":
        logger.info(f"Ignored range message from chat_id {current_chat_id}, not a private chat")
        return

    range_text = update.message.text.strip()
    logger.info(f"Received range '{range_text}' from user in chat_id {current_chat_id}")

    try:
        # Проверяем формат диапазона
        if "-" not in range_text:
            await update.message.reply_text(
                "❌ Неверный формат. Введи диапазон в формате <start>-<end>, например, '1-3'"
            )
            logger.info(f"Invalid range format '{range_text}' from chat_id {current_chat_id}")
            return

        start, end = map(str.strip, range_text.split("-", 1))
        start = int(start)
        end = int(end)

        if start > end:
            await update.message.reply_text(
                "❌ Начало диапазона должно быть меньше или равно концу. Попробуй снова, например, '1-3'"
            )
            logger.info(f"Invalid range: start {start} > end {end} from chat_id {current_chat_id}")
            return

        random_number = random.randint(start, end)
        await update.message.reply_text(f"🎲 Случайное число: {random_number}")
        logger.info(f"Generated random number {random_number} for range {start}-{end} in chat_id {current_chat_id}")
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат чисел. Используй целые числа, например, '1-3'"
        )
        logger.info(f"Invalid number format in range '{range_text}' from chat_id {current_chat_id}")
    except Exception as e:
        await update.message.reply_text("❌ Ошибка при генерации числа. Попробуй снова.")
        logger.error(f"Failed to generate random number for range '{range_text}' in chat_id {current_chat_id}: {e}")
    finally:
        context.user_data["awaiting_random_range"] = False

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
            "/rank - Показать ваш текущий ранг и количество сообщений\n"
            "/random - Сгенерировать случайное число (в личных сообщениях)"
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

    try:
        conn = sqlite3.connect('/app/bot.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT message_count, rank FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()

        if result:
            message_count, rank = result
            response = f"👤 Пользователь: {username}\n📊 Количество сообщений: {message_count}\n🏆 Ранг: {rank}"
        else:
            response = f"👤 Пользователь: {username}\n📊 Количество сообщений: 0\n🏆 Ранг: Странник Эфира"

        await update.message.reply_text(response)
        logger.info(f"Sent /rank response for user {user_id} in discussion group {discussion_group_id}")
    except Exception as e:
        logger.error(f"Failed to send /rank response in discussion group {discussion_group_id}: {e}")
        await update.message.reply_text("❌ Ошибка при получении ранга. Попробуй позже.")

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
    # Обработчик для пересланных постов из канала
    application.add_handler(MessageHandler(filters.FORWARDED & filters.ChatType.GROUPS, handle_forwarded_post_in_discussion))
    # Обработчик для подсчёта сообщений в группе
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & filters.ChatType.GROUPS, count_messages))
    # Обработчик для сообщений в личных чатах
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_private_message))
    # Обработчик для диапазона рандомайзера
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_random_range))
    # Команды
    application.add_handler(CommandHandler("site", site))
    application.add_handler(CommandHandler("servers", servers))
    application.add_handler(CommandHandler("partners", partners))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("rank", rank))
    application.add_handler(CommandHandler("random", random_command))
    
    port = int(os.getenv("PORT", 10000))
    logger.info(f"Starting Uvicorn server on host 0.0.0.0 and port {port}")
    config = uvicorn.Config(app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
