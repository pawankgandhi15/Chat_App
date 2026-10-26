# Project Requirements

**Status:** Proposed requirements; no implementation exists. See the [documentation index](../README.md).

**Design Revision 4 (2026-10-25):** Advanced production-grade baseline establishing strict interface contracts, quantitative reliability and recovery objectives, multi-tenant isolation boundaries, and deterministic acceptance criteria.

## Purpose

Design and deploy a containerized real-time chat application demonstrating distributed WebSockets, asynchronous messaging via Redis Pub/Sub, infrastructure as code (Terraform), secure automated delivery (GitHub Actions CI/CD with supply-chain provenance), and resilient operational recovery on a resource-constrained cloud environment (single AWS EC2 instance).

## Users and Main Journey

1. **Discovery & Connection:** A visitor opens the application URL through the reverse-proxy gateway (Nginx).
2. **Session Admission:** The browser initializes the chat runtime, generates an ephemeral display name, and requests an upgraded WebSocket connection at `/ws/{username}` negotiating the `chat.v1` subprotocol.
3. **Session Handshake:** The selected backend validates origin, username syntax, and capacity; reserves an admission slot; upgrades the connection; and immediately dispatches a private, connection-local `session` envelope establishing the client's session UUID and serving container identity.
4. **Presence Notification:** Once the backend's Redis subscriber acknowledges readiness, an advisory `system` join event is published to the shared Redis bus and broadcast to all connected clients across all backend replicas.
5. **Real-time Interaction:** The visitor views live connection status, system announcements, and user chat messages. Senders emit plain text messages; backends validate, envelope, and publish to Redis; and all backends fan out the message to their local client queues.
6. **Graceful Degraded & Reconnect States:** On network loss or server restart, the client transitions to an explicit reconnecting state with exponential backoff and full jitter. If the server is in a draining state, it closes active connections with code `1012` (Service Restart), prompting immediate reconnection to an alternate healthy replica without user intervention. If offline retries are exhausted, the client enters an explicit paused state requiring manual retry without resending unacknowledged drafts.

Display names are non-authoritative presentation labels. Verified authentication and guaranteed identity uniqueness are outside the baseline scope.

## Functional Requirements

| ID | Requirement | Specification Details |
| --- | --- | --- |
| FR-01 | Responsive Web Interface | Serve an accessible, semantic HTML5/CSS3/JavaScript interface through `/` via the Nginx frontend server without external CDN dependencies. |
| FR-02 | Versioned WebSocket Endpoint | Accept WebSocket connections at `/ws/{username}` enforcing mandatory subprotocol negotiation for `chat.v1`. Reject unnegotiated handshakes with HTTP 400/403. |
| FR-03 | Distributed Event Bus | Publish all validated chat, join, and leave events to a single project-scoped Redis Pub/Sub channel (`global_chat_channel` by default). |
| FR-04 | Asynchronous Fan-Out | Each backend replica subscribes to Redis and asynchronously dispatches events to its local active client delivery queues without blocking the subscriber loop. |
| FR-05 | Correlated Event Enveloping | Broadcast events must encapsulate: `schema_version` (int), `event_id` (UUIDv4), `sent_at` (ISO 8601 / RFC 3339 UTC with millisecond precision), `type` (`chat` or `system`), `user` (string), `text` (string), `container_id` (hostname), and `time` (HH:MM:SS UTC). |
| FR-06 | Multi-Replica Backend Mesh | Run two or more independent FastAPI backend replicas behind the gateway without exposing individual backend container ports to the host or public internet. |
| FR-07 | Multi-Tier Health & Liveness | Expose `/health` for dependency-aware readiness (probing Redis connectivity and subscriber loop freshness) and internal `/live` for process event-loop responsiveness. |
| FR-08 | Secure Input Validation & Rendering | Enforce strict UTF-8 code point limits (1-32 chars for usernames, 1-2000 code points for messages), reassembled frame byte ceilings (16 KiB), and inert text rendering via `textContent` to eliminate XSS. |
| FR-09 | Deterministic Connection Recovery | Client handles disconnects with bounded jittered exponential backoff. Preserves read history in the DOM (up to 500 entries) while explicitly marking disconnected messages as unrecovered. |
| FR-10 | Immutable Digest Releases | Package frontend and backend into OCI containers pinned by SHA-256 digests in production, built once and traced via unique `RELEASE_ID` values. |
| FR-11 | Connection-Local Handshake | Emit a direct `session` envelope to the connected client before any broadcast events, confirming socket UUID and serving replica without polluting the Redis bus. |
| FR-12 | Granular Telemetry Exposition | Expose private Prometheus-formatted metrics at `/metrics` (accessible only within internal networks, denied by the public gateway) measuring active connections, message throughput, queue lag, and dependency latencies. |
| FR-13 | Bounded Resource Accounting | Enforce per-socket token-bucket rate limits, replica-wide publication rate limits, per-socket outbound queue depths (32 events / 256 KiB), and graceful shutdown timeouts. |
| FR-14 | Segmented Network Topologies | Isolate proxy-facing traffic (`edge_network`) from data persistence (`data_network`). Redis must strictly reside within `data_network` with zero gateway or frontend reachability. |
| FR-15 | Slow Consumer Mitigation | If a client's outbound queue overflows or socket write exceeds timeout (2s), the backend forcibly terminates that socket with WebSocket close code `1013` (Try Again Later), protecting neighbor sockets. |
| FR-16 | Graceful Drain & Handoff | On SIGTERM, the backend transitions readiness to 503, stops accepting new handshakes, emits close frame `1012` to active sockets across a 10s drain budget, cleanly unsubscribes from Redis, and terminates within a 20s container grace window. |
| FR-17 | Authenticated Redis ACLs | Support authenticated Redis access via Docker secret mounts (`REDIS_URL_FILE`), restricting the application user to specific Pub/Sub channels and commands while disabling administrative commands. |
| FR-18 | Strict Header & Origin Enforcement | Gateway sanitizes and rewrites `Host`, `X-Forwarded-For`, and `X-Forwarded-Proto` headers; backend strictly validates `Origin` against a configured allowlist before upgrade. |

## Operational Requirements

- **Zero Host Contamination:** All application runtime services, database instances, reverse proxies, and integration test harnesses must execute strictly within Docker containers.
- **Network Ingress Protection:** Only gateway ports 80 and 443 are published to the host network interface. Backend port 8000 and Redis port 6379 remain strictly container-private.
- **Single-Worker Concurrency:** Each FastAPI backend replica runs as a single Uvicorn ASGI worker to maintain predictable asyncio task scheduling and avoid intra-container inter-process synchronization complexity.
- **Reproducible Infrastructure:** All cloud infrastructure (AWS VPC, subnets, route tables, security groups, EBS volumes, EC2 instance) is declared and provisioned via Terraform with pinned provider versions and remote/isolated state management.
- **Strict Memory & Log Ceilings:** Docker containers enforce explicit memory limits (`mem_limit`), CPU shares, PID limits, and log rotation (`max-size: 10m`, `max-file: 3`) to prevent out-of-memory kernel panics or disk exhaustion on a `t3.micro` host.
- **Observability Without Data Leakage:** Structured JSON logging captures lifecycle events, error classes, and duration percentiles while strictly redacting user message payloads, raw IP addresses, and authentication tokens.
- **Deterministic Rollback:** Support atomic rollbacks to the preceding verified release manifest within 10 minutes in response to failed deployment health or functional verification checks.

## Acceptance Criteria

| ID | Criterion | Evidence Needed for Verification |
| --- | --- | --- |
| AC-01 | Baseline Topology Spin-up | Clean `docker compose up -d` brings up gateway, frontend, two backend replicas, and Redis (5 containers across 4 services); frontend loads with HTTP 200 via gateway. |
| AC-02 | Bidirectional Cross-Replica Messaging | Client A (attached to Replica 1) and Client B (attached to Replica 2) successfully exchange messages; each receives the other's message with the counterpart's `container_id`. |
| AC-03 | No Duplicate Local Deliveries | A message published by Client A arrives exactly once at Client A and once at Client B under normal healthy operation (verifying publisher does not locally echo before Redis fan-out). |
| AC-04 | Envelope Schema Compliance | Broadcast events strictly conform to JSON Schema `events-v1.schema.json` with valid UUIDv4 `event_id`, ISO 8601 `sent_at`, matching `time` string, and correct event type. |
| AC-05 | Dependency Outage & Recovery | Stopping Redis causes both backends to transition `/health` to 503 and reject new sessions; restarting Redis restores `/health` to 200 and restores cross-replica messaging without backend restart. |
| AC-06 | Replica Replacement & Dynamic Routing | Killing or restarting one backend container causes its connected clients to reconnect; Nginx dynamic DNS upstream resolution routes new connections to the healthy/replacement container without 502 errors. |
| AC-07 | XSS Immunity & Input Boundary Enforcement | HTML tags, `<script>` payloads, and unicode control characters sent as chat messages render as literal text in the browser DOM. Messages exceeding 2,000 code points or 16 KiB are rejected with close code 1009/1008. |
| AC-08 | Automated Quality & Security Gate | Pull requests and CI runs must pass linting, contract tests, unit tests, integration tests, and Trivy container vulnerability scanning (zero High/Critical CVEs with fixes) before release builds. |
| AC-09 | Proven Rollback Rehearsal | An operator or deployment pipeline can roll back an active deployment to the prior recorded release manifest, verifying container image digest replacement and healthy messaging within 10 minutes. |
| AC-10 | Documented Capacity & Resource Profile | Resource consumption (CPU, memory, file descriptors, network) and latency distributions under candidate load are documented with raw test artifacts. |
| AC-11 | Clean Infrastructure Teardown | `terraform destroy` successfully removes all provisioned AWS cloud resources with verified zero orphaned volumes, Elastic IPs, or billing leakage. |
| AC-12 | Session Handshake & Subprotocol Verification | Connection negotiation requires subprotocol `chat.v1`. First message received by the client is a valid `session` envelope establishing socket UUID before any broadcasts arrive. |
| AC-13 | Backpressure & Slow Client Isolation | A simulated slow consumer with suspended read operations does not delay message delivery to healthy peers. The slow consumer's buffer overflows and is cleanly terminated with close code 1013. |
| AC-14 | Private Diagnostics & Structured Observability | Direct external requests to `/live` and `/metrics` through the gateway are blocked with HTTP 403/404. Internal queries return valid OpenMetrics and JSON health status. Application logs are structured JSON with redacted payloads. |
| AC-15 | Supply Chain & Manifest Integrity | Release deployments require a cryptographically verified `release.json` manifest matching exact container image SHA-256 digests, configuration hashes, and software bill of materials (SBOM). |
| AC-16 | Quantitative Performance Target Compliance | Candidate workload evaluated under NFR-01 through NFR-08 with empirical latency percentiles (p50, p95, p99), zero packet/delivery duplication, and verified host memory headroom. |
| AC-17 | Network Boundary Enforcement | Containers on `edge_network` (gateway, frontend) are incapable of establishing TCP connections to Redis port 6379 on `data_network`. Redis ACLs deny unauthorized commands and channels. |
| AC-18 | Subscriber Heartbeat & Generation Nonce | The subscriber loop uses periodic nonce-tagged heartbeats. A stale or stalled subscriber connection fails readiness even if publisher PINGs succeed, preventing silent message loss. |

## Measurable Engineering Targets

These targets define the quantitative envelope for system acceptance testing under controlled experimental conditions on a single `t3.micro` EC2 instance (1 vCPU, 1 GiB RAM, burstable CPU credits).

| ID | Metric / Target | Target Value | Measurement Methodology & Boundary |
| --- | --- | --- | --- |
| NFR-01 | Concurrent Admitted Clients | 25 active concurrent clients | External load generator maintaining 25 persistent WebSocket connections evenly distributed across both replicas (12-13 per replica). |
| NFR-02 | Aggregate Message Throughput | 5 chat messages / sec sustained | 512-byte payloads, Poisson or uniform arrival across clients, sustained for 30 minutes following a 2-minute warmup. |
| NFR-03 | End-to-End Delivery Latency | p95 < 250 ms, p99 < 1,000 ms | Measured from client send timestamp to recipient receipt timestamp using a single monotonic clock on the external load testing node. |
| NFR-04 | Message Delivery Reliability | >= 99.9% timely delivery | Expected deliveries = $M \times C$ (messages published $\times$ connected clients). Timely arrival within 2.0s. Zero duplicate event IDs per recipient. |
| NFR-05 | Dependency Recovery Time | Readiness <= 15s; Client <= 60s | Following Redis restoration: backend `/health` returns 200 within 15s; active-retrying clients re-establish session and receive live messages within 60s. |
| NFR-06 | Host Resource Headroom | Available RAM >= 256 MiB | Linux `MemAvailable` on host during steady-state baseline run >= 256 MiB. Zero swap thrashing or Linux OOM-killer invocations. |
| NFR-07 | Graceful Drain Window | 10s drain in 20s stop grace | On SIGTERM, stop new handshakes immediately; close active sockets with code 1012 within 10s; release tasks and Redis resources within 20s. |
| NFR-08 | Rollback Recovery RTO | Recovery Time <= 10 minutes | Time elapsed from operator rollback invocation to verified functional messaging on the restored release manifest. |

## Fault Tolerance & Degraded States

```
+-----------------------------------------------------------------------------+
|                            FAULT TOLERANCE MATRIX                           |
+-------------------+----------------------------+----------------------------+
| Fault Scenario    | System Behavior            | Client Experience          |
+-------------------+----------------------------+----------------------------+
| Single Backend    | Sockets on that replica    | Browser detects close code |
| Crash / Restart   | drop; other replica stays  | 1012 or abnormal drop;     |
|                   | fully functional.          | reconnects to alternate    |
|                   | Gateway updates upstream.  | replica with jitter.       |
+-------------------+----------------------------+----------------------------+
| Redis Outage      | Backends detect failed     | Active sessions terminated |
| (Process stop or  | subscriber heartbeat;      | with code 1011; UI shows   |
| network partition)| `/health` returns 503;     | "Connecting..." with retry |
|                   | active sockets closed.     | backoff; sends disabled.   |
+-------------------+----------------------------+----------------------------+
| Slow Consumer     | Outbound socket queue hits | Slow client terminated     |
| (Client network   | 32 events or 256 KiB;      | with code 1013; healthy    |
| throttled/halted) | sender task cancels socket.| peers continue unaffected. |
+-------------------+----------------------------+----------------------------+
| High Message Burst| Token bucket drains; per-  | Excess messages rejected   |
| (Rate limit abuse)| socket limit triggers close| with code 1008/1013; error |
|                   | or drop; neighbors safe.   | feedback displayed in UI.  |
+-------------------+----------------------------+----------------------------+
```

## User-Visible Reliability Rules

- **Clear Connection States:** The UI exposes five unambiguous states: `Connecting`, `Connected`, `Reconnecting (Attempt X/10)`, `Paused (Manual Retry Required)`, and `Protocol Error`.
- **Gated Sending:** The input field and submit button remain strictly disabled until a valid connection-local `session` envelope is processed.
- **No Invisible Draft Re-submission:** If a connection drops while the user is typing, the draft text is preserved in the input box, but it is **never** automatically submitted upon reconnect without explicit user action.
- **Non-disruptive Reading:** Incoming messages do not hijack scroll position if the user has scrolled up to inspect message history. A floating "New messages below" indicator alerts the user.
- **Bounded Local History:** The DOM retains a maximum of 500 messages to prevent browser tab memory exhaustion during extended sessions. Older nodes are purged from the top of the chat stream.

## Design Authority & Evolution

This document is the authoritative owner of system scope, functional boundaries, and measurable targets. 
- Wire formats are governed by [API_SPECIFICATION.md](API_SPECIFICATION.md).
- Architectural patterns and state ownership are governed by [ARCHITECTURE.md](ARCHITECTURE.md).
- Configuration variables and defaults are governed by [CONFIGURATION.md](CONFIGURATION.md).
- Verification methodologies are governed by [TESTING.md](TESTING.md).
- Security controls are governed by [SECURITY.md](SECURITY.md).
- Infrastructure specifications are governed by [INFRASTRUCTURE.md](INFRASTRUCTURE.md).

Any modifications to performance targets, acceptance criteria, or functional boundaries must be recorded in [DECISIONS_AND_RISKS.md](DECISIONS_AND_RISKS.md) and reflected across dependent guides.

## Scope Boundaries (Explicitly Deferred)

The following capabilities are deliberately excluded from the current single-host baseline:
- Persistent user accounts, password authentication, OAuth2/OIDC login.
- Multi-room routing, channel switching, and direct private messaging.
- Media/file attachments, audio/video streaming, WebRTC.
- Durable message storage, historical message querying, and read receipts.
- Multi-host clustering, Kubernetes/EKS orchestration, AWS ALB/NLB.
- End-to-end client-side message encryption.

## Related Guides

[Architecture](ARCHITECTURE.md) | [API Specification](API_SPECIFICATION.md) | [Configuration](CONFIGURATION.md) | [Testing](TESTING.md) | [Security](SECURITY.md) | [Decisions and Risks](DECISIONS_AND_RISKS.md)

