"""Public-gateway smoke check, including proof of cross-replica messaging."""
import argparse
import asyncio
import json
import secrets

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus


async def message(socket, kind="chat", text=None):
    async with asyncio.timeout(10):
        while True:
            event = json.loads(await socket.recv())
            if event["type"] == kind and (text is None or event.get("text") == text):
                return event


async def check(base):
    base = base.rstrip("/")
    async with httpx.AsyncClient(base_url=base) as client:
        response = await client.get("/")
        assert response.status_code == 200 and "Baatchit" in response.text
        for route in ["/health", "/live", "/metrics"]:
            assert (await client.get(route)).status_code in {403, 404}
    wsbase = base.replace("https://", "wss://").replace("http://", "ws://")
    try:
        async with connect(wsbase + "/ws/test", origin=base):
            raise AssertionError("Missing subprotocol was accepted")
    except InvalidStatus as exc:
        assert exc.response.status_code in {400, 403}
    clients = []
    try:
        for index in range(24):
            ws = await connect(wsbase + "/ws/probe_" + str(index), origin=base, subprotocols=["chat.v1"])
            first = json.loads(await asyncio.wait_for(ws.recv(), 5))
            assert first["type"] == "session" and ws.subprotocol == "chat.v1"
            clients.append((ws, first))
            if len({first["container_id"] for _, first in clients}) >= 2:
                break
            await asyncio.sleep(0.25)
        assert len({first["container_id"] for _, first in clients}) >= 2, "Could not observe two backend replicas"
        text = "smoke_" + secrets.token_hex(8)
        await clients[0][0].send(text)
        events = await asyncio.gather(*(message(ws, text=text) for ws, _ in clients))
        assert len({e["event_id"] for e in events}) == 1
        assert all(e["container_id"] == clients[0][1]["container_id"] for e in events)
        print("PASS: frontend, private diagnostics, mandatory subprotocol and cross-replica delivery.")
    finally:
        await asyncio.gather(*(ws.close() for ws, _ in clients), return_exceptions=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8080")
    asyncio.run(check(parser.parse_args().url))
