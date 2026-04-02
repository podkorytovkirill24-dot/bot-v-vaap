async def handle_group_request_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == "private":
        return
    if not update.message:
        return
    text = (update.message.text or "").strip().lower()
    if "номер" not in text:
        return
    if extract_numbers(text):
        return

    conn = get_conn()
    if is_lunch_time(conn):
        conn.close()
        await update.message.reply_text("Сейчас обед. Попробуйте позже.")
        return

    thread_id = update.message.message_thread_id or 0
    topic = conn.execute(
        "SELECT reception_chat_id FROM processing_topics WHERE chat_id = ? AND thread_id = ?",
        (update.effective_chat.id, thread_id),
    ).fetchone()
    if not topic:
        reception = conn.execute(
            "SELECT 1 FROM reception_groups WHERE chat_id = ? AND COALESCE(is_active, 1) = 1",
            (update.effective_chat.id,),
        ).fetchone()
        conn.close()
        if reception:
            return
        await update.message.reply_text("Тема не привязана к приемке. Напишите /set.")
        return

    issue_by_tariff = get_config_bool(conn, "issue_by_departments", False)
    if issue_by_tariff:
        tariff_rows = conn.execute(
            "SELECT tariff_id FROM tariff_topics WHERE chat_id = ? AND thread_id = ?",
            (update.effective_chat.id, thread_id),
        ).fetchall()
        tariff_ids = [r["tariff_id"] for r in tariff_rows]
        if not tariff_ids:
            conn.close()
            await update.message.reply_text("Для этой темы тарифы не привязаны. Админ: /admin → Привязки /set к тарифам.")
            return
        row = fetch_next_queue(conn, [], None, tariff_ids)
    else:
        departments = conn.execute(
            "SELECT id, name FROM departments ORDER BY id"
        ).fetchall()
        dept_ids = [d["id"] for d in departments] if departments else []
        row = fetch_next_queue(conn, dept_ids, topic["reception_chat_id"])
    if not row:
        conn.close()
        await update.message.reply_text("Очередь пуста.")
        return
    now = now_ts()
    conn.execute(
        "UPDATE queue_numbers SET status = 'taken', assigned_at = ?, stood_at = COALESCE(stood_at, ?), worker_id = ? WHERE id = ?",
        (now, now, update.effective_user.id, row["id"]),
    )
    conn.commit()
    conn.close()
    await send_number_to_worker(update, context, row)

