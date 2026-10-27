import asyncio
import contextlib
from uuid import uuid4

from starlette.websockets import WebSocketDisconnect

from .limits import DeliveryQueue, TokenBucket
from .protocol import broadcast_event, session_event
from .validation import InputError, normalize_text


class Session:
    def __init__(self, ws, user, settings):
        self.ws, self.user, self.settings = ws, user, settings
        self.id = str(uuid4())
        self.queue = DeliveryQueue(settings.outbound_queue_events, settings.outbound_queue_bytes)
        self.limiter = TokenBucket(settings.rate_messages_per_second, settings.rate_burst)
        self.closing = asyncio.Event()
        self.initialized = asyncio.Event()
        self.active = False
        self.code = 1000

    def close(self, code):
        if not self.closing.is_set():
            self.active = False
            self.code = code
            self.closing.set()

    async def writer(self, replica, metrics):
        try:
            await asyncio.wait_for(
                self.ws.send_text(session_event(self.user, replica, self.id)),
                self.settings.send_timeout_seconds)
            self.active = not self.closing.is_set()
            self.initialized.set()
            while not self.closing.is_set():
                item = asyncio.create_task(self.queue.get())
                closing = asyncio.create_task(self.closing.wait())
                try:
                    done, _ = await asyncio.wait([item, closing], return_when=asyncio.FIRST_COMPLETED)
                    if closing in done:
                        break
                    await asyncio.wait_for(self.ws.send_text(item.result()),
                                           self.settings.send_timeout_seconds)
                    metrics.deliveries.labels("sent").inc()
                finally:
                    item.cancel()
                    closing.cancel()
                    await asyncio.gather(item, closing, return_exceptions=True)
        except TimeoutError:
            metrics.deliveries.labels("timeout").inc()
            self.close(1013)
        except (WebSocketDisconnect, RuntimeError, OSError):
            self.close(1000)
        finally:
            self.initialized.set()
            self.active = False
            self.queue.clear()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.ws.close(code=self.code),
                                       self.settings.send_timeout_seconds)


class Sessions:
    def __init__(self, settings, metrics, replica):
        self.settings, self.metrics, self.replica = settings, metrics, replica
        self.sessions = {}
        self.metrics.queued.set_function(lambda: sum(s.queue.bytes for s in self.sessions.values()))
        self.reserved = 0
        self.draining = False
        self.publisher_budget = TokenBucket(settings.publish_rate_per_second, settings.publish_burst)

    def reserve(self):
        if self.draining or self.reserved >= self.settings.max_connections_per_replica:
            return False
        self.reserved += 1
        self.metrics.connections.set(self.reserved)
        return True

    def release(self):
        self.reserved -= 1
        self.metrics.connections.set(self.reserved)

    def fanout(self, payload):
        for session in tuple(self.sessions.values()):
            if session.active and not session.queue.put(payload):
                self.metrics.deliveries.labels("queue_overflow").inc()
                session.close(1013)
        self.update_queue_metric()

    def update_queue_metric(self):
        self.metrics.queued.set(sum(s.queue.bytes for s in self.sessions.values()))

    def close_all(self, code):
        for session in tuple(self.sessions.values()):
            session.close(code)

    def drain(self):
        self.draining = True
        self.close_all(1012)

    async def advisory(self, broker, user, text):
        if broker.ready and self.publisher_budget.consume():
            with contextlib.suppress(Exception):
                await broker.publish(broadcast_event("system", user, text, self.replica))

    async def run(self, ws, user, broker):
        session = Session(ws, user, self.settings)
        self.sessions[session.id] = session
        writer = asyncio.create_task(session.writer(self.replica, self.metrics))
        reader = None
        try:
            await session.initialized.wait()
            if not session.active:
                return
            await self.advisory(broker, user, f"User {user} has joined the room.")
            reader = asyncio.create_task(self.read(session, broker))
            done, _ = await asyncio.wait([reader, writer], return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            session.close(1000)
            if reader:
                reader.cancel()
                await asyncio.gather(reader, return_exceptions=True)
            try:
                await asyncio.wait_for(writer, self.settings.send_timeout_seconds + 0.5)
            except (TimeoutError, asyncio.CancelledError):
                writer.cancel()
                await asyncio.gather(writer, return_exceptions=True)
            self.sessions.pop(session.id, None)
            self.update_queue_metric()
            if not self.draining:
                await self.advisory(broker, user, f"User {user} has left the room.")

    async def read(self, session, broker):
        try:
            while not session.closing.is_set():
                packet = await session.ws.receive()
                if packet["type"] == "websocket.disconnect":
                    return
                if packet.get("bytes") is not None:
                    session.close(1003)
                    return
                if not session.limiter.consume():
                    session.close(1013)
                    return
                try:
                    text = normalize_text(packet.get("text", ""))
                except InputError as exc:
                    session.close(exc.code)
                    return
                if not text:
                    continue
                if not broker.ready:
                    session.close(1011)
                    return
                if not self.publisher_budget.consume():
                    self.metrics.published.labels("rate_limited").inc()
                    session.close(1013)
                    return
                await broker.publish(broadcast_event("chat", session.user, text, self.replica))
        except (WebSocketDisconnect, RuntimeError):
            pass
        except Exception:
            session.close(1011)
