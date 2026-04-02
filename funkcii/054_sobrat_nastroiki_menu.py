def build_settings_menu(conn: sqlite3.Connection) -> InlineKeyboardMarkup:
    stop = "⛔ Stop-Work" + (" ✅" if get_config_bool(conn, "stop_work") else " ❌")
    repeat = "🔁 Повтор кода" + (" ✅" if get_config_bool(conn, "repeat_code") else " ❌")
    qr = "📱 Запрос QR (WA)" + (" ✅" if get_config_bool(conn, "qr_request") else " ❌")
    repeat_submit = "🔁 Повторная сдача" + (" ✅" if get_config_bool(conn, "allow_repeat") else " ❌")
    detail_archive = "📊 Детальные отчёты в архив" + (" ✅" if get_config_bool(conn, "detail_archive") else " ❌")
    issue_map = "🗂 Привязки /set к тарифам" + (" ✅" if get_config_bool(conn, "issue_by_departments") else " ❌")
    lunch = "🍽 Расписание обедов" + (" ✅" if get_config_bool(conn, "lunch_info_on") else " ❌")
    input_type = "🧩 Тип вбива: приоритеты" if get_config_bool(conn, "use_priorities", True) else "🧩 Тип вбива: FIFO"
    referral = "👥 Рефералка" + (" ✅" if get_config_bool(conn, "referral_enabled", True) else " ❌")
    extbot_cmd = "🧾 Команда перед номером" + (" ✅" if get_config(conn, "extbot_pre_cmd", "").strip() else " ❌")
    extbot_forward = "📤 Только из бот2" + (" ✅" if get_config_bool(conn, "extbot_forward_only") else " ❌")
    iam_minutes = get_config_int(conn, "i_am_here_minutes", 10)
    iam_on = get_config_bool(conn, "i_am_here_on")
    iam_label = f"👋 Я тут ({iam_minutes}м)" + (" ✅" if iam_on else " ❌")
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(input_type, callback_data="adm:input_type"),
                InlineKeyboardButton(stop, callback_data="adm:toggle:stop_work"),
            ],
            [
                InlineKeyboardButton("💲 Тарифы", callback_data="adm:tariffs"),
                InlineKeyboardButton("⚡ Приоритеты", callback_data="adm:priorities"),
            ],
            [
                InlineKeyboardButton(repeat, callback_data="adm:toggle:repeat_code"),
                InlineKeyboardButton(qr, callback_data="adm:toggle:qr_request"),
            ],
            [
                InlineKeyboardButton(repeat_submit, callback_data="adm:toggle:allow_repeat"),
                InlineKeyboardButton(detail_archive, callback_data="adm:toggle:detail_archive"),
            ],
            [InlineKeyboardButton(iam_label, callback_data="adm:i_am_here")],
            [
                InlineKeyboardButton("🔢 Лимит сдачи", callback_data="adm:limit"),
                InlineKeyboardButton(lunch, callback_data="adm:lunch"),
            ],
            [
                InlineKeyboardButton("📥 Приемки", callback_data="adm:departments"),
                InlineKeyboardButton("🏢 Офисы", callback_data="adm:offices"),
            ],
            [InlineKeyboardButton(issue_map, callback_data="adm:issue_map")],
            [
                InlineKeyboardButton(referral, callback_data="adm:referral"),
                InlineKeyboardButton("✏ Саппорт", callback_data="adm:support"),
            ],
            [
                InlineKeyboardButton(extbot_cmd, callback_data="adm:extbot:cmd"),
                InlineKeyboardButton(extbot_forward, callback_data="adm:toggle:extbot_forward_only"),
            ],
            [InlineKeyboardButton("🔔 Уведомления", callback_data="adm:notifications")],
            [InlineKeyboardButton("⬇ Слёт всем", callback_data="adm:slip_all")],
            [InlineKeyboardButton("⬅ Назад", callback_data="adm:panel")],
        ]
    )
