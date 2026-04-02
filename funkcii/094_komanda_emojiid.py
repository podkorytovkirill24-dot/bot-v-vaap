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


async def cmd_emojiid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return

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
        env_key = _emoji_to_env_key(emoji_text) if emoji_text else "PREMIUM_EMOJI_UXXXX"
        items.append(f"{emoji_text} -> {emoji_id} -> {env_key}")

    if not items:
        await msg.reply_text(
            "Не вижу custom emoji.\n"
            "Отправьте премиум‑эмоджи и ответьте на него командой /emojiid."
        )
        return

    await msg.reply_text("custom_emoji_id:\n" + "\n".join(items))
