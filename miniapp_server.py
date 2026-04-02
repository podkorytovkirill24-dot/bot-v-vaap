import os
import sys
import socket
from http.server import ThreadingHTTPServer


def _ensure_env_defaults() -> None:
    if os.getenv("MINI_APP_HOST", "").strip() == "":
        ip_env = os.getenv("IP", "").strip()
        os.environ["MINI_APP_HOST"] = ip_env if ip_env else "0.0.0.0"
    if os.getenv("MINI_APP_PORT", "").strip() == "" and os.getenv("PORT", "").strip():
        os.environ["MINI_APP_PORT"] = os.getenv("PORT", "").strip()


def main() -> int:
    _ensure_env_defaults()
    import main as app  # noqa: E402

    if app.MINI_APP_PORT <= 0:
        app.logger.error("MINI_APP_PORT is not set or <= 0")
        return 1

    app.init_db()

    server_cls = ThreadingHTTPServer
    if ":" in app.MINI_APP_HOST:
        class _IPv6HTTPServer(ThreadingHTTPServer):
            address_family = socket.AF_INET6
        server_cls = _IPv6HTTPServer
    server = server_cls((app.MINI_APP_HOST, app.MINI_APP_PORT), app.MiniAppHandler)
    app.logger.info("MiniApp HTTP listening on http://%s:%s", app.MINI_APP_HOST, app.MINI_APP_PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
