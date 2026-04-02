def build_issue_map_menu(conn: sqlite3.Connection) -> Tuple[str, InlineKeyboardMarkup]:
    issue_on = get_config_bool(conn, "issue_by_departments")
    tariffs = conn.execute(
        "SELECT id, name, price, duration_min FROM tariffs ORDER BY id"
    ).fetchall()
    mappings = conn.execute(
        "SELECT tariff_id, chat_id, thread_id FROM tariff_topics"
    ).fetchall()
    map_by_tariff = {m["tariff_id"]: (m["chat_id"], m["thread_id"]) for m in mappings}

    lines = [
        "🗂 Привязки /set к тарифам",
        f"Статус: {'ВКЛ' if issue_on else 'ВЫКЛ'}",
    ]

    if not tariffs:
        lines.append("")
        lines.append("(тарифов нет)")
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Назад", callback_data="adm:settings")]]
        )
        return "\n".join(lines), keyboard

    lines.append("")
    for t in tariffs:
        label = f"{t['name']} | {t['duration_min']} мин | ${t['price']}"
        mapping = map_by_tariff.get(t["id"])
        if mapping:
            chat_id, thread_id = mapping
            topic_label = f"{chat_id}" + (f" / тема {thread_id}" if thread_id else "")
            lines.append(f"• {label} → {topic_label}")
        else:
            lines.append(f"• {label} → (не привязано)")

    toggle_label = "✅ Включено" if issue_on else "❌ Выключено"
    keyboard = [[InlineKeyboardButton(toggle_label, callback_data="adm:issue_map:toggle")]]
    for t in tariffs:
        keyboard.append([InlineKeyboardButton(t["name"], callback_data=f"adm:issue_map:tariff:{t['id']}")])
    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="adm:settings")])
    return "\n".join(lines), InlineKeyboardMarkup(keyboard)
