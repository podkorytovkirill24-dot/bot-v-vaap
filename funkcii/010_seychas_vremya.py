def now_ts() -> int:
    return int(time.time())


# Kazakhstan time (default UTC+5)
KZ_TZ = timezone(timedelta(hours=5))


def now_kz() -> datetime:
    return datetime.now(KZ_TZ)
