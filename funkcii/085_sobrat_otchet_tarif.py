def _report_rows(
    conn: sqlite3.Connection,
    statuses: List[str],
    limit: Optional[int] = 50,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
) -> List[sqlite3.Row]:
    if not statuses:
        return []
    placeholders = ",".join("?" * len(statuses))
    params: List = list(statuses)
    time_filter = ""
    if start_ts is not None and end_ts is not None:
        time_filter = " AND q.completed_at BETWEEN ? AND ?"
        params.extend([int(start_ts), int(end_ts)])
    if limit is None or int(limit) <= 0:
        return conn.execute(
            f"SELECT q.phone, q.user_id, q.username, q.status, q.assigned_at, q.stood_at, q.completed_at, "
            f"t.duration_min, t.name AS tariff "
            f"FROM queue_numbers q LEFT JOIN tariffs t ON q.tariff_id = t.id "
            f"WHERE q.status IN ({placeholders}) {time_filter} "
            f"ORDER BY q.completed_at DESC",
            tuple(params),
        ).fetchall()
    return conn.execute(
        f"SELECT q.phone, q.user_id, q.username, q.status, q.assigned_at, q.stood_at, q.completed_at, "
        f"t.duration_min, t.name AS tariff "
        f"FROM queue_numbers q LEFT JOIN tariffs t ON q.tariff_id = t.id "
        f"WHERE q.status IN ({placeholders}) {time_filter} "
        f"ORDER BY q.completed_at DESC LIMIT ?",
        tuple(params + [int(limit)]),
    ).fetchall()


def _duration_info(
    row: sqlite3.Row,
    now_ts_value: Optional[int] = None,
    end_ts: Optional[int] = None,
) -> Tuple[Optional[int], Optional[int], str, bool, Optional[int], Optional[int]]:
    start_ts = row["stood_at"] or row["assigned_at"] or (row["completed_at"] if row["status"] == "success" else None)
    tariff_min = int(row["duration_min"] or 0)
    if not start_ts:
        eligible = tariff_min <= 0
        mark = "✅" if eligible else "❌"
        return None, tariff_min if tariff_min > 0 else None, mark, eligible, None, None
    now_value = now_ts_value if now_ts_value is not None else now_ts()
    if row["status"] == "success":
        end_value = row["completed_at"] or now_value
        if end_ts:
            end_value = min(end_value, end_ts)
    else:
        end_value = row["completed_at"] or start_ts
    duration_sec = int(end_value) - int(start_ts)
    if duration_sec < 0:
        duration_sec = 0
    tariff_min = int(row["duration_min"] or 0)
    eligible = tariff_min <= 0 or duration_sec >= tariff_min * 60
    mark = "✅" if eligible else "❌"
    duration_min = duration_sec // 60
    return duration_min, tariff_min if tariff_min > 0 else None, mark, eligible, int(start_ts), int(end_value)


def _time_label(ts: Optional[int]) -> str:
    return format_ts(ts) if ts else "-"


def _format_report_entry(
    row: sqlite3.Row,
    duration_min: Optional[int],
    tariff_min: Optional[int],
    mark: str,
    start_ts: Optional[int],
    end_ts: Optional[int],
) -> List[str]:
    user = format_user_label(row["user_id"], row["username"])
    tariff_name = row["tariff"] or "-"
    tariff_label = f"{tariff_name} ({tariff_min}м)" if tariff_min else tariff_name
    start_label = format_ts(start_ts) if start_ts else "-"
    slip_label = "-"
    if row["status"] == "slip":
        slip_label = format_ts(row["completed_at"]) if row["completed_at"] else "-"
    if row["status"] == "error":
        slip_label = "ошибка"
    duration_label = f"{duration_min} мин" if duration_min is not None else "-"
    lines = [
        f"{mark} {row['phone']}",
        f"Пользователь: {user}",
        f"Тариф: {tariff_label}",
        f"Встал: {start_label}",
        f"Слетел: {slip_label}",
        f"Отстоял: {duration_label}",
        "",
    ]
    return lines


def build_report_by_date(
    conn: sqlite3.Connection,
    report_type: str,
    target_date: datetime.date,
    limit: Optional[int] = 50,
) -> Tuple[str, List[sqlite3.Row], int, int]:
    start_dt = datetime(target_date.year, target_date.month, target_date.day, tzinfo=KZ_TZ)
    end_dt = start_dt + timedelta(days=1)
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())
    rows = _report_rows(conn, ["success", "slip", "error"], limit=None, start_ts=start_ts, end_ts=end_ts)
    now_value = now_ts()
    filtered: List[sqlite3.Row] = []
    entry_lines: List[str] = []
    for r in rows:
        duration_min, tariff_min, mark, eligible, start_ts_row, end_ts_row = _duration_info(
            r, now_ts_value=now_value, end_ts=end_ts
        )
        if report_type == "stood" and not eligible:
            continue
        if report_type == "notstood" and eligible:
            continue
        filtered.append(r)
        if limit is not None and int(limit) > 0 and len(filtered) <= int(limit):
            entry_lines.extend(
                _format_report_entry(r, duration_min, tariff_min, mark, start_ts_row, end_ts_row)
            )
    date_label = target_date.strftime("%d.%m.%Y")
    title = {
        "stood": "✅ Отстоявшие номера",
        "notstood": "❌ Не отстоявшие номера",
        "general": "📋 Общий отчет",
    }.get(report_type, "📋 Отчет")
    lines = [
        title,
        f"Дата: {date_label}",
        f"Всего: {len(filtered)}",
        "",
    ]
    if not filtered:
        lines.append("Нет данных.")
    else:
        lines.extend(entry_lines)
    return "\n".join(lines), filtered, start_ts, end_ts


def build_report_csv(rows: List[sqlite3.Row], end_ts: Optional[int] = None) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "phone",
            "user_id",
            "username",
            "status",
            "assigned_at",
            "stood_at",
            "completed_at",
            "stood_min",
            "tariff",
            "tariff_min",
        ]
    )
    for r in rows:
        assigned_at = r["assigned_at"]
        stood_at = r["stood_at"] or r["assigned_at"] or (r["completed_at"] if r["status"] == "success" else None)
        completed_at = r["completed_at"]
        stood_min = ""
        if stood_at:
            now_value = now_ts()
            if r["status"] == "success":
                end_value = completed_at or now_value
                if end_ts:
                    end_value = min(end_value, end_ts)
            else:
                end_value = completed_at or stood_at
            stood_min = int(max(0, (int(end_value) - int(stood_at)) // 60))
        writer.writerow(
            [
                r["phone"],
                r["user_id"],
                r["username"] or "",
                r["status"],
                format_ts(assigned_at),
                format_ts(stood_at),
                format_ts(completed_at),
                stood_min,
                r["tariff"] or "",
                int(r["duration_min"] or 0),
            ]
        )
    return output.getvalue()


def build_report_stood(conn: sqlite3.Connection, limit: Optional[int] = 50) -> str:
    text, _, _, _ = build_report_by_date(conn, "stood", now_kz().date(), limit=limit)
    return text


def build_report_tariff(conn: sqlite3.Connection) -> str:
    return build_report_stood(conn)
