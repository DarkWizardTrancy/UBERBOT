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
if name == "main":
    # Запускаем основную асинхронную функцию.
    asyncio.run(main())
