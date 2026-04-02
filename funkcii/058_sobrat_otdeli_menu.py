def build_departments_menu(conn: sqlite3.Connection) -> Tuple[str, InlineKeyboardMarkup]:
    rows = conn.execute(
        "SELECT r.chat_id, r.chat_title, t.name, t.duration_min, t.price "
        "FROM reception_groups r "
        "LEFT JOIN tariffs t ON r.tariff_id = t.id "
        "WHERE COALESCE(r.is_active, 1) = 1 "
        "ORDER BY r.chat_title"
    ).fetchall()
    lines = ["📥 Приемки (/num)"]
    keyboard = []
    if not rows:
        lines.append("(привязок нет)")
    else:
        for r in rows:
            title = r["chat_title"] or str(r["chat_id"])
            tariff = r["name"] or "-"
            if r["name"]:
                tariff = f"{r['name']} | {r['duration_min']} мин | ${r['price']}"
            lines.append(f"• {title} → {tariff}")
            keyboard.append(
                [InlineKeyboardButton(f"🗑 Удалить: {title}", callback_data=f"adm:reception:delete:{r['chat_id']}")]
            )
    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="adm:settings")])
    return "\n".join(lines), InlineKeyboardMarkup(keyboard)
