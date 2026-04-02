def build_offices_menu(conn: sqlite3.Connection) -> Tuple[str, InlineKeyboardMarkup]:
    rows = conn.execute(
        "SELECT p.chat_id, p.thread_id, r.chat_title, t.name AS tariff_name, t.duration_min, t.price "
        "FROM processing_topics p "
        "LEFT JOIN reception_groups r ON r.chat_id = p.reception_chat_id "
        "LEFT JOIN tariffs t ON t.id = r.tariff_id "
        "ORDER BY p.chat_id, p.thread_id"
    ).fetchall()
    lines = ["🏢 Привязки /set"]
    keyboard = []
    if not rows:
        lines.append("(привязок нет)")
    else:
        for r in rows:
            topic_label = f"{r['chat_id']}" + (f" / тема {r['thread_id']}" if r["thread_id"] else "")
            target_title = r["chat_title"] or str(r["chat_id"])
            if r["tariff_name"]:
                tariff_label = f"{r['tariff_name']} | {r['duration_min']} мин | ${r['price']}"
            else:
                tariff_label = "-"
            lines.append(f"• {topic_label} → {target_title} ({tariff_label})")
            keyboard.append(
                [InlineKeyboardButton(f"🗑 Удалить: {topic_label}", callback_data=f"adm:topic:delete:{r['chat_id']}:{r['thread_id'] or 0}")]
            )
    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="adm:settings")])
    return "\n".join(lines), InlineKeyboardMarkup(keyboard)