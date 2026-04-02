def build_report_not_stood(conn: sqlite3.Connection, limit: Optional[int] = 50) -> str:
    text, _, _, _ = build_report_by_date(conn, "notstood", now_kz().date(), limit=limit)
    return text


def build_report_detailed(conn: sqlite3.Connection) -> str:
    return build_report_not_stood(conn)
