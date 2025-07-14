import asyncio
import os
import logging
import sqlite3
import random
import uvicorn
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    filters,
    CommandHandler,
    ContextTypes
)
from telegram.error import TelegramError
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
    conn = None
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
async def handle_forwarded_post_in_discussion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received an update in discussion group for forwarded message: {update.update_id}")

    message = update.message
    if not message:
        logger.info("Update is not a message in discussion group (forwarded). Skipping.")
        return

    current_chat_id = str(message.chat.id)
    discussion_group_id = os.getenv("DISCUSSION_GROUP_ID")

    if not discussion_group_id or current_chat_id != discussion_group_id:
        logger.info(f"Ignored forwarded message from chat_id {current_chat_id}, not the expected discussion group {discussion_group_id}")
        return

    if message.forward_from_chat and message.forward_from_chat.type == "channel":
        forwarded_from_channel_id = str(message.forward_from_chat.id)
        expected_channel_id = os.getenv("CHANNEL_ID")

        logger.info(f"Detected forwarded message from channel {forwarded_from_channel_id} in discussion group. Expected channel: {expected_channel_id}")

        if expected_channel_id and forwarded_from_channel_id == expected_channel_id:
            message_to_reply_id = message.message_id
            try:
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
async def count_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.from_user:
        logger.info("Update is not a message or has no user in count_messages. Skipping.")
        return

    current_chat_id = str(message.chat.id)
    discussion_group_id = os.getenv("DISCUSSION_GROUP_ID")

    if not discussion_group_id or current_chat_id != discussion_group_id:
        logger.info(f"Ignored message for counting from chat_id {current_chat_id}, not the expected discussion group {discussion_group_id}. Message text: '{message.text[:50] if message.text else 'N/A'}'")
        return

    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

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
    elif message.new_chat_members:
        message_type = "new_chat_members"
    elif message.left_chat_member:
        message_type = "left_chat_member"
    elif message.pinned_message:
        message_type = "pinned_message"
    elif message.animation: # Добавлено для гифок
        message_type = "animation"

    logger.info(f"Processing message for counting from user {user_id} ({username}), type: {message_type}, chat: {current_chat_id}")

    if message_type in ["new_chat_members", "left_chat_member", "pinned_message"]:
        logger.info(f"Skipping message count for service message type: {message_type}")
        return

    conn = None
    try:
        conn = sqlite3.connect('/app/bot.db', check_same_thread=False)
        c = conn.cursor()

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
        logger.info(f"Updated message count for user {user_id} ({username}): {message_count}, rank: {new_rank} in chat {current_chat_id}")
    except Exception as e:
        logger.error(f"Failed to update message count for user {user_id} in chat {current_chat_id}: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()

# --- Функция для обработки сообщений в личных чатах ---
async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_chat_id = str(update.message.chat.id)
    # Этот обработчик должен быть после handle_random_range,
    # т.к. handle_random_range использует user_data
    if context.user_data.get("awaiting_random_range", False):
        logger.info(f"Ignored private message from chat_id {current_chat_id}, awaiting random range.")
        return

    logger.info(f"Received private message from chat_id {current_chat_id}. Message: '{update.message.text[:50] if update.message.text else 'N/A'}'")

    try:
        await update.message.reply_text(
            "Привет! Я бот PWDarksearh by PWISMYLIFE. Используй /help, чтобы узнать, что я умею."
        )
        logger.info(f"Sent welcome message to user in chat_id {current_chat_id}")
    except Exception as e:
        logger.error(f"Failed to send welcome message in chat_id {current_chat_id}: {e}")

# --- Базовые команды ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /start command from user {update.effective_user.id}")
    await update.message.reply_text(
        "Привет! Я бот PWDarksearh by PWISMYLIFE. Я могу помочь с информацией, рангами и даже немного поиграть. "
        "Используй /help, чтобы увидеть список команд."
    )

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /info command from user {update.effective_user.id}")
    await update.message.reply_text(
        "Я бот, созданный для поддержки сообщества PWISMYLIFE. "
        "Мои функции включают подсчёт сообщений, выдачу рангов, рандомайзер и предоставление полезных ссылок."
    )

async def echo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Эта команда работает только в личных чатах
    if update.message.chat.type != "private":
        await update.message.reply_text("Эта команда работает только в личных сообщениях.")
        return

    if not context.args:
        await update.message.reply_text("Пожалуйста, введите текст после команды, например: /echo Привет!")
        return

    text_to_echo = " ".join(context.args)
    logger.info(f"Received /echo command with text: '{text_to_echo}' from user {update.effective_user.id}")
    await update.message.reply_text(text_to_echo)

# --- Функция для команды /random ---
async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_chat_id = str(update.message.chat.id)
    if update.message.chat.type != "private":
        logger.info(f"Ignored /random command from chat_id {current_chat_id}, not a private chat")
        await update.message.reply_text("Эта команда работает только в личных сообщениях.")
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
    # Убедитесь, что это действительно приватный чат и мы ожидаем диапазон
    if update.message.chat.type != "private" or not context.user_data.get("awaiting_random_range", False):
        logger.info(f"Ignored message from chat_id {str(update.message.chat.id)}, not awaiting random range in private chat.")
        return

    range_text = update.message.text.strip()
    current_chat_id = str(update.message.chat.id)
    logger.info(f"Received range '{range_text}' from user in chat_id {current_chat_id}")

    try:
        if "-" not in range_text:
            await update.message.reply_text(
                "❌ Неверный формат. Введи диапазон в формате <start>-<end>, например, '1-3'"
            )
            logger.info(f"Invalid range format '{range_text}' from chat_id {current_chat_id}")
            return

        start_str, end_str = map(str.strip, range_text.split("-", 1))
        start = int(start_str)
        end = int(end_str)

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
        logger.error(f"Failed to generate random number for range '{range_text}' in chat_id {current_chat_id}: {e}", exc_info=True)
    finally:
        context.user_data["awaiting_random_range"] = False

# --- Функции для команд в группе ---
async def site(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def servers(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def partners(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.message.chat.type
    user_id = update.effective_user.id
    logger.info(f"Received /help command from user {user_id} in chat type {chat_type}")

    if chat_type == "private":
        await update.message.reply_text(
            "📋 Доступные команды в личном чате:\n"
            "/start - Начать взаимодействие с ботом\n"
            "/info - Узнать информацию о боте\n"
            "/echo <текст> - Бот повторит ваш текст\n"
            "/random - Сгенерировать случайное число\n"
            "/help - Показать это сообщение"
        )
    else: # Группа
        discussion_group_id = os.getenv("DISCUSSION_GROUP_ID")
        current_chat_id = str(update.message.chat.id)
        if not discussion_group_id or current_chat_id != discussion_group_id:
            logger.info(f"Ignored /help command in group {current_chat_id}, not the expected discussion group {discussion_group_id}")
            return

        await update.message.reply_text(
            "📋 Доступные команды в группе:\n"
            "/site - Показать ссылку на наш любимый форум\n"
            "/servers - Показать список рекомендуемых серверов\n"
            "/partners - Показать список партнёрских каналов\n"
            "/help - Показать это сообщение\n"
            "/ping - Проверить статус бота\n"
            "/rank - Показать ваш текущий ранг и количество сообщений"
        )
    logger.info(f"Sent /help response to user {user_id} in chat type {chat_type}")


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_chat_id = str(update.message.chat.id)
    discussion_group_id = os.getenv("DISCUSSION_GROUP_ID")

    if not discussion_group_id or current_chat_id != discussion_group_id:
        logger.info(f"Ignored /rank command from chat_id {current_chat_id}, not the expected discussion group {discussion_group_id}")
        return

    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name

    conn = None
    try:
        conn = sqlite3.connect('/app/bot.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT message_count, rank FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()

        if result:
            message_count, rank = result
            response = f"👤 Пользователь: {username}\n📊 Количество сообщений: {message_count}\n🏆 Ранг: {rank}"
        else:
            response = f"👤 Пользователь: {username}\n📊 Количество сообщений: 0\n🏆 Ранг: Странник Эфира"

        await update.message.reply_text(response)
        logger.info(f"Sent /rank response for user {user_id} in discussion group {discussion_group_id}")
    except Exception as e:
        logger.error(f"Failed to send /rank response in discussion group {discussion_group_id}: {e}", exc_info=True)
        await update.message.reply_text("❌ Ошибка при получении ранга. Попробуй позже.")
    finally:
        if conn:
            conn.close()

# --- Эндпоинты FastAPI ---
@app.get("/")
async def health_check():
    logger.info("Received health check GET / request. Responding 200 OK.")
    return {"status": "ok", "message": "Bot is running"}

@app.post("/webhook")
async def webhook(request: Request):
    global application
    if application is None:
        logger.critical("Telegram Application is not initialized. Cannot process webhook.")
        return Response(status_code=500, content="Telegram Application not ready.")

    try:
        json_data = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse incoming JSON: {e}")
        return Response(status_code=400, content="Bad Request: Invalid JSON")

    logger.info(f"Received webhook payload: {json_data.get('update_id', 'N/A')}")

    try:
        update = Update.de_json(data=json_data, bot=application.bot)
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON into Update object: {e}", exc_info=True)
        return Response(status_code=400, content=f"Bad Request: Could not parse Update object: {e}")

    try:
        await application.process_update(update)
        logger.info(f"Webhook processed successfully for update_id: {json_data.get('update_id', 'N/A')}.")
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Error processing update {json_data.get('update_id', 'N/A')}: {e}", exc_info=True)
        return Response(status_code=500, content=f"Internal Server Error: {e}")

# --- Основная функция запуска бота ---
async def main():
    global application
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.critical("BOT_TOKEN environment variable is not set. Bot cannot start.")
        raise ValueError("BOT_TOKEN environment variable is not set")

    init_db()

    application = Application.builder().token(token).build()
    await application.initialize()

    # --- Установка вебхука ---
    render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if not render_hostname:
        logger.critical("RENDER_EXTERNAL_HOSTNAME environment variable is not set. Cannot determine webhook URL.")
        raise ValueError("RENDER_EXTERNAL_HOSTNAME is not set. Webhook URL cannot be determined automatically.")

    webhook_url = f"https://{render_hostname}/webhook"
    logger.info(f"Attempting to set webhook to: {webhook_url}")

    try:
        current_webhook_info = await application.bot.get_webhook_info()
        if current_webhook_info.url != webhook_url:
            await application.bot.set_webhook(url=webhook_url)
            logger.info("Webhook set successfully!")
        else:
            logger.info("Webhook is already set to the correct URL. Skipping.")
    except TelegramError as e:
        logger.critical(f"Failed to set webhook: {e}", exc_info=True)
        raise

    # --- Добавляем обработчики ---
    # Команды для любого типа чата
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("echo", echo_command)) # Echo может быть в группах, но будет работать только в личных
    application.add_handler(CommandHandler("random", random_command)) # Random только в личных

    # Сообщения, ожидающие диапазона для random (приватные чаты)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_random_range
    ))

    # Общие текстовые сообщения в приватных чатах (должен быть после других обработчиков приватных сообщений)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_private_message
    ))

    # Команды и сообщения для групп (ДИСКУССИОННАЯ ГРУППА)
    application.add_handler(CommandHandler("site", site))
    application.add_handler(CommandHandler("servers", servers))
    application.add_handler(CommandHandler("partners", partners))
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("rank", rank))

    # Обработчик для команды /help (может быть как в приватных, так и в группах)
    application.add_handler(CommandHandler("help", help_command))

    # Обработчик для пересланных постов из канала в дискуссионной группе
    application.add_handler(MessageHandler(
        filters.FORWARDED & filters.ChatType.GROUPS,
        handle_forwarded_post_in_discussion
    ))

    # Обработчик для подсчёта сообщений в группе (не команды, не форварды, не сервисные сообщения)
    application.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND & ~filters.FORWARDED & filters.ChatType.GROUPS,
        count_messages
    ))

    port = int(os.getenv("PORT", 10000))
    logger.info(f"Starting Uvicorn server on host 0.0.0.0 and port {port}")
    config = uvicorn.Config(app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"Bot failed to start: {e}", exc_info=True)
