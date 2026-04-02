async def job_tick(context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = get_conn()
    now = now_ts()
    if get_config_bool(conn, "auto_success_on"):
        minutes = get_config_int(conn, "auto_success_minutes", 5)
        if minutes > 0:
            rows = conn.execute(
                "SELECT id, user_id, phone FROM queue_numbers "
                "WHERE status='taken' AND assigned_at <= ?",
                (now - minutes * 60,),
            ).fetchall()
            for r in rows:
                conn.execute(
                    "UPDATE queue_numbers SET status='success', completed_at = ?, stood_at = COALESCE(stood_at, ?) WHERE id = ?",
                    (now, now, r["id"]),
                )
                if get_config_bool(conn, "notify_success"):
                    try:
                        await context.bot.send_message(
                            chat_id=r["user_id"],
                            text=f"✅ Ваш номер {r['phone']} встал.",
                        )
                    except Exception:
                        pass
    if get_config_bool(conn, "auto_slip_on"):
        minutes = get_config_int(conn, "auto_slip_minutes", 15)
        if minutes > 0:
            rows = conn.execute(
                "SELECT id, user_id, phone FROM queue_numbers "
                "WHERE status='taken' AND assigned_at <= ?",
                (now - minutes * 60,),
            ).fetchall()
            for r in rows:
                conn.execute(
                    "UPDATE queue_numbers SET status='slip', completed_at = ? WHERE id = ?",
                    (now, r["id"]),
                )
                if get_config_bool(conn, "notify_slip"):
                    try:
                        await context.bot.send_message(
                            chat_id=r["user_id"],
                            text=f"❌ Ваш номер {r['phone']} слетел.",
                        )
                    except Exception:
                        pass
    if get_config_bool(conn, "i_am_here_on"):
        minutes = get_config_int(conn, "i_am_here_minutes", 10)
        warn_before = 5
        if minutes > 0:
            users = conn.execute(
                "SELECT u.user_id, u.iam_here_at, u.iam_here_warned_at, MIN(q.created_at) AS first_created "
                "FROM queue_numbers q JOIN users u ON u.user_id = q.user_id "
                "WHERE q.status = 'queued' "
                "GROUP BY u.user_id"
            ).fetchall()
            for u in users:
                last = u["iam_here_at"] or u["first_created"] or now
                elapsed = now - int(last)
                remain = minutes * 60 - elapsed
                if remain <= 0:
                    conn.execute(
                        "UPDATE queue_numbers SET status='canceled', completed_at = ? "
                        "WHERE user_id = ? AND status = 'queued'",
                        (now, u["user_id"]),
                    )
                    conn.execute(
                        "UPDATE users SET iam_here_warned_at = 0 WHERE user_id = ?",
                        (u["user_id"],),
                    )
                    try:
                        await context.bot.send_message(
                            chat_id=u["user_id"],
                            text="❌ Ваши номера удалены из очереди: не нажали «Я тут» вовремя.",
                        )
                    except Exception:
                        pass
                elif remain <= warn_before * 60:
                    warned_at = u["iam_here_warned_at"] or 0
                    if warned_at < int(last):
                        conn.execute(
                            "UPDATE users SET iam_here_warned_at = ? WHERE user_id = ?",
                            (now, u["user_id"]),
                        )
                        try:
                            await context.bot.send_message(
                                chat_id=u["user_id"],
                                text="⏳ Осталось 5 минут. Нажмите «Я тут», иначе номера будут удалены из очереди.",
                            )
                        except Exception:
                            pass
    conn.commit()
    conn.close()
