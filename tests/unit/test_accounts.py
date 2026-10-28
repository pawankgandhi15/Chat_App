"""Security and persistence contracts against a real file-backed SQLite database."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select, update

from app.main import create_app
from app.settings import Settings
from app.storage import Storage, users, sessions, digest

ORIGIN = "http://localhost:8080"
PASSWORD = "a-long-test-password"


@pytest.fixture
def storage(tmp_path):
    store = Storage("sqlite:///" + (tmp_path / "accounts.db").as_posix())
    store.migrate()
    yield store
    store.engine.dispose()


def test_password_storage_login_revocation_and_expiry(storage):
    alice, token = storage.register("Alice", PASSWORD)
    assert alice["username"] == "alice"
    assert storage.me(token) == alice
    with storage.engine.connect() as db:
        row = db.execute(select(users)).mappings().one()
        session = db.execute(select(sessions)).mappings().one()
        assert PASSWORD not in row["password_hash"]
        assert row["password_hash"].startswith("scrypt32768r8p3$")
        assert session["token_hash"] == digest(token) and session["token_hash"] != token
    with pytest.raises(HTTPException) as wrong:
        storage.login("Alice", "incorrect-password")
    assert wrong.value.status_code == 401
    assert storage.login("ALICE", PASSWORD)[0] == alice
    storage.logout(token)
    with pytest.raises(HTTPException):
        storage.me(token)
    _, fresh = storage.login("alice", PASSWORD)
    with storage.engine.begin() as db:
        db.execute(update(sessions).values(expires_at=int(time.time()) - 1))
    with pytest.raises(HTTPException):
        storage.me(fresh)


def test_duplicate_username_and_concurrent_open(storage):
    alice, a = storage.register("Alice", PASSWORD)
    bob, b = storage.register("Bob", PASSWORD)
    with pytest.raises(HTTPException) as duplicate:
        storage.register("ALICE", PASSWORD)
    assert duplicate.value.status_code == 409
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda i: storage.open_conversation(a, bob["id"]) if i % 2 else storage.open_conversation(b, alice["id"]), range(8)))
    assert len({row["id"] for row in results}) == 1


def test_history_persists_across_new_engine_and_authorization(storage):
    alice, a = storage.register("Alice", PASSWORD)
    bob, b = storage.register("Bob", PASSWORD)
    _, other = storage.register("Observer", PASSWORD)
    conversation = storage.open_conversation(a, bob["id"])["id"]
    first, _ = storage.send(a, conversation, str(uuid4()), "saved while Bob is offline")
    storage.logout(b)
    replacement = Storage(str(storage.engine.url))
    try:
        replacement.check()
        assert replacement.login("bob", PASSWORD)[0]["id"] == bob["id"]
        _, new_token = replacement.login("bob", PASSWORD)
        assert replacement.history(new_token, conversation)["items"] == [first]
        assert replacement.list_conversations(new_token)["items"][0]["id"] == conversation
        assert replacement.history(a, conversation)["items"][0]["sender_id"] == alice["id"]
        for operation in (lambda: replacement.history(other, conversation),
                          lambda: replacement.send(other, conversation, str(uuid4()), "forged")):
            with pytest.raises(HTTPException) as denied:
                operation()
            assert denied.value.status_code == 404
    finally:
        replacement.engine.dispose()


def test_concurrent_sends_idempotency_and_history_pages(storage):
    _, token = storage.register("Alice", PASSWORD)
    bob, _ = storage.register("Bob", PASSWORD)
    c = storage.open_conversation(token, bob["id"])["id"]
    client_id = str(uuid4())
    with ThreadPoolExecutor(max_workers=4) as pool:
        same = list(pool.map(lambda _: storage.send(token, c, client_id, "one message")[0], range(8)))
        sent = list(pool.map(lambda i: storage.send(token, c, str(uuid4()), f"message {i}")[0], range(55)))
    assert len({row["id"] for row in same}) == 1
    assert sorted(row["seq"] for row in sent) == list(range(2, 57))
    with pytest.raises(HTTPException) as reused:
        storage.send(token, c, client_id, "changed body")
    assert reused.value.status_code == 409
    latest = storage.history(token, c)
    older = storage.history(token, c, latest["next_before"])
    assert [m["seq"] for m in older["items"] + latest["items"]] == list(range(1, 57))
    assert older["next_before"] is None


def test_rate_limits_are_shared_by_database(storage):
    other = Storage(str(storage.engine.url))
    try:
        storage.throttle("example", 2, 900)
        other.throttle("example", 2, 900)
        with pytest.raises(HTTPException) as limited:
            storage.throttle("example", 2, 900)
        assert limited.value.status_code == 429
    finally:
        other.engine.dispose()


async def test_http_auth_csrf_validation_and_commit_during_broker_failure(tmp_path):
    app = create_app(Settings(app_env="test", redis_url="redis://127.0.0.1:1/0",
        database_url="sqlite:///" + (tmp_path / "http.db").as_posix()))
    runtime = app.state.runtime
    runtime.accounts.storage.migrate()
    runtime.broker.publish = AsyncMock(side_effect=ConnectionError("broker unavailable"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN, headers={"Origin": ORIGIN}) as client:
        data = {"username": "Alice", "password": PASSWORD}
        assert (await client.get("/api/auth/me")).status_code == 401
        assert (await client.post("/api/auth/register", json=data, headers={"Origin": "https://evil.example"})).status_code == 403
        response = await client.post("/api/auth/register", json=data)
        assert response.status_code == 201
        assert "HttpOnly" in response.headers["set-cookie"] and "SameSite=strict" in response.headers["set-cookie"]
        assert response.headers["cache-control"] == "no-store"
        alice = response.json()["user"]
        assert (await client.get("/api/conversations", headers={"X-Account-ID": str(uuid4())})).status_code == 401
        bob, _ = runtime.accounts.storage.register("Bob", PASSWORD)
        result = await client.get("/api/users?q=bo")
        assert result.json()["items"] == [bob]
        conversation = (await client.post("/api/conversations", json={"user_id": bob["id"]})).json()["id"]
        payload = {"client_id": str(uuid4()), "text": "persist even without Redis"}
        saved = await client.post(f"/api/conversations/{conversation}/messages", json=payload)
        assert saved.status_code == 200 and saved.json()["status"] == "saved"
        assert saved.json()["message"]["sender_id"] == alice["id"]
        assert (await client.post(f"/api/conversations/{conversation}/messages", json={**payload, "sender_id": bob["id"]})).status_code == 422
        assert (await client.post(f"/api/conversations/{conversation}/messages", json={**payload, "text": " "})).status_code == 422
        assert len((await client.get(f"/api/conversations/{conversation}/messages")).json()["items"]) == 1
        invalid = await client.post("/api/auth/login", json={**data, "password": "sensitive"})
        assert invalid.status_code == 422 and "sensitive" not in invalid.text
        assert (await client.post("/api/auth/login", content="x" * 17000)).status_code == 413
        await client.post("/api/auth/logout", json={})
        assert (await client.get(f"/api/conversations/{conversation}/messages")).status_code == 401
        await client.post("/api/auth/login", json=data)
        assert len((await client.get(f"/api/conversations/{conversation}/messages")).json()["items"]) == 1
    await runtime.broker.client.aclose()
    runtime.accounts.storage.engine.dispose()
