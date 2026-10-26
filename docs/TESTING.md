# Testing and Verification Plan

**Status:** Planned test specifications, property-based boundary checks, and chaos engineering methodologies. See the [documentation index](../README.md).

**Design Revision 4 (2026-10-25):** Comprehensive verification harness establishing property-based fuzzing, concrete `pytest-asyncio` fixtures, chaos failure injections, and monotonic load latency calculation models.

---

## Verification Matrix & Acceptance Mapping

| Area | Scenario | Required Invariant / Observation | AC ID | Target |
| --- | --- | --- | --- | --- |
| **Startup & Topology** | Spin up complete 5-container Compose cluster. | Gateway serves HTTP 200 on `/`; two backend replicas report ready on `/health`; Redis is isolated. | AC-01 | $\le 10\text{s}$ spin-up |
| **Cross-Replica Fan-out** | Client A on Replica 1, Client B on Replica 2. | Bidirectional message exchange; each client observes counterpart's `container_id`; zero duplicate deliveries. | AC-02, AC-03 | 100% arrival |
| **Schema Compliance** | Emit session, chat, and system events. | Payloads strictly conform to `events-v1.schema.json`; valid UUIDv4 IDs and RFC 3339 timestamps. | AC-04, AC-12 | 100% schema match |
| **Dependency Loss** | Terminate Redis container during active chat. | Backends transition `/health` to 503 within 10s; active sockets close with code 1011; restarts restore health. | AC-05, AC-18 | Health $\le 15\text{s}$ |
| **Replica Replacement** | Force-kill and restart Backend Replica 1. | Sockets on Replica 1 drop and reconnect to Replica 2; Nginx dynamic DNS resolves replacement IP within 5s. | AC-06 | Zero 502 errors |
| **XSS & Injection** | Transmit script tags, HTML markup, SQL strings. | Rendered in DOM via `textContent` as literal characters; zero DOM script execution. | AC-07 | Zero XSS vectors |
| **Input Boundaries** | Send empty text, whitespace, 2,001 chars, binary frame. | Whitespace charges bucket; >2,000 chars rejected with 1008; binary frame rejected with 1003. | AC-07 | Strict rejection |
| **Backpressure / Slow Client** | Throttle socket read loop on Client A; flood messages. | Client A queue overflows (32 events); server terminates Client A with close code 1013; Client B continues unaffected. | AC-13 | Neighbor isolation |
| **Diagnostic Privacy** | Public request to `/live` or `/metrics` via Gateway. | Gateway immediately returns HTTP 403 Forbidden; internal queries return valid OpenMetrics. | AC-14 | Zero public leaks |
| **Network Isolation** | Probe Redis port 6379 from Gateway or Frontend. | TCP SYN packet times out or rejected; no route to host; ACL rejects unauthenticated ping. | AC-17 | Zero route access |
| **Steady Baseline Load** | 25 concurrent clients, 5 msg/s aggregate, 30 min. | p95 latency < 250ms, p99 < 1,000ms, $\ge 99.9\%$ delivery ratio, host free RAM $\ge 256\text{ MiB}$. | AC-16, NFR-01..05 | Zero OOM |

---

## Property-Based Testing Strategy (`hypothesis`)

To prevent parsing ambiguities between Python and JavaScript, property-based tests fuzz boundary text inputs using `hypothesis`:

```python
from hypothesis import given, strategies as st
from app.protocol import normalize_message_text, validate_username

# 1. Fuzz Username Validation
@given(st.text())
def test_fuzz_username_validation(raw_name):
    # Only alphanumeric, hyphen, underscore between 1-32 chars must pass
    import re
    expected = bool(re.match(r"^[A-Za-z0-9_-]{1,32}$", raw_name))
    try:
        result = validate_username(raw_name)
        assert expected is True
        assert result == raw_name
    except ValueError:
        assert expected is False

# 2. Fuzz Unicode Message Normalization
@given(st.text(min_size=1, max_size=5000))
def test_fuzz_message_normalization(raw_text):
    try:
        normalized = normalize_message_text(raw_text)
        # Normalization Invariants:
        assert "\r" not in normalized  # All CRLF converted to LF
        assert len(normalized) <= 2000  # Enforces code point ceiling
        assert not normalized.startswith((" ", "\t", "\n"))  # Trimmed
        assert not normalized.endswith((" ", "\t", "\n"))    # Trimmed
    except ValueError:
        # Rejection must be due to length > 2000 or forbidden C0 controls
        pass
```

---

## Concrete Pytest Async Integration Fixtures

The integration test suite utilizes isolated Docker networks and ephemeral Redis instances:

```python
# tests/integration/test_messaging.py
import pytest
import asyncio
import websockets
import json

@pytest.mark.asyncio
async def test_cross_replica_bidirectional_delivery():
    uri_rep1 = "ws://localhost:8001/ws/Alice_Test"
    uri_rep2 = "ws://localhost:8002/ws/Bob_Test"
    subprotocol = ["chat.v1"]
    headers = [("Origin", "http://localhost")]

    async with websockets.connect(uri_rep1, subprotocols=subprotocol, extra_headers=headers) as ws1, \
               websockets.connect(uri_rep2, subprotocols=subprotocol, extra_headers=headers) as ws2:
        
        # 1. Verify connection-local session envelopes
        session1 = json.loads(await ws1.recv())
        session2 = json.loads(await ws2.recv())
        assert session1["type"] == "session"
        assert session2["type"] == "session"
        assert session1["container_id"] != session2["container_id"]

        # 2. Consume advisory join broadcasts
        _ = await ws1.recv()
        _ = await ws2.recv()

        # 3. Alice sends to Replica 1 -> Bob on Replica 2 receives
        test_payload = "Cross-replica broadcast message 🚀"
        await ws1.send(test_payload)

        # Bob receives chat broadcast
        msg_bob = json.loads(await ws2.recv())
        assert msg_bob["type"] == "chat"
        assert msg_bob["user"] == "Alice_Test"
        assert msg_bob["text"] == test_payload
        assert msg_bob["container_id"] == session1["container_id"]

        # Alice receives echo confirmation via Redis fan-out
        msg_alice = json.loads(await ws1.recv())
        assert msg_alice["event_id"] == msg_bob["event_id"]
        assert msg_alice["text"] == test_payload
```

---

## Chaos Engineering & Fault Injection Runbooks

| Chaos Experiment | Injection Method | Expected Invariant & Recovery Assertion |
| --- | --- | --- |
| **Subscriber Coroutine Freeze** | Send `CLIENT PAUSE 15000` via Redis admin socket. | Backend supervisor detects heartbeat non-acknowledgment; drops `/health` to 503; reconnects fresh subscriber loop. |
| **Redis Network Blackhole** | Inject `iptables -A INPUT -p tcp --dport 6379 -j DROP` on Redis. | TCP socket write/read times out; backends cleanly close active client sockets with code 1011; zero process crashes. |
| **Backend OOM Simulation** | Send rapid burst of 100,000 messages exceeding socket queues. | Sockets with saturated queues drop with code 1013; container memory stays bounded under 192 MiB ceiling. |
| **Gateway Upstream Severance** | Terminate Backend Replica A with `docker kill --signal=KILL`. | Nginx dynamic resolver invalidates upstream within 5s; subsequent WebSocket handshakes automatically route to Replica B. |

---

## High-Precision Monotonic Latency Benchmark Model

Under NFR-01 through NFR-04, end-to-end delivery latency is measured by an external load generator maintaining a single monotonic clock:

```
[Load Generator (Single Clock Process)]
  │
  ├── 1. Timestamp t_send = time.monotonic() (Embedded in message payload marker)
  ├── 2. Dispatch WebSocket frame to Replica 1
  │      └── Proxy -> Backend 1 -> Redis PUBLISH -> Backend 2 -> Fan-out
  └── 3. Recipient on Replica 2 receives frame at t_recv = time.monotonic()
         └── Latency = (t_recv - t_send) * 1000  [Milliseconds]
```

### Mathematical Formulation of Latency Percentiles:
Given ordered observations $L = [l_1, l_2, \dots, l_k]$ where $l_i \le l_{i+1}$:
$$p95 = L_{\lceil 0.95 \times k \rceil}, \quad p99 = L_{\lceil 0.99 \times k \rceil}$$

### Total Delivery Population Accounting:
For $M = 9,000\text{ chat publications}$ ($5\text{ msg/s} \times 1,800\text{s}$) across $C = 25\text{ clients}$:
$$\text{Expected Deliveries } D_{\text{expected}} = M \times C = 9,000 \times 25 = 225,000\text{ recipient deliveries}$$
$$\text{Timely Delivery Ratio } R = \frac{D_{\text{received } \le 2.0\text{s}}}{D_{\text{expected}}} \ge 0.999 \quad (99.9\%)$$

---

## Related Guides

[Requirements](REQUIREMENTS.md) | [Architecture](ARCHITECTURE.md) | [Development](DEVELOPMENT.md) | [Operations](OPERATIONS.md) | [Release Checklist](RELEASE_CHECKLIST.md)

