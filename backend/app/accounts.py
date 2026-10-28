"""Cookie-authenticated saved chat API and lightweight WebSocket invalidations."""
import asyncio
from functools import partial
from uuid import UUID

import anyio
from fastapi import HTTPException, Request, WebSocket, Query
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect

from .protocol import SavedNotification
from .storage import Storage
from .validation import normalize_text, InputError

COOKIE = "baatchit_session"


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(pattern=r"^[A-Za-z0-9_-]{3,32}$")
    password: str = Field(min_length=15, max_length=128)

    @field_validator("password")
    @classmethod
    def valid_password(cls, value):
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeError:
            raise ValueError("Invalid password encoding") from None
        return value


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: UUID
    text: str = Field(min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def valid_text(cls, value):
        try:
            value = normalize_text(value)
        except InputError:
            raise ValueError("Invalid message") from None
        if not value:
            raise ValueError("Message is empty")
        return value


class Accounts:
    def __init__(self, runtime):
        self.runtime = runtime
        url = runtime.settings.resolve_database_url()
        self.storage = Storage(url, runtime.settings.session_days) if url else None
        self.workers = anyio.CapacityLimiter(4)
        self.listeners = {}  # user ID -> set of coalescing queues

    async def call(self, method, *args):
        if not self.storage:
            raise HTTPException(503, "Saved chats are unavailable. Start the backend with a configured database.")
        return await anyio.to_thread.run_sync(partial(getattr(self.storage, method), *args), limiter=self.workers)

    def notify(self, user_ids):
        for user_id in user_ids:
            for queue in self.listeners.get(user_id, ()):
                if queue.empty():
                    queue.put_nowait(True)

    async def announce(self, user_ids):
        self.notify(user_ids)
        try:
            await self.runtime.broker.publish(SavedNotification(users=user_ids).model_dump_json())
        except Exception:
            # The transaction already committed. Periodic refresh repairs missed hints.
            pass


def install_accounts(app, runtime):
    accounts = runtime.accounts

    @app.middleware("http")
    async def account_boundary(request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("origin") not in runtime.settings.origins:
                return JSONResponse({"detail": "Untrusted request origin."}, status_code=403)
            length = request.headers.get("content-length", "")
            if not length.isdigit() or int(length) > 16384:
                return JSONResponse({"detail": "Request body is too large or has no length."}, status_code=413)
        expected = request.headers.get("x-account-id")
        if expected:
            try:
                user = await accounts.call("me", request.cookies.get(COOKIE))
                if user["id"] != expected:
                    return JSONResponse({"detail": "The signed-in account changed in another tab. Sign in again."}, status_code=401, headers={"Cache-Control": "no-store"})
            except HTTPException as exc:
                return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers={"Cache-Control": "no-store"})
            except SQLAlchemyError:
                return JSONResponse({"detail": "Saved chats are temporarily unavailable."}, status_code=503, headers={"Cache-Control": "no-store"})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse({"detail": "Saved chats are temporarily unavailable. Please retry."}, status_code=503)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        # Never reflect a rejected password or message in a validation response.
        return JSONResponse({"detail": "Invalid input. Check the required fields and limits."}, status_code=422)

    async def authentication(request, data, action):
        # Account and address limits live in PostgreSQL, shared by all replicas.
        address = request.client.host if request.client else "unknown"
        await accounts.call("throttle", "auth-ip:" + address, 100, 900)
        await accounts.call("throttle", "auth-name:" + data.username.lower(), 20, 900)
        user, token = await accounts.call(action, data.username, data.password)
        previous = request.cookies.get(COOKIE)
        if previous:
            await accounts.call("logout", previous)
        response = JSONResponse({"user": user})
        response.set_cookie(COOKIE, token, httponly=True, secure=runtime.settings.app_env == "public",
            samesite="strict", path="/", max_age=runtime.settings.session_days * 86400)
        return response

    @app.post("/api/auth/register", status_code=201)
    async def register(request: Request, data: Credentials):
        response = await authentication(request, data, "register")
        response.status_code = 201
        return response

    @app.post("/api/auth/login")
    async def login(request: Request, data: Credentials):
        return await authentication(request, data, "login")

    @app.get("/api/auth/me")
    async def me(request: Request):
        return {"user": await accounts.call("me", request.cookies.get(COOKIE))}

    @app.post("/api/auth/logout")
    async def logout(request: Request):
        await accounts.call("logout", request.cookies.get(COOKIE))
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE, path="/", secure=runtime.settings.app_env == "public", httponly=True, samesite="strict")
        return response

    @app.get("/api/users")
    async def search(request: Request, q: str = Query(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")):
        return {"items": await accounts.call("search", request.cookies.get(COOKIE), q)}

    @app.get("/api/conversations")
    async def list_conversations(request: Request, after: UUID | None = None):
        return await accounts.call("list_conversations", request.cookies.get(COOKIE), str(after) if after else None)

    @app.post("/api/conversations")
    async def open_conversation(request: Request, data: Target):
        token = request.cookies.get(COOKIE)
        user = await accounts.call("me", token)
        await accounts.call("throttle", "open:" + user["id"], 30, 60)
        conversation = await accounts.call("open_conversation", token, str(data.user_id))
        await accounts.announce([conversation["user_a"], conversation["user_b"]])
        return {"id": conversation["id"]}

    @app.get("/api/conversations/{conversation_id}/messages")
    async def history(request: Request, conversation_id: UUID, before: int | None = Query(default=None, ge=1)):
        return await accounts.call("history", request.cookies.get(COOKIE), str(conversation_id), before)

    @app.post("/api/conversations/{conversation_id}/messages")
    async def send(request: Request, conversation_id: UUID, data: Message):
        token = request.cookies.get(COOKIE)
        user = await accounts.call("me", token)
        await accounts.call("throttle", "send:" + user["id"], 120, 60)
        message, members = await accounts.call("send", token, str(conversation_id), str(data.client_id), data.text)
        await accounts.announce(members)
        return {"message": message, "status": "saved"}

    @app.websocket("/ws/accounts/live")
    async def live(ws: WebSocket):
        if ws.headers.get("origin") not in runtime.settings.origins:
            return await ws.close(code=1008)
        if "chat.accounts.v1" not in ws.scope.get("subprotocols", []):
            return await ws.close(code=1008)
        token = ws.cookies.get(COOKIE)
        try:
            user = await accounts.call("me", token)
        except (HTTPException, SQLAlchemyError):
            return await ws.close(code=1008)
        if ws.query_params.get("account_id", user["id"]) != user["id"]:
            return await ws.close(code=1008)
        if not runtime.sessions.reserve():
            return await ws.close(code=1013)
        queue = asyncio.Queue(maxsize=1)
        listeners = accounts.listeners.setdefault(user["id"], set())
        listeners.add(queue)
        reader = None
        try:
            await ws.accept(subprotocol="chat.accounts.v1")
            async def read():
                while True:
                    packet = await ws.receive()
                    if packet["type"] == "websocket.disconnect":
                        return
                    # This socket is server-to-client only.
                    await ws.close(code=1008)
                    return
            reader = asyncio.create_task(read())
            await ws.send_json({"type": "sync"})
            while not reader.done() and not runtime.sessions.draining:
                waiter = asyncio.create_task(queue.get())
                try:
                    done, _ = await asyncio.wait([reader, waiter], timeout=20, return_when=asyncio.FIRST_COMPLETED)
                    if reader in done:
                        break
                finally:
                    waiter.cancel()
                    await asyncio.gather(waiter, return_exceptions=True)
                # Recheck revocation before every invalidation, or at least every 20s.
                await accounts.call("me", token)
                await asyncio.wait_for(ws.send_json({"type": "sync"}), runtime.settings.send_timeout_seconds)
            if runtime.sessions.draining:
                await ws.close(code=1012)
        except (HTTPException, SQLAlchemyError):
            await ws.close(code=1008)
        except (WebSocketDisconnect, TimeoutError, RuntimeError):
            pass
        finally:
            if reader:
                reader.cancel()
                await asyncio.gather(reader, return_exceptions=True)
            listeners.discard(queue)
            if not listeners:
                accounts.listeners.pop(user["id"], None)
            runtime.sessions.release()
