"""Exercise chat.v2 across two ASGI servers using a local RESP Pub/Sub test double."""
import asyncio
import json
import socket
from contextlib import suppress
from uuid import uuid4

from uvicorn import Config, Server
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from app.main import create_app
from app.settings import Settings


def resp(value):
    if isinstance(value, int):
        return f":{value}\r\n".encode()
    if isinstance(value, list):
        return f"*{len(value)}\r\n".encode() + b"".join(resp(item) for item in value)
    encoded = value.encode()
    return f"${len(encoded)}\r\n".encode() + encoded + b"\r\n"


class LocalPubSub:
    def __init__(self):
        self.subscribers = set()

    async def handle(self, reader, writer):
        try:
            while line := await reader.readline():
                if not line.startswith(b"*"):
                    return
                args = []
                for _ in range(int(line[1:])):
                    length = await reader.readline()
                    if not length.startswith(b"$"):
                        return
                    args.append((await reader.readexactly(int(length[1:]) + 2))[:-2].decode())
                command = args[0].upper()
                if command == "SUBSCRIBE":
                    self.subscribers.add(writer)
                    writer.write(resp(["subscribe", args[1], 1]))
                elif command == "UNSUBSCRIBE":
                    self.subscribers.discard(writer)
                    writer.write(resp(["unsubscribe", args[1] if len(args) > 1 else "", 0]))
                elif command == "PUBLISH":
                    listeners = list(self.subscribers)
                    for subscriber in listeners:
                        subscriber.write(resp(["message", args[1], args[2]]))
                    writer.write(resp(len(listeners)))
                elif command == "PING":
                    writer.write(b"+PONG\r\n")
                else:
                    writer.write(b"-ERR unsupported test command\r\n")
                await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            self.subscribers.discard(writer)
            writer.close()
            with suppress(ConnectionError):
                await writer.wait_closed()


async def wait_until(predicate, timeout=10):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(.02)


async def receive(socket, kind, condition=lambda event: True):
    async with asyncio.timeout(10):
        while True:
            event = json.loads(await socket.recv())
            if event["type"] == kind and condition(event):
                return event


async def assert_no_private(socket):
    try:
        async with asyncio.timeout(.5):
            while True:
                event = json.loads(await socket.recv())
                if socket.subprotocol == "chat.v1":
                    assert event["type"] not in {"private", "peers", "_presence"}
                else:
                    assert event["type"] != "private"
    except TimeoutError:
        pass


async def test_private_messages_across_replicas_and_legacy_isolation():
    bus = LocalPubSub()
    redis_server = await asyncio.start_server(bus.handle, "127.0.0.1", 0)
    redis_port = redis_server.sockets[0].getsockname()[1]
    servers, tasks, listeners, apps = [], [], [], []
    try:
        for _ in range(2):
            settings = Settings(app_env="test", redis_url=f"redis://127.0.0.1:{redis_port}/0",
                subscriber_heartbeat_seconds=1, subscriber_stale_seconds=3)
            app = create_app(settings)
            apps.append(app)
            server = Server(Config(app, host="127.0.0.1", port=0,
                                   log_level="error", lifespan="on", access_log=False))
            listener = socket.socket()
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 0))
            listener.listen(128)
            listener.setblocking(False)
            servers.append(server)
            listeners.append(listener)
            tasks.append(asyncio.create_task(server.serve(sockets=[listener])))
        await wait_until(lambda: all(server.started for server in servers))
        await wait_until(lambda: all(app.state.runtime.broker.ready for app in apps))
        urls = [f"ws://127.0.0.1:{listener.getsockname()[1]}/ws/" for listener in listeners]
        opts = {"origin": "http://localhost:8080"}
        async with (connect(urls[0] + "Alice", subprotocols=["chat.v2"], **opts) as alice,
                    connect(urls[1] + "Bob", subprotocols=["chat.v2"], **opts) as bob,
                    connect(urls[0] + "Observer", subprotocols=["chat.v2"], **opts) as observer,
                    connect(urls[1] + "Legacy", subprotocols=["chat.v1"], **opts) as legacy):
            a, b, c, old = [json.loads(await client.recv()) for client in (alice, bob, observer, legacy)]
            assert all(item["type"] == "session" for item in (a, b, c, old))
            assert len({item["connection_id"] for item in (a, b, c, old)}) == 4
            await receive(alice, "peers", lambda e: any(p["connection_id"] == b["connection_id"] for p in e["peers"]))
            await receive(bob, "peers", lambda e: any(p["connection_id"] == a["connection_id"] for p in e["peers"]))

            client_id = str(uuid4())
            await alice.send(json.dumps({"type": "private", "to": b["connection_id"],
                                         "text": "secret for Bob", "client_id": client_id}))
            sent, received = await asyncio.gather(receive(alice, "private"), receive(bob, "private"))
            assert sent == received
            assert sent["sender_id"] == a["connection_id"] and sent["recipient_id"] == b["connection_id"]
            assert sent["user"] == "Alice" and sent["recipient_user"] == "Bob"
            assert sent["client_id"] == client_id and sent["text"] == "secret for Bob"
            await asyncio.gather(assert_no_private(observer), assert_no_private(legacy))

            await alice.send(json.dumps({"type": "chat", "text": "hello everyone"}))
            public = await asyncio.gather(*(receive(client, "chat") for client in (alice, bob, observer, legacy)))
            assert all(event["text"] == "hello everyone" for event in public)
            assert len({event["event_id"] for event in public}) == 1

            await bob.close()
            await receive(alice, "peers", lambda e: all(p["connection_id"] != b["connection_id"] for p in e["peers"]))
            rejected_id = str(uuid4())
            await alice.send(json.dumps({"type": "private", "to": b["connection_id"],
                                         "text": "please keep my draft", "client_id": rejected_id}))
            notice = await receive(alice, "notice")
            assert notice["client_id"] == rejected_id and "draft" in notice["message"]
            await alice.send(json.dumps({"type": "private", "to": c["connection_id"],
                                         "text": "forged", "client_id": str(uuid4()), "sender_id": b["connection_id"]}))
            try:
                async with asyncio.timeout(5):
                    while True:
                        await alice.recv()
            except ConnectionClosed as closed:
                assert closed.rcvd.code == 1008
            else:
                raise AssertionError("Forged sender field was accepted")
    finally:
        for server in servers:
            server.should_exit = True
        await asyncio.gather(*tasks, return_exceptions=True)
        for listener in listeners:
            listener.close()
        redis_server.close()
        await redis_server.wait_closed()
