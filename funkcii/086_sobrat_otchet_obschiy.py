def build_report_general(conn: sqlite3.Connection, limit: Optional[int] = 50) -> str:
    text, _, _, _ = build_report_by_date(conn, "general", now_kz().date(), limit=limit)
    return text
