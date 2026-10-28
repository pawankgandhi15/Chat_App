"""Run against an isolated PostgreSQL database supplied by CI (never production)."""
from concurrent.futures import ThreadPoolExecutor
import os
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.storage import Storage


def test_postgres_concurrency_restart_isolation_and_pagination():
    url = os.environ.get("BAATCHIT_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set BAATCHIT_TEST_DATABASE_URL to an isolated test PostgreSQL database")
    first = Storage(url)
    second = Storage(url)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda store: store.migrate(), [first, second]))
        suffix = uuid4().hex[:10]
        a, alice = first.register("alice_" + suffix, "a-long-test-password")
        b, bob = second.register("bob_" + suffix, "a-long-test-password")
        _, other = first.register("other_" + suffix, "a-long-test-password")
        with ThreadPoolExecutor(max_workers=4) as pool:
            opened = list(pool.map(lambda i: first.open_conversation(alice, b["id"]) if i % 2 else second.open_conversation(bob, a["id"]), range(10)))
        assert len({c["id"] for c in opened}) == 1
        cid = opened[0]["id"]
        request = str(uuid4())
        with ThreadPoolExecutor(max_workers=4) as pool:
            copies = list(pool.map(lambda i: (first if i % 2 else second).send(alice, cid, request, "deduplicated")[0], range(8)))
            writes = list(pool.map(lambda i: (first if i % 2 else second).send(alice, cid, str(uuid4()), str(i))[0], range(55)))
        assert len({message["id"] for message in copies}) == 1
        assert sorted(message["seq"] for message in writes) == list(range(2, 57))
        with pytest.raises(HTTPException) as denied:
            second.history(other, cid)
        assert denied.value.status_code == 404
        with pytest.raises(HTTPException):
            second.send(alice, cid, request, "different body")
        first.engine.dispose()
        second.engine.dispose()
        second.check()
        assert second.login("bob_" + suffix, "a-long-test-password")[0] == b
        newest = second.history(bob, cid)
        older = second.history(bob, cid, newest["next_before"])
        assert [m["seq"] for m in older["items"] + newest["items"]] == list(range(1, 57))
        assert second.list_conversations(bob)["items"][0]["id"] == cid
    finally:
        first.engine.dispose()
        second.engine.dispose()
