import socket
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import JSONResponse, Response

from .broker import Broker
from .health import readiness
from .protocol import timestamp
from .sessions import Sessions
from .settings import Settings
from .telemetry import Metrics, log_event
from .validation import valid_username


class Runtime:
    def __init__(self, settings):
        self.settings = settings
        self.replica = socket.gethostname()[:64]
        self.metrics = Metrics(self.replica)
        self.sessions = Sessions(settings, self.metrics, self.replica)
        self.broker = Broker(settings, self.metrics, self.sessions.fanout,
                             lambda: self.sessions.close_all(1011))

    def drain(self):
        self.sessions.drain()


def create_app(settings=None):
    runtime = Runtime(settings or Settings())

    @asynccontextmanager
    async def lifespan(app):
        await runtime.broker.start()
        log_event("started", release_id=runtime.settings.release_id)
        try:
            yield
        finally:
            runtime.drain()
            await runtime.broker.stop()
            log_event("stopped")

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.runtime = runtime

    @app.get("/live")
    async def live():
        return {"status": "alive", "timestamp": timestamp()}

    @app.get("/health")
    async def health():
        body, status = await readiness(runtime)
        return JSONResponse(body, status_code=status)

    @app.get("/metrics")
    async def metrics():
        runtime.sessions.update_queue_metric()
        return Response(generate_latest(runtime.metrics.registry), headers={"Content-Type": CONTENT_TYPE_LATEST})

    @app.websocket("/ws/{username}")
    async def chat(ws: WebSocket, username: str):
        async def deny(code, error):
            runtime.metrics.admission.labels(error).inc()
            await ws.send_denial_response(JSONResponse({"error": error}, status_code=code))

        if ws.headers.get("origin") not in runtime.settings.origins:
            return await deny(403, "forbidden_origin")
        if "chat.v1" not in ws.scope.get("subprotocols", []):
            return await deny(400, "unsupported_subprotocol")
        if not valid_username(username):
            return await deny(400, "invalid_username")
        if not runtime.broker.ready or not runtime.sessions.reserve():
            return await deny(503, "server_busy_or_draining")
        try:
            await ws.accept(subprotocol="chat.v1")
            runtime.metrics.admission.labels("accepted").inc()
            await runtime.sessions.run(ws, username, runtime.broker)
        finally:
            runtime.sessions.release()

    return app
