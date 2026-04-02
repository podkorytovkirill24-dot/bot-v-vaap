import asyncio
import io
import os
import threading
from typing import List, Optional


_EXTBOT_THREAD: Optional[threading.Thread] = None


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "y", "on"}


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _env_str(key: str, default: str = "") -> str:
    raw = os.getenv(key, "").strip()
    return raw if raw else default


def _parse_int_list(raw: str) -> List[int]:
    if not raw:
        return []
    out: List[int] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except Exception:
            continue
    return out


_QUEUE_BLOCK_MARKERS = (
    "очеред",   # очередь/очереди/очередь
    "принят",   # принят/приняты/принято
    "позици",   # позиция/позиции
)


def _is_queue_notice(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(marker in lower for marker in _QUEUE_BLOCK_MARKERS)


def start_external_bot_bridge() -> None:
    global _EXTBOT_THREAD
    if _EXTBOT_THREAD is not None:
        return
    if not _env_bool("EXTBOT_ENABLED", False):
        return

    api_id = _env_int("EXTBOT_API_ID", 0)
    api_hash = _env_str("EXTBOT_API_HASH")
    session = _env_str("EXTBOT_SESSION")
    target = _env_str("EXTBOT_TARGET").lstrip("@")
    target_chat_raw = _env_str("EXTBOT_TARGET_CHAT")
    target_chat = None
    if target_chat_raw:
        if target_chat_raw.lstrip("-").isdigit():
            target_chat = int(target_chat_raw)
        else:
            target_chat = target_chat_raw
    target_bot = _env_str("EXTBOT_TARGET_BOT").lstrip("@")
    group_mode = bool(target_chat)

    missing = []
    if not api_id:
        missing.append("EXTBOT_API_ID")
    if not api_hash:
        missing.append("EXTBOT_API_HASH")
    if not session:
        missing.append("EXTBOT_SESSION")
    if group_mode:
        if not target_chat:
            missing.append("EXTBOT_TARGET_CHAT")
        if not target_bot:
            missing.append("EXTBOT_TARGET_BOT")
    else:
        if not target:
            missing.append("EXTBOT_TARGET")
    if missing:
        logger.warning("External bot bridge disabled. Missing: %s", ", ".join(missing))
        return

    cfg = {
        "api_id": api_id,
        "api_hash": api_hash,
        "session": session,
        "target": target,
        "target_chat": target_chat,
        "target_bot": target_bot,
        "group_mode": group_mode,
        "send_interval": max(1, _env_int("EXTBOT_SEND_INTERVAL", 3)),
        "max_inflight": max(1, _env_int("EXTBOT_MAX_INFLIGHT", 1)),
        "auto_status": _env_bool("EXTBOT_AUTO_STATUS", True),
        "cmd_delay": max(0, _env_int("EXTBOT_CMD_DELAY", 1)),
        "worker_id": _env_int("EXTBOT_WORKER_ID", 0),
        "reception_chat_id": _env_int("EXTBOT_RECEPTION_CHAT_ID", 0) or None,
        "tariff_ids": _parse_int_list(_env_str("EXTBOT_TARIFF_IDS")),
        "dept_ids": _parse_int_list(_env_str("EXTBOT_DEPT_IDS")),
    }

    _EXTBOT_THREAD = threading.Thread(
        target=_extbot_thread_main,
        args=(cfg,),
        name="extbot-bridge",
        daemon=True,
    )
    _EXTBOT_THREAD.start()
    logger.info("External bot bridge started.")


def _extbot_thread_main(cfg: dict) -> None:
    try:
        from telethon import TelegramClient, events
        from telethon.sessions import StringSession
    except Exception as exc:
        logger.warning("Telethon is not available: %s", exc)
        return
    try:
        from telegram import Bot, InputFile
    except Exception as exc:
        logger.warning("python-telegram-bot is not available: %s", exc)
        return

    bot = Bot(BOT_TOKEN)

    def _pick_phone(text: str) -> Optional[str]:
        nums = extract_numbers(text)
        for num in nums:
            if len(num) >= 10:
                return num
        return nums[0] if nums else None

    def _normalize_text(text: str, phone: str) -> str:
        if not text:
            return f"Сообщение от офиса по номеру {format_phone(phone)}"
        if phone in text or f"+{phone}" in text:
            return text
        return f"Сообщение от офиса по номеру {format_phone(phone)}:\n{text}"

    async def _send_to_user(user_id: int, text: str, media_bytes: Optional[bytes], is_photo: bool, filename: str) -> None:
        try:
            if media_bytes:
                bio = io.BytesIO(media_bytes)
                bio.name = filename or ("photo.jpg" if is_photo else "file.bin")
                if is_photo:
                    await bot.send_photo(chat_id=user_id, photo=InputFile(bio), caption=text or None)
                else:
                    await bot.send_document(chat_id=user_id, document=InputFile(bio), caption=text or None)
            elif text:
                await bot.send_message(chat_id=user_id, text=text)
        except Exception as exc:
            logger.warning("Failed to send to user: %s", exc)

    async def _handle_message(event) -> None:
        msg = event.message
        if not msg or msg.out:
            return
        if cfg.get("group_mode") and cfg.get("target_bot_id") and event.sender_id != cfg["target_bot_id"]:
            return
        reply_id = getattr(msg, "reply_to_msg_id", None)
        conn = get_conn()
        row = None
        if reply_id:
            row = conn.execute(
                "SELECT id, user_id, phone, status FROM queue_numbers "
                "WHERE worker_chat_id = ? AND worker_msg_id = ?",
                (event.chat_id, reply_id),
            ).fetchone()
        if not row:
            text = msg.message or ""
            phone = _pick_phone(text)
            if phone:
                row = conn.execute(
                    "SELECT id, user_id, phone, status FROM queue_numbers "
                    "WHERE phone = ? ORDER BY created_at DESC LIMIT 1",
                    (phone,),
                ).fetchone()
        if not row and cfg["max_inflight"] == 1:
            row = conn.execute(
                "SELECT id, user_id, phone, status FROM queue_numbers "
                "WHERE status = 'taken' AND worker_id = ? AND worker_chat_id = ? "
                "ORDER BY assigned_at DESC LIMIT 1",
                (cfg["worker_id"], event.chat_id),
            ).fetchone()
        if not row:
            conn.close()
            return

        text = msg.message or ""
        if _is_queue_notice(text):
            conn.close()
            return
        out_text = _normalize_text(text, row["phone"])
        media_bytes = None
        is_photo = False
        filename = ""
        if msg.photo:
            is_photo = True
            media_bytes = await event.client.download_media(msg, file=bytes)
        elif msg.document:
            is_photo = False
            media_bytes = await event.client.download_media(msg, file=bytes)
            if getattr(msg.file, "name", None):
                filename = msg.file.name
            elif getattr(msg.file, "ext", None):
                filename = f"file{msg.file.ext}"
        await _send_to_user(row["user_id"], out_text, media_bytes, is_photo, filename)

        if cfg["auto_status"] and row["status"] in ("taken", "queued"):
            t = text.lower()
            status_update = None
            if "слет" in t:
                status_update = "slip"
            elif "ошиб" in t:
                status_update = "error"
            elif "встал" in t or "код" in t or "успеш" in t:
                status_update = "success"
            if status_update:
                now = now_ts()
                if status_update == "success":
                    conn.execute(
                        "UPDATE queue_numbers SET status='success', completed_at = ?, "
                        "stood_at = COALESCE(stood_at, assigned_at, ?) WHERE id = ?",
                        (now, now, row["id"]),
                    )
                else:
                    conn.execute(
                        "UPDATE queue_numbers SET status = ?, completed_at = ? WHERE id = ?",
                        (status_update, now, row["id"]),
                    )
        conn.commit()
        conn.close()

    async def _send_loop(client: TelegramClient, target) -> None:
        while True:
            try:
                await _send_next_number(client, target, cfg)
            except Exception as exc:
                logger.warning("External bot send loop error: %s", exc)
            await asyncio.sleep(cfg["send_interval"])

    async def _extbot_main() -> None:
        client = TelegramClient(StringSession(cfg["session"]), cfg["api_id"], cfg["api_hash"])
        try:
            await client.start()
        except Exception as exc:
            logger.warning("External bot login failed: %s", exc)
            return

        try:
            if cfg.get("group_mode"):
                target = await client.get_entity(cfg["target_chat"])
                bot_user = await client.get_entity(cfg["target_bot"])
                cfg["target_bot_id"] = bot_user.id
            else:
                target = await client.get_entity(cfg["target"])
        except Exception as exc:
            logger.warning("External bot target not found: %s", exc)
            await client.disconnect()
            return

        if cfg.get("group_mode"):
            client.add_event_handler(_handle_message, events.NewMessage(chats=target))
        else:
            client.add_event_handler(_handle_message, events.NewMessage(from_users=target))
        asyncio.create_task(_send_loop(client, target))
        await client.run_until_disconnected()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_extbot_main())


async def _send_next_number(client, target, cfg: dict) -> None:
    conn = get_conn()
    inflight = conn.execute(
        "SELECT COUNT(*) AS cnt FROM queue_numbers WHERE status='taken' AND worker_id = ?",
        (cfg["worker_id"],),
    ).fetchone()["cnt"]
    if inflight >= cfg["max_inflight"]:
        conn.close()
        return

    row = fetch_next_queue(
        conn,
        cfg["dept_ids"],
        cfg["reception_chat_id"],
        cfg["tariff_ids"] or None,
    )
    if not row:
        conn.close()
        return

    now = now_ts()
    cur = conn.execute(
        "UPDATE queue_numbers SET status='taken', assigned_at = ?, stood_at = COALESCE(stood_at, ?), "
        "worker_id = ?, worker_chat_id = NULL, worker_msg_id = NULL "
        "WHERE id = ? AND status = 'queued'",
        (now, now, cfg["worker_id"], row["id"]),
    )
    if cur.rowcount == 0:
        conn.close()
        return
    conn.commit()
    pre_cmd = get_config(conn, "extbot_pre_cmd", "").strip()
    conn.close()

    try:
        if pre_cmd:
            await client.send_message(target, pre_cmd)
            if cfg["cmd_delay"] > 0:
                await asyncio.sleep(cfg["cmd_delay"])
        msg = await client.send_message(target, row["phone"])
    except Exception as exc:
        logger.warning("External bot send failed: %s", exc)
        conn = get_conn()
        conn.execute(
            "UPDATE queue_numbers SET status='queued', assigned_at = NULL, worker_id = NULL, worker_chat_id = NULL, worker_msg_id = NULL "
            "WHERE id = ?",
            (row["id"],),
        )
        conn.commit()
        conn.close()
        return

    conn = get_conn()
    conn.execute(
        "UPDATE queue_numbers SET worker_chat_id = ?, worker_msg_id = ? WHERE id = ?",
        (msg.chat_id, msg.id, row["id"]),
    )
    conn.commit()
    conn.close()
