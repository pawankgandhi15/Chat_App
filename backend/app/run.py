"""Canonical entrypoint: configures real transport limits and early signal draining."""
import logging
import sys

import uvicorn

from .main import create_app


class TransportLogFilter(logging.Filter):
    def filter(self, record):
        # Uvicorn's WS handshake logs bypass access_log=False and include names/IPs.
        if "WebSocket" in str(record.msg):
            return False
        if record.exc_info:
            record.msg = "transport_error: " + record.exc_info[0].__name__
            record.args = ()
            record.exc_info = None
            record.exc_text = None
        return True


class DrainingServer(uvicorn.Server):
    def handle_exit(self, sig, frame):
        self.config.app.state.runtime.drain()
        super().handle_exit(sig, frame)


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        app = create_app()
    except Exception:
        # Pydantic errors may embed input values; never print resolved credentials.
        print("Invalid application settings; check the configuration contract.", file=sys.stderr)
        raise SystemExit(1) from None
    config = uvicorn.Config(
        app, host="0.0.0.0", port=8000, workers=1,
        ws="websockets", ws_max_size=16384, ws_max_queue=4,
        ws_per_message_deflate=False, ws_ping_interval=20, ws_ping_timeout=20,
        timeout_graceful_shutdown=app.state.runtime.settings.shutdown_drain_seconds,
        access_log=False, proxy_headers=False,
    )
    logging.getLogger("uvicorn.error").addFilter(TransportLogFilter())
    DrainingServer(config).run()


if __name__ == "__main__":
    main()
