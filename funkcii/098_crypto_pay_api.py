from typing import Any, Dict, Optional
import os
import json
import time
import uuid
import sqlite3
from urllib.request import Request, urlopen
from urllib.error import HTTPError


CRYPTO_PAY_DEFAULT_ASSET = "USDT"


def crypto_pay_base_url() -> str:
    base = os.getenv("CRYPTO_PAY_BASE_URL", "").strip().rstrip("/")
    return base or "https://pay.crypt.bot"


def get_crypto_pay_token(conn: sqlite3.Connection) -> str:
    token = get_config(conn, "crypto_pay_token", "").strip()
    if not token:
        token = os.getenv("CRYPTO_PAY_TOKEN", "").strip()
    return token


def get_crypto_pay_asset(conn: sqlite3.Connection) -> str:
    asset = get_config(conn, "crypto_pay_asset", "").strip().upper()
    if not asset:
        asset = os.getenv("CRYPTO_PAY_ASSET", "").strip().upper()
    return asset or CRYPTO_PAY_DEFAULT_ASSET


def _crypto_pay_request(method: str, token: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not token:
        return {"ok": False, "error": "TOKEN_NOT_SET"}
    url = f"{crypto_pay_base_url()}/api/{method}"
    headers = {"Crypto-Pay-API-Token": token, "User-Agent": "CryptoPayBot/1.0"}
    data = None
    req_method = "GET"
    if params is not None:
        body = json.dumps(params, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
        data = body
        req_method = "POST"
    req = Request(url, data=data, headers=headers, method=req_method)
    try:
        with urlopen(req, timeout=10) as resp:
            payload = resp.read().decode("utf-8")
        return json.loads(payload)
    except HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
            data = json.loads(body) if body else {}
            if isinstance(data, dict):
                if "ok" in data:
                    return data
                return {"ok": False, "error": data.get("error") or f"HTTP {exc.code}: {exc.reason}"}
        except Exception:
            pass
        return {"ok": False, "error": f"HTTP {exc.code}: {exc.reason}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def crypto_pay_get_balance(token: str) -> Dict[str, Any]:
    return _crypto_pay_request("getBalance", token)


def crypto_pay_create_invoice(token: str, amount: float, asset: str, description: str = "") -> Dict[str, Any]:
    params = {"asset": asset, "amount": f"{amount:.2f}"}
    if description:
        params["description"] = description
    return _crypto_pay_request("createInvoice", token, params)


def crypto_pay_transfer(
    token: str,
    user_id: int,
    amount: float,
    asset: str,
    spend_id: str,
    comment: str = "",
) -> Dict[str, Any]:
    params = {"user_id": int(user_id), "asset": asset, "amount": f"{amount:.2f}", "spend_id": spend_id}
    if comment:
        params["comment"] = comment
    return _crypto_pay_request("transfer", token, params)


def crypto_pay_get_transfers(token: str, asset: str = "", count: int = 20) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    if asset:
        params["asset"] = asset
    if count:
        params["count"] = int(count)
    return _crypto_pay_request("getTransfers", token, params)


def crypto_pay_pick_balance(result: Any, asset: str) -> float:
    try:
        for row in result or []:
            if str(row.get("currency_code", "")).upper() == asset.upper():
                return float(row.get("available", 0) or 0)
    except Exception:
        pass
    return 0.0


def crypto_pay_invoice_url(invoice: Dict[str, Any]) -> str:
    if not invoice:
        return ""
    return (
        invoice.get("bot_invoice_url")
        or invoice.get("web_app_invoice_url")
        or invoice.get("mini_app_invoice_url")
        or invoice.get("pay_url")
        or ""
    )


def crypto_pay_make_spend_id(prefix: str = "payout") -> str:
    token = f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:10]}"
    return token[:64]
