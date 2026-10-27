"""Measure client-observed fanout from an off-node process; emits JSON evidence."""
import argparse
import asyncio
from collections import Counter
import json
import math
from pathlib import Path
import secrets
import time

from websockets.asyncio.client import connect


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)] if ordered else None


async def run(args):
    base = args.url.rstrip("/")
    wsbase = base.replace("https://", "wss://").replace("http://", "ws://")
    sockets, readers = [], []
    replicas = Counter()
    sent, observed, event_ids, latencies = {}, {}, {}, []
    errors, duplicates = [], [0]
    prefix = "load_" + secrets.token_hex(6) + "_"

    async def receive(index, ws):
        try:
            async for raw in ws:
                event = json.loads(raw)
                text = event.get("text", "")
                if event.get("type") != "chat" or text not in sent:
                    continue
                key = (index, text)
                if key in observed:
                    duplicates[0] += 1
                    continue
                latency = (time.monotonic() - sent[text]) * 1000
                observed[key] = latency
                latencies.append(latency)
                if text in event_ids and event_ids[text] != event["event_id"]:
                    errors.append("Event ID differs between recipients")
                event_ids[text] = event["event_id"]
        except Exception as exc:
            errors.append(type(exc).__name__)

    try:
        for index in range(args.clients):
            # Admission is staggered to respect the gateway handshake limiter.
            for attempt in range(100):
                ws = await connect(wsbase + "/ws/load_" + str(index), origin=base,
                                   subprotocols=["chat.v1"], max_queue=64, close_timeout=2)
                first = json.loads(await asyncio.wait_for(ws.recv(), 5))
                if first.get("type") != "session":
                    raise ValueError("First event was not a session")
                replica = first["container_id"]
                if replicas[replica] < math.ceil(args.clients / 2):
                    replicas[replica] += 1
                    sockets.append(ws)
                    readers.append(asyncio.create_task(receive(index, ws)))
                    break
                await ws.close()
                await asyncio.sleep(0.3)
            else:
                raise RuntimeError("Could not balance clients between two replicas")
            await asyncio.sleep(0.3)
        if len(replicas) != 2:
            raise RuntimeError("Expected two backend replicas")

        async def phase(seconds, measured):
            start = time.monotonic()
            count = int(seconds * args.rate)
            for n in range(count):
                await asyncio.sleep(max(0, start + n / args.rate - time.monotonic()))
                head = prefix + ("m" if measured else "w") + str(n) + "_"
                text = head + "x" * (args.payload_bytes - len(head.encode()))
                if measured:
                    sent[text] = time.monotonic()
                await sockets[n % len(sockets)].send(text)
            await asyncio.sleep(max(0, start + seconds - time.monotonic()))

        await phase(args.warmup, False)
        await phase(args.duration, True)
        await asyncio.sleep(2)
        expected = len(sent) * len(sockets)
        on_time = sum(ms <= 2000 for ms in observed.values())
        report = {"url":base, "clients":len(sockets), "replica_distribution":dict(replicas),
                  "warmup_seconds":args.warmup, "steady_seconds":args.duration,
                  "aggregate_messages_per_second":args.rate, "payload_bytes":args.payload_bytes,
                  "messages_sent":len(sent), "expected_deliveries":expected,
                  "observed_deliveries":len(observed), "delivery_within_2s_percent":100 * on_time / expected if expected else 0,
                  "p95_ms":percentile(latencies, .95), "p99_ms":percentile(latencies, .99),
                  "duplicates":duplicates[0], "errors":errors,
                  "scope":"Client-observed latency; node memory and AWS cost require separate measurements."}
        report["passed"] = (expected > 0 and report["delivery_within_2s_percent"] >= 99.9
                            and report["p95_ms"] is not None and report["p95_ms"] < 250
                            and report["p99_ms"] < 1000 and not duplicates[0] and not errors)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return report["passed"]
    finally:
        await asyncio.gather(*(ws.close() for ws in sockets), return_exceptions=True)
        for reader in readers:
            reader.cancel()
        await asyncio.gather(*readers, return_exceptions=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--clients", type=int, default=25)
    parser.add_argument("--rate", type=float, default=5)
    parser.add_argument("--payload-bytes", type=int, default=512)
    parser.add_argument("--warmup", type=float, default=120)
    parser.add_argument("--duration", type=float, default=1800)
    parser.add_argument("--output", default="artifacts/load.json")
    args = parser.parse_args()
    if not (2 <= args.clients <= 100 and 0 < args.rate <= min(10, args.clients)
            and 64 <= args.payload_bytes <= 2000 and args.duration > 0 and args.warmup >= 0):
        parser.error("Use 2–100 clients, positive rate <= min(10, clients), 64–2000 bytes and positive duration.")
    raise SystemExit(0 if asyncio.run(run(args)) else 1)
