import asyncio
import time


class TokenBucket:
    def __init__(self, rate: float, burst: int, clock=time.monotonic):
        self.rate, self.burst, self.clock = rate, burst, clock
        self.tokens = float(burst)
        self.updated = clock()

    def consume(self) -> bool:
        # No await: one event-loop task completes the accounting atomically.
        now = self.clock()
        self.tokens = min(self.burst, self.tokens + max(0, now - self.updated) * self.rate)
        self.updated = now
        if self.tokens < 1:
            return False
        self.tokens -= 1
        return True


class DeliveryQueue:
    def __init__(self, events: int, byte_limit: int):
        self.queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue(maxsize=events)
        self.byte_limit, self.bytes = byte_limit, 0

    def put(self, payload: str) -> bool:
        size = len(payload.encode("utf-8"))
        if self.queue.full() or self.bytes + size > self.byte_limit:
            return False
        self.queue.put_nowait((payload, size))
        self.bytes += size
        return True

    async def get(self) -> str:
        payload, size = await self.queue.get()
        self.bytes -= size
        return payload

    def clear(self):
        while not self.queue.empty():
            _, size = self.queue.get_nowait()
            self.bytes -= size
