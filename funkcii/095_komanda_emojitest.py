async def cmd_emojitest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return

    # allow /emojitest <custom_emoji_id>
    emoji_id = None
    if context.args:
        emoji_id = context.args[0].strip()
    if not emoji_id:
        emoji_id = os.getenv("PREMIUM_EMOJI_TEST_ID", "").strip()
    if not emoji_id:
        # try any id from loaded map
        try:
            emoji_id = next(iter(_PREMIUM_EMOJI_MAP.values()))
        except Exception:
            emoji_id = ""

    if not emoji_id:
        await msg.reply_text("Не задан id. Используйте /emojitest <custom_emoji_id> или укажите PREMIUM_EMOJI_TEST_ID в .env")
        return

    try:
        stickers = await context.bot.get_custom_emoji_stickers([str(emoji_id)])
    except Exception as exc:
        await msg.reply_text(f"get_custom_emoji_stickers error: {exc}")
        return

    if not stickers:
        await msg.reply_text("custom_emoji_id invalid или недоступен боту.")
        return

    sticker = stickers[0]
    emoji_text = sticker.emoji or "🙂"
    # build custom emoji entity
    offset = _utf16_len("ENT ")
    length = _utf16_len(emoji_text)
    entities = [
        MessageEntity(
            type=MessageEntity.CUSTOM_EMOJI,
            offset=offset,
            length=length,
            custom_emoji_id=str(emoji_id),
        )
    ]
    try:
        sent_ent = await context.bot.send_message(
            chat_id=msg.chat_id,
            text=f"ENT {emoji_text}",
            entities=entities,
            parse_mode=None,
            disable_premium_emoji=True,
        )
    except Exception as exc:
        await msg.reply_text(f"send_message (ENT) error: {exc}")
        return

    html_text = f'HTML <tg-emoji emoji-id="{emoji_id}">{emoji_text}</tg-emoji>'
    try:
        sent_html = await context.bot.send_message(
            chat_id=msg.chat_id,
            text=html_text,
            parse_mode=ParseMode.HTML,
            disable_premium_emoji=True,
        )
    except Exception as exc:
        await msg.reply_text(f"send_message (HTML) error: {exc}")
        return

    try:
        back = [e.to_dict() for e in (sent_ent.entities or [])]
    except Exception:
        back = sent_ent.entities

    await msg.reply_text(
        f"OK. base_emoji={emoji_text} ent_entities={back} "
        f"html_entities={(sent_html.entities or [])}"
    )
