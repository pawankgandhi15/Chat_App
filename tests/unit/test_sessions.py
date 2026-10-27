import asyncio
import json

from app.sessions import Session, Sessions
from app.settings import Settings
from app.telemetry import Metrics


class Socket:
    def __init__(self, block=False):
        self.messages = []
        self.codes = []
        self.block = block

    async def send_text(self, message):
        if self.messages and self.block:
            await asyncio.Event().wait()
        self.messages.append(json.loads(message))

    async def close(self, code):
        self.codes.append(code)


def settings():
    return Settings(redis_url="redis://localhost", send_timeout_seconds=0.5)


async def test_session_first_single_writer_and_close():
    sock = Socket()
    s = Session(sock, "user", settings())
    s.queue.put('{"type":"chat"}')
    task = asyncio.create_task(s.writer("replica", Metrics("replica")))
    await s.initialized.wait()
    await asyncio.sleep(0.01)
    s.close(1012)
    await task
    assert [x["type"] for x in sock.messages] == ["session", "chat"]
    assert sock.codes == [1012] and s.queue.bytes == 0


async def test_slow_writer_evicted_without_blocking_healthy_writer():
    slow, healthy = Socket(True), Socket()
    a, b = Session(slow, "slow", settings()), Session(healthy, "healthy", settings())
    metrics = Metrics("replica")
    tasks = [asyncio.create_task(s.writer("replica", metrics)) for s in [a, b]]
    await asyncio.gather(a.initialized.wait(), b.initialized.wait())
    a.queue.put('{"type":"chat"}')
    b.queue.put('{"type":"chat"}')
    await asyncio.sleep(0.1)
    assert len(healthy.messages) == 2 and not tasks[0].done()
    await asyncio.wait_for(tasks[0], 1)
    assert slow.codes == [1013]
    b.close(1000)
    await tasks[1]


def test_admission_and_overflow_are_bounded():
    manager = Sessions(settings(), Metrics("replica"), "replica")
    assert sum(manager.reserve() for _ in range(100)) == 64
    manager.drain()
    assert not manager.reserve()
