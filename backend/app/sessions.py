import asyncio
import contextlib
import json
import re
import time
from uuid import uuid4

from starlette.websockets import WebSocketDisconnect

from .limits import DeliveryQueue, TokenBucket
from .protocol import UUID4, PresenceSnapshot, broadcast_event, private_event, session_event
from .validation import InputError, normalize_text


class Session:
    def __init__(self, ws, user, settings, protocol="chat.v1"):
        self.ws, self.user, self.settings = ws, user, settings
        self.protocol = protocol
        self.last_peers = None
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
        self.instance_id = str(uuid4())
        self.presence_sequence = 0
        self.presence = {}
        self.presence_changed = asyncio.Event()
        self.presence_task = None

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
        event = json.loads(payload)  # Broker validates the exact event schema first.
        if event["type"] == "_presence":
            if event["instance_id"] != self.instance_id:
                previous = self.presence.get(event["instance_id"])
                if previous is None or event["sequence"] > previous["sequence"]:
                    if previous is not None or len(self.presence) < 128:
                        self.presence[event["instance_id"]] = {
                            "sequence": event["sequence"], "peers": event["peers"],
                            "seen": time.monotonic()}
                        self.notify_peers()
            return
        for session in tuple(self.sessions.values()):
            if event["type"] == "private" and (session.protocol != "chat.v2" or
                    session.id not in {event["sender_id"], event["recipient_id"]}):
                continue
            if session.active and not session.queue.put(payload):
                self.metrics.deliveries.labels("queue_overflow").inc()
                session.close(1013)
        self.update_queue_metric()

    def peers(self, exclude=None):
        now = time.monotonic()
        peers = {s.id: {"connection_id": s.id, "user": s.user}
                 for s in self.sessions.values() if s.active and s.protocol == "chat.v2"}
        for snapshot in self.presence.values():
            if now - snapshot["seen"] < 12:
                for peer in snapshot["peers"]:
                    peers.setdefault(peer["connection_id"], peer)
        peers.pop(exclude, None)
        return sorted(peers.values(), key=lambda peer: (peer["user"].lower(), peer["connection_id"]))[:512]

    def notify_peers(self):
        for session in tuple(self.sessions.values()):
            if not session.active or session.protocol != "chat.v2":
                continue
            peers = self.peers(session.id)
            fingerprint = tuple((peer["connection_id"], peer["user"]) for peer in peers)
            if fingerprint == session.last_peers:
                continue
            payload = json.dumps({"schema_version": 1, "type": "peers", "peers": peers}, separators=(",", ":"))
            if session.queue.put(payload):
                session.last_peers = fingerprint
            else:
                self.metrics.deliveries.labels("queue_overflow").inc()
                session.close(1013)
        self.update_queue_metric()

    def broker_unavailable(self):
        self.presence.clear()
        self.close_all(1011)
        self.presence_changed.set()

    async def start_presence(self, broker):
        self.presence_task = asyncio.create_task(self.publish_presence(broker), name="presence-publisher")

    async def stop_presence(self):
        if self.presence_task:
            self.presence_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.presence_task
            self.presence_task = None

    async def publish_presence(self, broker):
        while True:
            self.presence_changed.clear()
            now = time.monotonic()
            expired = [key for key, value in self.presence.items() if now - value["seen"] >= 12]
            for key in expired:
                self.presence.pop(key, None)
            if expired:
                self.notify_peers()
            if broker.ready:
                self.presence_sequence += 1
                local = [{"connection_id": s.id, "user": s.user} for s in self.sessions.values()
                         if s.active and s.protocol == "chat.v2"]
                snapshot = PresenceSnapshot(instance_id=self.instance_id,
                                            sequence=self.presence_sequence, peers=local)
                with contextlib.suppress(Exception):
                    await broker.publish(snapshot.model_dump_json())
            try:
                await asyncio.wait_for(self.presence_changed.wait(), timeout=3)
                # Coalesce rapid joins/leaves so presence cannot flood per-session queues.
                await asyncio.sleep(0.1)
            except TimeoutError:
                pass

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

    async def run(self, ws, user, broker, protocol="chat.v1"):
        session = Session(ws, user, self.settings, protocol)
        self.sessions[session.id] = session
        writer = asyncio.create_task(session.writer(self.replica, self.metrics))
        reader = None
        try:
            await session.initialized.wait()
            if not session.active:
                return
            if protocol == "chat.v2":
                self.notify_peers()
                self.presence_changed.set()
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
            if protocol == "chat.v2":
                self.notify_peers()
                self.presence_changed.set()
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
                raw = packet.get("text", "")
                recipient = None
                try:
                    if session.protocol == "chat.v2":
                        if len(raw.encode("utf-8")) > 16384:
                            raise InputError(1009)
                        data = json.loads(raw)
                        if not isinstance(data, dict) or type(data.get("text")) is not str:
                            raise ValueError("Invalid message")
                        if data.get("type") == "chat" and set(data) == {"type", "text"}:
                            pass
                        elif data.get("type") == "private" and set(data) == {"type", "text", "to", "client_id"}:
                            if (not isinstance(data["to"], str) or not re.fullmatch(UUID4, data["to"]) or data["to"] == session.id
                                    or not isinstance(data["client_id"], str) or not re.fullmatch(UUID4, data["client_id"])):
                                raise ValueError("Invalid recipient")
                            recipient = data["to"]
                        else:
                            raise ValueError("Invalid message")
                        raw = data["text"]
                    text = normalize_text(raw)
                except InputError as exc:
                    session.close(exc.code)
                    return
                except UnicodeEncodeError:
                    session.close(1007)
                    return
                except (ValueError, TypeError):
                    session.close(1008)
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
                if recipient:
                    peer = next((p for p in self.peers(session.id) if p["connection_id"] == recipient), None)
                    if not peer:
                        notice = json.dumps({"schema_version": 1, "type": "notice",
                                             "client_id": data["client_id"],
                                             "message": "This person is no longer available. Your draft was kept."})
                        if not session.queue.put(notice):
                            session.close(1013)
                        continue
                    payload = private_event(session.user, text, self.replica, session.id, recipient, peer["user"], data["client_id"])
                else:
                    payload = broadcast_event("chat", session.user, text, self.replica)
                await broker.publish(payload)
        except (WebSocketDisconnect, RuntimeError):
            pass
        except Exception:
            session.close(1011)
