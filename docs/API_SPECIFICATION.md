# API & WebSocket Wire Specification

**Status: Production Architecture Specification. Baseline: Design Revision 5 (Reviewed 2026-10-26).**

This document establishes the authoritative wire protocol contracts, discriminated JSON schemas, RFC 6455 WebSocket frame invariants, strict Unicode normalization rules, denial and close code semantics, and OpenMetrics telemetry exposition for Chat App.

---

## 1. HTTP & WebSocket Route Matrix

| Route | Protocol | Exposure Boundary | Auth & Security Policy | Response & Wire Behavior |
| :--- | :--- | :--- | :--- | :--- |
| `/` | HTTP GET | Public (via Gateway) | None | Serves static frontend shell (`index.html`). |
| `/assets/*` | HTTP GET | Public (via Gateway) | None | Serves immutable static CSS, JS, and image assets with caching headers. |
| `/health` | HTTP GET | Cluster-Private (Denied by Gateway) | NetworkPolicy enforced | Kubernetes readiness probe. Returns HTTP 200 `{"status":"healthy",...}` or 503 `{"status":"degraded",...}`. |
| `/live` | HTTP GET | Cluster-Private (Denied by Gateway) | NetworkPolicy enforced | Process event-loop liveness probe. Returns HTTP 200 `{"status":"alive"}`. Never queries Redis. |
| `/metrics` | HTTP GET | Cluster-Private (Denied by Gateway) | NetworkPolicy enforced | Prometheus / OpenMetrics text exposition for authorized scraping. |
| `/ws/{username}` | WebSocket (WS/WSS) | Public (via Gateway) | `Origin` checked against `ALLOWED_ORIGINS` | Real-time chat connection enforcing subprotocol `chat.v1`. |

---

## 2. Health, Liveness & Metrics Specifications

### 2.1 Readiness Probe: `GET /health`
* **Purpose:** Controls backend endpoint inclusion in the `backend` Kubernetes Service.
* **Success (`200 OK`):** Returned only when the backend can execute `PING` on Redis within `REDIS_COMMAND_TIMEOUT_SECONDS` (1.0s) **AND** the subscriber heartbeat was echoed within `SUBSCRIBER_STALE_SECONDS` (10s) on the current generation nonce.
* **Failure (`503 Service Unavailable`):** Returned if the process is starting up, in `DRAINING` state, Redis is unreachable, or the subscriber coroutine has stalled.

```json
{
  "status": "healthy",
  "container_id": "backend-7f8d6c4b5-x2z9q",
  "timestamp": "2026-10-26T21:15:30.125Z",
  "release_id": "20261026.1-sha.4c6607d",
  "subsystems": {
    "redis_connection": "connected",
    "subscriber_heartbeat": "fresh",
    "generation_nonce": 4,
    "active_connections": 18,
    "capacity_available": 46
  }
}
```

### 2.2 Process Liveness: `GET /live`
* Returns HTTP 200 `{"status": "alive", "timestamp": "..."}` as long as the Python `asyncio` event loop can dispatch coroutines. This probe **never** queries Redis.

### 2.3 Telemetry Exposition: `GET /metrics`
Exposes OpenMetrics / Prometheus standard text exposition format:

```text
# HELP chat_connections_active Current number of active admitted client WebSocket connections
# TYPE chat_connections_active gauge
chat_connections_active{replica_id="backend-7f8d6c4b5-x2z9q"} 18

# HELP chat_messages_published_total Total messages published to Redis bus
# TYPE chat_messages_published_total counter
chat_messages_published_total{replica_id="backend-7f8d6c4b5-x2z9q",status="ok"} 4120
chat_messages_published_total{replica_id="backend-7f8d6c4b5-x2z9q",status="timeout"} 0
chat_messages_published_total{replica_id="backend-7f8d6c4b5-x2z9q",status="rate_limited"} 3

# HELP chat_deliveries_total Total outbound messages sent to local client sockets
# TYPE chat_deliveries_total counter
chat_deliveries_total{replica_id="backend-7f8d6c4b5-x2z9q",status="sent"} 74160
chat_deliveries_total{replica_id="backend-7f8d6c4b5-x2z9q",status="queue_overflow"} 1

# HELP chat_outbound_queue_bytes Total bytes currently queued across all client queues
# TYPE chat_outbound_queue_bytes gauge
chat_outbound_queue_bytes{replica_id="backend-7f8d6c4b5-x2z9q"} 14336
```

---

## 3. WebSocket Handshake & Subprotocol Negotiation

1. **Mandatory Subprotocol:** The client must supply `Sec-WebSocket-Protocol: chat.v1`. The backend echoes `Sec-WebSocket-Protocol: chat.v1` in the HTTP 101 response. Sockets without this header are rejected before upgrade.
2. **Pre-Upgrade Denial Responses:**
   * **Origin Forbidden:** HTTP 403 Forbidden (`{"error": "forbidden_origin"}`).
   * **Invalid Username:** HTTP 400 Bad Request (`{"error": "invalid_username"}`).
   * **Capacity Exhaustion / Server Draining:** HTTP 503 Service Unavailable (`{"error": "server_busy_or_draining"}`).
3. **Username Lexical Specification:** Must match regex `^[A-Za-z0-9_-]{1,32}$`. Exactly 1 to 32 ASCII alphanumeric characters, hyphens, or underscores. Path traversal segments (`../`), spaces, or non-ASCII characters are immediately rejected.

---

## 4. Discriminated JSON Message Envelopes (`chat.v1`)

All JSON payloads exchanged over WebSocket or Redis Pub/Sub enforce `schema_version: 1` with a strict `type` discriminator and reject additional properties (`extra="forbid"`).

### 4.1 Connection-Local `session` Envelope
Dispatched directly from the serving backend to the newly connected socket. **Never** published to Redis.

```json
{
  "schema_version": 1,
  "type": "session",
  "connection_id": "5b2420aa-520f-4f0a-aea6-2a0d571098cf",
  "container_id": "backend-7f8d6c4b5-x2z9q",
  "user": "alice_99",
  "sent_at": "2026-10-26T21:15:30.100Z"
}
```

### 4.2 Broadcast `chat` Envelope
Constructed by the backend upon receiving valid plain text from a client, dispatched via Redis Pub/Sub, and fanned out to all connected clients.

```json
{
  "schema_version": 1,
  "type": "chat",
  "event_id": "7228a607-018c-45bb-91fd-3a7a0bad84a3",
  "sent_at": "2026-10-26T21:15:32.125Z",
  "user": "alice_99",
  "text": "Hello, distributed real-time world! 🚀",
  "container_id": "backend-7f8d6c4b5-x2z9q",
  "time": "21:15:32 UTC"
}
```

### 4.3 Broadcast `system` Envelope
Generated by backends for advisory join, leave, or administrative announcements.

```json
{
  "schema_version": 1,
  "type": "system",
  "event_id": "c138d4f2-90ab-48e3-b31c-529a8a701df1",
  "sent_at": "2026-10-26T21:15:30.150Z",
  "user": "alice_99",
  "text": "User alice_99 has joined the room.",
  "container_id": "backend-7f8d6c4b5-x2z9q",
  "time": "21:15:30 UTC"
}
```

### 4.4 Formal JSON Schema Specification (`events-v1.schema.json`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://chatapp.internal/schemas/events-v1.schema.json",
  "title": "ChatAppV1EventEnvelope",
  "oneOf": [
    {
      "type": "object",
      "required": ["schema_version", "type", "connection_id", "container_id", "user", "sent_at"],
      "properties": {
        "schema_version": { "const": 1 },
        "type": { "const": "session" },
        "connection_id": { "type": "string", "format": "uuid" },
        "container_id": { "type": "string", "minLength": 1, "maxLength": 64 },
        "user": { "type": "string", "pattern": "^[A-Za-z0-9_-]{1,32}$" },
        "sent_at": { "type": "string", "format": "date-time" }
      },
      "additionalProperties": false
    },
    {
      "type": "object",
      "required": ["schema_version", "event_id", "sent_at", "type", "user", "text", "container_id", "time"],
      "properties": {
        "schema_version": { "const": 1 },
        "event_id": { "type": "string", "format": "uuid" },
        "sent_at": { "type": "string", "format": "date-time" },
        "type": { "enum": ["chat", "system"] },
        "user": { "type": "string", "minLength": 1, "maxLength": 32 },
        "text": { "type": "string", "minLength": 1, "maxLength": 2000 },
        "container_id": { "type": "string", "minLength": 1, "maxLength": 64 },
        "time": { "type": "string", "pattern": "^[0-9]{2}:[0-9]{2}:[0-9]{2} UTC$" }
      },
      "additionalProperties": false
    }
  ]
}
```

---

## 5. Client Inbound Frame & Unicode Normalization Rules

Clients transmit raw plain text WebSocket frames (Opcode `0x1`).
1. **Reassembled Frame Byte Limit:** Maximum 16,384 bytes ($16\text{ KiB}$) ceiling across all reassembled WebSocket frames before text parsing.
2. **Binary Frame Rejection:** Opcode `0x2` (Binary) frames trigger immediate close code `1003` (Unsupported Data).
3. **CRLF Normalization:** Convert `\r\n` and standalone `\r` to single `\n` line feeds.
4. **Boundary Trimming:** Strip leading and trailing ASCII whitespace only (`U+0020`, `U+0009`, `U+000D`, `U+000A`). Empty trimmed messages are ignored without error, but the socket token bucket is charged.
5. **Control Character Filtering:** Reject ASCII C0 control characters (`U+0000` to `U+001F` except tab `\t` and newline `\n`) and DEL (`U+007F`) with close code `1008`.
6. **Code Point Length Bounds:** After trimming, length must be $\ge 1$ and $\le 2,000$ Unicode code points.

---

## 6. WebSocket Close Code Matrix

| Code | Standard Name | Trigger Scenario | Client Action |
| :--- | :--- | :--- | :--- |
| `1000` | Normal Closure | User clicks "Disconnect" or closes browser tab cleanly. | Terminal; no reconnect. |
| `1001` | Going Away | Browser window navigates to a new URL. | Terminal; no reconnect. |
| `1003` | Unsupported Data | Client transmitted a binary WebSocket frame. | UI displays protocol error; no automatic reconnect. |
| `1007` | Invalid Payload Data | Transport encountered malformed UTF-8 byte sequences. | UI displays encoding error; no automatic reconnect. |
| `1008` | Policy Violation | Disallowed control characters, failed origin check, or invalid syntax. | UI displays policy error; no automatic reconnect. |
| `1009` | Message Too Big | Inbound frame reassembly exceeded 16,384 bytes. | UI alerts user message was too large; no auto-reconnect. |
| `1011` | Internal Server Error | Unhandled backend exception or unexpected Redis failure. | UI transitions to reconnecting with exponential backoff. |
| `1012` | Service Restart | Planned container shutdown / drain (`SIGTERM`). | UI immediately attempts jittered reconnection to alternate replica. |
| `1013` | Try Again Later | Outbound queue overflow (slow consumer) or rate limit exhausted. | UI pauses briefly; reconnects with exponential backoff. |
