async def menu_show_archive(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> None:
    conn = get_conn()
    rows = conn.execute(
        "SELECT q.phone, q.status, q.created_at, q.assigned_at, q.stood_at, q.completed_at, "
        "t.name AS tariff, t.duration_min AS duration_min "
        "FROM queue_numbers q LEFT JOIN tariffs t ON q.tariff_id = t.id "
        "WHERE q.user_id = ? AND q.status IN ('success','slip','error','canceled') "
        "ORDER BY q.completed_at DESC LIMIT 30",
        (user_id,),
    ).fetchall()
    conn.close()
    if not rows:
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📞 Сдать номер", callback_data="menu:submit")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="user:home")],
            ]
        )
        await context.bot.send_message(chat_id=chat_id, text=ui("empty_archive"), reply_markup=keyboard)
        return

    lines = ["🗂 Архив (последние 30):"]
    for r in rows:
        start_ts = r["stood_at"] or (r["completed_at"] if r["status"] == "success" else None) or r["created_at"]
        if r["status"] == "success":
            end_ts = now_ts()
        else:
            end_ts = r["completed_at"] or r["created_at"]
        stood_min = int(max(0, (end_ts - start_ts) // 60)) if start_ts and end_ts else 0
        tariff_min = int(r["duration_min"] or 0)
        tariff_name = r["tariff"] or "-"
        tariff_label = f"{tariff_name} ({tariff_min} мин)" if tariff_min > 0 else tariff_name
        ok_mark = "✅" if tariff_min <= 0 or stood_min >= tariff_min else "❌"
        lines.append(
            f"{ok_mark} {r['phone']} | {tariff_label} | {stood_min} мин | {status_human(r['status'])}"
        )
        lines.append(f"{format_ts(start_ts)} → {format_ts(end_ts)}")

    await context.bot.send_message(chat_id=chat_id, text="\n".join(lines))
