async def handle_group_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == "private":
        return
    if not update.message:
        return
    if update.message.reply_to_message and update.message.reply_to_message.from_user and update.message.reply_to_message.from_user.is_bot:
        return
    if update.message.text and update.message.text.strip().startswith("/"):
        return
    text = update.message.text or update.message.caption or ""
    raw_numbers = extract_numbers(text)
    numbers = filter_kz_numbers(raw_numbers)
    if not numbers:
        if raw_numbers:
            await update.message.reply_text(f"Принимаем только KZ номера.\n\n{SUBMIT_RULES_TEXT}")
        return

    conn = get_conn()
    reception = conn.execute(
        "SELECT tariff_id FROM reception_groups WHERE chat_id = ? AND COALESCE(is_active, 1) = 1",
        (update.effective_chat.id,),
    ).fetchone()
    if not reception:
        conn.close()
        return
    if get_config_bool(conn, "stop_work"):
        conn.close()
        await update.message.reply_text(ui("stop_work_alert"))
        return

    upsert_user(conn, update.effective_user)

    pending_before = conn.execute(
        "SELECT COUNT(*) AS cnt FROM queue_numbers WHERE status = 'queued' AND reception_chat_id = ?",
        (update.effective_chat.id,),
    ).fetchone()["cnt"]

    created_at = now_ts()
    photo_id = None
    if update.message.photo:
        photo_id = update.message.photo[-1].file_id

    accepted = []
    duplicates = []
    for idx, phone in enumerate(numbers, start=1):
        exists = conn.execute(
            "SELECT id FROM queue_numbers WHERE phone = ? AND status IN ('queued','taken')",
            (phone,),
        ).fetchone()
        if exists:
            duplicates.append(phone)
            continue
        conn.execute(
            "INSERT INTO queue_numbers "
            "(reception_chat_id, user_id, username, phone, status, created_at, tariff_id, photo_file_id) "
            "VALUES (?, ?, ?, ?, 'queued', ?, ?, ?)",
            (
                update.effective_chat.id,
                update.effective_user.id,
                update.effective_user.username,
                phone,
                created_at + idx,
                reception["tariff_id"],
                photo_id,
            ),
        )
        accepted.append(phone)
    conn.execute(
        "UPDATE users SET iam_here_at = ?, iam_here_warned_at = 0 WHERE user_id = ?",
        (created_at, update.effective_user.id),
    )
    conn.commit()
    conn.close()

    if not accepted:
        if duplicates:
            dup_lines = ["⚠ Номер уже в очереди:"]
            dup_lines.extend([f"• {format_phone(p)}" for p in duplicates[:20]])
            await update.message.reply_text("\n".join(dup_lines))
        return
    text_out = build_accept_text(accepted, pending_before)
    if duplicates:
        text_out += "\n\n⚠ Уже в очереди:\n" + "\n".join([f"• {format_phone(p)}" for p in duplicates[:20]])
    await update.message.reply_text(text_out)

