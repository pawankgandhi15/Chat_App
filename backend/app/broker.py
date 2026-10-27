import asyncio
import contextlib
import json
import secrets
import time

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from .protocol import BroadcastEvent
from .telemetry import log_event


class Broker:
    def __init__(self, settings, metrics, on_event, on_unavailable):
        self.settings, self.metrics = settings, metrics
        self.on_event, self.on_unavailable = on_event, on_unavailable
        self.generation = 0
        self.last_probe = 0.0
        self.subscribed = False
        self.task = None
        self.client = Redis.from_url(
            settings.resolve_redis_url(), decode_responses=True, protocol=2,
            max_connections=9, socket_connect_timeout=settings.redis_command_timeout_seconds,
            socket_timeout=settings.redis_command_timeout_seconds,
            retry=Retry(NoBackoff(), 0), health_check_interval=0,
            lib_name=None, lib_version=None,
        )

    @property
    def ready(self):
        return self.subscribed and time.monotonic() - self.last_probe < self.settings.subscriber_stale_seconds

    def unavailable(self):
        self.subscribed = False
        self.metrics.ready.set(0)
        self.on_unavailable()

    async def ping(self) -> bool:
        try:
            await asyncio.wait_for(self.client.ping(), self.settings.redis_command_timeout_seconds)
            return self.ready
        except Exception:
            self.unavailable()
            return False

    async def publish(self, payload: str):
        try:
            result = await asyncio.wait_for(
                self.client.publish(self.settings.channel_name, payload),
                self.settings.redis_command_timeout_seconds)
            self.metrics.published.labels("ok").inc()
            return result
        except Exception:
            self.metrics.published.labels("failed").inc()
            self.unavailable()
            raise

    async def start(self):
        self.task = asyncio.create_task(self.supervise(), name="redis-supervisor")

    async def stop(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        self.unavailable()
        await self.client.aclose()

    async def supervise(self):
        delay = 0.25
        while True:
            try:
                self.generation += 1
                await self.subscribe_generation()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log_event("redis_unavailable", error_class=type(exc).__name__)
                self.unavailable()
                await asyncio.sleep(delay)
                delay = min(5, delay * 2)

    async def subscribe_generation(self):
        self.subscribed = False
        nonce = secrets.token_hex(16)
        probe_received = asyncio.Event()
        pending_probe = {"value": None}
        async with self.client.pubsub() as subscriber:
            await subscriber.subscribe(self.settings.channel_name)
            ack = await subscriber.get_message(ignore_subscribe_messages=False,
                                               timeout=self.settings.redis_command_timeout_seconds)
            if not ack or ack["type"] != "subscribe":
                raise ConnectionError("Subscription not acknowledged")

            async def consume():
                while True:
                    packet = await subscriber.get_message(ignore_subscribe_messages=True, timeout=0.5)
                    if self.subscribed and not self.ready:
                        raise TimeoutError("Subscriber heartbeat stale")
                    if packet is None:
                        continue
                    raw = packet.get("data")
                    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 65536:
                        continue
                    try:
                        value = json.loads(raw)
                        if not isinstance(value, dict):
                            continue
                        if value.get("_probe") == nonce:
                            if value.get("sequence") == pending_probe["value"]:
                                probe_received.set()
                            continue
                        if "_probe" in value:
                            continue  # Another replica's control packet never reaches browsers.
                        event = BroadcastEvent.model_validate(value)
                        if event.time != event.sent_at[11:19] + " UTC":
                            continue
                        self.on_event(event.model_dump_json())
                    except (ValueError, ValidationError):
                        continue

            async def heartbeat():
                sequence = 0
                while True:
                    sequence += 1
                    pending_probe["value"] = sequence
                    probe_received.clear()
                    await self.publish(json.dumps({"_probe": nonce, "sequence": sequence}))
                    await asyncio.wait_for(probe_received.wait(), self.settings.subscriber_stale_seconds)
                    self.last_probe = time.monotonic()
                    self.subscribed = True
                    self.metrics.ready.set(1)
                    await asyncio.sleep(self.settings.subscriber_heartbeat_seconds)

            tasks = [asyncio.create_task(consume()), asyncio.create_task(heartbeat())]
            try:
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
