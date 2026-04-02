async def handle_group_worker_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == "private":
        return
    if not update.message:
        return
    state = get_state(context)
    if not state or state.get("name") != "worker_message_user":
        return
    data = state.get("data", {})
    expected_chat_id = data.get("chat_id")
    if expected_chat_id and expected_chat_id != update.effective_chat.id:
        return

    queue_id = data.get("queue_id")
    if not queue_id:
        clear_state(context)
        return

    text_msg = update.message.text or update.message.caption or ""
    if not text_msg and not update.message.photo:
        try:
            await update.message.reply_text("Отправьте текст или фото для владельца.")
        except Exception:
            pass
        return

    conn = get_conn()
    row = conn.execute(
        "SELECT user_id, phone FROM queue_numbers WHERE id = ?",
        (queue_id,),
    ).fetchone()
    conn.close()
    if not row:
        clear_state(context)
        return

    phone_display = format_phone(row["phone"])
    sent_ok = False
    try:
        if update.message.photo:
            photo_id = update.message.photo[-1].file_id
            caption = f"Сообщение от оператора по номеру {phone_display}"
            if text_msg:
                caption = f"{caption}\n{text_msg}"
            await context.bot.send_photo(
                chat_id=row["user_id"],
                photo=photo_id,
                caption=caption,
            )
        else:
            await context.bot.send_message(
                chat_id=row["user_id"],
                text=f"Сообщение от оператора по номеру {phone_display}:\n{text_msg}",
            )
        sent_ok = True
    except Exception as exc:
        logger.warning("Failed to send message to owner: %s", exc)

    clear_state(context)
    try:
        if sent_ok:
            await update.message.reply_text("✅ Сообщение отправлено владельцу.")
        else:
            await update.message.reply_text("Не удалось отправить владельцу. Попросите владельца написать боту /start.")
    except Exception:
        pass
