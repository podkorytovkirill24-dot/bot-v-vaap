def _crypto_history_error_count(details: str) -> int:
    if not details:
        return 0
    try:
        parts = str(details).split("|")
        for part in parts:
            part = part.strip()
            if part.startswith("errors="):
                return int(part.split("=", 1)[1])
    except Exception:
        return 0
    return 0


def _build_crypto_history_report(conn: sqlite3.Connection, target_date: datetime.date) -> Tuple[str, InlineKeyboardMarkup]:
    asset_default = get_crypto_pay_asset(conn)
    start_dt = datetime(target_date.year, target_date.month, target_date.day, tzinfo=KZ_TZ)
    end_dt = start_dt + timedelta(days=1)
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    rows = conn.execute(
        "SELECT p.user_id, u.username, p.amount, p.asset, p.transfer_id "
        "FROM payouts p LEFT JOIN users u ON u.user_id = p.user_id "
        "WHERE p.source = 'crypto' AND p.created_at >= ? AND p.created_at < ? "
        "ORDER BY p.created_at",
        (start_ts, end_ts),
    ).fetchall()

    log_rows = conn.execute(
        "SELECT details FROM admin_logs WHERE action = 'crypto_pay_payouts' "
        "AND created_at >= ? AND created_at < ?",
        (start_ts, end_ts),
    ).fetchall()
    error_count = sum(_crypto_history_error_count(r["details"]) for r in log_rows)

    date_label = target_date.strftime("%d.%m.%Y")
    lines = [
        f"📊 Отчет о выплатах за {date_label}:",
        f"✅ Успешно: {len(rows)}",
        f"❌ Ошибок: {error_count}",
        "",
        "Детали всех операций:",
    ]
    if not rows:
        lines.append("Пока пусто.")
    else:
        for r in rows:
            user_label = f"@{r['username']}" if r["username"] else f"ID {r['user_id']}"
            amount = float(r["amount"] or 0)
            asset = r["asset"] or asset_default
            transfer_id = r["transfer_id"] or "-"
            lines.append(f"✅ {user_label} - {amount:.2f} {asset} отправлено (ID: {transfer_id})")

    today = now_kz().date()
    yesterday = today - timedelta(days=1)
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📅 Сегодня", callback_data="adm:crypto:history")],
            [InlineKeyboardButton("📅 Вчера", callback_data=f"adm:crypto:history:{yesterday.isoformat()}")],
            [InlineKeyboardButton("🗓 Другая дата", callback_data="adm:crypto:history:pick")],
            [InlineKeyboardButton("⬅ В меню Crypto", callback_data="adm:payouts")],
        ]
    )
    return "\n".join(lines), keyboard


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    data = query.data or ""
    parts = data.split(":")

    if data.startswith("menu:"):
        action = parts[1]
        if action == "submit":
            conn = get_conn()
            stop_work = get_config_bool(conn, "stop_work")
            conn.close()
            if stop_work:
                await query.answer(ui("stop_work_alert"), show_alert=True)
                return
            await menu_show_tariffs(context, query.from_user.id)
            await query.answer()
            return
        if action == "queue":
            await menu_show_queue(context, query.from_user.id, query.from_user.id)
            await query.answer()
            return
        if action == "archive":
            await menu_show_archive(context, query.from_user.id, query.from_user.id)
            await query.answer()
            return
        if action == "profile":
            await menu_show_profile(context, query.from_user.id, query.from_user.id)
            await query.answer()
            return
        if action == "support":
            clear_state(context)
            await menu_start_support(context, query.from_user.id, query.from_user.id)
            await query.answer()
            return
        if action == "lunch":
            conn = get_conn()
            lunch_on = get_config_bool(conn, "lunch_info_on")
            lunch_text = get_config(conn, "lunch_text", DEFAULT_CONFIG["lunch_text"])
            conn.close()
            if not lunch_on:
                await query.answer("Функция отключена", show_alert=True)
                return
            if query.message:
                await query.message.reply_text(lunch_text)
            else:
                await context.bot.send_message(chat_id=query.from_user.id, text=lunch_text)
            await query.answer()
            return
        if action == "admin":
            conn = get_conn()
            if not is_admin(conn, query.from_user.id):
                conn.close()
                await query.answer(ui("no_access"), show_alert=True)
                return
            conn.close()
            await query.message.reply_text(ui("admin_panel_title"), reply_markup=build_admin_panel())
            await query.answer()
            return
        await query.answer()
        return

    if data == "adm:panel":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        conn.close()
        await query.edit_message_text(ui("admin_panel_title"), reply_markup=build_admin_panel())
        await query.answer()
        return

    if data == "adm:service":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        conn.close()
        await query.edit_message_text(ui("service_title"), reply_markup=build_service_menu())
        await query.answer()
        return

    if data == "adm:service:info":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        text_info = build_service_text(conn)
        conn.close()
        await query.edit_message_text(text_info, reply_markup=build_service_menu())
        await query.answer()
        return

    if data == "adm:service:logs":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        text_logs = build_admin_logs_text(conn)
        conn.close()
        await query.edit_message_text(text_logs, reply_markup=build_service_menu())
        await query.answer()
        return

    if data == "adm:service:export_queue":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        csv_data = build_queue_csv(conn)
        conn.close()
        filename = "queue.csv"
        await query.message.reply_document(InputFile(io.BytesIO(csv_data.encode("utf-8")), filename=filename))
        await query.answer("Готово")
        return

    if data == "adm:service:clear_queue":
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Очистить", callback_data="adm:service:clear_queue_confirm")],
                [InlineKeyboardButton("↩ Назад", callback_data="adm:service")],
            ]
        )
        await query.edit_message_text("Очистить активную очередь?", reply_markup=keyboard)
        await query.answer()
        return

    if data == "adm:service:clear_queue_confirm":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        conn.execute(
            "UPDATE queue_numbers SET status='canceled', completed_at = ? WHERE status IN ('queued','taken')",
            (now_ts(),),
        )
        conn.commit()
        conn.close()
        log_admin_action(query.from_user.id, query.from_user.username, "queue_clear", "status in queued,taken -> canceled")
        await query.edit_message_text("✅ Очередь очищена.", reply_markup=build_service_menu())
        await query.answer()
        return

    if data == "adm:settings":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        text = ui("settings_title")
        keyboard = build_settings_menu(conn)
        conn.close()
        await query.edit_message_text(text, reply_markup=keyboard)
        await query.answer()
        return

    if data == "adm:extbot:cmd":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        current = get_config(conn, "extbot_pre_cmd", "").strip()
        conn.close()
        set_state(context, "admin_extbot_cmd")
        current_line = current if current else "не задана"
        await query.edit_message_text(
            "Введите команду, которую нужно отправлять перед каждым номером.\n"
            f"Текущая: {current_line}\n"
            "Чтобы очистить, отправьте -"
        )
        await query.answer()
        return

    if data.startswith("adm:toggle:"):
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        key = parts[2]
        current = get_config_bool(conn, key)
        set_config(conn, key, "0" if current else "1")
        keyboard = build_settings_menu(conn)
        conn.close()
        log_admin_action(query.from_user.id, query.from_user.username, "toggle_setting", f"{key}={'0' if current else '1'}")
        await query.edit_message_text(ui("settings_title"), reply_markup=keyboard)
        await query.answer("Обновлено")
        return

    if data == "adm:notifications":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        keyboard = build_notifications_menu(conn)
        conn.close()
        await query.edit_message_text("🔔 Уведомления", reply_markup=keyboard)
        await query.answer()
        return

    if data == "adm:tariffs":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        text, keyboard = build_tariffs_menu(conn)
        conn.close()
        await query.edit_message_text(text, reply_markup=keyboard)
        await query.answer()
        return

    if data == "adm:tariff:add":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        conn.close()
        set_state(context, "admin_tariff_add", step="name")
        await query.edit_message_text("Введите название тарифа:")
        await query.answer()
        return

    if data == "adm:tariff:edit":
        conn = get_conn()
        tariffs = conn.execute("SELECT id, name FROM tariffs ORDER BY id").fetchall()
        conn.close()
        if not tariffs:
            await query.answer("Нет тарифов", show_alert=True)
            return
        keyboard = [[InlineKeyboardButton(f"{t['id']} {t['name']}", callback_data=f"adm:tariff:edit:{t['id']}")] for t in tariffs]
        keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="adm:tariffs")])
        await query.edit_message_text("Выберите тариф:", reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer()
        return

    if data.startswith("adm:tariff:edit:"):
        tariff_id = int(parts[3])
        set_state(context, "admin_tariff_edit", tariff_id=tariff_id)
        await query.edit_message_text("Введите: Название | цена | минуты")
        await query.answer()
        return

    if data == "adm:tariff:delete":
        set_state(context, "admin_tariff_delete")
        await query.edit_message_text("Введите ID тарифа для удаления:")
        await query.answer()
        return

    if data == "adm:priorities":
        conn = get_conn()
        tariffs = conn.execute("SELECT id, name, priority FROM tariffs ORDER BY id").fetchall()
        conn.close()
        if not tariffs:
            await query.edit_message_text(ui("empty_tariffs"), reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Назад", callback_data="adm:settings")]]
            ))
            await query.answer()
            return
        lines = ["⚡ Приоритеты тарифов:"]
        keyboard = []
        for t in tariffs:
            lines.append(f"{t['id']}. {t['name']} — {t['priority']}")
            keyboard.append([InlineKeyboardButton(f"Изменить {t['id']}", callback_data=f"adm:priority:{t['id']}")])
        keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="adm:settings")])
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer()
        return

    if data.startswith("adm:priority:"):
        tariff_id = int(parts[2])
        set_state(context, "admin_set_priority", tariff_id=tariff_id)
        await query.edit_message_text("Введите новый приоритет (число):")
        await query.answer()
        return

    if data == "adm:departments":
        conn = get_conn()
        text, keyboard = build_departments_menu(conn)
        conn.close()
        await query.edit_message_text(text, reply_markup=keyboard)
        await query.answer()
        return

    if data.startswith("adm:reception:delete:"):
        chat_id = int(parts[3])
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        conn.execute(
            "UPDATE reception_groups SET is_active = 0 WHERE chat_id = ?",
            (chat_id,),
        )
        conn.commit()
        text, keyboard = build_departments_menu(conn)
        conn.close()
        await query.edit_message_text(text, reply_markup=keyboard)
        await query.answer("Удалено")
        return

    if data == "adm:dept:add":
        set_state(context, "admin_department_add")
        await query.edit_message_text("Введите название приемки:")
        await query.answer()
        return

    if data == "adm:dept:edit":
        conn = get_conn()
        depts = conn.execute("SELECT id, name FROM departments ORDER BY id").fetchall()
        conn.close()
        if not depts:
            await query.answer("Нет приемок", show_alert=True)
            return
        keyboard = [[InlineKeyboardButton(f"{d['id']} {d['name']}", callback_data=f"adm:dept:edit:{d['id']}")] for d in depts]
        keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="adm:departments")])
        await query.edit_message_text("Выберите приемку:", reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer()
        return

    if data.startswith("adm:dept:edit:"):
        dept_id = int(parts[3])
        set_state(context, "admin_department_edit", department_id=dept_id)
        await query.edit_message_text("Введите новое название приемки:")
        await query.answer()
        return

    if data == "adm:dept:delete":
        set_state(context, "admin_department_delete")
        await query.edit_message_text("Введите ID приемки для удаления:")
        await query.answer()
        return

    if data == "adm:offices":
        conn = get_conn()
        text, keyboard = build_offices_menu(conn)
        conn.close()
        await query.edit_message_text(text, reply_markup=keyboard)
        await query.answer()
        return

    if data == "adm:issue_map":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        text, keyboard = build_issue_map_menu(conn)
        conn.close()
        await query.edit_message_text(text, reply_markup=keyboard)
        await query.answer()
        return

    if data == "adm:issue_map:toggle":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        current = get_config_bool(conn, "issue_by_departments")
        set_config(conn, "issue_by_departments", "0" if current else "1")
        text, keyboard = build_issue_map_menu(conn)
        conn.close()
        await query.edit_message_text(text, reply_markup=keyboard)
        await query.answer("Обновлено")
        return

    if data.startswith("adm:issue_map:tariff:"):
        tariff_id = int(parts[3])
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        tariff = conn.execute(
            "SELECT id, name, price, duration_min FROM tariffs WHERE id = ?",
            (tariff_id,),
        ).fetchone()
        topics = conn.execute(
            "SELECT p.chat_id, p.thread_id, p.reception_chat_id, r.chat_title, "
            "t.name AS tariff_name, t.duration_min, t.price "
            "FROM processing_topics p "
            "LEFT JOIN reception_groups r ON r.chat_id = p.reception_chat_id "
            "LEFT JOIN tariffs t ON t.id = r.tariff_id "
            "ORDER BY p.chat_id, p.thread_id"
        ).fetchall()
        current = conn.execute(
            "SELECT chat_id, thread_id FROM tariff_topics WHERE tariff_id = ?",
            (tariff_id,),
        ).fetchone()
        conn.close()
        if not tariff:
            await query.answer("Тариф не найден", show_alert=True)
            return
        if current:
            current_label = f"{current['chat_id']}" + (f" / тема {current['thread_id']}" if current["thread_id"] else "")
        else:
            current_label = "(не привязано)"
        if not topics:
            lines = [
                f"Тариф: {tariff['name']} | {tariff['duration_min']} мин | ${tariff['price']}",
                f"Текущая привязка: {current_label}",
                "",
                "Нет привязок /set. Напишите /set в рабочей группе.",
            ]
            keyboard = []
            if current:
                keyboard.append([InlineKeyboardButton("🗑 Сбросить привязку", callback_data=f"adm:issue_map:clear:{tariff_id}")])
            keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="adm:issue_map")])
            await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard))
            await query.answer()
            return
        lines = [
            f"Тариф: {tariff['name']} | {tariff['duration_min']} мин | ${tariff['price']}",
            f"Текущая привязка: {current_label}",
            "",
            "Выберите привязку /set:",
        ]
        keyboard = []
        for p in topics:
            topic_label = f"{p['chat_id']}" + (f" / тема {p['thread_id']}" if p["thread_id"] else "")
            keyboard.append(
                [InlineKeyboardButton(topic_label, callback_data=f"adm:issue_map:set:{tariff_id}:{p['chat_id']}:{p['thread_id']}")]
            )
        if current:
            keyboard.append([InlineKeyboardButton("🗑 Сбросить привязку", callback_data=f"adm:issue_map:clear:{tariff_id}")])
        keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="adm:issue_map")])
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer()
        return

    if data.startswith("adm:issue_map:set:"):
        tariff_id = int(parts[3])
        chat_id = int(parts[4])
        thread_id = int(parts[5])
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        conn.execute(
            "INSERT INTO tariff_topics (tariff_id, chat_id, thread_id) VALUES (?, ?, ?) "
            "ON CONFLICT(tariff_id) DO UPDATE SET chat_id = excluded.chat_id, thread_id = excluded.thread_id",
            (tariff_id, chat_id, thread_id),
        )
        conn.commit()
        text, keyboard = build_issue_map_menu(conn)
        conn.close()
        await query.edit_message_text(text, reply_markup=keyboard)
        await query.answer("Готово")
        return

    if data.startswith("adm:issue_map:clear:"):
        tariff_id = int(parts[3])
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        conn.execute("DELETE FROM tariff_topics WHERE tariff_id = ?", (tariff_id,))
        conn.commit()
        text, keyboard = build_issue_map_menu(conn)
        conn.close()
        await query.edit_message_text(text, reply_markup=keyboard)
        await query.answer("Обновлено")
        return

    if data.startswith("adm:topic:delete:"):
        chat_id = int(parts[3])
        thread_id = int(parts[4])
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        conn.execute(
            "DELETE FROM processing_topics WHERE chat_id = ? AND thread_id = ?",
            (chat_id, thread_id),
        )
        conn.execute(
            "DELETE FROM tariff_topics WHERE chat_id = ? AND thread_id = ?",
            (chat_id, thread_id),
        )
        conn.commit()
        text, keyboard = build_offices_menu(conn)
        conn.close()
        await query.edit_message_text(text, reply_markup=keyboard)
        await query.answer("Удалено")
        return

    if data == "adm:office:add":
        set_state(context, "admin_office_add")
        await query.edit_message_text("Введите название офиса:")
        await query.answer()
        return

    if data == "adm:office:edit":
        conn = get_conn()
        offices = conn.execute("SELECT id, name FROM offices ORDER BY id").fetchall()
        conn.close()
        if not offices:
            await query.answer("Нет офисов", show_alert=True)
            return
        keyboard = [[InlineKeyboardButton(f"{o['id']} {o['name']}", callback_data=f"adm:office:edit:{o['id']}")] for o in offices]
        keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="adm:offices")])
        await query.edit_message_text("Выберите офис:", reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer()
        return

    if data.startswith("adm:office:edit:"):
        office_id = int(parts[3])
        set_state(context, "admin_office_edit", office_id=office_id)
        await query.edit_message_text("Введите новое название офиса:")
        await query.answer()
        return

    if data == "adm:office:delete":
        set_state(context, "admin_office_delete")
        await query.edit_message_text("Введите ID офиса для удаления:")
        await query.answer()
        return

    if data == "adm:office:bind":
        await query.edit_message_text("Чтобы привязать офис, напишите /set в нужной группе/теме.")
        await query.answer()
        return

    if data.startswith("office_bind:"):
        office_id = int(parts[1])
        chat_id = int(parts[2])
        thread_id = int(parts[3])
        conn = get_conn()
        if not (is_admin(conn, query.from_user.id) or await is_chat_admin(chat_id, query.from_user.id, context)):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        conn.execute(
            "UPDATE offices SET chat_id = ?, thread_id = ? WHERE id = ?",
            (chat_id, thread_id if thread_id > 0 else None, office_id),
        )
        conn.commit()
        conn.close()
        await query.edit_message_text("✅ Офис привязан к этой группе.")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                message_thread_id=thread_id if thread_id > 0 else None,
                text="📥 Рабочая панель\nНажмите кнопку ниже, чтобы получить номер из очереди.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📩 Получить номер", callback_data=f"office:next:{office_id}")]]
                ),
            )
        except Exception:
            pass
        await query.answer("Готово")
        return

    if data.startswith("set_topic:"):
        chat_id = int(parts[1])
        thread_id = int(parts[2])
        reception_chat_id = int(parts[3])
        conn = get_conn()
        if not (is_admin(conn, query.from_user.id) or await is_chat_admin(chat_id, query.from_user.id, context)):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        conn.execute(
            "INSERT INTO processing_topics (chat_id, thread_id, reception_chat_id) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id, thread_id) DO UPDATE SET reception_chat_id = excluded.reception_chat_id",
            (chat_id, thread_id, reception_chat_id),
        )
        conn.commit()
        conn.close()
        await query.edit_message_text("✅ Тема привязана к приемке.")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                message_thread_id=thread_id if thread_id > 0 else None,
                text="📦 Рабочая панель\nНажмите кнопку ниже, чтобы получить номер из очереди.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📩 Получить номер", callback_data="topic:next")]]
                ),
            )
        except Exception:
            pass
        await query.answer("Готово")
        return

    if data.startswith("set_reception:"):


        chat_id = int(parts[1])
        tariff_id = int(parts[2])
        conn = get_conn()
        if not (is_admin(conn, query.from_user.id) or await is_chat_admin(chat_id, query.from_user.id, context)):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        tariff = conn.execute(
            "SELECT name, price, duration_min FROM tariffs WHERE id = ?",
            (tariff_id,),
        ).fetchone()
        conn.execute(
            "INSERT INTO reception_groups (chat_id, chat_title, tariff_id, is_active) "
            "VALUES (?, ?, ?, 1) "
            "ON CONFLICT(chat_id) DO UPDATE SET tariff_id = excluded.tariff_id, is_active = 1",
            (
                chat_id,
                query.message.chat.title if query.message else str(chat_id),
                tariff_id,
            ),
        )
        conn.commit()
        conn.close()
        if tariff:
            hint = build_submit_hint(tariff["name"], tariff["duration_min"], tariff["price"])
            await query.edit_message_text(f"✅ Приемка настроена.\n\n{hint}")
        else:
            await query.edit_message_text("✅ Приемка настроена. Тариф привязан к этой группе.")
        await query.answer("Готово")
        return

    if data == "adm:mainmenu":
        conn = get_conn()
        text, keyboard = build_main_menu_settings(conn)
        conn.close()
        await query.edit_message_text(text, reply_markup=keyboard)
        await query.answer()
        return

    if data == "adm:mainmenu:text":
        set_state(context, "mainmenu_text")
        await query.edit_message_text("Введите новый текст главного меню:")
        await query.answer()
        return

    if data == "adm:mainmenu:photo":
        set_state(context, "mainmenu_photo")
        await query.edit_message_text("Отправьте новое фото для главного меню:")
        await query.answer()
        return

    if data.startswith("adm:mainmenu:btn:"):
        key_map = {
            "submit": "menu_btn_submit",
            "queue": "menu_btn_queue",
            "archive": "menu_btn_archive",
            "profile": "menu_btn_profile",
            "support": "menu_btn_support",
        }
        key = key_map.get(parts[3])
        if not key:
            await query.answer("Не найдено", show_alert=True)
            return
        set_state(context, "mainmenu_btn", key=key)
        await query.edit_message_text("Введите новый текст кнопки:")
        await query.answer()
        return

    if data == "adm:mainmenu:reset":
        conn = get_conn()
        for k, v in DEFAULT_CONFIG.items():
            if k.startswith("menu_btn_") or k.startswith("main_menu_"):
                set_config(conn, k, v)
        conn.close()
        await query.edit_message_text("Сброшено.", reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Назад", callback_data="adm:mainmenu")]]
        ))
        await query.answer()
        return

    if data == "adm:stats:today" or data.startswith("adm:stats:"):
        period = parts[2] if len(parts) > 2 else "today"
        conn = get_conn()
        text = build_stats_text(conn, period)
        conn.close()
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Сегодня", callback_data="adm:stats:today"),
                    InlineKeyboardButton("Вчера", callback_data="adm:stats:yesterday"),
                    InlineKeyboardButton("7 дней", callback_data="adm:stats:7d"),
                ],
                [
                    InlineKeyboardButton("30 дней", callback_data="adm:stats:30d"),
                    InlineKeyboardButton("Всё время", callback_data="adm:stats:all"),
                ],
                [InlineKeyboardButton("⬇ CSV за период", callback_data=f"adm:stats_csv:{period}")],
                [InlineKeyboardButton("⬇ CSV за всё время", callback_data="adm:stats_csv:all")],
                [InlineKeyboardButton("⬅ Назад", callback_data="adm:panel")],
            ]
        )
        await query.edit_message_text(text, reply_markup=keyboard)
        await query.answer()
        return

    if data.startswith("adm:stats_csv:"):
        period = parts[2]
        conn = get_conn()
        csv_data = build_csv(conn, period)
        conn.close()
        filename = f"stats_{period}.csv"
        await query.message.reply_document(InputFile(io.BytesIO(csv_data.encode("utf-8")), filename=filename))
        await query.answer("Готово")
        return

    if data == "adm:reports":
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Отстоявшие номера", callback_data="adm:report:stood")],
                [InlineKeyboardButton("❌ Не отстоявшие номера", callback_data="adm:report:notstood")],
                [InlineKeyboardButton("📋 Общий отчет", callback_data="adm:report:general")],
                [InlineKeyboardButton("⬅ Назад", callback_data="adm:panel")],
            ]
        )
        await query.edit_message_text(ui("reports_menu_title"), reply_markup=keyboard)
        await query.answer()
        return
    if data.startswith("adm:report:"):
        report_type = parts[2]
        action = parts[3] if len(parts) > 3 else "today"
        if action == "pick":
            set_state(context, "admin_reports_date", report_type=report_type)
            await query.edit_message_text(
                "Введите дату в формате ДД.ММ.ГГГГ (например 29.03.2026):",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅ Назад", callback_data="adm:reports")]]
                ),
            )
            await query.answer()
            return
        if action == "date" and len(parts) > 4:
            try:
                target_date = datetime.strptime(parts[4], "%Y-%m-%d").date()
            except Exception:
                await query.answer("Неверная дата", show_alert=True)
                return
        else:
            target_date = now_kz().date()
        conn = get_conn()
        text_limit = 50
        text, rows_all, _, end_ts = build_report_by_date(conn, report_type, target_date, limit=text_limit)
        if len(rows_all) > text_limit:
            csv_data = build_report_csv(rows_all, end_ts=end_ts)
            filename = f"report_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            await query.message.reply_document(
                InputFile(io.BytesIO(csv_data.encode("utf-8")), filename=filename)
            )
            text = text + f"\n\nПоказаны последние {text_limit}. Полный отчёт отправлен файлом."
        conn.close()
        yesterday = (now_kz().date() - timedelta(days=1)).isoformat()
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📅 Сегодня", callback_data=f"adm:report:{report_type}:today"),
                    InlineKeyboardButton("📅 Вчера", callback_data=f"adm:report:{report_type}:date:{yesterday}"),
                ],
                [InlineKeyboardButton("🗓 Другая дата", callback_data=f"adm:report:{report_type}:pick")],
                [InlineKeyboardButton("⬅ Назад", callback_data="adm:reports")],
            ]
        )
        await query.edit_message_text(text, reply_markup=keyboard)
        await query.answer()
        return
    if data.startswith("adm:tops:"):
        metric = parts[2]
        period = parts[3] if len(parts) > 3 else "all"
        conn = get_conn()
        text = build_tops(conn, metric, period)
        conn.close()
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Сдано номеров", callback_data="adm:tops:submitted:all"),
                    InlineKeyboardButton("Приглашенные", callback_data="adm:tops:invited:all"),
                ],
                [
                    InlineKeyboardButton("Встал", callback_data="adm:tops:success:all"),
                    InlineKeyboardButton("Слетел", callback_data="adm:tops:slip:all"),
                    InlineKeyboardButton("Ошибки", callback_data="adm:tops:error:all"),
                ],
                [
                    InlineKeyboardButton("Сегодня", callback_data=f"adm:tops:{metric}:today"),
                    InlineKeyboardButton("Вчера", callback_data=f"adm:tops:{metric}:yesterday"),
                    InlineKeyboardButton("7 дней", callback_data=f"adm:tops:{metric}:7d"),
                ],
                [
                    InlineKeyboardButton("30 дней", callback_data=f"adm:tops:{metric}:30d"),
                    InlineKeyboardButton("Всё время", callback_data=f"adm:tops:{metric}:all"),
                ],
                [InlineKeyboardButton("⬇ CSV", callback_data=f"adm:tops_csv:{metric}:{period}")],
                [InlineKeyboardButton("⬅ Назад", callback_data="adm:panel")],
            ]
        )
        await query.edit_message_text(text, reply_markup=keyboard)
        await query.answer()
        return

    if data.startswith("adm:tops_csv:"):
        metric = parts[2]
        period = parts[3]
        conn = get_conn()
        csv_data = build_tops_csv(conn, metric, period)
        conn.close()
        filename = f"tops_{metric}_{period}.csv"
        await query.message.reply_document(InputFile(io.BytesIO(csv_data.encode("utf-8")), filename=filename))
        await query.answer("Готово")
        return

    if data == "adm:users":
        conn = get_conn()
        total = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"]
        lines = [f"👥 Пользователи: {total}"]
        rows = conn.execute(
            "SELECT user_id, username, last_seen FROM users ORDER BY last_seen DESC LIMIT 10"
        ).fetchall()
        for r in rows:
            lines.append(f"{format_user_label(r['user_id'], r['username'])} | {format_ts(r['last_seen'])}")
        conn.close()
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔎 Поиск по ЮЗ/ID", callback_data="adm:user:search")],
                [InlineKeyboardButton("🔗 Выдать подписку", callback_data="adm:user:sub")],
                [InlineKeyboardButton("⬅ Назад", callback_data="adm:panel")],
            ]
        )
        await query.edit_message_text("\n".join(lines), reply_markup=keyboard)
        await query.answer()
        return

    if data == "adm:user:search":
        set_state(context, "admin_user_search")
        await query.edit_message_text("Введите ЮЗ (@username) или ID пользователя:")
        await query.answer()
        return

    if data == "adm:user:sub":
        set_state(context, "admin_user_subscription")
        await query.edit_message_text("Формат: юз(@username)/id | дней")
        await query.answer()
        return

    if data == "adm:queue":
        conn = get_conn()
        queued = conn.execute("SELECT COUNT(*) AS cnt FROM queue_numbers WHERE status = 'queued'").fetchone()["cnt"]
        taken = conn.execute("SELECT COUNT(*) AS cnt FROM queue_numbers WHERE status = 'taken'").fetchone()["cnt"]
        rows = conn.execute(
            "SELECT phone, user_id, username FROM queue_numbers "
            "WHERE status = 'queued' ORDER BY created_at, id"
        ).fetchall()
        conn.close()
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🧹 Очистить очередь", callback_data="adm:queue:clear")],
                [InlineKeyboardButton("⬅ Назад", callback_data="adm:panel")],
            ]
        )
        lines = [
            "🧹 Очередь",
            f"В ожидании: {queued}",
            f"В работе: {taken}",
        ]
        if rows:
            lines.append("")
            lines.append("Номера в очереди:")
            for r in rows[:30]:
                user = format_user_label(r["user_id"], r["username"])
                lines.append(f"• {format_phone(r['phone'])} | {user}")
            if len(rows) > 30:
                lines.append("…")
        else:
            lines.append("Очередь пуста.")
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=keyboard,
        )
        await query.answer()
        return

    if data == "adm:queue:clear":
        conn = get_conn()
        conn.execute(
            "UPDATE queue_numbers SET status = 'canceled', completed_at = ? WHERE status = 'queued'",
            (now_ts(),),
        )
        conn.commit()
        conn.close()
        log_admin_action(query.from_user.id, query.from_user.username, "queue_clear", "status=queued->canceled")
        await query.edit_message_text("✅ Очередь очищена.", reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Назад", callback_data="adm:queue")]]
        ))
        await query.answer("Готово")
        return

    if data == "adm:search":
        set_state(context, "admin_search_number")
        await query.edit_message_text("Введите номер для поиска:")
        await query.answer()
        return

    if data == "adm:withdrawals":
        conn = get_conn()
        rows = conn.execute(
            "SELECT w.id, w.user_id, u.username, w.amount, w.status "
            "FROM withdrawal_requests w "
            "LEFT JOIN users u ON u.user_id = w.user_id "
            "ORDER BY w.created_at DESC LIMIT 10"
        ).fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text(ui("empty_withdrawals"), reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Назад", callback_data="adm:panel")]]
            ))
            await query.answer()
            return
        lines = ["💰 Запросы вывода:"]
        keyboard = []
        for r in rows:
            lines.append(
                f"#{r['id']} | {format_user_label(r['user_id'], r['username'])} | "
                f"${r['amount']} | {status_human(r['status'])}"
            )
            if r["status"] == "pending":
                keyboard.append(
                    [InlineKeyboardButton(f"✅ Оплачено #{r['id']}", callback_data=f"adm:withdraw:pay:{r['id']}")]
                )
                keyboard.append(
                    [InlineKeyboardButton(f"❌ Ошибка #{r['id']}", callback_data=f"adm:withdraw:error:{r['id']}")]
                )
        keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="adm:panel")])
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer()
        return

    if data.startswith("adm:withdraw:pay:"):
        req_id = int(parts[3])
        conn = get_conn()
        req = conn.execute(
            "SELECT user_id, amount FROM withdrawal_requests WHERE id = ?",
            (req_id,),
        ).fetchone()
        conn.execute(
            "UPDATE withdrawal_requests SET status = 'paid', updated_at = ? WHERE id = ? AND status = 'pending'",
            (now_ts(), req_id),
        )
        conn.commit()
        conn.close()
        log_admin_action(query.from_user.id, query.from_user.username, "mark_withdraw_paid", f"request_id={req_id}")
        if req:
            try:
                await context.bot.send_message(
                    chat_id=req["user_id"],
                    text=f"✅ Ваш запрос вывода #{req_id} на ${float(req['amount']):.2f} отмечен как оплаченный.",
                )
            except Exception:
                pass
        await query.edit_message_text("Выплата отмечена.", reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Назад", callback_data="adm:withdrawals")]]
        ))
        await query.answer("Готово")
        return

    if data.startswith("adm:withdraw:error:") or data.startswith("adm:withdraw:cancel:"):
        req_id = int(parts[3])
        conn = get_conn()
        req = conn.execute(
            "SELECT user_id, amount FROM withdrawal_requests WHERE id = ?",
            (req_id,),
        ).fetchone()
        conn.execute(
            "UPDATE withdrawal_requests SET status = 'error', updated_at = ? WHERE id = ? AND status = 'pending'",
            (now_ts(), req_id),
        )
        conn.commit()
        conn.close()
        log_admin_action(query.from_user.id, query.from_user.username, "error_withdraw_request", f"request_id={req_id}")
        if req:
            try:
                await context.bot.send_message(
                    chat_id=req["user_id"],
                    text=f"❌ По вашему запросу вывода #{req_id} возникла ошибка. Сумма ${float(req['amount']):.2f} не списана.",
                )
            except Exception:
                pass
        await query.edit_message_text("Отмечено как ошибка (деньги не списаны).", reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Назад", callback_data="adm:withdrawals")]]
        ))
        await query.answer("Готово")
        return

    if data == "adm:payouts":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        token = get_crypto_pay_token(conn)
        asset = get_crypto_pay_asset(conn)
        conn.close()
        token_status = "✅ задан" if token else "❌ не задан"
        balance_line = "—"
        if token:
            bal_resp = crypto_pay_get_balance(token)
            if bal_resp.get("ok"):
                balance = crypto_pay_pick_balance(bal_resp.get("result"), asset)
                balance_line = f"{balance:.2f} {asset}"
            else:
                balance_line = "ошибка"
        lines = [
            "🪙 Крипто-платежи (Crypto Pay)",
            f"API token: {token_status}",
            f"Баланс: {balance_line}",
        ]
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔑 Установить токен", callback_data="adm:crypto:token")],
                [InlineKeyboardButton("➕ Создать инвойс (пополнение)", callback_data="adm:crypto:invoice")],
                [InlineKeyboardButton("💸 Выплаты (Crypto Pay)", callback_data="adm:crypto:payouts")],
                [InlineKeyboardButton("🧾 История выводов", callback_data="adm:crypto:history")],
                [InlineKeyboardButton("📝 Внутренние выплаты", callback_data="adm:payouts:manual")],
                [InlineKeyboardButton("⬅ В админ-меню", callback_data="adm:panel")],
            ]
        )
        await query.edit_message_text("\n".join(lines), reply_markup=keyboard)
        await query.answer()
        return

    if data == "adm:payouts:manual":
        set_state(context, "admin_payout")
        await query.edit_message_text(
            "Формат: юз(@username)/id | сумма | примечание(необязательно)",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ В меню Crypto", callback_data="adm:payouts")]]
            ),
        )
        await query.answer()
        return

    if data == "adm:crypto:token":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        conn.close()
        set_state(context, "admin_crypto_token")
        await query.edit_message_text(
            "🔑 API token Crypto Pay\n\nПришлите токен приложения. Чтобы удалить токен — отправьте -.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Назад", callback_data="adm:payouts")]]
            ),
        )
        await query.answer()
        return

    if data == "adm:crypto:invoice":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        asset = get_crypto_pay_asset(conn)
        conn.close()
        set_state(context, "admin_crypto_invoice")
        await query.edit_message_text(
            f"Введите сумму пополнения в {asset} (например 25):",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ В меню Crypto", callback_data="adm:payouts")]]
            ),
        )
        await query.answer()
        return

    if data == "adm:crypto:payouts":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        conn.close()
        set_state(context, "admin_crypto_payouts")
        await query.edit_message_text(
            "💸 Выплаты\n\nОтправьте список выплат в формате (по одной на строке):\n@username 10\n@user2 15.5",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🧾 История выводов", callback_data="adm:crypto:history")],
                    [InlineKeyboardButton("⬅ В меню Crypto", callback_data="adm:payouts")],
                ]
            ),
        )
        await query.answer()
        return

    if data == "adm:crypto:history":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        text_report, keyboard = _build_crypto_history_report(conn, now_kz().date())
        conn.close()
        await query.edit_message_text(text_report, reply_markup=keyboard)
        await query.answer()
        return

    if data == "adm:crypto:history:pick":
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        conn.close()
        set_state(context, "admin_crypto_history_date")
        await query.edit_message_text(
            "Введите дату в формате ДД.ММ.ГГГГ (например 29.03.2026):",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ В меню Crypto", callback_data="adm:payouts")]]
            ),
        )
        await query.answer()
        return

    if data.startswith("adm:crypto:history:"):
        raw_date = parts[3] if len(parts) > 3 else ""
        try:
            target_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except Exception:
            await query.answer("Неверная дата", show_alert=True)
            return
        conn = get_conn()
        if not is_admin(conn, query.from_user.id):
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        text_report, keyboard = _build_crypto_history_report(conn, target_date)
        conn.close()
        await query.edit_message_text(text_report, reply_markup=keyboard)
        await query.answer()
        return

    if data == "adm:broadcast":
        set_state(context, "admin_broadcast")
        await query.edit_message_text("Отправьте сообщение для рассылки (текст или фото).")
        await query.answer()
        return

    if data == "adm:admins":
        conn = get_conn()
        rows = conn.execute(
            "SELECT a.user_id, u.username "
            "FROM admins a LEFT JOIN users u ON u.user_id = a.user_id "
            "ORDER BY a.user_id"
        ).fetchall()
        conn.close()
        lines = ["🛡 Админы:"]
        for r in rows:
            lines.append(f"• {format_user_label(r['user_id'], r['username'])}")
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("➕ Добавить", callback_data="adm:admins:add")],
                [InlineKeyboardButton("➖ Удалить", callback_data="adm:admins:remove")],
                [InlineKeyboardButton("⬅ Назад", callback_data="adm:panel")],
            ]
        )
        await query.edit_message_text("\n".join(lines), reply_markup=keyboard)
        await query.answer()
        return

    if data == "adm:admins:add":
        set_state(context, "admin_add_admin")
        await query.edit_message_text("Введите ЮЗ (@username) или ID пользователя:")
        await query.answer()
        return

    if data == "adm:admins:remove":
        set_state(context, "admin_remove_admin")
        await query.edit_message_text("Введите ЮЗ (@username) или ID пользователя для удаления:")
        await query.answer()
        return

    if data == "adm:subscription":
        conn = get_conn()
        current = get_config_bool(conn, "require_subscription", False)
        set_config(conn, "require_subscription", "0" if current else "1")
        conn.close()
        log_admin_action(
            query.from_user.id,
            query.from_user.username,
            "toggle_subscription_required",
            f"require_subscription={'0' if current else '1'}",
        )
        await query.edit_message_text(
            f"ОП (подписка): {'ВКЛ' if not current else 'ВЫКЛ'}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Назад", callback_data="adm:settings")]]
            ),
        )
        await query.answer("Обновлено")
        return

    if data == "adm:limit":
        set_state(context, "admin_limit")
        await query.edit_message_text("Введите лимит сдачи в день (0 = без лимита):")
        await query.answer()
        return

    if data == "adm:auto_success":
        set_state(context, "admin_auto_success")
        await query.edit_message_text("Введите минуты для авто-встал (0 = выкл):")
        await query.answer()
        return

    if data == "adm:auto_slip":
        set_state(context, "admin_auto_slip")
        await query.edit_message_text("Введите минуты для авто-слет (0 = выкл):")
        await query.answer()
        return

    if data == "adm:lunch":
        conn = get_conn()
        current_on = get_config_bool(conn, "lunch_info_on")
        current_text = get_config(conn, "lunch_text", DEFAULT_CONFIG["lunch_text"])
        conn.close()
        status = "ВКЛ" if current_on else "ВЫКЛ"
        toggle_label = "❌ Выключить" if current_on else "✅ Включить"
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✏ Изменить текст", callback_data="adm:lunch:text")],
                [InlineKeyboardButton(toggle_label, callback_data="adm:lunch:toggle")],
                [InlineKeyboardButton("⬅ Назад", callback_data="adm:settings")],
            ]
        )
        await query.edit_message_text(
            "🍽 Расписание обедов\n\n"
            f"Статус: {status}\n\n"
            "Текст:\n"
            f"{current_text}",
            reply_markup=keyboard,
        )
        await query.answer()
        return

    if data == "adm:lunch:text":
        set_state(context, "admin_lunch")
        await query.edit_message_text("Введите текст расписания обедов:")
        await query.answer()
        return

    if data == "adm:lunch:toggle":
        conn = get_conn()
        current_on = get_config_bool(conn, "lunch_info_on")
        new_on = not current_on
        set_config(conn, "lunch_info_on", "1" if new_on else "0")
        current_text = get_config(conn, "lunch_text", DEFAULT_CONFIG["lunch_text"])
        conn.close()
        status = "ВКЛ" if new_on else "ВЫКЛ"
        toggle_label = "❌ Выключить" if new_on else "✅ Включить"
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✏ Изменить текст", callback_data="adm:lunch:text")],
                [InlineKeyboardButton(toggle_label, callback_data="adm:lunch:toggle")],
                [InlineKeyboardButton("⬅ Назад", callback_data="adm:settings")],
            ]
        )
        await query.edit_message_text(
            "🍽 Расписание обедов\n\n"
            f"Статус: {status}\n\n"
            "Текст:\n"
            f"{current_text}",
            reply_markup=keyboard,
        )
        await query.answer("Обновлено")
        return

    if data == "adm:requests":
        conn = get_conn()
        rows = conn.execute(
            "SELECT r.id, r.user_id, u.username, r.status "
            "FROM access_requests r LEFT JOIN users u ON u.user_id = r.user_id "
            "WHERE r.status = 'pending' ORDER BY r.created_at DESC"
        ).fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text(ui("empty_requests"), reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Назад", callback_data="adm:settings")]]
            ))
            await query.answer()
            return
        lines = ["📝 Заявки:"]
        keyboard = []
        for r in rows:
            lines.append(f"#{r['id']} | {format_user_label(r['user_id'], r['username'])}")
            keyboard.append([InlineKeyboardButton(f"✅ Одобрить #{r['id']}", callback_data=f"adm:req:approve:{r['id']}")])
        keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="adm:settings")])
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer()
        return

    if data.startswith("adm:req:approve:"):
        req_id = int(parts[3])
        conn = get_conn()
        row = conn.execute("SELECT user_id FROM access_requests WHERE id = ?", (req_id,)).fetchone()
        if row:
            conn.execute("UPDATE access_requests SET status = 'approved' WHERE id = ?", (req_id,))
            conn.execute("UPDATE users SET is_approved = 1 WHERE user_id = ?", (row["user_id"],))
            conn.commit()
            log_admin_action(query.from_user.id, query.from_user.username, "approve_access_request", f"request_id={req_id}|user_id={row['user_id']}")
        conn.close()
        await query.edit_message_text("Заявка одобрена.", reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Назад", callback_data="adm:requests")]]
        ))
        await query.answer("Готово")
        return

    if data == "adm:referral":
        conn = get_conn()
        current = get_config_bool(conn, "referral_enabled", True)
        set_config(conn, "referral_enabled", "0" if current else "1")
        keyboard = build_settings_menu(conn)
        conn.close()
        log_admin_action(
            query.from_user.id,
            query.from_user.username,
            "toggle_referral",
            f"referral_enabled={'0' if current else '1'}",
        )
        status = "включена" if not current else "выключена"
        await query.edit_message_text(f"👥 Рефералка {status}.", reply_markup=keyboard)
        await query.answer("Обновлено")
        return

    if data == "adm:support":
        conn = get_conn()
        tickets = conn.execute(
            "SELECT t.id, t.user_id, u.username "
            "FROM support_tickets t LEFT JOIN users u ON u.user_id = t.user_id "
            "WHERE t.status = 'open' ORDER BY t.created_at DESC LIMIT 10"
        ).fetchall()
        conn.close()
        if not tickets:
            await query.edit_message_text(ui("empty_support_tickets"), reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Назад", callback_data="adm:settings")]]
            ))
            await query.answer()
            return
        lines = ["✏ Саппорт:"]
        keyboard = []
        for t in tickets:
            lines.append(f"#{t['id']} | {format_user_label(t['user_id'], t['username'])}")
            keyboard.append([InlineKeyboardButton(f"Ответить #{t['id']}", callback_data=f"adm:support_reply:{t['id']}")])
        keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="adm:settings")])
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer()
        return

    if data.startswith("adm:support_reply:"):
        ticket_id = int(parts[2])
        set_state(context, "admin_support_reply", ticket_id=ticket_id)
        await query.edit_message_text("Введите ответ пользователю:")
        await query.answer()
        return

    if data == "adm:slip_all":
        conn = get_conn()
        rows = conn.execute(
            "SELECT id, user_id, phone FROM queue_numbers WHERE status = 'taken'"
        ).fetchall()
        conn.execute(
            "UPDATE queue_numbers SET status = 'slip', completed_at = ? WHERE status = 'taken'",
            (now_ts(),),
        )
        conn.commit()
        conn.close()
        for r in rows:
            try:
                await context.bot.send_message(
                    chat_id=r["user_id"],
                    text=f"❌ Ваш номер {r['phone']} слетел.",
                )
            except Exception:
                continue
        await query.edit_message_text("Все активные номера отмечены как слет.", reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Назад", callback_data="adm:settings")]]
        ))
        await query.answer("Готово")
        return

    if data == "adm:i_am_here":
        conn = get_conn()
        current_on = get_config_bool(conn, "i_am_here_on")
        current_minutes = get_config_int(conn, "i_am_here_minutes", 10)
        conn.close()
        set_state(context, "admin_i_am_here")
        status_text = "включено" if current_on else "выключено"
        await query.edit_message_text(
            "👋 Я тут\n"
            f"Статус: {status_text}\n"
            f"Текущий интервал: {current_minutes} мин\n\n"
            "Введите интервал в минутах (0 = выключить):"
        )
        await query.answer()
        return

    if data == "user:i_am_here":
        conn = get_conn()
        if not get_config_bool(conn, "i_am_here_on"):
            conn.close()
            await query.answer("Функция отключена.", show_alert=True)
            return
        cnt = conn.execute(
            "SELECT COUNT(*) AS cnt FROM queue_numbers WHERE user_id = ? AND status = 'queued'",
            (query.from_user.id,),
        ).fetchone()["cnt"]
        if cnt <= 0:
            conn.close()
            await query.answer("У вас нет номеров в очереди.", show_alert=True)
            return
        now = now_ts()
        conn.execute(
            "UPDATE users SET iam_here_at = ?, iam_here_warned_at = 0 WHERE user_id = ?",
            (now, query.from_user.id),
        )
        conn.commit()
        conn.close()
        await query.answer("✅ Принято. Вы отметились.", show_alert=True)
        return

    if data == "adm:input_type":
        conn = get_conn()
        current = get_config_bool(conn, "use_priorities", True)
        set_config(conn, "use_priorities", "0" if current else "1")
        keyboard = build_settings_menu(conn)
        conn.close()
        mode = "FIFO (по времени)" if current else "По приоритетам тарифа"
        log_admin_action(
            query.from_user.id,
            query.from_user.username,
            "switch_issue_mode",
            "use_priorities=0 (FIFO)" if current else "use_priorities=1 (priority)",
        )
        await query.edit_message_text(f"🧩 Тип вбива: {mode}", reply_markup=keyboard)
        await query.answer("Обновлено")
        return

    if data == "adm:back_to_menu":
        await query.answer("Главное меню отправлено")
        await send_main_menu_chat(context, query.from_user.id, query.from_user.id)
        return

    if data.startswith("user:tariff:"):
        tariff_id = int(parts[2])
        conn = get_conn()
        tariff = conn.execute(
            "SELECT id, name, price, duration_min FROM tariffs WHERE id = ?",
            (tariff_id,),
        ).fetchone()
        receptions = conn.execute(
            "SELECT chat_id, chat_title FROM reception_groups WHERE COALESCE(is_active, 1) = 1 AND tariff_id = ? ORDER BY chat_title",
            (tariff_id,),
        ).fetchall()
        depts = conn.execute("SELECT id, name FROM departments ORDER BY id").fetchall()
        conn.close()
        if not tariff:
            await query.edit_message_text("Тариф не найден.")
            await query.answer()
            return
        if not receptions:
            await query.edit_message_text("Приемки для этого тарифа не настроены. Админ: /num в нужной приемке.")
            await query.answer()
            return
        if len(receptions) == 1:
            reception_chat_id = receptions[0]["chat_id"]
            hint = build_submit_hint(tariff["name"], tariff["duration_min"], tariff["price"])
            if not depts:
                set_state(context, "submit_numbers", tariff_id=tariff_id, department_id=None, reception_chat_id=reception_chat_id)
                await query.edit_message_text(f"{hint}\n\nОтправьте номера одним сообщением:")
                await query.answer()
                return
            keyboard = [[InlineKeyboardButton(d["name"], callback_data=f"user:dept:{tariff_id}:{d['id']}:{reception_chat_id}")] for d in depts]
            await query.edit_message_text("Выберите отдел:", reply_markup=InlineKeyboardMarkup(keyboard))
            await query.answer()
            return
        keyboard = []
        for r in receptions:
            title = r["chat_title"] or str(r["chat_id"])
            keyboard.append([InlineKeyboardButton(title, callback_data=f"user:reception:{tariff_id}:{r['chat_id']}")])
        await query.edit_message_text("Выберите приемку:", reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer()
        return

    if data.startswith("user:reception:"):
        tariff_id = int(parts[2])
        reception_chat_id = int(parts[3])
        conn = get_conn()
        tariff = conn.execute(
            "SELECT id, name, price, duration_min FROM tariffs WHERE id = ?",
            (tariff_id,),
        ).fetchone()
        depts = conn.execute("SELECT id, name FROM departments ORDER BY id").fetchall()
        conn.close()
        if not tariff:
            await query.edit_message_text("Тариф не найден.")
            await query.answer()
            return
        hint = build_submit_hint(tariff["name"], tariff["duration_min"], tariff["price"])
        if not depts:
            set_state(context, "submit_numbers", tariff_id=tariff_id, department_id=None, reception_chat_id=reception_chat_id)
            await query.edit_message_text(f"{hint}\n\nОтправьте номера одним сообщением:")
            await query.answer()
            return
        keyboard = [[InlineKeyboardButton(d["name"], callback_data=f"user:dept:{tariff_id}:{d['id']}:{reception_chat_id}")] for d in depts]
        await query.edit_message_text("Выберите отдел:", reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer()
        return

    if data.startswith("user:dept:"):
        tariff_id = int(parts[2])
        dept_id = int(parts[3])
        reception_chat_id = int(parts[4]) if len(parts) > 4 else None
        if reception_chat_id is None:
            await query.edit_message_text("Приемка не выбрана. Откройте меню и выберите тариф заново.")
            await query.answer()
            return
        conn = get_conn()
        tariff = conn.execute(
            "SELECT id, name, price, duration_min FROM tariffs WHERE id = ?",
            (tariff_id,),
        ).fetchone()
        conn.close()
        if not tariff:
            await query.edit_message_text("Тариф не найден.")
            await query.answer()
            return
        set_state(context, "submit_numbers", tariff_id=tariff_id, department_id=dept_id, reception_chat_id=reception_chat_id)
        hint = build_submit_hint(tariff["name"], tariff["duration_min"], tariff["price"])
        await query.edit_message_text(f"{hint}\n\nОтправьте номера одним сообщением:")
        await query.answer()
        return
    if data == "user:request_access":
        conn = get_conn()
        conn.execute(
            "INSERT INTO access_requests (user_id, status, created_at) VALUES (?, 'pending', ?)",
            (query.from_user.id, now_ts()),
        )
        conn.commit()
        conn.close()
        await query.edit_message_text("Заявка отправлена администратору.")
        await query.answer("Готово")
        return

    if data == "user:withdraw":
        set_state(context, "user_withdraw")
        await query.edit_message_text("Введите сумму для вывода:")
        await query.answer()
        return

    if data.startswith("user:qr:") or data.startswith("user:repeat:"):
        action = parts[1]
        queue_id = int(parts[2])
        conn = get_conn()
        row = conn.execute(
            "SELECT id, user_id, phone, status, worker_chat_id, worker_msg_id "
            "FROM queue_numbers WHERE id = ?",
            (queue_id,),
        ).fetchone()
        if not row:
            conn.close()
            await query.answer("Номер не найден.", show_alert=True)
            return
        if row["user_id"] != query.from_user.id:
            conn.close()
            await query.answer(ui("no_access"), show_alert=True)
            return
        if row["status"] != "taken":
            conn.close()
            await query.answer("Номер еще не взят в работу.", show_alert=True)
            return
        if not row["worker_chat_id"] or not row["worker_msg_id"]:
            conn.close()
            await query.answer("Оператор еще не взял номер.", show_alert=True)
            return
        phone_display = format_phone(row["phone"])
        req_label = "QR" if action == "qr" else "повтор кода"
        try:
            msg = await context.bot.send_message(
                chat_id=row["worker_chat_id"],
                text=(
                    "📩 Запрос от пользователя\n"
                    f"Номер: {phone_display}\n"
                    f"Запрос: {req_label}\n"
                    "Ответьте на это сообщение, чтобы отправить пользователю."
                ),
                reply_to_message_id=row["worker_msg_id"],
            )
            conn.execute(
                "UPDATE queue_numbers SET worker_msg_id = ? WHERE id = ?",
                (msg.message_id, row["id"]),
            )
            conn.commit()
        except Exception:
            conn.close()
            await query.answer("Не удалось отправить запрос.", show_alert=True)
            return
        conn.close()
        await query.answer("Запрос отправлен.", show_alert=True)
        return

    if data == "user:home":
        await query.answer("Главное меню отправлено")
        await send_main_menu_chat(context, query.from_user.id, query.from_user.id)
        return

    if data.startswith("issue:"):
        dept_id = int(parts[1])
        reception_chat_id = int(parts[2])
        conn = get_conn()
        row = fetch_next_queue(conn, [dept_id], reception_chat_id)
        if not row:
            conn.close()
            await query.edit_message_text("Очередь пуста.")
            await query.answer()
            return
        now = now_ts()
        conn.execute(
            "UPDATE queue_numbers SET status = 'taken', assigned_at = ?, stood_at = COALESCE(stood_at, ?), worker_id = ? WHERE id = ?",
            (now, now, query.from_user.id, row["id"]),
        )
        conn.commit()
        conn.close()
        await send_number_to_worker(update, context, row)
        await query.answer()
        return

    if data.startswith("q:msg:"):
        queue_id = int(parts[2])
        set_state(context, "worker_message_user", queue_id=queue_id, chat_id=query.message.chat_id if query.message else None)
        await query.answer("Введите сообщение")
        if query.message:
            await query.message.reply_text(
                "\u0412\u0432\u0435\u0434\u0438\u0442\u0435\u0020\u0441\u043E\u043E\u0431\u0449\u0435\u043D\u0438\u0435\u0020\u0432\u043B\u0430\u0434\u0435\u043B\u044C\u0446\u0443\u0020\u0028\u0442\u0435\u043A\u0441\u0442\u0020\u0438\u043B\u0438\u0020\u0444\u043E\u0442\u043E\u0029\u002E\n\u041E\u0442\u0432\u0435\u0442\u044C\u0442\u0435\u0020\u043D\u0430\u0020\u044D\u0442\u043E\u0020\u0441\u043E\u043E\u0431\u0449\u0435\u043D\u0438\u0435\u002E",
                reply_markup=ForceReply(selective=True),
            )
        return

    if data.startswith("q:skip:"):
        queue_id = int(parts[2])
        conn = get_conn()
        row = conn.execute("SELECT user_id, phone, status FROM queue_numbers WHERE id = ?", (queue_id,)).fetchone()
        if not row:
            conn.close()
            await query.answer("Не найдено", show_alert=True)
            return
        if row["status"] not in ("taken", "queued"):
            conn.close()
            await query.answer("Уже закрыто", show_alert=True)
            return
        conn.execute(
            "UPDATE queue_numbers SET status = 'canceled', completed_at = ? WHERE id = ?",
            (now_ts(), queue_id),
        )
        conn.commit()
        conn.close()
        try:
            if query.message:
                status_line = f"⏭ пропущен ({format_msk()})"
                if query.message.photo:
                    caption = query.message.caption or ""
                    await query.message.edit_caption(
                        caption=merge_status_text(caption, status_line),
                        reply_markup=None,
                    )
                else:
                    txt = query.message.text or ""
                    await query.message.edit_text(
                        text=merge_status_text(txt, status_line),
                        reply_markup=None,
                    )
        except Exception:
            pass
        await query.answer("Пропущено")
        return

    if data.startswith("q:status:"):
        status = parts[2]
        queue_id = int(parts[3])
        conn = get_conn()
        row = conn.execute("SELECT * FROM queue_numbers WHERE id = ?", (queue_id,)).fetchone()
        if not row:
            conn.close()
            await query.answer("Не найдено", show_alert=True)
            return

        if status == "slip":
            allowed = row["status"] in ("taken", "queued", "success")
        else:
            allowed = row["status"] in ("taken", "queued")
        if not allowed:
            conn.close()
            await query.answer("Уже закрыто", show_alert=True)
            return

        now = now_ts()
        if status == "success":
            conn.execute(
                "UPDATE queue_numbers SET status = ?, completed_at = ?, stood_at = COALESCE(stood_at, ?) WHERE id = ?",
                (status, now, now, queue_id),
            )
        else:
            conn.execute(
                "UPDATE queue_numbers SET status = ?, completed_at = ? WHERE id = ?",
                (status, now, queue_id),
            )
        conn.commit()
        notify_key = {
            "success": "notify_success",
            "slip": "notify_slip",
            "error": "notify_error",
        }.get(status, "")
        notify_on = get_config_bool(conn, notify_key) if notify_key else False
        conn.close()

        status_text = {
            "success": "✅ встал",
            "slip": "❌ слетел",
            "error": "⚠ ошибка",
        }.get(status, status)
        status_line = f"{status_text} ({format_msk()})"
        phone_display = format_phone(row["phone"])

        if notify_on:
            try:
                await context.bot.send_message(
                    chat_id=row["user_id"],
                    text=f"Ваш номер {phone_display} {status_line}.",
                )
            except Exception:
                pass

        try:
            if query.message:
                keep_success = status == "slip"
                if status == "success":
                    keyboard = InlineKeyboardMarkup(
                        [
                            [InlineKeyboardButton("⚠ Слетел", callback_data=f"q:status:slip:{row['id']}")],
                            [InlineKeyboardButton("✉ Сообщение владельцу", callback_data=f"q:msg:{row['id']}")],
                        ]
                    )
                else:
                    keyboard = None
                if query.message.photo:
                    caption = query.message.caption or ""
                    await query.message.edit_caption(
                        caption=merge_status_text(caption, status_line, keep_success=keep_success),
                        reply_markup=keyboard,
                    )
                else:
                    txt = query.message.text or ""
                    await query.message.edit_text(
                        text=merge_status_text(txt, status_line, keep_success=keep_success),
                        reply_markup=keyboard,
                    )
        except Exception:
            pass
        if status == "slip" and query.message:
            try:
                thread_id = query.message.message_thread_id or 0
                conn = get_conn()
                try:
                    topic = conn.execute(
                        "SELECT 1 FROM processing_topics WHERE chat_id = ? AND thread_id = ?",
                        (query.message.chat_id, thread_id),
                    ).fetchone()
                finally:
                    conn.close()
                if topic:
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        message_thread_id=thread_id if thread_id > 0 else None,
                        text="📦 Рабочая панель\nНажмите кнопку ниже, чтобы получить номер из очереди.",
                        reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton("📩 Получить номер", callback_data="topic:next")]]
                        ),
                    )
            except Exception:
                pass
        await query.answer("Статус обновлен")
        return

        if row["status"] not in ("taken", "queued"):
            conn.close()
            await query.answer("Уже закрыто", show_alert=True)
            return
        conn.execute(
            "UPDATE queue_numbers SET status = ?, completed_at = ? WHERE id = ?",
            (status, now_ts(), queue_id),
        )
        conn.commit()
        notify_key = {
            "success": "notify_success",
            "slip": "notify_slip",
            "error": "notify_error",
        }.get(status, "")
        notify_on = get_config_bool(conn, notify_key) if notify_key else False
        conn.close()

        status_text = {
            "success": "✅ встал",
            "slip": "❌ слетел",
            "error": "⚠ ошибка",
        }.get(status, status)

        if notify_on:
            try:
                await context.bot.send_message(
                    chat_id=row["user_id"],
                    text=f"Ваш номер {row['phone']} {status_text}.",
                )
            except Exception:
                pass
        try:
            if query.message:
                if query.message.photo:
                    caption = query.message.caption or ""
                    await query.message.edit_caption(
                        caption=f"{caption}\nСтатус: {status_text}".strip(),
                        reply_markup=None,
                    )
                else:
                    txt = query.message.text or ""
                    await query.message.edit_text(
                        text=f"{txt}\nСтатус: {status_text}".strip(),
                        reply_markup=None,
                    )
        except Exception:
            pass
        await query.answer("Статус обновлен")
        return

    if data.startswith("q:repeat:"):
        queue_id = int(parts[2])
        conn = get_conn()
        row = conn.execute("SELECT photo_file_id FROM queue_numbers WHERE id = ?", (queue_id,)).fetchone()
        conn.close()
        if not row or not row["photo_file_id"]:
            await query.answer("Фото нет", show_alert=True)
            return
        try:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                message_thread_id=query.message.message_thread_id,
                photo=row["photo_file_id"],
                caption="Повтор кода",
            )
        except Exception:
            pass
        await query.answer("Отправлено")
        return

    if data.startswith("q:qr:"):
        queue_id = int(parts[2])
        conn = get_conn()
        row = conn.execute("SELECT user_id, phone FROM queue_numbers WHERE id = ?", (queue_id,)).fetchone()
        conn.execute("UPDATE queue_numbers SET qr_requested = 1 WHERE id = ?", (queue_id,))
        conn.commit()
        conn.close()
        if row:
            try:
                await context.bot.send_message(
                    chat_id=row["user_id"],
                    text=f"Отправьте QR/код для номера {row['phone']}.",
                )
            except Exception:
                pass
        await query.answer("Запрос отправлен")
        return

    if data == "topic:next" or data.startswith("office:next:"):
        if not query.message:
            await query.answer("Нет данных", show_alert=True)
            return
        conn = get_conn()
        thread_id = query.message.message_thread_id or 0
        topic = conn.execute(
            "SELECT reception_chat_id FROM processing_topics WHERE chat_id = ? AND thread_id = ?",
            (query.message.chat_id, thread_id),
        ).fetchone()
        if not topic:
            conn.close()
            await query.answer("Тема не привязана. Напишите /set", show_alert=True)
            return
        if is_lunch_time(conn):
            conn.close()
            await query.answer("Сейчас обед", show_alert=True)
            return
        issue_by_tariff = get_config_bool(conn, "issue_by_departments", False)
        if issue_by_tariff:
            tariff_rows = conn.execute(
                "SELECT tariff_id FROM tariff_topics WHERE chat_id = ? AND thread_id = ?",
                (query.message.chat_id, thread_id),
            ).fetchall()
            tariff_ids = [r["tariff_id"] for r in tariff_rows]
            if not tariff_ids:
                conn.close()
                await query.answer("Для этой темы тарифы не привязаны.", show_alert=True)
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
            await query.answer("Очередь пуста", show_alert=True)
            return
        now = now_ts()
        conn.execute(
            "UPDATE queue_numbers SET status = 'taken', assigned_at = ?, stood_at = COALESCE(stood_at, ?), worker_id = ? WHERE id = ?",
            (now, now, query.from_user.id, row["id"]),
        )
        conn.commit()
        conn.close()
        await send_number_to_worker(update, context, row)
        await query.answer("Выдано")
        return


