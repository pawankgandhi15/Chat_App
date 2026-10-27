import json
from uuid import uuid4

import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError

from app.limits import DeliveryQueue, TokenBucket
from app.protocol import BroadcastEvent, broadcast_event, session_event
from app.settings import Settings
from app.validation import InputError, normalize_text, valid_username


def test_normalization_is_exact():
    assert normalize_text(" \tHello\r\nworld\r \n") == "Hello\nworld"
    assert normalize_text("\u00a0A\u3000") == "\u00a0A\u3000"
    assert normalize_text("Ａ") == "Ａ"  # No NFC/NFKC.
    assert normalize_text("😀" * 2000) == "😀" * 2000
    assert normalize_text(" \r\n\t") == ""


@pytest.mark.parametrize("text,code", [("\x00x", 1008), ("\x7f", 1008), ("x"*2001, 1008),
                                      ("x"*16385, 1009), ("\ud800", 1007)])
def test_invalid_input(text, code):
    with pytest.raises(InputError) as error:
        normalize_text(text)
    assert error.value.code == code


@given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=100))
def test_normalization_idempotent(text):
    try:
        first = normalize_text(text)
    except InputError:
        return
    assert normalize_text(first) == first


@pytest.mark.parametrize("name,valid", [("Alice_1-x", True), ("x"*32, True), ("x"*33, False),
                                       ("a b", False), ("é", False), ("../x", False), ("x\n", False)])
def test_username(name, valid):
    assert valid_username(name) is valid


def test_event_fields_are_strict_and_timestamp_consistent():
    raw = broadcast_event("chat", "Alice", "Hello", "replica1")
    event = BroadcastEvent.model_validate_json(raw)
    assert event.time == event.sent_at[11:19] + " UTC"
    data = json.loads(raw)
    data["room"] = "extra"
    with pytest.raises(ValidationError):
        BroadcastEvent.model_validate(data)
    first = json.loads(session_event("Alice", "replica1", str(uuid4())))
    assert first["type"] == "session" and "event_id" not in first


def test_settings_require_explicit_secret_and_public_policy(tmp_path, monkeypatch):
    for name in ("REDIS_URL", "REDIS_URL_FILE", "APP_ENV", "ALLOWED_ORIGINS", "RELEASE_ID"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValidationError):
        Settings()
    s = Settings(redis_url="redis://localhost:6379/0")
    assert "localhost:6379" not in repr(s)
    with pytest.raises(ValidationError):
        Settings(redis_url="redis://localhost", app_env="public")
    path = tmp_path / "url"
    path.write_text("redis://app:generated@redis:6379/0")
    Settings(redis_url_file=path, app_env="public", release_id="sha-123",
             allowed_origins="https://chat.example.com")
    for overrides in [{"allowed_origins": "*"}, {"allowed_origins": "https://example.com/path"},
                      {"subscriber_heartbeat_seconds": 10, "subscriber_stale_seconds": 10},
                      {"redis_url_file": path}]:
        with pytest.raises(ValidationError):
            Settings(redis_url="redis://localhost", **overrides)


def test_bucket_refills_and_never_oversubscribes():
    now = [0.]
    bucket = TokenBucket(2, 3, lambda: now[0])
    assert [bucket.consume() for _ in range(4)] == [True, True, True, False]
    now[0] = 0.5
    assert bucket.consume()
    assert not bucket.consume()
    now[0] = 100
    assert [bucket.consume() for _ in range(4)] == [True, True, True, False]


async def test_queue_enforces_utf8_bytes_and_releases():
    queue = DeliveryQueue(2, 5)
    assert queue.put("😀")
    assert not queue.put("é")
    assert queue.bytes == 4
    assert await queue.get() == "😀"
    assert queue.bytes == 0
    assert queue.put("a") and queue.put("b")
    assert not queue.put("c")
    queue.clear()
    queue.clear()
    assert queue.bytes == 0 and queue.queue.empty()
