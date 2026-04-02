def _emoji_to_env_key(emoji_text: str) -> str:
    parts = [f"U{ord(ch):04X}" for ch in emoji_text]
    return "PREMIUM_EMOJI_" + "_".join(parts)


def _slice_utf16(text: str, offset: int, length: int) -> str:
    if not text or length <= 0:
        return ""
    data = text.encode("utf-16-le")
    start = max(0, offset) * 2
    end = max(0, offset + length) * 2
    try:
        return data[start:end].decode("utf-16-le")
    except Exception:
        return ""


def _env_path() -> Path:
    return Path(__file__).resolve().parent.parent / ".env"


def _set_env_value(key: str, value: str) -> None:
    path = _env_path()
    lines = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    pattern = f"{key}="
    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith(pattern):
            lines[i] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[key] = value


async def cmd_emojiset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return
    conn = get_conn()
    if not is_admin(conn, update.effective_user.id):
        conn.close()
        await msg.reply_text(ui("no_access"))
        return
    conn.close()

    target = msg.reply_to_message or msg
    text = target.text or target.caption or ""
    entities = list(target.entities or [])
    entities.extend(target.caption_entities or [])

    items = []
    for ent in entities:
        if getattr(ent, "type", "") != "custom_emoji":
            continue
        emoji_id = getattr(ent, "custom_emoji_id", None)
        if not emoji_id:
            continue
        start = ent.offset or 0
        length = ent.length or 0
        emoji_text = _slice_utf16(text, start, length) if length else ""
        if not emoji_text:
            continue
        env_key = _emoji_to_env_key(emoji_text)
        _set_env_value(env_key, str(emoji_id))
        items.append(f"{emoji_text} -> {emoji_id} -> {env_key}")

    if not items:
        await msg.reply_text(
            "Не вижу premium emoji.\n"
            "Отправьте премиум-эмоджи и ответьте на него командой /emojiset."
        )
        return

    count = reload_premium_emojis()
    await msg.reply_text("Готово. Обновлено:\n" + "\n".join(items) + f"\n\nВ мапе: {count}")


async def cmd_emojireload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return
    conn = get_conn()
    if not is_admin(conn, update.effective_user.id):
        conn.close()
        await msg.reply_text(ui("no_access"))
        return
    conn.close()
    count = reload_premium_emojis()
    await msg.reply_text(f"Премиум-эмоджи перечитаны. В мапе: {count}")
