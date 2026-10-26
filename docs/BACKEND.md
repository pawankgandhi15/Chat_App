# Backend Technology, Concurrency & Engineering Guide

**Design Revision 5 — 2026-10-26. Status: Production Architecture Specification.** This document provides the engineering specifications for the Python 3.12 / FastAPI backend runtime, AsyncIO concurrency models, Redis Pub/Sub supervision, backpressure mechanics, and graceful shutdown lifecycle for Chat App.

---

## 1. Backend Architecture & Modular Decomposition

The backend service runs on Python 3.12 using FastAPI and Uvicorn. To eliminate hidden global state and ensure testability, all components are initialized via FastAPI's `lifespan` manager and explicitly injected into the application state:

```mermaid
flowchart TD
    subgraph Bootstrap["Process Lifecycle & Bootstrap"]
        Main["main.py<br/><i>FastAPI App Lifespan & Signal Handling</i>"]
        Settings["settings.py<br/><i>Immutable Pydantic V2 Configuration</i>"]
    end

    subgraph CoreEngine["Connection & State Engine"]
        Validation["validation.py<br/><i>NFC Unicode, Regex, Length Checks</i>"]
        Limits["limits.py<br/><i>Monotonic Token-Bucket Limiting</i>"]
        Sessions["sessions.py<br/><i>Session Registry & Double-Accounting Deques</i>"]
    end

    subgraph BrokerMesh["Distributed Broker Interface"]
        Protocol["protocol.py<br/><i>Pydantic Wire Envelopes & Serialization</i>"]
        Broker["broker.py<br/><i>Redis Subscriber Supervision & Publisher Pool</i>"]
    end

    subgraph Telemetry["Observability & Gating"]
        Health["health.py<br/><i>Readiness (/health) & Liveness (/live)</i>"]
        Metrics["telemetry.py<br/><i>Prometheus Metrics & Redacted Logging</i>"]
    end

    Main --> Settings
    Main --> Broker
    Main --> Sessions
    Main --> Health
    Main --> Metrics

    Sessions --> Limits
    Sessions --> Validation
    Sessions --> Protocol
    Broker --> Protocol
    Health --> Broker
    Health --> Sessions

    classDef core fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#f8fafc;
    classDef engine fill:#0f172a,stroke:#10b981,stroke-width:2px,color:#f8fafc;
    classDef broker fill:#3b0764,stroke:#a855f7,stroke-width:2px,color:#f8fafc;
    classDef obs fill:#451a03,stroke:#f59e0b,stroke-width:2px,color:#f8fafc;
    class Main,Settings core;
    class Validation,Limits,Sessions engine;
    class Protocol,Broker broker;
    class Health,Metrics obs;
```

---

## 2. Asynchronous Concurrency & Task Topology

For each accepted WebSocket connection, the backend allocates **exactly two cooperative AsyncIO tasks**, enforcing the Single-Writer Principle:

```mermaid
flowchart TD
    subgraph ConnectionScope["Per-Connection Task Allocation"]
        Reader["Reader Task (asyncio.Task)<br/>1. Reads inbound WebSocket frames<br/>2. Reassembles frames (<= 16 KiB)<br/>3. Enforces UTF-8 & code point limits<br/>4. Charges socket TokenBucket (5 burst, 1/s)<br/>5. Publishes valid events to Redis"]

        Writer["Writer Task (Single-Writer Principle)<br/>1. Awaits payloads from DeliveryQueue<br/>2. Flushes JSON frame to transport (timeout: 2.0s)<br/>3. Decrements memory accounting<br/>4. Coordinates clean socket close"]
    end

    subgraph ProcessShared["Process-Wide Asynchronous Services"]
        SubTask["Redis Subscriber Task<br/><i>Single Process-Wide Loop</i><br/>Dispatches messages to session queues"]
        Watchdog["Watchdog Task<br/><i>5s Nonce Prober Loop</i>"]
    end

    Reader -->|PUBLISH| ProcessShared
    ProcessShared -->|Fan-Out try_enqueue| Writer

    classDef task fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#f8fafc;
    class Reader,Writer,SubTask,Watchdog task;
```

### Invariant Rules
1. **The Single-Writer Principle:** The `Reader Task` is strictly forbidden from writing to the raw WebSocket stream (including ping/pong control frames). All network transmissions flow through the dedicated `Writer Task`.
2. **Unbuffered Dispatch:** The `Redis Subscriber Task` iterates across active sessions and invokes `try_enqueue()`. It never awaits I/O or network flushes, guaranteeing that slow consumers cannot delay broadcast distribution to healthy peers.

---

## 3. Double-Accounting Delivery Queue Mechanics

To isolate slow consumers and guarantee that memory remains bounded under network congestion, each session owns a private `DeliveryQueue` enforcing strict **double accounting**:

$$\text{len}(Q) \le 32 \quad \text{AND} \quad \sum_{e \in Q} \text{len}(e.\text{payload\_bytes}) \le 262,144 \text{ bytes } (256\text{ KiB})$$

```python
from collections import deque
from dataclasses import dataclass

@dataclass(slots=True)
class DeliveryQueue:
    max_items: int = 32
    max_bytes: int = 262_144
    items: deque = deque()
    current_bytes: int = 0
    closed: bool = False

    def try_enqueue(self, payload: bytes) -> bool:
        if self.closed:
            return False
        size = len(payload)
        if len(self.items) >= self.max_items or (self.current_bytes + size) > self.max_bytes:
            return False  # Queue saturated: slow consumer detected
        self.items.append(payload)
        self.current_bytes += size
        return True

    def pop_left(self) -> bytes | None:
        if not self.items:
            return None
        payload = self.items.popleft()
        self.current_bytes -= len(payload)
        return payload
```

* **Eviction Policy:** When `try_enqueue()` returns `False` or a socket write times out ($> 2.0\text{s}$), the backend terminates the socket with close code `1013` (Try Again Later) and purges all queued bytes from process memory.

---

## 4. Redis Pub/Sub Supervision & Generational Heartbeat Probing

To guarantee subscriber liveliness and detect silent network partitions, the backend executes a background watchdog prober:

```mermaid
sequenceDiagram
    autonumber
    participant K8s as Kubelet Probe Prober
    participant BE as FastAPI Backend Pod
    participant R as Redis Broker Pod

    Note over BE: Generation 1 Active
    loop Every 5 Seconds
        BE->>R: PUBLISH probe:gen1:<uuid>
        R-->>BE: Echo probe back to subscriber
        BE->>BE: Update last_echo_timestamp = now()
    end

    Note over R: Redis Connection Stalled / Partitioned
    BE-xR: PUBLISH probe:gen1:<uuid> (Message Dropped)
    
    Note over BE: 10s Stale Threshold Breached
    BE->>BE: now() - last_echo_timestamp > 10.0s
    BE->>BE: Set process_state = DEGRADED
    
    K8s->>BE: GET /health (Readiness Probe)
    BE-->>K8s: HTTP 503 Service Unavailable
    Note over K8s: Pod removed from ServiceLB endpoints
    
    Note over BE: Generational Reconnection
    BE->>R: Reconnect & SUBSCRIBE (Generation 2)
    R-->>BE: Subscription Confirmed
    BE->>R: PUBLISH probe:gen2:<new_uuid>
    R-->>BE: Echo probe:gen2:<new_uuid>
    
    BE->>BE: Set process_state = READY (Generation 2 Active)
    K8s->>BE: GET /health (Readiness Probe)
    BE-->>K8s: HTTP 200 OK
```

---

## 5. Graceful Drain & Kubernetes Lifecycle Timeline

When the container receives `SIGTERM` from the Kubelet during a rolling deployment, the backend coordinates a multi-stage graceful shutdown:

```mermaid
sequenceDiagram
    autonumber
    participant K8s as Kubelet Controller
    participant Endpoints as K3s Endpoint Controller
    participant App as FastAPI Backend
    participant Writer as Connection Writers
    participant Client as Browser Sockets

    K8s->>App: SIGTERM Signal
    Note over App: Phase 1: Fail Readiness
    App->>App: Set process_state = DRAINING (/health returns 503)
    Endpoints->>Endpoints: Asynchronously remove Pod IP from Service
    
    Note over App: Phase 2: Refuse Ingress
    App->>App: Reject all new /ws/* handshakes with HTTP 503
    
    Note over App: Phase 3: Paced Connection Drain (10s Budget)
    loop Active Sockets
        App->>Writer: Trigger Close Frame 1012 (Service Restart)
        Writer->>Client: Send Close Frame 1012
        Client->>Client: Reconnect with full jitter to surviving Pod
    end
    
    Note over App: Phase 4: Teardown Dependencies
    App->>App: Unsubscribe Redis & close publisher pool
    App->>K8s: Process exits cleanly (Exit Code 0 within 20s grace)
```

---

## 6. Observability & Low-Cardinality Prometheus Metrics

Metrics are exposed at `GET /metrics` in standard OpenMetrics exposition format. Metric labels are strictly bounded to prevent high-cardinality memory leaks:

| Metric Name | Type | Labels | Description |
| :--- | :--- | :--- | :--- |
| `chat_connections_active` | Gauge | `replica_id` | Current number of active admitted client WebSocket connections. |
| `chat_messages_published_total` | Counter | `replica_id`, `status` (`ok`, `timeout`, `rate_limited`) | Total messages published to Redis bus. |
| `chat_deliveries_total` | Counter | `replica_id`, `status` (`sent`, `queue_overflow`, `timeout`) | Total outbound frames flushed to local client sockets. |
| `chat_outbound_queue_bytes` | Gauge | `replica_id` | Total memory bytes currently queued across all client queues. |
| `chat_heartbeat_latency_seconds` | Histogram | `replica_id` | End-to-end round-trip latency of generational watchdog nonces. |
