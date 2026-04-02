import asyncio
from pathlib import Path
from typing import Optional

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession


def _pick_mode() -> str:
    print("Выбери вход:")
    print("1 - по коду (номер телефона)")
    print("2 - по QR")
    while True:
        choice = input("> ").strip()
        if choice in ("1", "2"):
            return choice
        print("Нужно выбрать 1 или 2.")


def _try_render_qr(url: str) -> Optional[Path]:
    try:
        import qrcode  # type: ignore
    except Exception:
        return None

    try:
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        try:
            qr.print_ascii(invert=True)
        except Exception:
            pass
        img = qr.make_image(fill_color="black", back_color="white")
        path = Path("userbot_qr.png")
        img.save(path)
        return path.resolve()
    except Exception:
        return None


async def _login_by_code(client: TelegramClient) -> None:
    phone = input("Номер телефона (в формате +7...): ").strip()
    await client.send_code_request(phone)
    code = input("Код из Telegram: ").strip().replace(" ", "")
    try:
        await client.sign_in(phone=phone, code=code)
    except SessionPasswordNeededError:
        password = input("Пароль 2FA: ").strip()
        await client.sign_in(password=password)


async def _login_by_qr(client: TelegramClient) -> None:
    qr_login = await client.qr_login()
    print("\nСканируй QR в Telegram (Настройки -> Устройства -> Войти по QR).")
    url = qr_login.url
    qr_path = _try_render_qr(url)
    if qr_path:
        print(f"QR сохранен в: {qr_path}")
    else:
        print("QR библиотека не установлена.")
        print("Ссылка для входа:")
        print(url)
    try:
        await qr_login.wait()
    except SessionPasswordNeededError:
        password = input("Пароль 2FA: ").strip()
        await client.sign_in(password=password)


async def _run() -> None:
    api_id = int(input("API ID: ").strip())
    api_hash = input("API HASH: ").strip()

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    try:
        mode = _pick_mode()
        if mode == "1":
            await _login_by_code(client)
        else:
            await _login_by_qr(client)

        session = client.session.save()
        print("\nEXTBOT_SESSION=" + session)
    finally:
        await client.disconnect()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
