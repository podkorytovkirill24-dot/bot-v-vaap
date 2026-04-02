def format_msk(ts: Optional[int] = None) -> str:
    if not ts:
        ts = now_ts()
    dt = datetime.fromtimestamp(ts, KZ_TZ)
    return f"{dt.strftime('%d.%m %H:%M')} KZ"
