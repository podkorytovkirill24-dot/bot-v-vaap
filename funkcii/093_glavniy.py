from telegram.request import HTTPXRequest


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return float(raw.replace(",", "."))
    except Exception:
        return default


def main() -> None:
    init_db()
    start_miniapp_server()

    proxy_url = os.getenv("TG_PROXY_URL", "").strip() or None
    request = HTTPXRequest(
        proxy_url=proxy_url,
        connect_timeout=_env_float("TG_CONNECT_TIMEOUT", 20.0),
        read_timeout=_env_float("TG_READ_TIMEOUT", 20.0),
        write_timeout=_env_float("TG_WRITE_TIMEOUT", 20.0),
        pool_timeout=_env_float("TG_POOL_TIMEOUT", 5.0),
    )

    application = ApplicationBuilder().token(BOT_TOKEN).request(request).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("admin", cmd_admin))
    application.add_handler(CommandHandler("app", cmd_app))
    application.add_handler(CommandHandler("set", cmd_set))
    application.add_handler(CommandHandler("num", cmd_num))
    application.add_handler(CommandHandler("emojiid", cmd_emojiid))
    application.add_handler(CommandHandler("emojitest", cmd_emojitest))
    application.add_handler(CommandHandler("emojiset", cmd_emojiset))
    application.add_handler(CommandHandler("emojireload", cmd_emojireload))

    application.add_handler(CallbackQueryHandler(handle_callback))

    application.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & (filters.TEXT | filters.PHOTO), handle_private_state)
    )
    application.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_private_menu)
    )
    application.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & filters.PHOTO, handle_photo_qr)
    )
    application.add_handler(
        MessageHandler(filters.ChatType.GROUPS & filters.REPLY & (filters.TEXT | filters.PHOTO), handle_worker_code_reply, block=False)
    )
    application.add_handler(
        MessageHandler(filters.ChatType.GROUPS & (filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_group_worker_state, block=False)
    )
    application.add_handler(
        MessageHandler(filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND, handle_group_request_number, block=False)
    )
    application.add_handler(
        MessageHandler(filters.ChatType.GROUPS & (filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_group_submission)
    )

    if application.job_queue is not None:
        application.job_queue.run_repeating(job_tick, interval=60, first=10)
    else:
        logger.warning(
            "JobQueue ne dostupen. Ustanovite python-telegram-bot[job-queue], "
            "chtoby vklyuchit fonovye avto-zadachi."
        )

    start_external_bot_bridge()

    logger.info("Bot started")
    application.run_polling()
