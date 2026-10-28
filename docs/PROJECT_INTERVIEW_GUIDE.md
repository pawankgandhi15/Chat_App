# Baatchit: Complete Project and Interview Guide (Easy + Advanced Edition)

**Historical snapshot:** 27 October 2026. Most of this interview guide describes the original anonymous public-room baseline and its measured local tests. On 28 October, React and session-based direct messaging were added; use [Direct messaging](DIRECT_MESSAGING.md) and [Implementation status](IMPLEMENTATION_STATUS.md) for the current behavior and evidence. AWS deployment remains a target.

When a design document disagrees with the running code, the source code and the implementation status file win. Commands and defaults can change after this snapshot, so re-check the linked files before repeating a deployment.

**Frontend update — 28 October 2026:** React 19 and Vite 8 now provide the presentation/build layer. Frontend descriptions and source links below reflect this migration. The 42-test and load results remain the original October 27 baseline; see [implementation status](IMPLEMENTATION_STATUS.md) for the separate React checks.

## How to read this guide

- **Simple view** boxes explain an idea in plain words. Read these first.
- **Deep dive** boxes add the engineering detail, math, and trade-offs. Read these when you want interview-level depth.
- **Proposal** labels mark ideas that are NOT implemented. Never present a proposal as a feature.
- Numbers marked **measured** came from a real run. Numbers marked **target** or **nominal** are plans or limits, not results.
- **Interview practice:** 130 questions cover the project and system design. Start with questions 1–50, continue with [system design questions 51–80](#system-design-requirements-and-capacity-planning), then use [deep system design questions 81–130](#deep-system-design-concurrency-and-parallel-execution) for concurrency, sharding, replication, networking, databases and production trade-offs.

## 1. The answer in 30 seconds

> I built Baatchit, a React-based real-time chat with two FastAPI WebSocket replicas behind Nginx. Redis Pub/Sub carries public messages and routes direct events to the two selected sessions. The system includes strict protocol validation, bounded queues and rate limits, Kubernetes policies and release tooling. The original public-room deployment was verified locally on k3d; the newer direct-message path has been checked with a Pub/Sub test double and browser mocks. AWS provisioning and full-stack verification of direct messaging remain pending.

**Do not say:** WhatsApp clone, production high-availability service, or deployed AWS application. Session-based direct messaging exists, but it has no verified identity or end-to-end encryption. There are no accounts, durable database, or offline delivery.

### The two-minute explanation

1. The browser opens the Nginx gateway. Nginx serves the static UI and proxies `/ws/{username}` to the backend Service.
2. The backend checks the exact `Origin`, a supported `chat.v2` or `chat.v1` subprotocol, the username, Redis subscriber readiness, and replica capacity before accepting the socket.
3. It sends a private `session` event first. The browser enables sending only after it validates that event.
4. A v2 browser sends a JSON public or direct command; v1 clients send public plain text. The backend validates it, applies rate limits, adds a server-owned event ID and timestamp, and publishes once to Redis.
5. Both backend replicas subscribe to the same Redis channel. Public messages fan out locally; direct events are queued only for the sender and recipient session IDs. Separate writer tasks stop one slow client from blocking others.
6. Delivery is live and ephemeral. Redis Pub/Sub stores nothing and replays nothing, so the UI never promises delivery just because `send()` worked.
7. Local k3d validates the whole topology. The AWS design is one EC2 host running K3s, so the host and Redis remain single points of failure.

> **Simple view: the loudspeaker analogy.** Imagine a building with two reception desks (the two backends). Visitors (browsers) are each served by one desk. When a visitor writes a note, their desk reads it out on a shared loudspeaker (Redis). Both desks hear the loudspeaker and hand the note to all their own visitors. The loudspeaker keeps no recordings: if you were out of the room, you missed it.

## 2. Problem, scope, and success criteria

Baatchit demonstrates multi-replica real-time messaging on a small infrastructure budget. The central problem: **a WebSocket belongs to one backend process, but a message must reach sockets on both processes.** Redis Pub/Sub bridges the two sets of connections.

| Dimension | Implemented baseline |
| --- | --- |
| Product | One public `#general` room and direct messaging between active sessions, anonymous temporary names and advisory join/leave messages |
| Client | Responsive desktop and mobile UI, in-memory draft and recent events, connection feedback |
| Identity | No login. Names can be reused or impersonated |
| Durability | None. Missed events cannot be replayed |
| Scale model | Two backend Pods, one Redis Pod, 64 admitted connections per backend by default |
| Local runtime | k3d cluster, five application Pods across four Deployments |
| Cloud target | One EC2 instance with K3s. Code exists, cloud run pending |

**Target workload (not yet an AWS result):** 25 simultaneous clients, 5 aggregate messages per second at 512 bytes, a 2-minute warmup, a 30-minute measured period, at least 99.9% delivered within 2 seconds, p95 latency under 250 ms, p99 under 1 second, and at least 512 MiB of host `MemAvailable`.

> **Deep dive: what the target means in numbers.**
> - 30 minutes at 5 msg/s = 9,000 messages. With 25 clients that is 9,000 x 25 = **225,000 expected deliveries**.
> - A 99.9% on-time rate allows at most **225 late or missing deliveries** in the whole run.
> - Fanout rate: 5 x 25 = **125 deliveries/s**. At 512-byte payloads that is about 64,000 payload bytes/s (roughly 0.5 Mbit/s) before JSON, WebSocket, TCP and TLS overhead.
> - The configured budgets are far above this: 20 publishes/s per replica (40/s across two) against a 5/s target, so the rate limiter is not the expected bottleneck. CPU, memory and network on one small host are.

## 3. Architecture and data ownership

```
Browser tabs --HTTP/WS (HTTPS/WSS in AWS)--> Nginx gateway
   Gateway --static files--------------------> Frontend (Nginx)
   Gateway --WebSocket upgrade---------------> backend Service
                                                 |-> FastAPI Pod A <--PUBLISH/SUBSCRIBE--> Redis
                                                 |-> FastAPI Pod B <--PUBLISH/SUBSCRIBE--> Redis
   Cluster diagnostics --private--> /health /live /metrics on each backend Pod
```

| Component | Responsibility | What it owns |
| --- | --- | --- |
| Browser | UI, draft, validation, reconnect state | One tab's draft, session, and at most 500 recent events (not persisted) |
| Gateway | Public entry, HTTP/WSS routing, TLS in AWS, security headers, handshake rate limit | No chat data |
| Frontend server | Serves static HTML, CSS, JS | Versioned image assets |
| Backend Pod | Admission, validation, event creation, connection queues | Its own sockets and per-process metrics |
| Redis | Shared channel `global_chat_channel` | Live fanout only. Persistence disabled |
| Kubernetes | Service routing, desired Pods, probes, isolation | Orchestration, not chat history |
| Terraform | AWS network, EC2/EBS, S3 state bootstrap | Declarations, not a deployed account |

**Why two backend Pods?** Each Pod holds only its own sockets. The Service picks a Pod per connection but never copies messages between Pods. Both Pods subscribe to Redis, so one published event reaches each Pod once under healthy conditions. The sender also gets its own message back through Redis; there is no separate local echo.

**Failure domains.** A Pod restart is recovered by browser reconnect. Losing Redis makes the room unavailable. Losing the host takes everything down. Two replicas demonstrate distributed state, not host-level high availability.

> **Simple view.** Two backends = two doors into the same room, not two copies of the building. If the building's power (host) or loudspeaker (Redis) fails, both doors stop working.

### Ports and network path

| Port or endpoint | Exposure | Purpose |
| --- | --- | --- |
| Local `localhost:8080` | Local host | k3d HTTP entry |
| AWS 80/443 | Public via EC2 security group and K3s ServiceLB | HTTP redirects to HTTPS; serves HTTPS/WSS |
| Gateway container 8080/8443 | Cluster/ServiceLB | Non-root Nginx listeners |
| Frontend service 80 to Pod 8080 | Cluster only | Static files |
| Backend service/Pod 8000 | Cluster only | WebSocket and private probes |
| Redis 6379 | Backend Pods only, by policy | Authenticated Pub/Sub |
| EC2 SSH 22 | Operator CIDRs only | Host administration, if provisioned |

The gateway returns HTTP 403 for external `/health`, `/live` and `/metrics`, and exposes its own small `/ready`. The local gateway is HTTP. The AWS config requires an operator-supplied certificate, accepts TLS 1.2/1.3, and redirects port 80 except `/ready`. DNS and certificate renewal are not automated.

## 4. Technologies and why they fit

| Layer | Technology | Rationale and trade-off |
| --- | --- | --- |
| Browser | React 19, JSX, CSS and Vite 8 | Component rendering, a bundled static build and explicit protocol/state modules |
| API | Python 3.12, FastAPI/Starlette, Uvicorn | Async WebSocket handling. One worker per Pod keeps process state simple |
| Contracts | Pydantic models plus JSON Schema | Strict server event shapes. Browser independently re-validates |
| Bus | Redis 7 Pub/Sub, `redis.asyncio` | Simple low-latency fanout. No replay or acknowledgments |
| Edge | Nginx gateway and static Nginx | TLS termination, reverse proxy, security headers |
| Runtime | OCI images, Docker, k3d locally, K3s/containerd on AWS | Kubernetes features on a small host with no EKS control-plane fee |
| Manifests | Kubernetes + Kustomize | Shared base, local and AWS overlays, probes, limits, network policies |
| Infrastructure | Terraform | Explicit AWS network and compute, separate state bootstrap |
| Delivery | GitHub Actions, GHCR, Trivy SBOM/scans, Buildx metadata, Cosign | Validation, scanning, signing, digest-pinned releases |
| Verification | pytest, Hypothesis, Node test runner, Playwright, smoke/integration/load scripts | Protocol, real Redis, browser flow, measured fanout |

Exact versions and digests live in lockfiles and Dockerfiles. K3s avoids the managed EKS control-plane fee, but **AWS is not zero-cost**: EC2, EBS, data transfer, DNS and credits need account-specific review.

> **Deep dive: why one Uvicorn worker per Pod?** Each worker process owns its own socket list, queues, token buckets and metrics. Running four workers in one Pod would make four independent socket sets and four Redis subscribers inside one failure and memory boundary, and would complicate per-Pod capacity numbers. Kubernetes replicas give the same horizontal scaling with clearer limits, probes and restarts.

## 5. End-to-end user and message flow

### 5.1 Opening a session

1. `frontend/src/useChat.js` generates a name like `guest_1234abcd` (first eight characters of a random UUID). The user may edit it; it is only a label.
2. `frontend/js/connection.js` opens `ws://<host>/ws/<encoded-name>` (or `wss://` from HTTPS), requesting `chat.v1`.
3. The gateway proxies the upgrade to the backend Service. `backend/app/main.py` rejects: unapproved origin with 403; wrong or missing subprotocol with 400; invalid name with 400; unready, full or draining replica with 503. All of this happens **before** the socket is accepted.
4. The backend reserves a capacity slot and sends a direct `session` event. It is not published to Redis.
5. The client checks exact fields, version, name and `chat.v1` before marking itself connected. A missing first `session` times out after 10 seconds.
6. The backend attempts a best-effort `system` join broadcast. If the publish budget or Redis is unavailable, the notice may be absent.

The username rule is ASCII `[A-Za-z0-9_-]{1,32}`. Origins are a comma-separated list of exact HTTP(S) origins, with HTTPS required in public mode. CORS middleware alone is not a WebSocket origin policy, so the handshake checks `Origin` directly. This guards against browser-origin misuse but **does not authenticate anyone**: a non-browser client can send any Origin header.

> **Simple view.** Think of the handshake as a bouncer with a checklist: right website, right protocol, valid name, room for one more, system healthy. Only then does the visitor get in, and the first thing they receive is a welcome card (`session`) that tells them who they are.

> **Deep dive: why reject before accepting?** Refusing during the HTTP upgrade costs far less than accepting, allocating a reader, a writer and a queue, and then closing. It also gives load balancers and clients a clean HTTP status (400, 403, 503) instead of a WebSocket close code. Reserving the capacity slot at admission time (not at first message) is what makes the 64-connection cap a real bound.

### 5.2 Sending one chat message

```
Sender browser --text frame--> Backend A
Backend A: check rate, bytes, Unicode, policy
Backend A --PUBLISH server-created chat event--> Redis
Redis --event--> Backend A  and  Backend B
Backend A --queue + writer--> Sender browser
Backend B --queue + writer--> Other browsers
```

The browser sends **raw text**, not client-authored JSON. The backend owns the sender label (from the socket path), event ID, UTC timestamp and Pod identity. It normalizes line endings, strips only ASCII spaces, tabs and newlines at both ends, rejects forbidden control characters, and limits text to 2,000 Unicode code points. The Uvicorn entrypoint caps a complete incoming frame at 16,384 bytes, so fragmentation cannot bypass it. Empty text after normalization is ignored but still consumes a rate token.

A successful Redis `PUBLISH` means Redis accepted the command. It does **not** prove every recipient read or displayed the event. In the UI, `WebSocket.send()` only means the browser handed data to its socket buffer, so the notice says delivery is unconfirmed until the event appears. An ambiguous publish failure is **not retried**, because it might have succeeded and a retry could duplicate the message.

> **Deep dive: the idempotency problem.** After a timeout the backend cannot tell 'Redis never got it' from 'Redis got it but the reply was lost'. Safe retry needs an idempotency key stored somewhere durable (for example a client-generated message ID checked against a database or Redis key with expiry). Baatchit deliberately has none, so the honest choice is to never auto-retry and to tell the user the truth.

### 5.3 Ordering and semantics

One backend session writer serializes its own outbound queue, and each backend receives Pub/Sub messages in the order Redis delivers them on its subscription. There are no global sequence numbers, no durable ordering, no delivery acknowledgments, no deduplication and no replay. In a healthy local run each recipient received exactly one event per publish; that observation is **not** an exactly-once guarantee. Join and leave events are advisory: absence must not affect correctness, and presence is not a membership database.

| Property | Status |
| --- | --- |
| Delivery to live, healthy recipients | Best effort, observed once per recipient locally |
| At-least-once | Not guaranteed |
| Exactly-once | Not guaranteed |
| Replay after reconnect | None |
| Global order across reconnects | None |
| Unique, verified names | None |

> **Deep dive: what ordering you do get.** Redis processes commands from all publishers on a single thread, so subscribers on one connection see published messages in a consistent order. Two backends subscribed to the same channel normally see the same order. But a client that reconnects, or a Pod that restarts its subscription, can see a gap, and the app cannot detect or fill it. Detecting gaps needs sequence numbers; filling them needs storage (see the Proposals section).

## 6. Wire contract and validation

The JSON Schema (`schemas/events-v1.schema.json`) and `backend/app/protocol.py` define outbound events. `schema_version` is the integer `1`. Unexpected fields are rejected by both the strict backend model and the browser parser. Times are UTC.

| Event | Direction | Required fields | Meaning |
| --- | --- | --- | --- |
| `session` | Server to one socket only | `schema_version`, `type`, `connection_id`, `container_id`, `user`, `sent_at` | First event: UUIDv4 socket identity and assigned Pod |
| `chat` | Server to all live sockets | `schema_version`, `type`, `event_id`, `sent_at`, `user`, `text`, `container_id`, `time` | A validated user message |
| `system` | Server to all live sockets | Same shape as `chat` | Best-effort join/leave notice |

A valid broadcast looks like this (IDs and times are illustrative):

```json
{
  "schema_version": 1,
  "type": "chat",
  "event_id": "f4b36d74-c9d9-4b23-84a9-f3e2c6388eb3",
  "sent_at": "2026-10-27T10:12:34.567Z",
  "user": "guest_1234abcd",
  "text": "Hello",
  "container_id": "backend-abc123",
  "time": "10:12:34 UTC"
}
```

A `session` event has `connection_id` instead of `event_id`, and no `text` or `time`. `time` must match the time portion of `sent_at`; the backend checks this when consuming from Redis and the browser checks it again. The wire name `chat.v1` stays stable even after the product was renamed Baatchit, because changing it would break existing clients.

### Close codes: what the server tells the client

| Situation | Close code | Meaning in plain words |
| --- | --- | --- |
| Normal manual disconnect | 1000 | Clean goodbye |
| Binary frame | 1003 | Only text is allowed |
| Invalid UTF-8 | 1007 | The bytes were not valid text |
| Forbidden controls or over 2,000 code points | 1008 | Policy violation |
| Frame over 16 KiB after reassembly | 1009 | Message too big |
| Server drain | 1012 | Server is restarting, retry soon |
| Publish rate limit or slow outbound queue or send timeout | 1013 | Try again later |
| Redis unavailable or publish error | 1011 | Server-side failure |

The browser also pre-validates text and refuses to send when its buffered socket data exceeds 65,536 bytes. Server checks remain authoritative because clients can bypass browser code. Neither side applies NFC/NFKC Unicode normalization, so visually identical strings can still be different.

> **Simple view.** Every closed connection comes with a number that says why. 1008 to 1009 mean 'you broke a rule'. 1011 to 1013 mean 'the server is having trouble or is busy'. 1012 means 'we are restarting, come right back'. The browser uses these numbers to decide whether to retry.

> **Deep dive: fail-closed validation and schema evolution.**
> - Rejecting unknown fields (strict mode) makes a version mismatch loud instead of silent. The cost: any additive change needs a new `schema_version` or a coordinated deploy.
> - Validation exists at three boundaries: browser input, server input, and server-side re-validation of every event coming back from Redis. The third matters because Redis is a shared bus: a bug in one Pod, or a compromised credential, must not push malformed events to browsers.
> - Safe upgrade path (proposal): accept both `chat.v1` and `chat.v2` in the subprotocol negotiation, have the server choose per connection, and keep v1 envelopes unchanged until traffic on v1 is zero.

## 7. Backend internals and resource controls

`backend/app/run.py` is the canonical entrypoint. It starts one Uvicorn worker on port 8000 with a 16 KiB WebSocket message limit, receive queue of four, compression disabled, 20-second ping interval and timeout, access logging disabled, and no trusted proxy headers. The FastAPI lifespan starts and stops the Redis supervisor. Running bare `uvicorn app.main:app` would skip some transport and drain behavior.

| Module | Main concern |
| --- | --- |
| `main.py` | App assembly, private HTTP routes, handshake validation and slot reservation |
| `settings.py` | Startup-validated settings and secret source |
| `protocol.py` | Strict Pydantic event models, server-generated IDs and times |
| `validation.py` | Username and Unicode/text boundary rules |
| `sessions.py` | One reader and one writer per connection, local fanout, drain |
| `limits.py` | Token buckets and bounded delivery queues |
| `broker.py` | Redis client, subscriber generation, heartbeat, reconnect |
| `health.py` | Dependency-aware readiness |
| `telemetry.py` | Local Prometheus registry and structured logs |
| `run.py` | Hardened server process and termination handling |

### 7.1 Concurrency and backpressure

Each connection gets a **reader task** and a **writer task**. The Redis subscriber callback places a validated, serialized event into each active socket's queue **without waiting for any socket write**. Each writer drains only its own queue. If a queue is full, its byte budget is exceeded, or one write takes longer than two seconds, only that session is closed with `1013`. This stops one slow reader from building an unbounded backlog or blocking healthy readers. It does not make delivery durable: an event sitting in a queue is lost if that Pod or socket disappears.

| Default limit | Value |
| --- | --- |
| Admitted connections per replica | 64 |
| Per-socket message rate | 2 msg/s, burst 5 |
| Per-replica publish rate | 20 publishes/s, burst 40 (includes join/leave notices) |
| Queue per socket | 32 events and 262,144 serialized UTF-8 bytes |
| Socket write deadline | 2 seconds |

> **Simple view: the token bucket.** Picture a bucket that holds 5 tokens and gets 2 new tokens every second. Each message costs one token. You can send 5 messages quickly, then you are held to about 2 per second. The server keeps one bucket per connection and one bigger bucket for the whole Pod.

> **Deep dive: capacity math you can defend in an interview.**
> - **Configured queue-payload bound:** 64 sockets x 262,144 serialized bytes = 16 MiB per replica (32 MiB across two). This is not total queue or process memory: Python objects, an item already removed for sending, transport buffers and the rest of the runtime add overhead. The event-count limit can bind before the byte cap. Measure actual RSS and host headroom rather than inferring OOM safety from this arithmetic.
> - **Why two limits:** the per-socket bucket stops one noisy client; the per-replica bucket stops many individually polite clients from overloading one Pod. Both are needed.
> - **Aggregate ceiling:** two replicas allow about 40 publishes/s sustained. At the 25-client target that is 40 x 25 = 1,000 deliveries/s. At a full 128 clients it is 40 x 128 = 5,120 deliveries/s, or about 2.5 MiB/s (roughly 21 Mbit/s) of 512-byte payloads before protocol overhead.
> - **Fanout is the cost driver:** work grows as publishes x connected clients. Doubling clients doubles deliveries at the same send rate. A room of N people where everyone sends at rate r produces r x N x N deliveries per second, which is quadratic in room size. This is why a single global room does not scale far.
> - **Budgets are per process, not global.** Each replica enforces its own rates. Global fairness would need a shared counter (for example Redis) at the cost of one extra round trip per message.
> - **128 slots is nominal.** The Service does not guarantee a 64/64 split, and CPU, memory, file descriptors and network may run out before slots do.

### 7.2 Why subscriber readiness needs a heartbeat

A Redis `PING` can succeed while the separate Pub/Sub consumer is stuck, which would silently drop messages. The broker subscribes, confirms the subscription acknowledgment, publishes a private control packet with a random generation nonce and a sequence number, and waits to receive that exact packet through its own subscriber. It repeats about every five seconds. A subscriber probe older than ten seconds makes readiness false. Control packets are filtered and never reach browsers. A failed generation closes active sockets with `1011`, marks the Pod unready, and reconnects with a 0.25-second initial backoff capped at five seconds.

`/health` returns 200 only when the process is not draining, the subscriber probe is fresh, and a Redis `PING` succeeds; otherwise 503. `/live` reports process responsiveness only, so a Redis outage does not cause restart loops. Redis itself has only TCP probes, which cannot prove ACL or Pub/Sub health, so the backend probe adds that application-level check.

> **Simple view.** It is not enough to ask Redis 'are you awake?'. The backend sends itself a test note through the real loudspeaker path and checks that it hears it. If it does not, the Pod tells Kubernetes 'do not send me visitors'.

> **Deep dive: the detection window.** With a 5 s probe interval and a 10 s freshness limit, a silently stuck subscriber is declared unready within roughly 10 s, plus the Kubernetes probe period and failure threshold. In that window messages can be lost. Tightening the interval shortens the window but increases control traffic and false positives under load. This is an explicit availability vs. accuracy trade-off.

### 7.3 Shutdown behavior

On a termination signal the entrypoint starts a drain: new sessions are refused, existing sessions are asked to close with `1012`, and the broker stops during lifecycle shutdown. Backend Pods have a 20-second termination grace and a configured 10-second drain budget. The frontend treats `1012` as a fast jittered retry (0 to 500 ms). Gateway, frontend and Redis use the `Recreate` strategy, so there is **no claim of end-to-end zero-downtime releases**.

> **Deep dive: reconnect storms.** When a Pod holding 64 clients drains, they all reconnect within a 0 to 500 ms window, roughly 128 attempts/s at the peak. The remaining ready Pod must absorb them within its own 64-slot cap, which is why a rolling update with `maxUnavailable: 1` on two replicas is safe only if the room is below about 64 users. Above that, reconnecting clients would receive 503 until the new Pod is ready. Full jitter on the longer backoff path spreads load further.

## 8. Frontend and UI/UX

Vite bundles the React entrypoint in `frontend/src/main.jsx`. `App.jsx` composes the sidebar, header, message list and composer. `useChat.js` subscribes to the existing store through `useSyncExternalStore` and releases sockets/timers on effect cleanup. `state.js`, `connection.js` and `protocol.js` remain framework-independent. `MessageList.jsx` renders escaped text and preserves the reader's position across updates and history eviction.

| UI behavior | Implementation and consequence |
| --- | --- |
| Responsive layout | Desktop sidebar and chat pane adapt to mobile; a 390 px Chromium flow was tested |
| Safe rendering | Message bodies and labels use escaped React text children, so HTML-like input shows as plain text |
| Accessibility basics | Semantic labels, skip link, live status and log regions, keyboard controls. Full audit pending |
| Compose | Enter sends; Shift+Enter inserts a newline; IME composition is handled |
| Reading continuity | Scroll position is kept while reading older messages; a 'New messages' button appears |
| Connection gating | Composer stays disabled until a valid first `session` event |
| Memory bound | At most 500 events in state and DOM; older ones are dropped |
| Draft behavior | Unsent draft survives reconnect in memory; no localStorage or server draft |
| Delivery semantics | No automatic resend after a lost connection; notices never claim acknowledgment |

**Reconnect policy:** exponential backoff with full jitter, 500 ms base, 15 s cap, up to ten attempts. A stable 30-second connection resets the counter. Terminal normal or policy close codes stop retrying. A new connection generation ignores messages from stale sockets. An incompatible envelope stops the client with a protocol error instead of rendering it.

> **Simple view.** If the connection drops, the app waits a random short time and tries again, waiting longer each time (up to 15 seconds), and gives up after ten tries. Randomness keeps thousands of browsers from all knocking at the same instant.

> **Deep dive: the backoff schedule.** With full jitter, each wait is a random value between 0 and min(15 s, 0.5 s x 2^n). The upper bounds run roughly 0.5, 1, 2, 4, 8, then 15 s for the remaining attempts, so ten attempts wait at most about 90 s in total and on average about half that. Full jitter gives lower server load than 'equal jitter' or no jitter during a mass reconnect, at the price of occasional very short waits.

> **Deep dive: safe React text.** JSX string children are rendered as text, so HTML-like message content appears literally. The app never sends message text through `dangerouslySetInnerHTML`. It is the primary XSS defense. The Nginx CSP is a second layer. Input validation is NOT treated as sanitization, because blocking control characters says nothing about HTML safety. Any future markdown, link previews or attachments need a new sanitization design and a fresh threat review.

The UI has no read receipts, typing indicators, user list, private messages, media, search, or push notifications. Those are product extensions, not hidden features.

## 9. Kubernetes and infrastructure

### 9.1 Local and AWS topology

The common Kustomize base defines four Deployments and four Services in namespace `baatchit`: one gateway, one frontend, **two backend replicas**, and one Redis. The local overlay patches gateway routing for loopback HTTP and runs in k3d. The AWS overlay holds deliberate origin and release placeholders; the release renderer replaces them and pins all four images by digest. Applying the raw AWS overlay is **not** the release procedure.

| Pod type | Replicas | CPU request / limit | Memory request / limit | Rollout |
| --- | ---: | ---: | ---: | --- |
| Gateway | 1 | 50m / 250m | 32 / 64 MiB | Recreate |
| Frontend | 1 | 25m / 100m | 16 / 48 MiB | Recreate |
| Backend | 2 | 100m / 500m each | 128 / 256 MiB each | RollingUpdate, max unavailable 1 |
| Redis | 1 | 50m / 250m | 64 / 128 MiB | Recreate |

Memory **requests** total 368 MiB (32 + 16 + 2 x 128 + 64) and **limits** total 752 MiB (64 + 48 + 2 x 256 + 128). This excludes K3s, system Pods, Linux, page cache and network buffers. Requests drive scheduling; limits can trigger OOM kills. The AWS candidate defaults to `c7i-flex.large` (2 vCPU, 4 GiB) in `ap-south-1`; check account eligibility and real price before creating it.

All app containers run non-root with read-only root filesystems, dropped capabilities, no privilege escalation, `RuntimeDefault` seccomp and no auto-mounted ServiceAccount token. Temporary writes use bounded `emptyDir` volumes. Redis data also uses `emptyDir`, so replacing the Redis Pod loses all ephemeral state.

> **Simple view.** A 'request' is what a Pod is promised; a 'limit' is the most it may use before Kubernetes stops it. Total promises here are small, about 368 MiB, so the app fits on a 4 GiB machine with plenty left for the system.

> **Deep dive: headroom budget on 4 GiB.** Even at the 752 MiB worst-case limit total, the app leaves over 3 GiB for K3s (control plane, containerd, ServiceLB), the OS and cache. The 512 MiB `MemAvailable` floor in the requirements is therefore a sanity check against leaks and bursts, not a tight constraint. CPU is likelier to be the first pressure point: two backends can each burst to 500m, plus Nginx and K3s overhead, on 2 vCPUs. On burstable instance families, sustained CPU use can also hit credit or throttling behavior, so the 30-minute run matters.

### 9.2 Network and secrets

A default-deny NetworkPolicy blocks all ingress and egress unless explicitly allowed. Allowed paths: gateway to frontend and backend, backend to Redis, and cluster DNS. Gateway or frontend to Redis is denied. The local network script tested these boundaries by both Redis Service and Pod IP. Backend and Redis have no public host port.

Redis uses an ACL Secret with the default user disabled. The `app` user may only `PING`, `PUBLISH`, `SUBSCRIBE` and `UNSUBSCRIBE` on the chat channel. The backend reads an authenticated URI from the `redis-url` Secret file. `gateway-tls` holds the AWS certificate and key. The local launcher generates a random Redis credential; `scripts/bootstrap_secrets.py` is the operator path for a cloud cluster. The two Redis Secrets must be rotated as a pair. Public backend startup requires an authenticated file-based URI, a real release ID and an HTTPS origin.

Redis config: persistence disabled, `maxmemory` 48 MiB, `noeviction`, and Pub/Sub output buffer limits of 4 MiB hard and 1 MiB soft for ten seconds. These make resource exhaustion less likely; they do not stop host exhaustion or a public denial-of-service attack.

> **Deep dive: defense in depth for Redis.** Three independent layers protect the bus: (1) the NetworkPolicy limits who can connect, (2) the ACL limits what an authenticated client may do, and (3) buffer and memory caps limit what a misbehaving client can consume. If any one layer is misconfigured, the others still limit blast radius. The residual risk: a compromised backend holds a valid credential and can publish forged events to the real channel, which is why the backend re-validates every event it consumes.

### 9.3 AWS Terraform

`infra/bootstrap-state` creates an S3 bucket for Terraform state with versioning, server-side encryption, public-access blocking, a TLS-only policy and destroy protection. `infra/workload` declares a VPC (`10.0.0.0/16`), a public subnet (`10.0.1.0/24`), an Internet gateway and route table, a security group, and one EC2 node with a 20 GiB encrypted gp3 root disk. The security group allows 80/443 publicly and SSH only from explicit operator CIDRs. IMDSv2 is required. User data installs a checksum-verified K3s binary, disables bundled Traefik, enables Kubernetes secret encryption and limits container logs.

The state bucket and the workload are separate Terraform roots. This avoids a circular state setup and keeps the state store safe from ordinary teardown. Terraform validation has passed, but **no AWS plan, apply or live host verification has been recorded**. There is no managed EKS, RDS, ALB or NAT gateway, and no automated DNS record or certificate issuance.

| Resource | Present in baseline | Why it matters |
| --- | --- | --- |
| S3 state bucket | Yes (bootstrap root) | Protected, versioned, encrypted Terraform state |
| VPC, public subnet, IGW, route table | Yes | Minimal network, no NAT cost |
| Security group | Yes | 80/443 public, 22 restricted |
| EC2 + encrypted gp3 root | Yes | Single K3s host |
| EKS, RDS, ALB, NAT gateway | No | Avoids managed-service fees, but also managed resilience |
| DNS record, certificate issuance | No | Operator-supplied |

> **Deep dive: why a public subnet with no NAT.** A NAT gateway has an hourly charge plus data processing fees, and would be the largest line item for a demo. Placing the single node in a public subnet avoids it, at the cost of a public IP on the host. That is why the security group, IMDSv2, SSH CIDR restriction and Kubernetes NetworkPolicies are not optional: the host itself is internet-facing.

## 10. CI/CD and release trust

| Workflow | Trigger | What it does |
| --- | --- | --- |
| Validate | PR, push to `main`, reusable call | Terraform checks; Python compile and unit tests; JS tests; local k3d stack; smoke, real Redis integration, Chromium and network tests |
| Release | Manual on `main` with a public origin | Reuses validation, builds and publishes four GHCR images, scans them, writes SBOMs, signs images and the release bundle |
| Deploy | Manual on `main`, controlled Linux runner | Downloads the chosen release, verifies identity, signatures and hashes, applies manifests, waits for rollouts, smoke-tests, records the accepted bundle |

`release.json` identifies the source commit, release ID, origin, image digests, and hashes of the rendered manifests, SBOM and scan files. `scripts/release.py` rejects unexpected resource kinds, namespaces, images and unsafe container settings. `scripts/deploy.py` verifies Cosign signatures against an operator-specified GitHub workflow identity and OIDC issuer, takes a deployment lock, does a server-side dry run, checks rollouts and smoke-tests. If a previously accepted bundle exists and a deploy fails, it restores and re-verifies that bundle. A first deployment has nothing to restore.

Scanning gates fixable HIGH and CRITICAL vulnerabilities only. It does not mean zero vulnerabilities. The release and deploy workflows exist, but a signed remote release, a cloud deployment and a rollback rehearsal are still pending. A normal `git push` runs validation; it never provisions or deploys AWS.

> **Simple view.** Think of three separate gates: 'does the code pass tests?' (Validate), 'build a sealed, signed package' (Release), 'verify the seal and install it' (Deploy). Pushing code only opens the first gate.

> **Deep dive: what each supply-chain control actually proves.**
> - **Digest pinning** (`image@sha256:...`) identifies immutable image content; testing and verifying that specific digest are separate steps. A mutable tag can be repointed.
> - **SBOM:** the publication script emits SPDX reports with Trivy and requests Buildx SBOM/provenance metadata. These inventory packaged components; they are not a safety certificate.
> - **Scan** (Trivy) reports known vulnerabilities at build time; it cannot see future ones or unknown ones.
> - **Cosign signature** proves the artifact came from a specific workflow identity. It only protects you if the deployer verifies against an identity it already trusts, which is why the deploy script takes the expected identity from the operator, not from the bundle.
> - **Hash-locked Python dependencies** restrict installation to the versions and distribution hashes reviewed in the lockfile. They do not establish that an approved dependency is safe.
> - **Gap:** none of this has run against a real registry and real cloud cluster yet, so the end-to-end trust chain is designed and unit-tested, not proven in production.

## 11. Security model and limits

| Risk | Current control | Residual risk |
| --- | --- | --- |
| Cross-site WebSocket use from a browser | Exact `Origin` check plus required subprotocol | Origin is not authentication; custom clients can set headers |
| Script injection in chat | Strict validation, escaped React text, gateway CSP | Future rich text or attachments need new rules |
| Oversized or flooded input | 16 KiB frame cap, 2,000 code points, connection and token budgets, gateway handshake limit | Distributed abuse can still overload a small host |
| Slow reader | Per-client event and byte queue, write deadline | Its queued messages are discarded when it is closed |
| Redis misuse | ACL, Secret mounts, restricted network path | A compromised backend can still use the authorized channel |
| Container breakout | Non-root, read-only root, dropped capabilities, seccomp | Kernel or runtime flaws remain possible |
| Dependency compromise | Hash-locked dependencies, digest-pinned images, scans, SBOM, signatures | Gate excludes some severities and unfixed findings |
| Confidentiality | TLS at the AWS gateway, private internal services | Server and Redis see plaintext; no end-to-end encryption |
| Abuse and impersonation | Syntax limits, rate budgets | No verified identity, moderation, banning or audit trail |
| Operational recovery | Readiness, reconnect, signed prior-bundle restore | Single host and Redis; messages are ephemeral |

Structured logs record bounded event and outcome classes, not chat bodies, raw IP addresses or Redis credentials. Private Prometheus metrics include `chat_connections_active`, `chat_outbound_queue_bytes`, `chat_subscriber_ready`, `chat_messages_published_total{status}`, `chat_deliveries_total{status}` and `chat_admission_total{status}`. They are local to each backend process. There is no bundled long-term metrics server or alert routing, and no per-replica label on these series.

> **Deep dive: a mini threat model (STRIDE style).**
> - **Spoofing:** anyone can pick any name. Mitigation today: none beyond syntax. Fix: authentication (see Proposals).
> - **Tampering:** clients cannot set event ID, time, sender or Pod; the server does. A compromised backend with Redis access could still forge events.
> - **Repudiation:** logs omit message bodies and IPs for privacy, so you cannot prove who said what. That is a deliberate privacy-versus-accountability trade.
> - **Information disclosure:** plaintext on the server and bus; metrics and health routes blocked at the gateway; Secrets mounted as files.
> - **Denial of service:** many layers of caps, but one small host is easy to saturate with a distributed flood. A CDN or cloud WAF would be the next step.
> - **Elevation of privilege:** non-root containers, no ServiceAccount token, default-deny network policy, narrow Redis ACL.

## 12. Verification, performance, and honest interpretation

The implementation status records **42 automated tests passing locally** after the Baatchit rename: 26 Python unit, six JavaScript, nine real Docker/Redis integration, and one Chromium browser flow. The local smoke and network isolation checks, Kustomize rendering, schema consistency and both Terraform root validations also passed. Coverage includes fragmented oversize and binary frames, policy rejection, cross-replica delivery, Redis outage and recovery, shutdown, ACL restrictions, safe HTML-like rendering, draft behavior and mobile width.

A short **pre-rename baseline load run** (measured): 25 clients split 13/12 across backends, five aggregate publishes per second, 512-byte payloads, five-second warmup, 60 seconds of measurement. It sent 300 messages, expected 300 x 25 = 7,500 deliveries, observed 7,500, saw zero duplicates and zero reader errors, and measured about 16 ms p95 and p99 delivery latency with 100% inside two seconds. It ran locally on the Windows host's monotonic clock and was not repeated after the rename.

These results do **not** measure internet latency, AWS host headroom, a 30-minute run, availability under host failure, or the full target SLO.

| What you can claim | What you cannot claim |
| --- | --- |
| 7,500 of 7,500 deliveries in a 60 s local run, no duplicates | It will hold for 30 minutes on AWS |
| About 16 ms p95/p99 locally | Any internet or cross-region latency number |
| 42 tests passed locally | Production-grade reliability or HA |
| Cross-replica delivery works with real Redis | Exactly-once or durable delivery |
| Terraform validates | Cost, capacity or apply behavior on AWS |

> **Deep dive: designing a trustworthy load test.**
> - **Coordinated omission:** a generator that slows its offered work during a stall can hide intended-arrival delay. The current harness has scheduled sends and independent readers, but timestamps actual sends and awaits them sequentially; it does not fully measure from intended send time. Question 41 explains the limitation and a stronger measurement design.
> - **Where to run the generator:** off the node under test, so the load client does not steal the CPU you are measuring. Collect host CPU, `MemAvailable`, network and restart counts independently.
> - **Latency clock:** measuring send and receive on the same host's monotonic clock removes clock-skew error. For multi-host tests, use one generator host or synchronized clocks.
> - **Percentiles need context:** the short run had 300 publications and 7,500 recipient latency observations. The planned 30-minute workload expects 9,000 publications and 225,000 deliveries. These observations are correlated, and missing deliveries do not enter the percentile list, so always assess loss, errors, duration and latency together.
> - **Test the ugly paths too:** kill one backend Pod mid-run, restart Redis, and add a deliberately slow reader. The system is defined as much by these failures as by the happy path.

### Reproduce the local stack and checks

On Windows PowerShell from the repository root:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.venv\Scripts\python.exe scripts/local.py up
.venv\Scripts\python.exe -m pytest tests/unit -q
node --test tests/frontend/*.test.js
.venv\Scripts\python.exe scripts/check_manifests.py
.venv\Scripts\python.exe scripts/smoke.py
.venv\Scripts\python.exe scripts/check_network.py
.venv\Scripts\python.exe scripts/load.py --warmup 5 --duration 60 --output artifacts/load-local.json
.venv\Scripts\python.exe scripts/local.py down
```

Prerequisites: Docker with Linux containers, k3d, kubectl, Python 3.12 and Node 24. Real integration tests need built local images; Playwright needs its Chromium install. See the development doc for exact steps. The app runs at `http://localhost:8080`. The launcher uses its own `.local/kubeconfig` and `k3d-baatchit` context. Keep `.local/` and `artifacts/` untracked.

## 13. Troubleshooting and debugging playbook

| Symptom | Likely checks |
| --- | --- |
| UI loads but cannot connect | Browser console, exact allowed Origin, `chat.v1`, gateway `/ws/` route, backend ready endpoints |
| New handshakes return 503 | Redis probe freshness, Pod capacity or drain state, backend logs, Redis Secret mounts |
| `/live` passes but `/health` fails | Redis connection or ACL, subscriber heartbeat; do not assume a crashed process |
| Only one replica receives messages | Subscription readiness, Service endpoints, network policy, cross-replica integration test |
| Browser closes with 1008, 1009 or 1013 | Invalid input, oversize or rate, or slow queue; inspect the close code and bounded metrics |
| HTTPS works but WebSocket fails in AWS | Certificate, HTTPS Origin value, proxy upgrade headers, release-configured `ALLOWED_ORIGINS` |
| Deployment rejected | Signed bundle, trusted identity, hashes, namespace, digest references, Secrets and RBAC |
| Port 8080 busy locally | Old k3d cluster or another listener; see development rename notes |

### A step-by-step method (general kubectl approach)

These are standard Kubernetes commands, not repository scripts. Adjust the context name to your cluster.

1. **Is everything running?** `kubectl -n baatchit get pods -o wide` and look for restarts, `NotReady` and Pending.
2. **Why is a Pod not ready?** `kubectl -n baatchit describe pod <name>` for probe failures and events; then `kubectl -n baatchit logs <name>` for the structured event logs.
3. **Is the Service routing?** `kubectl -n baatchit get endpoints` and confirm two backend addresses.
4. **Is the network policy the cause?** Test from a debug Pod that is allowed to reach Redis versus one that is not; compare.
5. **Is it Redis?** Check Redis Pod logs and the backend `chat_subscriber_ready` metric on each replica.
6. **Is it capacity?** Compare `chat_connections_active` to the 64 cap and watch `chat_outbound_queue_bytes` for a slow reader.
7. **Reproduce in a browser:** open DevTools, Network, WS tab, and read the exact close code and reason.

> **Simple view.** Work from the outside in: browser, then gateway, then backend, then Redis. At each step ask 'does this layer see the request?' The first layer that says no is where the problem is.

> **Deep dive: the signals to alert on (proposal).** Because no alerting ships today, a first set would be: subscriber not ready for more than 30 s on any replica; admission 503 rate above 1% for five minutes; connection count above 80% of the cap; any backend restart; p95 delivery latency above 250 ms; Redis memory above 80% of 48 MiB. Each alert needs an owner and a runbook step, or it becomes noise.

## 14. Advanced design topics (all are proposals, not implemented)

Use this section to show you understand where the design ends and how you would extend it. Always say 'this is a proposal'. Each idea lists what it buys and what it costs.

### 14.1 Delivery guarantees ladder

| Level | What it means | What it needs | Status |
| --- | --- | --- | --- |
| Broker at-most-once | A publication can be delivered once or missed by a subscription | Live Pub/Sub; no retry/replay | **Current broker property**; browser path is best-effort |
| At-least-once processing | Retained accepted work is retried, so duplicates are possible | Durable acceptance, acknowledgments, retention and recovery assumptions | Proposal |
| Effectively-once effect | Repeated delivery does not create repeated logical effects | Stable submission/event IDs and recorded idempotency/deduplication decisions | Proposal |
| Exactly-once claim | Must specify the precise transaction/effect boundary | A database guarantee does not establish human receipt or uninterrupted browser delivery | Not claimed end to end |

### 14.2 Replay and history

- **Sequence numbers.** Assign each event a monotonically increasing sequence at publish time. Clients track the last number seen; a jump reveals a gap.
- **Durable log.** A proposed source of truth could be a properly persisted stream or database/outbox. Independent stream readers can follow room positions; one shared consumer group distributes work and would not automatically broadcast every event to every backend. Database storage plus notification needs a recovery mechanism for the commit/publish gap. See questions 37–38.
- **Cost.** Memory or disk grows with history, so you need retention (for example last 1,000 messages or 24 hours). The Redis 48 MiB cap and `noeviction` policy would have to be revisited. Persistence on `emptyDir` is not durable, so a real log needs a PersistentVolume or an external store.
- **Hard part.** Use an ordered committed boundary and bounded replay/buffering with overlap suppression, or continuously read the same durable log from the last cursor. Define behavior for retention gaps and overflow; timestamps/random UUIDs alone are insufficient boundaries. See question 38.

### 14.3 Identity and authorization

- **Browser constraint.** The native constructor accepts URL/subprotocols, not arbitrary Authorization headers. A proposed authenticated session-cookie design would validate the session at admission and retain exact Origin checks. A first-frame ticket design would need a strict pre-auth timeout and resource cap.
- **Credential handling.** Keep `chat.v1` as compatibility metadata. Bearer credentials in URLs or subprotocol values need careful leakage/logging review; do not treat those fields as a casual secret transport. Define expiry, revocation and authorization for long-lived sessions. See question 40.
- **Also needed.** Verified account IDs, conversation membership checks, account-level abuse controls and a deliberate privacy/audit policy. Unique display names or logging message bodies are product choices, not prerequisites for every authentication design.

### 14.4 Multiple rooms

- One channel per room (`room:{id}`) with each backend subscribing only to rooms that have local members, and unsubscribing when the last local member leaves.
- Fanout then depends on the audience and sender rate within each room. It bounds cross-room work but does not remove quadratic growth inside a large room when its per-user send rate remains fixed; with fixed aggregate send rate, recipient work is linear. See question 39.
- **Cost:** subscription management, per-room authorization, and a mapping of sockets to rooms in each backend. Redis can handle many channels, but very high churn of subscribe and unsubscribe has its own overhead.

### 14.5 Availability and scaling beyond one host

| Step | Gain | Cost or risk |
| --- | --- | --- |
| Second worker node | Survives one node loss for backends | More cost, cross-node networking, ingress must also be redundant |
| Replicated Redis (Sentinel or managed) | Removes the Redis single point of failure | Pub/Sub does not survive failover without client reconnect; brief gap on switch |
| Pod anti-affinity or topology spread | Backends land on different nodes | Needs at least two nodes |
| Horizontal Pod Autoscaler on connections | Capacity follows load | Needs a custom metric, and scale-down must drain gracefully (the `1012` path helps) |
| Managed load balancer | Redundant ingress, health checks | Hourly and data cost; WebSocket idle timeouts must be set above the 20 s ping |
| PodDisruptionBudget | Safer node maintenance | Only meaningful with more than one node |

> **Deep dive: measure first.** Candidate bottlenecks include admission limits, backend CPU/throttling, socket and Redis buffers, gateway throughput and host memory. The current fanout reuses a serialized payload for local queues rather than constructing a new envelope per recipient. There is no measured AWS bottleneck ranking; question 45 describes how to find one.

### 14.6 Observability roadmap

- **Metrics:** run a Prometheus-compatible collector, add a per-Pod label, and add histograms for publish-to-deliver latency and queue depth.
- **Tracing:** carry `event_id` in logs at publish, consume and write steps so one message can be followed across Pods.
- **SLO thinking:** define the SLI (share of deliveries within 2 s) and an error budget. At 99.9% over 30 days with 125 deliveries/s, the budget is about 0.1% of roughly 324 million deliveries. Alert on burn rate (how fast the budget is being used), not on single spikes.
- **Synthetic probe:** a tiny client that joins, sends, and checks receipt on the other replica every minute gives an end-to-end signal that Pod-level probes cannot.

### 14.7 Cost reasoning (method, not numbers)

List each billable item (EC2 hours, EBS GiB-months, public IPv4 address, data transfer out, DNS, registry storage), multiply by quantity and hours, and compare to credits or free-tier eligibility for the specific account. Prices and eligibility change, so look them up at decision time and keep the worksheet next to the architecture.

## 15. Known gaps

| Gap today | Impact | Sensible next step |
| --- | --- | --- |
| No verified identity or moderation | Impersonation, public-room abuse | Authentication, access policy, abuse process, privacy review |
| No persistence or replay | Disconnected users miss messages | Message log, cursor-based replay, delivery states |
| No end-to-end encryption | Infrastructure can read plaintext | Client-side key design after a threat model |
| Single Redis, gateway and host | One failure takes down the room | Multi-node spread, redundant ingress and broker |
| No cloud run evidence | Cost, headroom and rollback unknown | Reviewed AWS apply, DNS and TLS, off-node 30-minute test, rollback drill |
| Limited observability | No history, dashboards or alert routing | Metrics collector, dashboards, thresholds, owners |
| Limited browser and accessibility evidence | Cross-browser and assistive-tech behavior unknown | Screen-reader, keyboard, mobile and multi-browser audits |
| No offline messages, receipts, attachments | Narrower than commercial messengers | Define semantics, storage and security first |

Do not repeat improvement numbers from speculative design documents as benchmarks. Every expansion needs requirements, a failure model, migration and rollback steps, measurable acceptance criteria and a cost review.

## 16. Interview questions with evidence-backed answers

### Product and architecture

#### 1. What problem did you solve?

Baatchit solves a specific distributed messaging problem: **how can one message reach every browser when those browsers have persistent WebSocket connections to different backend processes?** A backend can write directly only to sockets it owns. If Alice is connected to backend A and Bob to backend B, an in-memory list of A's sockets cannot reach Bob. Adding a second backend for capacity or replacement therefore creates a communication gap unless there is a shared message path.

The implemented path is: browser text frame → admission and input checks in the receiving FastAPI process → server-created `chat` envelope → one Redis `PUBLISH` → each backend's Redis subscription → that backend's local connection queues → browser sockets. Every backend subscribes to the same `global_chat_channel`. The sender also receives the event through the subscription; the publisher does not separately echo it, which avoids a duplicate local delivery in the healthy path. Each connection has its own bounded writer queue, so a slow browser cannot make the subscriber await its network writes.

The product is deliberately a **single anonymous public room**. The engineering goals include a versioned wire protocol, safe rendering, resource limits, failure-aware readiness and repeatable deployment. This is not a general messaging platform: there is no verified account, private room, persistent history or offline delivery. In an interview, the useful distinction is that the project demonstrates *cross-process live fanout*; it does not claim durable or guaranteed messaging.

#### 2. Why use WebSockets instead of polling or Server-Sent Events?

Chat is interactive in both directions. A browser must submit text promptly and receive messages from other people without repeatedly asking whether anything changed. After an HTTP upgrade, a WebSocket supplies one long-lived, bidirectional connection. The browser sends a text frame and the backend can push a broadcast on that same socket. That fits Baatchit's small, live room and allows the first server event to be a `session` envelope before sending is enabled.

With periodic polling, the browser would issue repeated HTTP requests even when the room is quiet. A longer interval would make messages feel delayed; a shorter interval increases request overhead. Long polling can reduce idle requests, but it still requires managing repeated request lifecycles. Server-Sent Events are useful for one-way server-to-browser streams, but sending chat text would need a separate request endpoint and a way to associate that request with the stream's user/session. Those approaches are viable designs, just less direct for this bidirectional protocol.

WebSockets create their own costs. The backend must keep a socket open, track admission capacity, detect disconnects, bound outgoing data, handle slow readers and drain connections on restart. The browser must validate events and reconnect carefully. Baatchit implements those controls: one reader/writer pair per session, per-socket limits, bounded queues, heartbeat-dependent readiness, and retry with jitter. A successful browser `send()` only buffers data; it is not proof that another user received the message.

#### 3. Why use Redis Pub/Sub instead of a database queue?

The current requirement is to broadcast **live** messages to all currently connected clients, with no history or replay. Redis Pub/Sub matches that scope: each backend subscribes to the room channel, and a publishing backend sends one event that Redis forwards to all active subscribers. It avoids a database write and a consumer-acknowledgment workflow for messages the product does not retain. The app's Redis instance has persistence disabled, and no chat tables or message keys are created.

That choice fixes the delivery semantics. A subscriber that is disconnected or unhealthy when an event is published misses it. Redis does not keep the event for that backend to read later. A `PUBLISH` result does not prove that browser recipients received the event, and retrying after an uncertain publish timeout could create a duplicate. Baatchit therefore does not automatically replay or retry an ambiguous chat publication. It marks an unhealthy subscriber unready and closes its sockets rather than silently promising uninterrupted delivery.

If requirements added offline messages, conversation history or delivery receipts, I would first define user identity, durable message IDs and recipient state, then select a persistent store and a replayable delivery mechanism. For example, a database-backed log with a transactional outbox or a stream/queue could record an event before fanout. That design would also need idempotency, cursors, retention, migration and failure recovery. Merely swapping Redis Pub/Sub for a queue would not automatically deliver exactly-once messages to browsers; the application protocol would need acknowledgments and deduplication.

#### 4. Why doesn't the Kubernetes Service alone solve cross-replica chat?

A Kubernetes Service provides a stable address and chooses an available backend endpoint when the gateway establishes a connection. Once a WebSocket is upgraded, its long-lived TCP connection stays with the selected Pod. The Service can direct Alice to backend A and Bob to backend B, but it neither knows the application's room membership nor forwards Alice's text to B. The socket lists live inside separate FastAPI processes and cannot be shared through Service routing.

Redis is the separate **application event bus**. A receives and validates Alice's text, creates an event ID and timestamp, and publishes the serialized event. Redis sends it to both A and B. A enqueues it for Alice and its other local users; B enqueues it for Bob and its local users. The backend Service solves *which process accepts a connection*; the Redis subscription solves *how a message reaches every process*. This is why the cross-replica integration test deliberately connects clients to different backend replicas and compares the events they receive.

Readiness affects Service routing: a backend whose Redis subscriber is stale should leave the ready endpoint set and refuse new chat sessions. It does not move an existing WebSocket automatically. The browser has to notice closure and establish a new connection; messages missed in the gap cannot be recovered in the current design.

#### 5. Do two backend replicas make the system highly available?

They reduce dependence on **one backend process**. If one backend Pod fails while the gateway, Redis, host and other backend remain healthy, the other backend can continue serving its existing sockets and may accept reconnecting clients if it has capacity. Kubernetes readiness keeps unready Pods out of new Service routing. The backend's drain path closes sockets with code `1012` during a planned restart, which tells browsers to retry quickly. This is useful process-level recovery, not a proven availability guarantee.

The baseline still has single points of failure: one Redis Pod, one gateway Pod, one frontend Pod and, in the AWS design, **one EC2/K3s host**. Redis failure makes both backend replicas unready. Host or gateway loss makes the whole application unavailable. Redis and gateway Deployments use `Recreate`, so full releases are not designed for uninterrupted traffic. The two backends also share the same host resources, and their nominal `64 + 64` admission slots depend on how connections distribute and whether the host has enough CPU, memory and file descriptors.

To claim host-level high availability, I would need at least separate failure domains, backend placement across nodes, redundant ingress and a broker arrangement that can tolerate failure. I would then test node loss, broker failover, reconnect behavior, data loss and recovery time against explicit objectives. Those are future changes. The repository's AWS manifests/Terraform target a single host and have **not** been applied to AWS as of the recorded project status.

#### 6. What data is stored where?

| Location | Current data | Lifetime and consequence |
| --- | --- | --- |
| Browser tab memory | Current session, unsent draft, connection state and up to 500 recent `chat`/`system` events | Lost when the tab is closed or reloaded; old events are evicted; no localStorage or IndexedDB history |
| Backend process memory | Its own active WebSockets, per-socket delivery queues and rate buckets, replica publication bucket, Redis subscriber state and private metrics | Lost on Pod/process restart; another replica cannot read its socket list |
| Redis | Current Pub/Sub subscriptions and transient in-flight event delivery | No retained message log; persistence is disabled and events missed while unsubscribed are gone |
| Kubernetes/host | Desired workload configuration, Secrets and cluster runtime state | Operational data, not a chat history; the baseline uses one host and ephemeral Redis data |
| S3 Terraform state bucket, if provisioned | Infrastructure state and resource identifiers | Needed to manage AWS resources; does **not** contain room messages; no AWS provisioning is recorded yet |

The distinction between an **unsent draft** and a **submitted message** matters. The browser preserves text the user has not successfully passed to `WebSocket.send()`. Once it passes text to `send()`, the UI clears the draft, but delivery is still unconfirmed. The app does not persist or automatically resend that uncertain message. A page refresh also cannot recover the 500-event display history because that history was only in tab memory.

This data placement explains both the low-complexity design and its limits. There is no chat database to back up, search or replay. Terraform state is durable infrastructure metadata, not message storage. Adding durable history would require a separate data model, retention/privacy rules, migration plan and a way for reconnecting clients to ask for events after a known cursor.

#### 7. What does `container_id` prove?

`container_id` is set by the backend from its hostname (in Kubernetes, normally the Pod hostname) when it creates a `session`, `chat` or `system` event. A direct `session` event tells a browser which backend accepted its socket. A broadcast `chat` event records which backend created and published that event; a different backend can later deliver the same event to one of its local clients. This makes the multi-replica path visible during demos and tests. For example, Bob may be connected to Pod B while a chat message from Alice carries Pod A's `container_id`: that is evidence Bob received an event originating on a different backend.

The field has important limits. It identifies a **process/Pod source**, not a human author, room membership, global sequence or delivery receipt. Pod hostnames can change when Pods are replaced. The event also has a server-created `event_id` UUIDv4 for correlation, but neither field proves that every client received it. The backend validates the envelope shape after reading Redis; `container_id` is not a cryptographic signature. The Redis ACL and network boundaries limit who may publish, but this field alone should never be used as an authentication or security decision.

### Protocol and consistency

#### 8. Why send `session` first?

An open WebSocket only tells the browser that the transport upgrade succeeded. The `session` event establishes that the server and browser agree on the application's protocol and the assigned connection. It includes `schema_version`, `type`, `connection_id`, `container_id`, `user` and `sent_at`. The browser verifies the exact field set, version, UUIDv4 connection ID, timestamp, requested username and negotiated `chat.v1` before enabling its composer. This prevents it from submitting text while it still lacks a valid application session.

The ordering is explicit in [sessions.py](../backend/app/sessions.py): the writer sends `session` directly, then marks the session active. Only active sessions participate in local broadcast fanout. The session envelope never travels through Redis because its connection ID and admission result belong to one socket. The browser waits at most ten seconds for initialization, rejects a broadcast arriving first, and treats a second `session` as a protocol error.

For example, receiving a successful HTTP upgrade followed by an incompatible server envelope must not show “Connected” and enable sending. This first-event rule gives the frontend a clear state transition. It still does not authenticate a human, promise future Redis availability, or acknowledge any chat message; those are different concerns.

#### 9. Why can't clients send event JSON?

The current client-to-server contract is a text frame containing message text. The backend validates that text and constructs its own JSON envelope. A client cannot choose the authoritative `event_id`, timestamp, event `type` or publishing `container_id` by submitting a JSON object. Sending the string `{"type":"system","user":"admin"}` would make it ordinary chat text, subject to validation and safe rendering, rather than a privileged system event.

The backend gets `user` from the already admitted socket path and creates the remaining metadata in [protocol.py](../backend/app/protocol.py). This keeps event creation in one trusted code path and gives both replicas and browsers the same envelope shape. Strict Pydantic models reject extra envelope fields when consuming broadcasts; the browser independently checks the received field set.

There is an identity limitation: the user chose that socket's display name, so deriving it on the server does not make it a verified account. Someone can still connect using another person's display name. A future authenticated protocol would bind an account ID to the session and authorize commands against that identity. Structured client commands could be introduced then, but the server would still own authoritative metadata.

#### 10. What is the delivery guarantee?

Baatchit provides **best-effort live delivery**. For the broker layer, Redis documents Pub/Sub as at-most-once: a publication can reach an active subscription once or be missed, and Redis does not replay it after a disconnect. That broker property does not by itself establish end-to-end browser delivery. The backend still has to validate, enqueue and write the event, and the browser still has to receive and process it. [Redis Pub/Sub delivery semantics](https://redis.io/docs/latest/develop/pubsub/#delivery-semantics).

Consider an event that Redis sends to backend B just before B crashes. Redis has completed its part, but B's browsers may never see the event. Similarly, a slow browser can be closed with queued events still undelivered. There is no durable message record, recipient acknowledgment, replay cursor or deduplication store in the current app. A socket write completing is not a durable recipient receipt.

The local benchmark observed all 7,500 expected deliveries without duplicates in its measured window. That supports the healthy scenario that was tested; it does not prove exactly-once delivery during failures. Stronger guarantees would require defining what “delivered” means, persisting accepted messages, adding acknowledgments and retries, and making repeated submissions idempotent.

#### 11. Why not retry a failed `PUBLISH`?

A timeout leaves the publisher uncertain. Two different sequences can produce the same error: the command might fail before Redis receives it, or Redis might publish successfully and the reply might be lost. In the second case, retrying publishes again. Even if the retry uses the same `event_id`, the current subscribers and browser do not maintain a deduplication record, so a duplicate can be displayed.

[broker.py](../backend/app/broker.py) disables automatic Redis command retries and does not retry a failed chat publication. It increments a failure outcome, marks the broker unavailable and closes dependent sessions. The Redis subscriber supervisor may reconnect, but reconnecting the dependency is different from replaying an uncertain publication. The existing event ID helps correlate copies; it is not an idempotency mechanism.

A future reliable send path would let the client retain a stable submission ID, atomically record that ID with the accepted message, and return the same result for a repeat. A durable outbox or stream could drive later fanout. Acknowledgment would then refer to a specific durability stage. Without that recorded decision, retrying trades possible loss for possible duplication without resolving the uncertainty.

#### 12. Why does the UI say delivery is unconfirmed?

Several stages can succeed independently: browser buffering, backend receipt, validation, Redis publication, recipient queueing, recipient socket write, and recipient rendering. `WebSocket.send()` only hands text to the browser's transport buffer. It returns without waiting for those later stages. The frontend therefore clears a successfully submitted draft but tells the user that delivery is not confirmed until the event appears in the room.

Seeing the sender's own event return provides useful evidence: the backend created an event and the Redis subscription path brought it back to that browser. It does not prove that every other browser received it, that a person read it, or that it was stored durably. The current API has no message-specific accepted/delivered/read acknowledgment and no persistent status table.

This distinction prevents misleading status indicators. A future UI could show “pending,” “server accepted,” “delivered to device” and “read,” but each label would require a defined server/client acknowledgment and persistence policy. A successful local queue write or a Redis subscriber count would not be enough to implement those claims.

#### 13. What happens to a message during a disconnect?

There are three cases. Text still in the composer is an **unsent draft**: the tab keeps it in memory through reconnect attempts, so the user can choose to submit it later. A message already handed to `send()` is uncertain: it may have failed before reaching the backend or may already have reached other users. The client clears that submitted draft and never automatically resends it. Events published by other users while this browser is disconnected are missed because there is no replay.

Reconnect creates a new socket and receives a new `connection_id`. The browser preserves its existing in-memory event list, but the server cannot fill the gap. Socket generation checks prevent callbacks from an old connection from updating the new session. Automatic retries use jitter and eventually pause after ten failed attempts; protocol/policy closures require manual action. Reloading or closing the tab loses both the draft and displayed history.

A reliable reconnect design would need durable message IDs, a last-received cursor, bounded history retrieval and idempotent submission. Draft retention alone solves only the user experience of interrupted typing; it cannot recover missed events or determine whether an earlier send succeeded.

#### 14. What ordering is guaranteed?

Within one session, one writer sends its FIFO queue serially. Within a continuously healthy subscription to the single Redis channel, the backend receives publications in Redis's publication order and enqueues them in that order. Independent socket writers can run at different speeds, so two users need not see a given event at the same wall-clock instant.

For simultaneous sends from different backend replicas, the order that matters is when Redis processes their publications. The server's `sent_at` is created before publication and depends on the publishing host's clock; it is not a global ordering authority. UUIDv4 `event_id` values are identifiers, not increasing sequence numbers. Sorting by either of those fields would not establish a reliable room order.

This ordering holds only for events actually received during a healthy interval. A subscriber restart, queue overflow or browser reconnect can leave gaps. There is no room sequence or replay log to detect and repair them. If product requirements demanded a recoverable total order, I would assign ordered room positions in a shared durable log and have clients track those positions.

#### 15. Why are join and leave messages advisory?

The backend attempts to publish a join after the direct session event is sent, and a leave during ordinary session cleanup when it is not draining. These messages use the same Redis path as chat and draw from the replica-wide publication budget. [`Sessions.advisory`](../backend/app/sessions.py) skips them when the broker is unready or the budget is exhausted and suppresses publication exceptions so a presence announcement does not become a separate correctness dependency.

A crash cannot reliably publish a final leave. A network partition can delay disconnect detection. Two sessions can use the same display name, and a reconnect may produce another join for the same label. During a planned drain, leave publication is deliberately skipped. Counting “joins minus leaves” would therefore produce an unreliable online-user total.

If exact presence became a requirement, it would need connection identities, leases/heartbeats, expiry and a definition of “online,” with account aggregation when multiple devices belong to one person. Even then, presence during network partitions is a time-based approximation. The current announcements are useful room context, not an authoritative membership ledger.

#### 16. How is the protocol versioned?

Baatchit has two explicit compatibility checks. The browser requests `chat.v1` as a WebSocket subprotocol, and the backend rejects a handshake that does not offer it. Every server envelope also includes the integer `schema_version: 1`. The frontend checks both, validates exact fields and distinguishes `session`, `chat` and `system`. The corresponding server models and [JSON Schema](../schemas/events-v1.schema.json) describe the event contract.

“Adding an optional field” is not automatically compatible here: the existing browser rejects unexpected fields. A changed field set, message meaning or send format therefore needs a reviewed migration. One approach would be to support a new subprotocol alongside the old one, select one at admission, and maintain matching serializers/parsers while clients upgrade. The current implementation supports only `chat.v1`.

A migration would update backend models, schema, frontend parser and contract tests together, and test old/new client-server combinations. Product branding is independent of protocol compatibility: renaming the application to Baatchit did not require renaming `chat.v1`. Versions describe the wire contract, not the displayed product name.

### Concurrency, failure and performance

#### 17. How is a slow reader isolated?

Each `Session` has a `DeliveryQueue` bounded by both event count and serialized UTF-8 bytes. The default is 32 events or 262,144 bytes, whichever limit is reached first. The Redis subscriber's fanout loop uses non-blocking `put_nowait` behavior; it does not wait for a client's network write. A separate writer task removes events from that socket's queue and sends them one at a time with a two-second deadline.

If queue insertion fails, the backend records `queue_overflow` and closes that session with `1013`. If sending times out, it records `timeout` and also closes with `1013`. Other sessions retain independent writers, so a single blocked connection does not directly hold their writes. A client that simply stops reading might not trigger this immediately because TCP and WebSocket buffers can absorb data; tests must create enough pressure or deterministically stall the writer.

The byte counter measures queued serialized payloads. An item removed for sending is no longer counted, and Python objects, transport buffers and kernel buffers add memory beyond that counter. Thus `64 × 256 KiB = 16 MiB` is a configured queue-payload bound per backend, not a bound on the process's total RSS. Closing a slow socket discards pending deliveries; this protects availability without making messages durable.

#### 18. Why use both per-socket and per-replica limits?

The per-socket token bucket limits one connection to a default refill of two messages per second with an initial burst of five. That stops one connection from continuously occupying the publish path. It is applied before text normalization, so even whitespace-only input consumes a socket token. A second bucket limits accepted chat and advisory system publications across the replica to 20 per second with a burst of 40.

These controls address different load shapes. Fifty clients could each stay below two messages per second while collectively asking one backend to publish far more work than intended. Conversely, a replica-only budget would let one noisy connection consume most of the available publications. Exceeding either relevant bucket closes the offending chat socket with `1013`; it does not silently buffer unlimited work.

The limits are process-local, not an authenticated user quota or a strict global room quota. Reconnecting obtains a new socket bucket, and reaching another Pod reaches another replica bucket. Redis heartbeat control probes are published by the broker outside the session publication bucket. Gateway handshake throttling and admission caps provide additional coarse protection, but do not replace authentication, distributed abuse controls or volumetric DDoS protection.

#### 19. How does the token bucket work in this code?

A bucket starts with `burst` tokens. On each check it computes elapsed monotonic time and refills using `tokens = min(burst, tokens + elapsed × rate)`. If fewer than one token remains, the check fails; otherwise it subtracts one and succeeds. Monotonic time avoids errors caused by wall-clock corrections. The implementation also prevents a negative elapsed value from removing tokens.

With the socket defaults, five messages can consume the initial five tokens immediately. A sixth immediate message fails and closes the socket. If the client instead sends two more after a full second, two tokens have refilled and those may pass. The rough upper budget over one second from a full bucket is seven messages, but the timing of every send matters: a client that exceeds the bucket early is closed and cannot use tokens that would have arrived later.

[`TokenBucket.consume`](../backend/app/limits.py) contains no `await`, so in the current single event-loop process, another asyncio task cannot interleave halfway through the token update. This is not a thread-safe or cross-process distributed limiter. Increasing Uvicorn workers or moving accounting between processes would require reviewing those assumptions.

#### 20. Why is readiness different from liveness?

Readiness asks whether a backend can currently serve the application correctly. Baatchit's private `/health` checks that it is not draining, that a Redis command ping works, and that its current subscriber heartbeat is fresh. Failure returns 503 and Kubernetes should remove the Pod from ready Service endpoints for new connections. Liveness asks whether the process can respond at all; `/live` returns a small response without requiring Redis.

During a Redis outage, restarting every backend repeatedly would not repair Redis. Keeping liveness independent lets the existing broker supervisor recover the dependency while readiness rejects new chat sessions. Conversely, a process whose event loop stops responding can fail liveness and be restarted. A startup probe allows the process time to begin before normal liveness enforcement.

Readiness is not a guarantee about every existing connection. Service endpoint updates take time, established sockets are not migrated, and capacity exhaustion is separately checked during admission. A full backend can remain dependency-ready while rejecting a new socket with 503 at its connection cap. These checks serve distinct purposes and should be diagnosed separately.

#### 21. Why not trust Redis `PING` alone?

The Redis command path and the long-lived Pub/Sub receive path are different. A command connection can answer `PING` while the subscription has disconnected, its consume task is stuck, or the backend is reading the wrong generation of a subscription. Declaring such a Pod healthy would admit users who can publish but silently miss room events.

The broker first receives a subscription acknowledgment. It then creates a random nonce for that subscription generation and publishes a control packet with the nonce and an incrementing sequence. Its consumer must observe that exact pending probe before the heartbeat is refreshed. Probes from another replica or an earlier generation do not satisfy the current wait, and all control packets are filtered out before browser fanout.

The default probe interval is five seconds and the stale threshold is ten seconds. These are configuration intervals, not an exact upper bound on end-to-end failure detection under every scheduler/network condition. The probe demonstrates that the backend's Redis receive loop made progress; it does not exercise browser delivery or prove that every other backend is healthy. A synthetic browser-to-browser check would measure that wider path.

#### 22. What happens when Redis goes down?

A command error, a failed publication, or a failed/stale subscriber probe marks the broker unavailable. Its callback closes that backend's active sessions with `1011`, and `/health` becomes degraded. New WebSocket handshakes are rejected while `broker.ready` is false. `/live` can remain successful because the Python process is still operating.

The subscriber supervisor retries failed subscription generations with an initial 250 ms backoff capped at five seconds. A new generation must subscribe successfully and observe its own control probe before it becomes ready. Active browser clients react to eligible failures with bounded jittered retry; after ten failed attempts they pause for manual action. Redis recovery after a long outage therefore does not guarantee every paused browser reconnects automatically.

Messages sent during the failure can be rejected, missed or ambiguous if a publish reply is lost. There is no recovery replay. Local real-Redis integration tests exercised outage and recovery without restarting the backend, but cloud recovery-time targets and host-level failure recovery remain to be measured in the target environment.

#### 23. What happens when a backend Pod terminates?

For a normal signal-driven shutdown, [run.py](../backend/app/run.py) starts draining before handing the signal to Uvicorn. The session registry refuses new reservations and asks active sessions to close with `1012`. Readiness becomes false, the session tasks exit, and the lifespan cleanup stops the Redis supervisor/client. Defaults allow ten seconds for Uvicorn graceful shutdown inside a 20-second Pod termination grace.

The browser recognizes `1012` as service restart and chooses a short random retry delay of up to 500 ms. A reconnect is a new handshake through the Service and may reach the other ready backend. This depends on endpoint propagation, remaining capacity and the rest of the stack being healthy. There is no transparent transfer of an existing TCP socket or its queued messages between Pods.

A crash, OOM kill or forced termination may skip the close frame and cleanup entirely; the client then detects an abnormal connection loss. Even graceful drain is not a durable queue flush. The local integration suite observed the intended `1012` behavior for SIGTERM, while actual cloud rollout timing and node failure behavior need separate acceptance evidence. [Kubernetes Pod termination lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-termination).

#### 24. Why is 128 connections only a nominal capacity?

The configured admission ceiling is 64 sockets in each backend process. With two Pods, there are at most 128 such slots, but the Service does not promise that all connections distribute exactly 64/64. One Pod may reject a connection at 64 while another still has space. The gateway does not implement application-aware “try the other Pod until a slot is found” admission.

Capacity also includes CPU, memory, file descriptors, transport buffers, Redis output buffers, gateway connections and the cost of delivering each publication to every recipient. A connection cap is a protective setting; it is not a benchmark. With all 64 queues at their byte cap, queued serialized payloads alone could account for 16 MiB per backend, plus in-flight sends and runtime overhead. Different message rates and slow-client mixes can bind different resources.

The measured local scenario used 25 clients, deliberately balanced 13/12 by the load harness. That does not prove that 128 active clients meet latency or reliability targets. A capacity experiment should vary client count and send rate, record replica distribution and resource pressure, and retain enough headroom for a backend replacement and reconnect surge.

#### 25. How was latency measured, and what are the measurement limits?

[scripts/load.py](../scripts/load.py) creates unique test texts and records `time.monotonic()` just before awaiting each measured socket send. Reader tasks in that same load-generator process match received chat text to the send timestamp and record one latency per recipient. A single monotonic clock avoids comparing clocks on different backend hosts. Warmup events are excluded, and the report includes expected/observed deliveries, timely delivery percentage, p95/p99, duplicates and reader errors.

The measurement ends at receipt/parsing in the Python load client, not at browser DOM rendering or a human reading. The script schedules sends against a target timeline, but timestamps **actual sends** and awaits them sequentially. If the generator falls behind or a send blocks, intended arrival delay can be hidden. It is therefore not a fully corrected intended-send-time latency measurement.

Missing deliveries do not enter the latency percentile list, so percentiles must always be read with the delivery ratio and errors. The short recorded run was local, sharing a Windows host/Docker environment. AWS acceptance should use an independent load machine, record generator scheduling lag and host metrics, and run the full warmup/measurement period. See question 41 for coordinated omission.

#### 26. What do 7,500 deliveries mean?

The short measured phase lasted 60 seconds at five aggregate messages per second: `60 × 5 = 300` published test messages. Every one should reach all 25 connected clients, including its sender, so expected recipient deliveries were `300 × 25 = 7,500`. Those are **7,500 delivery observations from 300 publications**, not 7,500 independently published messages.

The report observed all expected deliveries, no duplicates/reader errors and approximately 16 ms p95/p99. The harness associates unique message text with recipients and checks that recipients see the same `event_id` for that test message. The result supports the tested cross-replica fanout scenario; it does not establish exactly-once semantics, a sustained AWS capacity limit or correctness through failures.

For the planned 30-minute measured phase, the same workload would produce `1,800 × 5 = 9,000` messages and `9,000 × 25 = 225,000` expected deliveries. More observations help assess tails and sustained resource behavior, but many recipients of one publication share the same underlying delays. Sample count alone does not make those observations statistically independent or prove an availability SLO.

### Security and deployment

#### 27. Is the Origin check authentication?

`Origin` identifies the browser page that initiated the connection. Baatchit compares it with a configured set of exact origins before upgrading a WebSocket. This helps prevent an unrelated web page from using a victim's browser to open a connection to the application. An origin includes scheme, host and port, so `http://localhost:8080` and `http://127.0.0.1:8080` are separate configured values.

It does not identify a person. A custom client can send an allowed Origin header, and a valid username only proves that its syntax matches the policy. The mandatory `chat.v1` subprotocol is also a compatibility check, not a credential. The current room is public and anonymous; the backend has no account login or room authorization decision.

A future authenticated version would validate credentials during admission, bind the verified account to the socket and authorize each room/action. It would still check Origin, especially if browser cookies carry credentials, and define expiry/logout behavior for already open connections. These controls complement each other: a valid session must not grant access to every room automatically. [OWASP WebSocket security guidance](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html).

#### 28. How do you prevent XSS?

The primary control is how content reaches the DOM. [MessageList.jsx](../frontend/src/components/MessageList.jsx) renders message bodies and labels as React text children. A string such as `<img src=x onerror=alert(1)>` becomes visible text rather than an HTML element with an executable handler. The browser integration test checks HTML-like text as inert content. This is stronger than hoping a character blacklist removes every dangerous HTML form.

The gateway also sends a restrictive Content Security Policy that limits scripts/styles/connections to the same origin, blocks objects, and disallows embedding the page in another frame. That provides additional defense but does not replace safe DOM construction. Backend Unicode/control/size validation serves the wire and resource policy; it is not an HTML sanitizer.

The guarantee depends on preserving these rendering rules. A later feature that inserts message text into `innerHTML`, creates unchecked links, or supports Markdown, media or SVG changes the attack surface. Such features would require context-specific URL/markup controls and new browser tests. The current app intentionally renders plain text and does not support arbitrary rich content.

#### 29. Why use both NetworkPolicy and Redis ACL?

NetworkPolicy controls which Pods can communicate. The namespace starts with ingress/egress denied, then allows gateway-to-frontend/backend, backend-to-Redis and DNS. A gateway or frontend Pod should not connect to Redis even if it knows the address. The network verification script checks denial through both the Redis Service and Pod IP; merely making a Service `ClusterIP` would not provide the same Pod-to-Pod boundary.

The Redis ACL controls what an authenticated connection may do after reaching Redis. The default user is disabled; the app user can use only the permitted Pub/Sub commands and chat channel. An authenticated backend cannot use that credential to read arbitrary keys, run administration commands or publish to another channel. The Redis URI and ACL are mounted from a paired Secret set.

These layers reduce different risks. A routing/policy mistake does not automatically remove Redis authentication, and possession of the app credential does not grant network access from every Pod. A compromised backend still has its legitimately authorized channel access, so neither layer makes its messages trustworthy by itself. Network-policy enforcement, Secret access, container restrictions and operational credential handling all remain relevant.

#### 30. What does single-node K3s mean for cost and reliability?

K3s runs Kubernetes components on the chosen EC2 host and uses containerd for application Pods. The baseline does not create a managed EKS cluster, managed ALB or NAT gateway. This keeps the infrastructure small, but the host must run the control plane, networking, gateway, frontend, both backend replicas and Redis together. It shares CPU, memory, disk and one failure domain across all those components.

EC2 runtime, the 20 GiB EBS root disk, public networking/data transfer and any separately configured services can still consume money or eligible credits. The project does not establish that a specific account receives a credit grant or that all resources qualify for free usage. The actual AMI, instance eligibility, regional pricing, remaining credits and teardown must be checked before provisioning. The Terraform default is a candidate configuration, not a verified cost or capacity result.

Reliability remains limited by that one host. Multiple backend Pods can demonstrate process replacement, but they do not survive host or single-zone loss. K3s reduces operational footprint; it does not turn shared hardware into redundant infrastructure. The cloud design therefore needs measured headroom, recovery tests and an explicit acceptable outage model before use beyond a demonstration.

#### 31. How does the pipeline reduce supply-chain risk?

The repository uses hash-locked Python dependencies and digest-pinned container bases to make unexpected dependency changes easier to detect. In the Release workflow, `scripts/publish.sh` builds four component images for Linux amd64, publishes them to GHCR, records immutable digests, scans the exact references and emits SPDX SBOM files using Trivy. Buildx is also asked to generate provenance/SBOM metadata; generating that metadata is distinct from verifying a complete provenance policy.

The release renderer records the source commit, release ID, actual HTTPS origin, image digests and hashes of manifests/scan/SBOM files. Cosign signs the images and `release.json`. Deployment verification checks the expected GitHub workflow identity and OIDC issuer supplied by the operator, verifies each image signature and trusted repository prefix, and checks the bundle's hashes and allowed resource configuration.

The scan gate covers fixable HIGH/CRITICAL findings, not every vulnerability. Signatures establish an expected signer and artifact integrity; they do not prove the application is safe or the signing workflow was uncompromised. The controlled runner, credentials and trust configuration are part of the security boundary. The code exists, but a signed remote release/deployment has not yet supplied real cloud acceptance evidence.

#### 32. What happens if deployment fails?

The deployment entrypoint obtains a Linux file lock, verifies and retains the selected bundle, and reads the record of the previous accepted release. It performs a Kubernetes server-side dry run, applies the manifests, waits for the four Deployments to roll out and runs a functional smoke check. Only after success does it atomically replace `current.json` with the newly accepted release record. A journal records the deployment outcome.

If those apply/rollout/smoke operations fail and a previous accepted bundle exists, the script verifies that prior bundle again, reapplies its manifests, waits for its rollouts and runs the smoke check. A first deployment has no prior accepted release to restore. Verification failures before application should fail without applying the untrusted new bundle. Kubernetes application across several resources is not one atomic transaction, so partial changes are possible before restoration begins.

Restoration can also fail if the cluster, registry, Secrets, network or prior artifact is unavailable. Restoring images/configuration does not recover ephemeral chat messages, rotate Secrets back, or undo Terraform changes. Those limitations need an operator runbook and a deliberate failed-release rehearsal. The repository implements the attempt but has not passed that real cloud rehearsal.

#### 33. Why isn't `git push` a deployment?

The workflows deliberately have different triggers and permissions. A pull request or push to `main` starts Validate, which checks code, Terraform configuration and the disposable local Kubernetes stack. It does not run Terraform apply or update the AWS application. A manual Release workflow on `main` accepts a public HTTPS origin and publishes a signed bundle only after validation passes.

A separate manual Deploy workflow selects a release run/source commit, downloads that artifact and runs on a self-hosted Linux runner labelled `baatchit-deployer`. It references the `aws-demo` environment and operator-configured kubeconfig/context, trusted identity and image prefix. The environment still has to be configured correctly; naming it does not itself prove that reviewers or protections have been enabled.

This separation allows source validation without giving every validation job production deployment access. It also makes a release an identifiable artifact that can be reviewed and restored later. Pushing documentation or code alone does not provision EC2, create DNS/TLS, publish the four release images or deploy them to a cloud cluster.

#### 34. Which AWS resources does Terraform actually define?

There are two Terraform roots. [bootstrap-state](../infra/bootstrap-state/main.tf) defines the S3 state bucket with versioning, server-side encryption, public-access blocking, a TLS-only access policy and destroy protection. Keeping it separate lets the workload use a remote state store without making routine workload teardown remove that store.

[workload](../infra/workload/main.tf) defines a VPC, public subnet, Internet gateway, default Internet route and association, security group and one EC2 instance. Its encrypted 20 GiB gp3 root disk is an inline instance block. Inbound 80/443 are public; SSH is restricted to explicit operator IPv4 CIDRs. The instance requires IMDSv2 and runs user data that installs a checksum-verified K3s binary, enables secret encryption and configures bounded container logs.

There is no Terraform-managed RDS, EKS, ALB, NAT gateway, DNS record or certificate issuance in this baseline. A Kubernetes Service of type `LoadBalancer` is served by the intended K3s ServiceLB arrangement; it does not mean this Terraform defines an AWS ALB. Both roots validated locally, but validation does not prove that an AMI, account quota, credit balance or live bootstrapping is correct. No AWS apply is recorded.

#### 35. What would you change first for reliable private messaging?

I would first define the privacy and delivery requirements. Private conversations need verified account identities and conversation membership checks for every send/read, rather than a display name from the URL. The data model would likely include accounts, conversations, membership and messages with stable IDs, plus device/session state if multiple devices are supported. All of this is future design.

Reliable submission then needs a durable acceptance point: atomically save the message and a client submission ID so retries return the same accepted result. A transactional outbox or suitable durable log can drive fanout after acceptance without losing the event in a save/publish gap. Recipients need cursors and acknowledgments whose meaning is explicit: stored by server, received by a device, and read by a user are different states.

I would add bounded history pagination, reconnect replay, retention/deletion rules and operational recovery tests before claiming offline delivery. End-to-end encryption would require a separate client key/device/trust design; adding TLS alone is insufficient. Private messaging changes the protocol, storage, authorization and threat model together, so it cannot be added merely by choosing a different Redis channel.

#### 36. How would you scale past one host?

The first step is to identify the actual constraint from measurements: admission saturation, event-loop CPU, queue growth, Redis output buffering, gateway throughput or host memory pressure. More Pods on the same exhausted host may increase contention. If the goal is host failure tolerance, that requires another failure domain even when current CPU usage is low.

A possible next stage is multiple worker nodes, backend topology spread/anti-affinity, resilient public ingress and a broker configuration with a tested failover model. The control plane also needs an appropriate availability design; keeping one control-plane host remains a risk. Connection-aware scaling should consider active sockets and publication/fanout work, because long-lived sockets do not automatically rebalance when new Pods appear.

One shared busy room still has to deliver each message to all its members. Scaling connection workers does not eliminate that delivery cost or Redis's shared-channel work. Room partitioning can bound audiences if the product supports it; durability/history require their own storage design. Each stage should include failure injection, resource/cost measurements and a migration/rollback plan. The [evolution handbook](design/ARCHITECTURE_EVOLUTION.md) proposes options rather than recording measured cloud outcomes.

### Advanced and follow-up questions

#### 37. How would you add message history without breaking live latency?

This would be a new protocol/storage design. The first decision is whether “accepted” means durably stored. If history must include every accepted message, publishing first and saving later is unsafe: the process can fail between those actions and leave users seeing an event that history never contains. Saving first and publishing separately also leaves a gap if the process fails before fanout.

A database transaction could save the message and an outbox row together; a dispatcher would then publish and retry outbox work. Recipients would deduplicate by stable event ID. Alternatively, a suitably configured durable stream could be the source of truth and feed live consumers. Either adds a persistence stage to acceptance; I would measure that latency rather than promise the original publish-only performance. The current Redis configuration has persistence disabled and is not such a durable store.

History reads should be paginated by cursor, authorized per conversation and bounded separately from live delivery. Long reads must not block socket writers or flood their queues. Retention, backup, unavailable-store behavior and replay tests become acceptance requirements. “Add a second write in the background” is insufficient when that background work is the only record of accepted messages.

#### 38. How would you avoid a gap between replay and live events?

A naive client that reads history and subscribes afterward can miss events published between those two actions. A safer proposed design uses an ordered durable log and one cursor for both phases. For example, a reader could replay entries after its last cursor in bounded batches and then continue blocking from the final cursor. Redis `XREAD` supports reading after a supplied stream ID; that is different from the current Pub/Sub channel. [Redis XREAD](https://redis.io/docs/latest/commands/xread/).

If live Pub/Sub remains separate, the handoff needs a precise boundary: establish the live subscription and confirm it, buffer live events within a strict cap, capture a reliable committed high-water mark, replay through that mark, then release later buffered events while suppressing overlaps. Event IDs identify duplicates; ordered positions define ranges. A maximum timestamp or random UUID is not a valid committed replay boundary, and even database sequence allocation may differ from commit order.

The design must also handle buffer overflow, retention trimming, dispatcher delay and reconnect during replay. If a gap cannot be recovered, tell the client to resynchronize instead of pretending continuity. One shared Redis consumer group would distribute stream entries between consumers, so it would not automatically broadcast every event to every backend's sockets; each backend's cursor/fanout responsibility must be designed explicitly. [Redis XREADGROUP](https://redis.io/docs/latest/commands/xreadgroup/).

#### 39. Why can fanout cost grow quadratically in one room?

Let `N` be the number of clients and `r` the average send rate **per client**. Total input is `r × N` messages per second. If every message is delivered to all `N` clients, including its sender as in Baatchit, output becomes `r × N × N` deliveries per second. Doubling both the audience and the number of active senders therefore quadruples the delivery work. Bytes per delivery and serialization/network overhead multiply that cost.

There is an important workload distinction: if the **aggregate** input is held fixed at five messages per second, output is `5 × N`, which grows linearly with the audience. The recorded 25-client workload used five aggregate messages per second, so it generated 125 deliveries per second. It did not make all 25 clients send five messages per second.

Adding backend Pods distributes local socket writes but does not remove the requirement to reach every recipient. Rooms can reduce the audience of each event if the product permits separate conversations, and subscriptions should then target relevant rooms. A very large single room may require different fanout tiers or limits. The existing app has one room and does not implement those extensions.

#### 40. How would you authenticate a browser WebSocket?

This is future work. A browser's native WebSocket constructor accepts a URL and optional subprotocols; it does not offer an arbitrary request-header parameter like a server-side HTTP client. A design therefore has to work with the browser's credential mechanisms rather than assume it can attach any desired Authorization header. [Browser WebSocket constructor](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket/WebSocket).

One proposed approach is an HTTPS login that establishes a protected session cookie. At WebSocket admission the backend validates that session, checks Origin and binds a verified account to the socket. It then checks conversation membership on every relevant action. Credentials need expiration/logout/revocation behavior for sockets that can remain open for a long time. Cookie flags, browser behavior and cross-site request risks must be reviewed together; Origin validation remains necessary. [OWASP WebSocket security](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html).

A short-lived one-use connection ticket or explicit authenticated first frame is another possible protocol, with strict expiry, timeout and pre-auth resource limits. Placing a bearer secret in a URL or treating `Sec-WebSocket-Protocol` as a casual credential container risks disclosure through infrastructure logging and conflates authentication with protocol selection. Baatchit's current `chat.v1` value is public compatibility metadata and supplies no authentication.

#### 41. What is coordinated omission, and does the current harness avoid it?

Coordinated omission occurs when a load generator's behavior hides delays during overload. Suppose traffic should arrive every 200 ms but the generator waits for a previous response or blocks for one second before sending again. The missing or delayed intended arrivals are absent from the latency calculation, making an overloaded server look better than the intended workload experienced. Constant-rate tools often measure from the intended request time to expose that delay. [wrk2's explanation of coordinated omission](https://github.com/giltene/wrk2).

Baatchit's harness has a target schedule and independent receiver tasks, so it does not simply wait for every recipient before planning another send. However, the sending loop still awaits `socket.send()` sequentially and records the timestamp immediately before that actual send. If the loop runs late or blocks, the report does not include the full delay since the intended send time. It should not be described as fully correcting coordinated omission.

For stronger evidence, record intended time, actual send time and receipt time separately, report scheduling lag, and bound concurrent in-flight work so the generator itself cannot grow without limit. Missing deliveries and failed sends must stay in reliability accounting. The local result remains useful as a client-observed send-to-receipt measurement within those limits.

#### 42. What does p99 mean, and how many samples were measured?

p99 is a high percentile of a defined observation set. The harness sorts recipient latencies and selects the nearest-rank observation at `ceil(0.99 × sample_count)`. About 99% of observed deliveries are at or below that value. It is not the slowest delivery, and it says nothing about deliveries absent from the sample list. That is why the timely-delivery ratio and errors accompany it.

The short run published **300 messages and measured 7,500 recipient deliveries**. Calling it “300 latency samples” would be inaccurate for this script. With 7,500 observed deliveries, about 75 lie in the slowest 1%; with 300 message-level observations, only about three lie there. Recipients of the same publication share delays, so those 7,500 observations are correlated and cannot be treated as 7,500 independent experiments.

The planned 30-minute workload would expect 225,000 recipient deliveries, but it remains a target until executed. Longer runs can expose memory growth, GC/scheduling effects and failures that a minute misses. Multiple runs, distributions by replica/time window, loss rates and maximum latency provide a more useful performance picture than a single rounded p99.

#### 43. Why run one Uvicorn worker per Pod?

The implementation stores sessions, token buckets, subscriber state and metrics inside one Python process. One Uvicorn worker per Pod makes the configured 64-connection cap and 20-publications/s budget apply to that Pod's one runtime. It also keeps the Redis subscription and shutdown lifecycle straightforward: one process owns one local session registry and one telemetry registry.

Adding four workers would create four independent copies of those structures, potentially allowing four times the intended admission/publication budgets in a Pod. Each worker would also subscribe to Redis, keep its own connection pool and expose its own metrics. That can be a valid architecture, but it would need revised resource budgets, metrics aggregation, health semantics and failure tests. It cannot be introduced as a harmless command-line performance tweak.

One worker does not make Python CPU work parallel; async scheduling primarily helps while tasks wait for I/O. CPU-bound work can still stall the loop. Kubernetes can scale Pods, but this repository uses two configured replicas and does not bundle an autoscaling policy. More Pods are useful only with measured host capacity or additional nodes.

#### 44. How do you limit a reconnect storm?

A reconnect storm occurs when many sockets fail together and immediately retry against recovering services. The browser uses full jitter: a random delay from zero to an exponentially increasing ceiling, starting at 500 ms and capped at 15 seconds. It stops after ten failed retry attempts and resets the counter after a stable 30-second session. Randomness spreads retry work instead of making clients synchronize at exact intervals.

For `1012` planned restart, the client uses a short 0–500 ms window to restore sessions quickly. That is useful at the current scale, but a much larger fleet might need a wider restart window. The gateway adds an observed-peer-IP handshake limit of five per second with a burst of 20, and backends reject connections beyond capacity or while unready/draining.

These controls reduce pressure; they do not guarantee fairness or prevent a hostile client from ignoring backoff. K3s ServiceLB/address translation may make several users appear under one gateway-observed peer address, so that limiter is coarse. A future large deployment would test retry distributions, recovery admission, available headroom and authentication-aware quotas rather than assuming the browser policy alone protects the server.

#### 45. What is likely to break first on a 2-vCPU host?

There is no measured answer for the intended AWS host yet. CPU saturation is plausible because JSON validation/serialization, Redis work, Nginx, K3s and many socket writes share two vCPUs. Memory or buffers can also bind first with many slow consumers, and the configured connection or publication limit can reject traffic before hardware is saturated. A confident claim that CPU always fails first would exceed the evidence.

I would increase one workload dimension at a time: clients, aggregate sends, payload size and slow-reader fraction. Collect per-Pod CPU/throttling, memory, event-loop symptoms, Redis buffers, gateway behavior, file descriptors, host `MemAvailable` and delivery errors/latencies. The backend's 500m CPU limit also matters: a Pod can be throttled even when the whole host is not fully busy.

The first violated acceptance criterion defines the useful capacity boundary, not necessarily a crash. Rising p99, queue overflow, admitted-capacity rejection or depleted host headroom can make the service unacceptable earlier. Record the bottleneck, change one relevant setting/design, and repeat the same workload before claiming an improvement.

#### 46. Could two Pods see messages in different orders?

During an uninterrupted healthy subscription to the same single Redis channel, both should receive the common publications in Redis's publication order. Their socket delivery times can differ because writers and networks progress independently. This does not imply that client timestamps or pre-publish server timestamps define that order.

Different observed histories are possible when a subscription starts late, disconnects, drops invalid envelopes, or a client is removed for backpressure. One Pod might receive A/B/C while another receives A/C because it missed B. That is a gap, not proof that Redis reordered B and C. The current protocol has UUIDv4 IDs and timestamps but no consecutive room positions, so clients cannot infer every missing event.

If future requirements demand detecting such gaps, assign an ordered room position from the durable source of truth and carry it through history and live delivery. Clients can then identify an interval to replay, subject to retention and authorization. Multi-channel or multi-region designs require a fresh ordering contract; the current single-channel behavior cannot simply be generalized to them.

#### 47. How would you design a release with no application outage?

First define the objective. Keeping new connections available during a rollout is different from keeping every existing WebSocket continuously open or guaranteeing no message loss. A backend replacement necessarily ends sockets owned by the old process unless a much more complex connection-transfer design exists. `1012` plus fast reconnect can reduce interruption but does not preserve the original connection or recover its missed messages.

A proposed design would provide redundant ingress and backend capacity, readiness gates that prove the subscription path, rolling updates with enough spare resources, graceful drain and compatible old/new protocols. Redis replacement/failover also needs its own continuity design. Static assets and cached clients must remain compatible during a mixed-version rollout, and client reconnect bursts must fit remaining capacity.

Today the gateway, frontend and Redis use `Recreate` and all components share one host, so full-stack uninterrupted availability is not claimed. The backend rollout uses `maxSurge: 0` and `maxUnavailable: 1`; it does not guarantee enough spare capacity for every reconnecting client. A real release/recovery rehearsal under load is needed before assigning an availability target.

#### 48. What would you monitor first in production?

Start with whether a real user can complete a session and exchange an event. A synthetic probe should connect through the public entry, validate its session, publish a uniquely identified message and observe cross-replica delivery with a timeout. That covers more than an Nginx `/ready` response. Track failures and latency over time and avoid inserting sensitive content in probes.

The existing private metrics help explain symptoms: `chat_subscriber_ready` for receive-path health; `chat_connections_active` against 64 per process; `chat_admission_total{status}` for rejection outcomes; `chat_outbound_queue_bytes` and `chat_deliveries_total{status}` for slow-reader pressure; `chat_messages_published_total{status}` for publication outcomes. Broker heartbeat publications also use that publish counter, so it is not a pure user-chat throughput counter. `sent` deliveries mean completed server socket sends, not browser acknowledgments.

Add Kubernetes restart/OOM/CPU-throttling data, host memory/disk pressure, TLS expiry and a trustworthy deployment/release view. These need a collector, retention and an alert owner; the repository does not bundle persistent monitoring or alert routing. Scrape each Pod separately and attach target identity at collection time because current series do not include a replica label.

#### 49. Why keep business logic out of Nginx?

Nginx handles the public HTTP/TLS boundary: route static and WebSocket requests, forward upgrade headers, apply security headers and coarse handshake limits, and deny private diagnostic paths. Those concerns benefit from an efficient reverse proxy and can be checked independently of the room's event handling.

FastAPI handles application rules: exact Origin/subprotocol admission, username/text policy, capacity, rate budgets, session creation and server-owned events. Keeping those decisions in the backend gives them access to the actual session and broker state and makes unit/integration testing direct. There is no duplicated chat validation policy to keep synchronized inside proxy configuration.

The proxy remains part of the trusted request path, so its header rewrites, TLS configuration and routes still need review. It also cannot enforce application message rates after a WebSocket upgrade using a simple HTTP request limiter. A future centralized authentication gateway could have a deliberate role, but the backend would still need to trust and authorize verified identity correctly.

#### 50. What is the weakest part of this design?

The answer depends on the intended product. For a public ephemeral demonstration, the main availability weaknesses are the single Redis instance, gateway and host. For a real private messenger, missing identity, authorization and durable delivery would be fundamental functional gaps. The current app also lacks moderation, long-term monitoring and complete browser/accessibility acceptance.

There are concrete failure consequences: loss of Redis interrupts both backend replicas; loss of the host interrupts the whole application; missed messages have no replay source; display names can be impersonated; and server infrastructure can read plaintext because there is no end-to-end encryption. Local tests exercise important application behaviors but do not certify a deployed AWS service, its rollback or internet abuse resistance.

A strong interview answer explains why those limits match the baseline scope and what evidence would justify the next step. I would prioritize requirements and measured failure impact, then add identity/durability or host redundancy according to the product goal. I would avoid calling the system production-ready based only on its Kubernetes manifests or short healthy benchmark.

### System design: requirements and capacity planning

The following questions extend the interview beyond the current ephemeral room. **Questions 51–80 are design discussions, not implemented features or measured capacity claims.** Use the current Baatchit behavior as the starting point, state assumptions, and explain the change in guarantees before proposing a larger architecture.

| Question range | Interview focus |
| --- | --- |
| 51–55 | Requirements, workload estimates, connection capacity, queueing and availability objectives |
| 56–60 | Database choice, message schema, pagination, sharding and large rooms |
| 61–65 | Network partitions, authorization races, concurrent edits, idempotency and multiple regions |
| 66–70 | Connection routing, autoscaling, overload protection, migrations and disaster recovery |
| 71–75 | Receipts, multiple devices, presence, attachments, search and encryption |
| 76–80 | Notifications, service boundaries, caching, failure testing and implementation priorities |

#### 51. How would you begin a system design interview for a chat application?

I would establish what the interviewer means by “chat” before drawing components. The main functional questions are public rooms versus private conversations, one-to-one versus groups, accounts and multiple devices, whether history/offline delivery is required, and whether attachments, search, receipts and end-to-end encryption are in scope. Baatchit's existing answer is one anonymous public text room without durable history; a WhatsApp-like answer would require a substantially different data and security model.

I would then ask about concurrent sockets, daily active users, aggregate send rate, group sizes, retention, acceptable latency, availability and recoverable data loss. “Support a million users” does not define how many are online or how much fanout occurs. I would state assumptions explicitly if the interviewer leaves them open and mark which targets are product decisions rather than established measurements.

The initial diagram should show the client transport, connection ownership, message acceptance point, fanout path and any durable store. After that, I would trace one normal send and one failure around acceptance. This exposes missing guarantees earlier than a long list of services and gives the interviewer clear decisions to challenge.

#### 52. How would you estimate capacity for one million registered users?

I would translate registered users into an explicit workload. As an **illustrative exercise**, suppose one million registered accounts yield 100,000 daily active users, each sending 20 messages/day. That is two million messages/day, about 23 messages/s on average. A chosen 10× peak assumption gives roughly 230 messages/s. These assumptions require validation; they are not Baatchit measurements or universal chat usage ratios.

If 5% of those daily active users are connected at peak, that implies 5,000 sockets. If each message has ten online recipients on average, peak fanout is about 2,300 recipient deliveries/s. At an assumed 1 KiB wire event, that is roughly 2.3 MiB/s of application payload before transport overhead and retransmissions. A separate assumption of 1 KiB stored per message would imply about 57 GiB for 30 days of two million messages/day, before indexes, replicas, backups and attachments.

I would size the connection tier, durable writes, fanout, storage and network separately, then load-test the intended distribution. Dividing 5,000 by the current 64-slot limit would produce a nominal Pod count, not an approved deployment: neither that per-Pod limit nor the current single host establishes capacity for this hypothetical workload.

#### 53. Why do concurrent connections and request rate need separate estimates?

A WebSocket can remain connected for minutes without sending a message. That consumes a socket, session state, tasks, transport buffers and heartbeat work even at low message throughput. Conversely, fewer highly active clients can saturate publication/fanout CPU while the connection count is still far below its cap. One number therefore cannot describe both resource demands.

For a proposed workload, I would estimate connection arrivals and average session lifetime separately from message arrivals and audience size. Under reasonably stable conditions, connection arrival rate multiplied by average session duration gives an approximate active-connection population. Long-tailed sessions, reconnects and peaks require more than the average; a dependency restart can create a burst of admissions unrelated to normal message QPS.

The design needs tests for idle connections, high send rate, large audiences and reconnect surges. Baatchit's current 64-per-process admission cap and token buckets address separate parts of this picture. The existing load run combined only 25 sockets with five aggregate messages/s, so it cannot identify the ceiling of either dimension.

#### 54. How would you choose queue sizes and a latency budget?

I would start with the delay the product can tolerate and allocate it across admission, validation, durable acceptance if added, broker transport, local queueing and socket delivery. A queue is not free capacity: it trades immediate rejection for waiting and memory. A large queue can hide overload until users see stale messages and the process consumes excessive memory.

For a stable stage, Little's Law relates average queued/in-system work to arrival rate and average time: `L = λ × W`, using matching boundaries and units. If a particular socket receives five events/s and its allowed average queue wait is 200 ms, the implied average queued work is about one event. That does not directly prescribe a one-event hard cap; bursts and tail behavior need separate treatment.

When arrival rate exceeds service rate, backlog grows approximately at the difference until a bound is reached. With no progress and five events/s, a 32-event queue fills in roughly 6.4 seconds from empty, although Baatchit's two-second write deadline may close it sooner. I would test burst tolerance, event/byte caps and rejection behavior instead of increasing limits until the test stops failing.

#### 55. How would you define an availability SLO for this system?

I would distinguish “the home page responds” from “a user can establish a session and exchange a message.” A useful messaging SLI might count valid send attempts whose event reaches an eligible online recipient within two seconds, with a clearly defined population and treatment of disconnects, invalid input and overload. A separate connection-admission SLI can reveal failures hidden by measuring only already connected users.

The observation boundary matters. Backend `/live` is process liveness, Redis subscriber readiness is dependency progress, and gateway `/ready` is only a small proxy response. None alone measures cross-replica chat. I would use synthetic sessions plus real outcome counters and define a time window, alert ownership and error-budget policy before committing to a percentage.

A series of required dependencies also compounds risk. Multiplying dependency availabilities can illustrate a series path only if the independence and definition assumptions hold; it is not a substitute for measurement. Shared EC2, zone, network and deployment failures are correlated. Baatchit's single host and Redis therefore prevent deriving a strong availability claim merely from two backend replicas or a short successful benchmark.

### System design: persistence, partitioning and access patterns

#### 56. Would you choose a relational database or a NoSQL database for persistent chat?

I would begin with access patterns and invariants rather than a category preference. A private messenger needs to look up conversation membership, append messages, retrieve history in order, record submission IDs and update per-user/device cursors. A relational store is a reasonable candidate when transactions and membership constraints simplify those operations; a partitioned key-value or wide-column model may suit predictable conversation-key reads at a different scale.

The important comparison is how each candidate supports ordered pagination, hot partitions, conditional writes, uniqueness, retention, failure recovery and operational ownership. A schema-less interface does not remove schema design, and a relational database does not automatically require one machine forever. I would benchmark a representative hot conversation and a realistic mix of writes and history reads, not just raw insert throughput.

For Baatchit's present ephemeral room, no database is necessary. Adding one would introduce a durability promise, backups and recovery work. If choosing a relational design for a first persistent version, I would explain its transaction boundaries and indexing before adding separate services. At a later proven bottleneck, the access-pattern measurements would guide partitioning or a different store.

#### 57. What tables or entities would you propose for group chat?

A possible model has `Account`, `DeviceSession`, `Conversation`, `Membership`, `Message`, `Submission` and `Outbox` entities. Membership connects accounts to conversations with role/status and any history-access boundary. Message records carry a stable ID, conversation, sender identity, an ordered conversation position or defined ordering key, content/version and creation metadata. Submission records bind a client retry key to a recorded acceptance decision.

Important proposed constraints include one membership entry per account/conversation, one accepted result per scoped submission key, and uniqueness of a conversation position where that is the ordering contract. Required fields, foreign keys and transaction behavior should protect invariants even when two requests race. Database constraints enforce rules independently of a friendly UI. [PostgreSQL constraints](https://www.postgresql.org/docs/current/ddl-constraints.html).

I would save the accepted message and notification work atomically when using an outbox. Read/delivery cursors could be separate per account/device rather than one row per recipient per message. Attachments would reference controlled object metadata instead of storing arbitrary file bytes in each message row. This schema is a discussion starting point; Baatchit has none of these persistent entities today.

#### 58. How would you paginate a long conversation history?

I would propose cursor-based pagination over a deterministic, indexed conversation order. A request might ask for up to 50 entries before a known position in a specific conversation. The query must include conversation authorization and a unique ordering key. A timestamp alone can tie, so the order needs a stable tie-breaker or an explicit conversation sequence.

Offset pagination is easy to demonstrate, but large offsets require skipping work and concurrent inserts/deletes can shift page boundaries. Even a limited SQL query needs a predictable ordering to return stable subsets. [PostgreSQL LIMIT/OFFSET behavior](https://www.postgresql.org/docs/current/queries-limit.html). A keyset cursor describes a boundary rather than “skip the first 20,000 rows,” making repeated older-page reads easier to reason about.

The cursor should be validated and scoped to its conversation; hiding a room ID in a token is not authorization. I would define what happens when retention removed the boundary or messages were deleted, cap page size and bytes, and consider whether a snapshot boundary is needed for a browsing session. Live events and history pages must share identifiers/order semantics to deduplicate overlap safely.

#### 59. How would you choose a partition key for messages?

The partition key should match the common read/write boundary. If most reads fetch one conversation's ordered history, `conversation_id` is a natural starting point because related messages stay together. Partitioning only by sender might spread writes well but make one group history expensive to assemble across many partitions.

The trade-off is skew. One conversation may be much busier than thousands of others, and a single partition then becomes a bottleneck. Time buckets or subpartitions can spread storage, but history queries, ordering, retention and migration must understand that additional boundary. A stable event ID and routing/version metadata are useful when records move, while the client-facing conversation identity should remain stable.

I would ask whether the store must support cross-conversation inbox queries, search and recipient delivery tracking; those may need separate indexes or projections rather than forcing one partition key to serve every access pattern. The current Redis room channel is a fanout path, not a database shard key or a durable ordering record. Splitting channels alone would not implement the proposed storage model.

#### 60. How would you handle a very large or unusually active room?

A “hot room” concentrates both message input and recipient output. Giving it another database shard does not eliminate the need to send its messages to a large audience. I would first quantify sender rate, audience, payload size, online fraction and acceptable delay, then identify whether ordering, storage writes, broker fanout or socket writes is the actual constraint.

A proposed architecture can separate one room's acceptance/order stage from multiple recipient-delivery workers, each responsible for a subset of live connections. The event is created once and distributed through bounded tiers. Admission, per-room publication limits, batching where latency permits, and separate ephemeral typing/presence traffic can keep one hot room from consuming all shared resources. Each tier still needs queue limits and failure semantics.

Product choices also matter: audience caps, slower posting modes or broadcast-style rooms can change the workload more than extra Pods. I would not promise arbitrary group size from the current five-messages/s benchmark. A hot-room load test should include skewed membership and slow readers, and verify that ordinary rooms retain their own resource budget.

### System design: consistency, authorization and multiple regions

#### 61. How does a network partition change the consistency/availability decision?

A partition means components that need to coordinate cannot communicate reliably. In a proposed durable chat service, the product must decide whether a disconnected side may acknowledge new messages as accepted. If acceptance requires a shared authoritative record/order, a side unable to reach that authority must wait or reject. Accepting independently may preserve local responsiveness but creates reconciliation and ordering work later.

This is the useful setting for a CAP discussion: which operations need a consistent authority during a partition, and which may serve stale or tentative state? It is too vague to label the entire app “CP” or “AP” without defining operations and guarantees. Typing indicators and a membership revocation do not have the same consistency requirement.

Baatchit's current implementation chooses to stop admitting/serving chat when the Redis path is unhealthy rather than create isolated local conversations. That avoids knowingly pretending the shared room is working, but the heartbeat is not consensus and messages can still be missed around failure detection. A future offline compose experience would need an explicit pending state, idempotent synchronization and conflict rules.

#### 62. What if a user is removed from a group while a send is in flight?

I would require a precise membership boundary: does a send count if it was accepted before the removal transaction, and can the removed user read old history afterward? Without that rule, “check membership” is underspecified. Checking only at WebSocket admission is insufficient because a socket can remain open after permissions change.

A proposed relational design can coordinate authoritative membership/version checks with message acceptance in a transaction or equivalent conditional operation. The exact isolation/locking approach must prevent the race the product forbids; merely doing a membership read and later an insert does not establish atomic authorization. Isolation levels differ in what concurrent changes they expose. [PostgreSQL transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html).

Cached membership needs version/expiry/invalidation behavior and a defined revocation delay. A removal event can also update or close affected sessions, but it cannot withdraw a message already delivered to a device. I would test both transaction orders, delayed invalidation and reconnect attempts. Baatchit currently has no private groups or membership authorization, so this is a new security contract.

#### 63. How would you handle concurrent message edits and deletions?

I would treat edits/deletions as versioned operations on a stable message ID. The client could supply the version it last saw; the server would conditionally update only that version after checking ownership/permission. Two simultaneous edits then produce a defined conflict rather than silently overwriting each other. Whether to reject, merge or use a documented winner is a product decision.

Deletion needs a rule too: a tombstone may preserve position and prevent an older delayed edit from resurrecting content. Every broadcast/projection should carry enough version information to ignore stale updates. A client reconnecting after a deletion must learn the new state; only broadcasting “delete” live would leave offline devices with an outdated copy.

“Delete for everyone” also has limits. It cannot guarantee a recipient did not copy or screenshot a message, and backups/search indexes/object storage need their own lifecycle rules. Retention, audit and encrypted-device behavior must be specified. The current app has append-only live display behavior without persistent edits or deletion, so adding buttons alone would not implement these semantics.

#### 64. What makes an idempotency design correct under concurrent retries?

A reliable design scopes a client submission key to the authenticated caller and operation/conversation, then records one acceptance decision atomically with the message. Two concurrent requests with the same key must not both create a new message. The stored result should let a retry return the original message identity/status even if the first response was lost.

The payload must also be checked: reusing the same key with different text or a different conversation should produce a defined conflict rather than silently return an unrelated success. Retention of idempotency records must cover the promised retry window; expiring the key too early allows an old retry to create a second message. A memory-only cache cannot provide this guarantee across a crash.

This is more than adding `event_id` after acceptance, because a retried submission could otherwise get a fresh event ID each time. Delivery consumers may still need deduplication when notification work retries. AWS describes caller-provided request identifiers and handling repeat intent as central to safe retry APIs. [Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/). No such submission protocol exists in current Baatchit.

#### 65. How would you design a chat service across multiple regions?

I would first identify the reason: lower connection latency, disaster recovery, regional availability or data placement. A simple proposed approach assigns each conversation an authoritative home region for acceptance/order while clients connect through a nearby edge. That preserves one ordering authority but may add a cross-region trip for remote senders and needs a defined failover process.

Allowing several regions to accept independently can improve local responsiveness, but requires conflict/ordering rules, deduplication and careful membership/revocation semantics. Replication delay affects history freshness, receipts and notification timing. A regional outage also raises the question of whether a failover side has all acknowledged messages; its RPO depends on how acceptance and replication were configured.

I would diagram the message and authorization paths and state which operations stop during a partition. I would measure cross-region latency and failover under load rather than multiply the local 16 ms number. Baatchit's current single-host K3s target has no regional routing, replication or disaster recovery, and adding a second deployment does not create those guarantees.

### System design: routing, scaling and recovery

#### 66. How would you locate an online user's connections across many backend servers?

A backend knows only its own socket objects. A proposed direct-message system therefore needs either a way to route events to the relevant connection servers or a fanout pattern those servers subscribe to. A directory could map an account/device/session to an owning backend and connection ID, with leases so crashed owners eventually disappear. It must support multiple simultaneous devices rather than one “user → server” entry.

The directory is a routing hint, not the durable message authority or an authorization record. A stale mapping can cause a missed live notification, so reliable delivery should still be recoverable from the recipient's durable inbox/cursor. When a user reconnects, a delayed cleanup from the old connection must not delete the new connection's mapping; ownership/version checks or session-specific entries prevent that race.

Sticky routing can improve locality for new connections but cannot move an existing socket after its process dies. Baatchit avoids a user directory because every backend subscribes to the one global room and fans out locally. A more selective directory becomes useful only with identities/conversations and a workload where global broadcast is too costly.

#### 67. How would you autoscale a WebSocket backend?

I would scale using demand that represents persistent sockets and their work, such as active connections relative to tested capacity, delivery rate, CPU/throttling and queue pressure. CPU alone can miss a large idle socket population; connection count alone can miss a few busy rooms. The metric must be collected per Pod and interpreted with enough resource headroom and minimum replicas for recovery.

Adding Pods does not redistribute existing WebSockets. New connections may use new Pods while old ones remain full, so scale-out benefit can be delayed and averages can hide imbalance. Scale-down must stop admission, drain a selected Pod, budget reconnects and retain capacity elsewhere. Aggressive oscillation would create repeated client disconnects and invalidate stable-load assumptions.

Kubernetes HPA supports resource/custom/external metrics when the corresponding metrics interfaces are available; it does not supply an application connection metric automatically. [Kubernetes horizontal autoscaling](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/). Baatchit has no HPA/adapter setup, and a single fixed host can run out of scheduling capacity even if an autoscaler requests more replicas.

#### 68. How would you shed load without letting one tenant or room overwhelm others?

I would distinguish critical work from disposable work. In a future persistent messenger, durable acceptance and required recovery reads may take priority over typing indicators, presence refreshes and notification decoration. Every queue needs a maximum depth/bytes and deadline; if the system cannot accept an operation within its contract, it should reject it clearly rather than acknowledge and silently drop it.

Fairness needs more than a global limit. Per-account, per-room and per-tenant budgets can prevent one audience or abusive sender from exhausting shared publication, storage or connection resources. A hierarchy must still cap the whole service, and a distributed limiter needs an explicit accuracy/failure model. A local bucket is inexpensive and protective but does not give a strict global quota when replicas multiply.

I would avoid retry amplification by making clients back off and by defining which failures are retryable. Expired optional events can be coalesced/dropped instead of retried. Baatchit's current per-socket/per-replica buckets and bounded writers are a small baseline; it has no authenticated tenants or global fairness guarantee. The test should show both overload rejection and healthy service for an independent allowed workload.

#### 69. How would you migrate the broker or database while clients remain active?

I would separate schema/protocol compatibility from data movement. An expand-then-contract plan first introduces readers that understand both old and new representations, then backfills/migrates under checkpoints, validates results, switches authority and finally removes the old path. Each phase needs a rollback condition and a way to identify which version produced an event.

Naive dual publishing is dangerous: a client can receive duplicates through both buses, order may diverge and one write may succeed while the other fails. For durable data, I would designate one authoritative acceptance log and replicate/dispatch from it, preserving IDs and order boundaries. A shadow consumer can compare output without delivering a second visible copy. [Transactional outbox and dual-write failure considerations](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html).

WebSocket clients may remain on an older frontend/server version throughout the migration. The handshake contract, event shapes, cursors and reconnect behavior therefore need compatibility tests. In current Baatchit, strict exact-field parsing and no durable replay make a live bus switch particularly easy to overstate: lost events cannot be reconstructed. A reconnect window or maintenance boundary may be the honest baseline choice until a durable migration path exists.

#### 70. What would a disaster recovery plan contain?

I would define the failure: loss of one process, the EC2 host, a zone, a region, data corruption or credential compromise. Each needs explicit RTO/RPO targets and evidence. Recreating a server in ten minutes is not enough if the restored service lacks keys or has lost messages that were promised durable.

For a future persistent version, the plan would inventory database/log backups, retention, restore checkpoints, encryption keys, credentials, object storage, DNS/TLS, image artifacts and infrastructure state. A restore drill should recover into an isolated environment, validate membership/message integrity, determine the last accepted recoverable position and verify a real send/read path before routing users there. Replication is not a substitute for protection against replicated deletion/corruption.

Today Baatchit's Terraform and manifests help recreate infrastructure, but its chat has no durable recovery source. The S3 state bucket, if created, records infrastructure state rather than message history. A single Redis/host outage can end the live room; missed messages remain lost. A useful current drill would measure environment reconstruction and new-session recovery without claiming restoration of old chat.

### System design: user-visible messaging features

#### 71. How would you implement delivery and read receipts?

I would define each receipt before choosing storage. “Accepted” could mean the server committed the message durably; “delivered” could mean a particular recipient device acknowledged receipt; “read” requires an explicit client action/visibility rule. A completed server socket write or push-provider response does not prove either device display or human reading.

A proposed model can store per-device delivery cursors and per-account/conversation read cursors instead of one row per message-recipient pair. A cursor must advance only across the range its semantics cover: the highest message number seen does not prove all earlier messages arrived if gaps exist. For group chat, the UI also needs a rule for how multiple members/devices aggregate into a badge or count.

Receipt updates themselves can be duplicated or arrive out of order, so monotonic/versioned updates and idempotency matter. Privacy preferences, blocked users and retention affect who may observe them. Baatchit currently returns room events with IDs but has no durable acceptance, device identity, acknowledgment command or receipt store. Implementing receipts would require those dependencies rather than adding checkmarks to existing messages.

#### 72. How would multiple devices stay in sync for one account?

I would separate account identity from device/session identity. Each device needs its own authorized session, last received position and possibly delivery acknowledgment, while some state—such as read position—may be shared at account/conversation level according to the product rules. Disconnecting one device must not mark every other device offline or discard their routes.

Messages should enter one authoritative history and fan out to the sender's other devices as well as recipients. A newly linked device would retrieve an authorized snapshot/history page and then follow a cursor without a replay gap. Repeat sends from one device need a scoped submission ID; synchronization copies must not create new messages. Device removal/logout needs credential revocation and a defined effect on open sockets.

End-to-end encryption adds per-device key distribution, verification and history-sharing decisions; it cannot be assumed to work because accounts share a username. Baatchit currently has independent anonymous tabs with only local memory. Two tabs choosing the same display name are not recognized as one account and do not share drafts or history.

#### 73. How would you implement typing indicators and online presence?

These are short-lived hints and should have different storage/delivery policies from durable messages. A typing update could carry a conversation, device/session and expiry, be rate-limited/coalesced and disappear automatically without an explicit stop event. Retrying every stale typing packet after reconnect would add load while showing incorrect activity.

Presence could be based on active session leases renewed by heartbeats, with account-level online state derived from its devices. A connection close can remove a lease promptly, but expiry is still needed for crashes. Delayed heartbeats or cleanup must not overwrite a newer session, and “offline” is an approximation when networks partition or browsers suspend background tabs.

I would specify visibility/privacy rules and whether a user can hide status, cap metadata retention, and keep these events out of durable chat history unless the product explicitly requires auditing. Baatchit's join/leave system messages are advisory announcements, not a presence registry. A future presence path should not be implemented by counting those notices.

#### 74. How would you add file and image attachments safely?

I would keep large file bytes out of the existing text WebSocket path. A proposed flow authenticates the sender, checks conversation access and upload limits, allocates an unpredictable object key, and gives a short-lived scoped upload capability. The client uploads to object storage; the service records attachment metadata and allows a chat message to reference only an authorized, finalized attachment.

S3 presigned upload URLs are one possible mechanism. They grant the signer's permitted operation for a period and can overwrite an existing object at the same key, so they should not be treated as inherently one-use tickets. [S3 presigned uploads](https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html). Unique keys, ownership checks, expiry and a controlled finalize step are design responsibilities.

The full lifecycle includes maximum size, content validation, quarantine/scanning where applicable, download authorization, orphan cleanup, retention/deletion and storage/egress cost. Server-side scanning of plaintext also conflicts with a claim that the server can never decrypt attachments; an encrypted design needs an explicit threat model. Baatchit's current 16 KiB text transport and ephemeral events do not supply any attachment flow.

#### 75. How would search work, especially with end-to-end encryption?

For a future plaintext-on-server design, search is usually a derived index of authorized message history. The source of truth should remain the durable message store, and the search result must be filtered by current conversation access. Index updates can lag, so the UI needs defined behavior for newly sent, edited, deleted or retention-expired messages.

End-to-end encryption changes the requirement: a server that has only ciphertext cannot simply build a plaintext inverted index without learning content through an additional mechanism. One option is local device indexing after decryption; that limits search to locally available/synchronized history. Other encrypted-search schemes have different leakage and operational trade-offs and need specialist review rather than a casual “encrypt the database” claim.

I would ask whether users need global search, only current-device history, and how deletion propagates to indexes/backups. Baatchit has neither persistent history nor encrypted device storage, so search and E2EE are separate future features. A design answer should expose that dependency instead of naming a search engine and assuming confidentiality follows automatically.

### System design: asynchronous work and design review

#### 76. How would you deliver push notifications to offline users?

I would treat push as a notification path rather than the authoritative message delivery store. After a durable message is accepted, notification work can be recorded with the same acceptance/outbox decision and processed asynchronously. A provider accepting a request does not prove that the recipient device received, displayed or read it.

The worker needs device registration, user notification preferences, conversation authorization, retry/backoff, expiry and duplicate suppression. A delayed job may become irrelevant if the recipient already read the message, left the group or revoked a device. Sensitive message bodies should not automatically appear in provider payloads; a minimal “new activity” notification can prompt the client to fetch authorized history.

Repeated failures need an operational policy, bounded retries and a dead-letter/review path, not an infinite tight retry loop. Losing the notification should not lose the durable chat message. Baatchit currently has no accounts, device tokens, history, push worker or notification queue, so this design would depend on substantial earlier changes.

#### 77. Would you split this application into microservices?

I would choose boundaries from independent scale, security and ownership requirements. The current frontend, gateway, backend and Redis are separate deployment components, but two replicas of the same backend are not two business services. The small codebase can keep authentication/conversation/message modules together while preserving clear interfaces and tests.

A modular application can make a first persistent message transaction easier to reason about. Splitting membership, messages and delivery into independently deployed services introduces network failures, versioned APIs, distributed tracing and cross-service consistency problems. The benefit must justify that operational cost. Media processing, push notifications or search indexing may become useful asynchronous boundaries because their resource needs and failure tolerance differ from live message acceptance.

If a split is justified, I would define ownership of data, the authoritative acceptance decision, event contracts, timeouts and recovery before moving code. Shared database tables with unclear ownership can leave the complexity of services without real independence. Baatchit's present scale and evidence do not require a large microservice architecture.

#### 78. What would you cache, and how would you keep authorization safe?

Candidate caches in a future persistent system include conversation metadata, profile display data and recent history pages. Each should have an authoritative source, bounded size, TTL/version and invalidation behavior. A cache hit improves latency only if its freshness is acceptable for that operation; permission to access a private conversation has a different risk from a stale avatar.

For membership, I would specify the maximum revocation delay and how accepted writes consult authoritative state. Merely invalidating a cache after removal is insufficient if the invalidation is lost or races with a new cache fill. Versioned membership state, conservative fallback and short-lived cached decisions may help, but the required guarantee determines the transaction/check strategy. Fail-open behavior must be an explicit security decision.

Cache failures must not trigger unlimited fallback queries that overwhelm the store. Coalesced refresh, timeouts and load shedding can protect that dependency. The current Redis instance is a Pub/Sub broker, not a general application cache; its app ACL does not permit arbitrary key operations. Reusing it as a cache would require an intentional privilege/resource review.

#### 79. How would you test the system's distributed guarantees?

I would convert each guarantee into a concrete invariant and a failure timeline. In a proposed durable design, examples are: one logical message per scoped submission ID; no acknowledgment before the selected durability point; unauthorized accounts never read/send in a private conversation; and replay returns the allowed missing interval without duplicate logical effects. The current anonymous ephemeral app has a narrower set of guarantees and should not be tested against features it does not claim.

The most revealing faults occur between steps: commit before reply, outbox publish before worker acknowledgment, membership removal during send, backend crash with queued writes, broker failover, slow readers and reconnect during replay. Capture operation IDs, recorded decisions, cursors and outcome times so a test can distinguish loss, duplication, ordering gaps and ordinary timing variation.

I would combine deterministic unit tests for concurrency/control logic with real dependency tests and a limited set of full-system fault drills. Random failure injection without a stated invariant can generate noise. Baatchit's existing unit/integration/browser/load suites are a useful starting point; cloud failure recovery, true signing/deployment and sustained AWS resource tests remain separate acceptance work.

#### 80. What would you prioritize with limited time and budget?

I would agree on the product promise first. For an anonymous learning demo, the current ephemeral scope can remain useful while effort goes into reproducible setup, boundary tests, clear UI status, measured resource limits and a documented recovery path. For a private messenger, verified identity, authorization and durable acceptance take priority because otherwise the central privacy/delivery promises cannot be met.

Next I would choose one measurable risk to reduce at a time. A second backend replica on the same host is useful for process replacement but does not solve host loss; a persistent database helps history but creates backup/restore obligations; multi-region replication is hard to justify before a single-region acceptance model works. Each step needs a cost/resource worksheet and evidence that it improves the selected objective.

In an interview, I would finish the design by tracing one success path, one failure around acceptance and one overload case, then name the largest unresolved risk and the next validation. The strength of the answer is a coherent scope and defensible guarantees, not the number of cloud services drawn. All proposed extensions above require additional design and implementation beyond current Baatchit.

### Deep system design: concurrency and parallel execution

**Questions 81–130 extend the guide into deeper system design.** Each answer explains the mechanism, a concrete example, failure cases and the relationship to Baatchit. Proposed databases, shards, replication, authenticated tenants and other extensions remain design discussions. Existing asyncio/session controls are identified explicitly when they come from current code.

| Questions | Focus |
| --- | --- |
| 81–90 | Concurrency, races, locks, deadlocks, cancellation, CPU work and bounded execution |
| 91–95 | Sharding strategies, consistent hashing, resharding, cross-shard work and indexes |
| 96–100 | Replication, consistency, leaders, quorum and split-brain recovery |
| 101–105 | Load balancing, TCP behavior, timeouts, TLS and service discovery |
| 106–110 | Database indexes, storage engines, MVCC, change logs and data lifecycle |
| 111–115 | Scaling limits, failure headroom, tail latency, retries and fault isolation |
| 116–120 | API/protocol choices, global quotas, tenant isolation, encryption and credential rotation |
| 121–125 | Stateful services, cache stampedes, poison events, canaries and graceful degradation |
| 126–130 | Control/data planes, broker selection, batching, operational signals and design synthesis |

#### 81. What is the difference between concurrency and parallelism in this backend?

**Concurrency** means several operations can make progress over overlapping periods. **Parallelism** means work actually executes simultaneously on separate execution resources. In the current backend, one Uvicorn worker uses an asyncio event loop to manage many sockets, Redis I/O and timers. When one task suspends while waiting for I/O, another can proceed. It does not give every connected user a dedicated CPU core or thread.

For example, a slow socket writer can await its send while a healthy writer sends an event and the broker consumer reads Redis. That works because the tasks cooperate and waiting operations yield. A long synchronous JSON transformation or tight CPU loop does not yield simply because the surrounding function is declared `async`; it can delay all those tasks in that worker.

Parallel CPU work would require an appropriate execution strategy, such as separate processes or a library operation that can use other cores. That changes data sharing, scheduling and resource budgets. Baatchit's current two backend Pods provide separate process runtimes, while the intended AWS host still supplies one shared finite CPU budget. An interview answer should separate I/O concurrency, CPU parallelism and horizontal deployment rather than treating them as interchangeable.

#### 82. Can a single-threaded asyncio application still have race conditions?

Yes. A logical operation can read shared state, suspend at an `await`, and resume after another task changed that state. Suppose a proposed admission routine checks `active < limit`, awaits an external call and then increments `active`. Two tasks could both observe the final free slot before either increments, admitting too many sessions even though only one event-loop task executes Python at a time.

Current `Sessions.reserve` avoids that particular interleaving: it checks and increments without an `await`, and the token bucket also completes its local accounting synchronously. That relies on the current single event-loop ownership. It is not a guarantee for OS threads, multiple workers or distributed replicas, and a future refactor that inserts a suspension would require reviewing the invariant.

I would define the invariant first—such as `0 <= reserved <= max_connections`—then identify every state transition and suspension boundary. A solution may use a short local lock, a single owner/actor, or an atomic operation in the authoritative store. Locking every function indiscriminately can introduce contention without protecting the real transaction boundary. Tests should deliberately pause tasks at the suspected interleaving rather than depend on a race happening by chance.

#### 83. When would you use optimistic locking versus pessimistic locking?

Optimistic concurrency checks whether the state is still the version a caller observed. A proposed message edit might update `message_id` only when `version = 7` and then produce version 8. A concurrent editor using version 7 gets a conflict and must reread or resolve it. This is attractive when conflicts are uncommon and holding a lock across user think time would be unacceptable.

Pessimistic locking reserves exclusive access while a short critical transaction runs. It can simplify heavily contended decisions but creates waiting and deadlock risk. In a database, row locks and conditional updates have different behavior from an in-process `asyncio.Lock`: an asyncio lock coordinates tasks in one event loop, not another Pod or thread. [Python synchronization scope](https://docs.python.org/3.12/library/asyncio-sync.html).

I would choose based on contention, retry cost and the invariant. Group membership checks and message acceptance may need a coordinated transaction; a profile edit may tolerate version-conflict handling. Neither approach justifies keeping a lock while waiting for a browser or slow network call. Baatchit's current live text protocol has no persistent edit transaction, so this comparison describes a future extension rather than a missing lock in existing code.

#### 84. How do deadlocks happen, and how would you prevent them?

A deadlock occurs when operations wait on each other in a cycle. For example, one transaction locks conversation A and then requests B, while another locks B and then requests A. Neither can finish. Similar cycles can occur with local locks, bounded queues or tasks waiting for cleanup that itself depends on a lock they still hold.

I would reduce the risk by acquiring related locks in a consistent order, keeping critical sections short and avoiding external I/O while holding them. Timeouts limit waiting but do not automatically undo partial work; the failure path must release resources and decide whether the whole operation can be retried safely. Database deadlock detection can abort a transaction, so callers still need a bounded retry policy. [PostgreSQL deadlock and locking behavior](https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-DEADLOCKS).

For Baatchit, a useful review question is whether a session writer, registry and Redis consumer can wait on one another during close/drain. The current fanout avoids waiting for socket writes and cleanup cancels/awaits subordinate tasks. If a future per-room lock is added, its scope must preserve those non-blocking paths instead of serializing all room delivery behind one slow client.

#### 85. Why are task ownership and cancellation part of system design?

Background tasks consume resources and perform side effects even after their original requester disappears unless their lifetime is managed. A WebSocket session can end while its reader, writer or timer is still running. A Redis subscription generation can fail while its heartbeat continues publishing. Those orphan tasks can leak connections, mutate stale state or report a false readiness signal.

The current backend explicitly owns reader/writer tasks per session and consume/heartbeat tasks per subscription generation. Cleanup cancels and awaits related tasks; the browser separately uses connection generations and clears timers to ignore old sockets. A proposed refactor should retain that ownership tree. Structured task groups can help express related lifetimes, but their exception behavior must match the intended session/supervisor boundaries.

Cancellation is cooperative and does not erase an external effect. A publish may have reached Redis before the awaiting task was cancelled, and a database transaction might have committed before a response timed out. Cleanup should release local resources without pretending it reversed those effects. Python's task documentation describes cancellation and task-group semantics; application acceptance/retry semantics still need their own design. [Python tasks and cancellation](https://docs.python.org/3.12/library/asyncio-task.html#task-cancellation).

#### 86. How would you keep blocking I/O or CPU-heavy work from stalling chat?

First identify the work. A synchronous file/network library can block the event-loop thread while waiting. CPU-heavy parsing, encryption, image processing or large serialization can occupy it while computing. Both delay unrelated socket reads, sends, probes and timers, but the remedy is not always the same.

A bounded thread executor can be useful for blocking I/O. In the conventional CPython 3.12 runtime used by this project, the GIL prevents ordinary Python threads from automatically executing CPU-bound Python code across cores; separate processes or suitable native operations may be needed. [Python 3.12 threading model](https://docs.python.org/3.12/library/threading.html). Any executor adds queueing, serialization/context propagation and shutdown concerns, so “offload it” is not enough without capacity limits.

For example, a future attachment scan should run outside the live socket acceptance/delivery path, with explicit job state and failure handling. The current app avoids that workload and keeps messages small. I would measure event-loop delay, CPU throttling and task queue length before selecting an optimization, then verify that timeouts and readiness remain responsive during the heaviest supported operation.

#### 87. Why bound concurrency with semaphores and connection pools?

A rate limit controls arrivals over time; a semaphore limits how many operations may be in progress at once. A database pool also bounds backend connections. Neither automatically bounds the number of waiting tasks. If 10,000 requests all wait for a 20-slot pool without a deadline or admission bound, their memory and latency can still overwhelm the application.

A proposed history endpoint could acquire a bounded execution slot within a short deadline, then use a database connection and return a byte/page-limited result. It should avoid holding that connection while waiting for a slow browser to receive a large response. Pool size across all Pods matters: ten Pods with 20 connections each ask the database to support 200, not 20.

Baatchit's Redis client has a finite connection pool and socket command timeouts, but these settings are not a general database admission design. A future service needs a total concurrency budget, maximum waiter population, timeout policy and overload response. Raising the pool size can reduce local waiting while making the shared dependency slower, so the target should be measured useful throughput rather than zero local queueing.

#### 88. How would you enforce a global connection limit across several Pods?

An in-memory counter enforces a limit only within its owning process. A global cap would need an authoritative shared decision, or deliberately approximate per-Pod budgets whose total is understood. A shared counter alone is fragile: a process can increment then crash without decrementing, and a retry can reserve twice if the original result was uncertain.

One proposed design uses uniquely identified reservations with leases, renewal and release conditional on reservation ownership. Admission must account for the reservation's validity throughout the handshake and cleanup. A lease expiry can free abandoned capacity, but a partitioned process may still have a real socket alive; the system must define whether temporary over-admission is acceptable or require it to stop serving after losing authority.

That trade-off is often more important than implementing a perfect global number. Per-Pod limits plus load-aware routing may be enough for resource protection, while a contractual tenant quota may need stronger accounting. Current Baatchit intentionally uses 64 local slots per process and makes no strict global 128-client fairness or distribution guarantee. A distributed cap would add availability and coordination cost to every admission.

#### 89. How would you prevent starvation while preserving message order?

Fairness asks whether one source can continually crowd out another. FIFO queueing gives a clear order within a queue, but a large fanout burst, long CPU loop or dominant room can still monopolize a worker or a shared budget. Priority queues can improve urgent work while starving low-priority work if their scheduling policy has no fairness bound.

A proposed multi-room backend could assign bounded per-room queues and schedule small batches across them, while preserving the chosen order within each conversation. Weighted fairness can reserve capacity for ordinary rooms without allowing one hot room to consume the whole replica. Optional typing/presence events could have lower priority and expire, while accepted durable messages require recovery rather than silent dropping.

The present app has one room, per-socket writers and process-local publication budgets. It does not implement a tenant/room scheduler. Increasing fanout to very large audiences would also require checking whether the synchronous enqueue loop runs too long between yields. Introducing yields must preserve session lifecycle and ordering invariants; fairness improvements should be tested with both a noisy producer and independent healthy traffic.

#### 90. How would you test concurrency bugs reliably?

I would make the critical interleaving controllable. For a proposed versioned edit, pause two requests after they read version 7, release them together and verify that the allowed acceptance/conflict result occurs. For admission, pause at any suspension between checking and reserving capacity. For cancellation, trigger close while a writer is blocked and assert that tasks, queue accounting and reservations are eventually cleaned up.

Useful invariants include no negative reservations, no admission above the intended scope, one writer per socket, no event before the session envelope, and no stale generation updating readiness. Fake clocks and explicit barriers/events make these tests more repeatable than arbitrary sleeps. Real integration tests are still needed for transport and broker behavior that a fake cannot reproduce.

A test passing once is weak evidence for rare races; stress and varied scheduling can complement deterministic cases. Failure histories should preserve operation/session IDs and outcomes without logging sensitive text. Existing [session tests](../tests/unit/test_sessions.py) already use a deliberately blocked writer to verify isolation; broader distributed tests would be added only alongside the proposed new guarantees.

### Deep system design: sharding and data placement

#### 91. How do range sharding, hash sharding and directory-based sharding differ?

All three divide data, but optimize different operations. A range strategy keeps neighboring keys together, which can help scans and time-based lifecycle management. A hash strategy spreads keys more evenly when the hash input has enough diversity, but does not preserve natural range locality. A directory maps a logical key to an assigned shard and supports deliberate placement at the cost of a routing authority.

| Strategy | Chat example | Useful property | Main risk |
| --- | --- | --- | --- |
| Range | Conversation/time ranges | Local ordered scans or partition retirement | Newest range or popular conversation becomes hot |
| Hash | Hash of conversation ID | Spreads many conversations | One hot conversation remains on one owner |
| Directory | Conversation → assigned shard | Explicit migration and tenant placement | Mapping freshness, availability and operational complexity |

I would evaluate required history queries, hot-key distribution, tenant placement, shard growth and migration before choosing. Combining a conversation hash with time buckets can be reasonable but changes the number of partitions each history request touches. “Use hashing” does not explain secondary indexes or how the mapping changes.

Current Baatchit has one channel and no partitioned durable message store. Choosing a shard algorithm would be part of a future persistence design, with routing/version metadata and recovery tests. It would not automatically shard the existing socket registry or provide independent room ordering.

#### 92. What does consistent hashing solve, and what does it leave unsolved?

With simple `hash(key) modulo shard_count`, changing the shard count can remap a large part of the keyspace. Consistent hashing arranges ownership so adding/removing a node moves a smaller portion of keys. Virtual nodes assign multiple positions to a physical node, helping distribution and capacity weighting. Amazon's Dynamo paper explains a production design using consistent hashing and virtual nodes. [Dynamo paper](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf).

For chat, the key might be conversation ID. This can reduce the amount of routing/data movement when the cluster changes, but a single extremely hot conversation still hashes to its assigned owner. Virtual nodes spread many keys; they do not split the work of one key. Unequal hardware, membership churn and temporary overload also need policies beyond the hash function.

Most importantly, a new ownership calculation does not copy records, reconcile concurrent writes, fence stale owners or update client routes. The application/store needs a migration protocol and authoritative membership version. I would describe consistent hashing as a placement mechanism, then separately explain correctness during movement. Baatchit currently implements none of that placement machinery.

#### 93. How would you reshard data while writes continue?

A proposed migration starts with one declared owner and a routing epoch. Copy a snapshot of the moving partition, then apply changes from a durable ordered source so the destination catches up. Validate record counts/checksums plus application invariants; counts alone can miss wrong content or missing relationships. The migration must know which acceptance decisions have been copied.

Cutover needs a defined boundary: briefly gate writes or use a store-supported ownership transfer, prevent the old owner from accepting new authoritative writes, advance the routing epoch and send new traffic to the destination. Stale routers need a safe redirect/retry path with idempotency. Merely updating a hash map while two owners accept independently risks lost updates and duplicate message positions.

~~~mermaid
flowchart LR
  A[Old owner remains authoritative] --> B[Snapshot and replay changes]
  B --> C[Validate and catch up]
  C --> D[Gate writes and fence old ownership]
  D --> E[Advance routing epoch]
  E --> F[New owner serves; old data retained briefly]
~~~

Rollback is not just “point back” once the new owner has accepted writes. Those writes must be included or explicitly reconciled before moving authority again. This is a conceptual protocol, not a custom sharding implementation recommended for the present small app. A managed/store-native migration mechanism may reduce the amount of correctness machinery the team has to own.

#### 94. How would you handle operations spanning multiple shards?

I would first try to place data involved in the strongest invariant together. Keeping a conversation's message acceptance and its relevant membership decision on one transactional boundary can avoid cross-shard coordination. However, account-level quotas, global uniqueness or operations across conversations may still span owners.

A supported distributed transaction can provide atomic commit across participants, but adds coordination, lock duration and recovery behavior when a participant/coordinator fails. An alternative is a saga of local transactions with explicit compensation. Compensation restores a business state where possible; it does not undo a message a user already read or erase an external notification.

For example, moving a private conversation between owners should not publish the new route before its required authorization/history state is ready. A product may allow an “operation pending” state instead of pretending all steps committed instantly. I would state the exact invariant, intermediate states, timeout/retry semantics and which effects are irreversible. Baatchit's current ephemeral global room avoids these transactions; introducing shards does not make their semantics disappear.

#### 95. How do secondary indexes work after messages are sharded?

The primary partition may be conversation-based, while the product asks for “all conversations for this account,” unread counts or search by text. Those queries do not automatically become efficient when one conversation's history is local. Broadcasting every query to every shard can create high latency and large aggregate load as the shard count grows.

A proposed design can maintain account-inbox or search projections keyed for those reads. They may be updated asynchronously from the authoritative message/membership log, so freshness, replay, idempotency and deletion propagation need explicit contracts. A stale projection must not bypass current authorization: returning an identifier from an index should still lead to an allowed read.

I would define which queries are eventually consistent, how far lag may grow, and how projections rebuild after corruption. A synchronous global index can tighten freshness but introduces another shared write dependency. Adding an index also multiplies storage/write work and can create a hot account key. The current app has no database or cross-room query path; this question matters when a persistent model is proposed.

### Deep system design: replication, leaders and consistency

#### 96. What is the difference between sharding and replication?

**Sharding** divides different data among owners to increase aggregate capacity or isolate workloads. **Replication** stores copies of the same logical data to improve availability, durability or read placement according to a chosen protocol. A system can use both: each shard may have several replicas. Adding copies does not increase independent write capacity in the same way as adding partitions.

| Change | What it can improve | What it does not establish |
| --- | --- | --- |
| More message shards | Aggregate storage/write capacity | Safe replication or one-room scalability |
| More storage replicas | Failure tolerance/read options | Fresh reads or loss-free failover by default |
| More connection Pods | Socket ownership/distribution | Durable message copies |
| More independent live subscribers | Live fanout reach | A retained replayable history |

Baatchit's two backend replicas are application processes with separate socket sets, not replicated message databases. Redis Pub/Sub forwards live events but keeps no durable history for later recovery. That distinction prevents presenting the current two-Pod demonstration as replicated storage.

For a proposed persistent system, I would state replication factor, acknowledgment policy, promotion rules and fault domains per shard. Three replicas on one physical host still share a host failure domain; capacity copies and independent failure tolerance are different properties.

#### 97. How would you prevent a user from missing their own recent write on a read replica?

Asynchronous replication can lag. If a send is accepted on a primary and the next history request goes to a lagging replica, the user may temporarily not see the message they just submitted. That is a read-your-writes problem, not necessarily a lost write. The application must define whether that temporary view is allowed.

Proposed options include reading from the authority for a period, carrying an accepted log/version position and waiting until the chosen replica has applied it, or displaying a pending accepted message while history catches up and deduplicating by ID. Each has latency/availability trade-offs. A timestamp-based guess is weaker than checking a position in the actual replication stream.

Membership and revocation reads may need a stricter authority than ordinary history because stale permission data can expose private content. Synchronous replication also needs a precise acknowledgment definition; acknowledging a remote log receipt is not automatically the same as applying it for queries. Baatchit currently has no storage replicas or history reads, so a future implementation must add this contract explicitly.

#### 98. Why do leases and distributed locks need fencing?

A lease lets an owner act for a period, but that owner can pause, lose contact and resume after another owner has taken over. If the old process simply assumes it still owns the resource, both can write. A lock service issuing ownership is not enough unless the protected resource can reject stale actions.

A proposed fencing scheme assigns increasing ownership tokens. The destination checks the token/epoch and refuses operations from an older owner after authority advances. For a shard, that validation must be part of the authoritative write path; checking a token only in the client does not protect against a delayed old request. Tokens also need a trustworthy issuing/ordering mechanism and lifecycle rules.

For example, an old outbox worker might resume and try to mark newer work complete. Conditional ownership/version checks prevent it from overwriting a current worker's state, while message consumers may still need idempotency. Current Baatchit has generation nonces for subscriber heartbeat correlation, but they are **not** distributed fencing tokens or leader election. I would keep that scope clear instead of attributing consensus properties to a readiness probe.

#### 99. What do quorum and consensus provide, and is a majority count enough?

Consensus coordinates agreement on an ordered sequence of decisions despite certain node failures. In a three-voter majority design, two voters can form a majority and one unavailable voter can be tolerated under the protocol's assumptions. Election and log rules are essential: simply obtaining any two replies does not by itself prove that a write is safe or that a read is current.

Raft, for example, specifies leader election, replicated-log commitment and safety rules, including how leaders handle terms and prior log entries. Its membership changes also require protocol-level care. [Raft paper](https://raft.github.io/raft.pdf). A majority design trades availability of an isolated minority for an agreed authority; successful operation still depends on connectivity and a sufficient healthy quorum.

I would distinguish quorum replication from application acknowledgments. A committed database operation does not prove all browser recipients rendered the message, and strong storage consistency does not remove client retry ambiguity. The current Redis Pub/Sub deployment is not a Raft message log, and the current backend heartbeat does not vote on room state. Consensus is a possible dependency property in a future design, not a feature created by adding Pods.

#### 100. What is split brain, and how should failover prevent it?

Split brain occurs when two sides act as authoritative owners for the same data or decisions. A partition, stale lease or unsafe manual promotion can produce this even when each side appears locally healthy. In chat, two owners might issue conflicting conversation positions, accept different membership decisions or acknowledge writes that later cannot both be preserved.

A safe proposed failover needs authority fencing, a promotion criterion based on the actual replication/commit protocol and a rule for the old leader when it reconnects. If an asynchronous replica is missing acknowledged writes, promotion may lose them; the acceptable RPO must be stated. DNS changes or a load balancer switch do not stop an old owner from accepting requests it still receives.

Recovery must preserve an incident record and decide whether to discard, reconcile or replay divergent work according to known acceptance boundaries. Automatically merging by wall-clock timestamp can hide data loss and authorization conflicts. Baatchit currently has one Redis instance and no storage-leader failover; its outage behavior is to stop the shared chat path, not to promote another authoritative message history.

### Deep system design: networking and long-lived connections

#### 101. How do Layer 4 and Layer 7 load balancing affect WebSockets?

A Layer 4 load balancer routes transport connections using information such as addresses/ports. A Layer 7 proxy understands HTTP and can route by host/path, terminate TLS and process the WebSocket upgrade. In either case, an established WebSocket remains attached to its selected connection path; it is not balanced again for every chat event.

Baatchit uses an HTTP-aware Nginx gateway and a Kubernetes backend Service. The gateway routes `/ws/` separately from static content and forwards upgrade headers. The backend Pod selected for a connection owns that socket. Sticky sessions are not required to make global-room messages reach it because Redis provides fanout, but any state needed after reconnect must still be reconstructed or recovered.

I would examine idle timeouts, maximum connections, health-check semantics, drain behavior and client-IP handling, not just round-robin versus least-connections. A proxy can remain healthy while every backend is unready, and forwarding to an unready/full endpoint can fail a handshake. Load balancing distributes admission; it does not solve durable delivery, state migration or a strict global capacity budget.

#### 102. What is head-of-line blocking, and can WebSockets avoid it?

TCP presents an ordered byte stream. If an earlier segment is missing, later bytes on that connection cannot be delivered to the application in order until recovery. At the application layer, a single serial writer also means a large or blocked send can delay later events for the same socket. A WebSocket does not remove those ordering constraints.

Baatchit's independent per-client writer tasks isolate one client's application send from another client's writer, but they do not eliminate shared host CPU or gateway/broker contention. Small bounded text events and a write deadline limit the harm. Mixing large file transfers into the same chat socket would introduce a new source of delay, which is one reason a proposed attachment path uses separate object transport.

Multiplexed transports can change blocking between independent streams, but changing the transport alone would not remove one application's FIFO queue, room-order contract or shared resource bottlenecks. I would identify the blocking boundary with traces/metrics before proposing HTTP/3 or another protocol as a fix. The current app uses its existing WebSocket path and does not implement those transports.

#### 103. How should timeouts, deadlines and heartbeats fit together?

A timeout limits one wait; a deadline limits the whole operation across stages. If a proposed send spends most of its budget waiting for a pool slot and each downstream call then gets a full fresh timeout, the total delay can greatly exceed what the caller expects. Propagating remaining budget and limiting in-flight work makes failure timing more predictable.

Heartbeats answer a different question: whether a connection/path has recently made progress. Baatchit has WebSocket ping interval/timeout of 20 seconds, gateway read timeout of 60 seconds, Redis command timeout of one second, subscriber heartbeat/staleness settings around five/ten seconds, and a two-second application socket write deadline. These protect different directions and scopes; adding them together does not produce one exact outage-detection SLA.

I would document each timer's owner, start point, cancellation effect and retry policy, then test delayed reads, delayed writes, blackholed packets and an alive-but-stalled consumer. A timeout does not prove the remote operation never happened. For a future durable acceptance path, a timed-out client needs idempotent retry/reconciliation rather than interpreting every timeout as a safe new send.

#### 104. Where should TLS terminate, and which proxy headers should be trusted?

TLS termination determines which infrastructure can read plaintext and which network segments remain encrypted. The planned AWS gateway terminates browser HTTPS/WSS, while current internal backend/Redis traffic is a separate trust boundary. That is not end-to-end encryption between users. Adding encrypted internal links could reduce network exposure but would still leave application servers able to read message content.

Forwarded headers also need a trust boundary. If an external client can provide an arbitrary `X-Forwarded-For` and the backend treats it as authoritative, logs or rate limits can be spoofed. Baatchit's gateway overwrites selected forwarded headers and the canonical Uvicorn entrypoint disables proxy-header trust. Any future real-client-IP design must account for the actual load balancer/ServiceLB path.

I would define approved proxy hops, certificate/hostname validation, renewal and failure behavior before using addresses or schemes for security decisions. Mutual TLS can authenticate services if deliberately configured, but does not replace user/room authorization. Cloud TLS and certificate renewal remain environment-dependent work; the local loopback setup intentionally uses HTTP.

#### 105. How do service discovery and DNS failures affect recovery?

Service discovery maps a logical name to a reachable endpoint; it does not guarantee that endpoint is healthy, authorized or current. A process may cache an old address while a service is recreated, and a connection already open to a failed endpoint will not move merely because DNS changed. Client libraries/proxies differ in when they resolve names again.

For Kubernetes, a Service normally supplies a stable virtual endpoint while its ready Pod endpoints change. That helps Pod replacement, but a service deletion/recreation or different discovery architecture has other consequences. I would verify Nginx resolver/reload behavior and Redis reconnection behavior instead of assuming every component dynamically refreshes all names. NetworkPolicy must also allow the required DNS paths.

A useful failure drill separately tests an endpoint failure, a DNS failure and a stale cached route. Retry with bounded backoff can recover transient discovery issues, but unbounded resolution/connection attempts can amplify an outage. Baatchit's local smoke/network tests cover important paths; they are not comprehensive evidence for every DNS/cache scenario in a future multi-node or multi-region deployment.

### Deep system design: database and storage internals

#### 106. Which indexes would a message history query need?

Start with the query. If it retrieves the newest 50 messages in one conversation before a position, a proposed ordered index beginning with `conversation_id` and then the position key can support that filter and traversal. An account inbox or search query has a different access pattern and may require its own projection/index. A globally unique message ID alone does not make conversation pagination efficient.

Column order matters for multicolumn B-tree access, and the actual planner behavior depends on query predicates and data distribution. [PostgreSQL multicolumn indexes](https://www.postgresql.org/docs/current/indexes-multicolumn.html). I would inspect the plan and measured rows/pages read at realistic history sizes and hot/cold conversation distributions rather than rely on a tiny development dataset.

Indexes consume storage and add write/update/retention work. Including a large text body to avoid table lookups can make an index much larger, so the read benefit must justify it. Uniqueness constraints also express correctness, not just speed. Baatchit currently has no message database, so this is a proposed query-driven index plan rather than a performance fix that can be applied to the live Pub/Sub code.

#### 107. How do B-tree and LSM-based storage engines trade read and write costs?

A B-tree-family structure organizes ordered pages and supports keyed/range traversal. An LSM design typically buffers writes and flushes sorted files, then compacts files to manage overlapping data and obsolete versions. Both can use logging and caches; neither category by itself specifies transaction guarantees or durability settings.

The trade-offs are often discussed as write amplification, read amplification and space amplification. Compaction can improve later reads and reclaim obsolete data while consuming background I/O/CPU and temporarily extra disk. RocksDB's leveled-compaction documentation describes that mechanism. [RocksDB leveled compaction](https://github.com/facebook/rocksdb/wiki/Leveled-Compaction). There is no universal “LSM is always faster” or “B-tree is only for reads” conclusion.

For a proposed chat store I would measure append-heavy writes, ordered conversation reads, edits/tombstones, retention deletion and recovery under background maintenance. Tail latency and free disk during compaction can matter more than peak throughput from an empty database. The selected database's implementation and operational settings matter; Baatchit's current Redis Pub/Sub baseline does not expose this storage-engine decision.

#### 108. What is MVCC, and why can long transactions be harmful?

Multi-Version Concurrency Control lets readers see a defined database snapshot while concurrent updates create other versions. It reduces conflicts between ordinary reads and writes compared with treating every read as one exclusive lock, but the isolation level still determines which anomalies are allowed. It does not automatically make a multi-statement business decision serializable. [PostgreSQL MVCC](https://www.postgresql.org/docs/current/mvcc-intro.html).

For example, two proposed group-administration operations might each read a condition and then update different rows, jointly violating a rule even though neither overwrote the other's row. The remedy depends on the invariant: a constraint, a coordinating lock, a conditional update or a stronger isolation level with appropriate retry handling. Blindly retrying only the final statement can preserve a decision based on an obsolete snapshot.

Long-running transactions/snapshots can hold resources and delay cleanup of old versions in relevant database systems. A history response should fetch a bounded page and release the transaction, not keep it open while a slow browser scrolls or receives data. Current Baatchit has no database transactions; these concerns arise when persistence is added to the acceptance/history path.

#### 109. How are CDC, a transactional outbox and event sourcing different?

Change Data Capture observes committed database changes and makes them available to downstream processing. A transactional outbox deliberately saves notification work with a business update, so a separate dispatcher can retry delivery. Event sourcing makes an authoritative sequence of domain events the basis for rebuilding application state. These techniques can be combined, but they are not synonyms.

A row-change record may say that columns changed without capturing the complete business meaning the public protocol needs. An outbox record can explicitly describe “message accepted” while the message table remains the source of truth. In an event-sourced design, schema/version evolution, replay side effects, snapshots and corrections become central because old events remain part of state reconstruction.

For Baatchit, choosing any of these would change the current publish-only ephemeral model. I would specify which record proves acceptance, how notification duplicates are handled, what order downstream consumers need, and how a projection is rebuilt. Logging all WebSocket events to a file is not automatically a durable CDC/outbox/event-sourcing design, and replay must not accidentally resend external notifications or bypass current authorization.

#### 110. How would retention and deletion work across all copies of data?

I would inventory every copy: authoritative messages, replicas, history/search projections, attachments, caches, device copies, logs, backups and restored environments. A deletion on the primary does not automatically erase those other locations. Product language must distinguish hiding a message immediately from completing the defined data lifecycle.

A proposed design can mark a deletion/tombstone, propagate its version through consumers and expire storage according to retention rules. Tombstones themselves need enough lifetime to prevent stale replicas or delayed jobs from resurrecting data. Attachments may become orphaned after a message deletion and need ownership-aware cleanup rather than a blanket bucket operation.

Backups complicate immediate deletion because old snapshots may still contain records until expiry; a restore process should reapply required deletion/retention state before serving users. Device copies and screenshots also limit “delete everywhere” claims. This is a product/security/storage policy discussion, not a statement of legal compliance. Current Baatchit does not persist history, but server-visible plaintext and temporary client memory still require honest privacy wording.

### Deep system design: capacity, latency and fault isolation

#### 111. When should you scale vertically, and when should you scale horizontally?

Vertical scaling adds resources to an existing machine/process deployment; horizontal scaling adds independent instances and routing. More RAM or CPU can buy headroom without introducing extra coordination, but it has a practical ceiling and does not remove a shared host failure domain. More instances can spread independent work, while making state ownership, placement and shared dependency limits more important.

I would find the serial portion before predicting speedup. If half the relevant processing were unavoidably serial, perfect parallel execution of the other half could not yield more than 2× speedup; coordination overhead makes real results lower. A shared room-order stage or saturated Redis/DB path can become that serial/shared constraint even when socket workers scale out.

Baatchit's two connection processes still share one intended EC2 node, gateway and Redis. Increasing a Pod's CPU limit might help throttling if the host has capacity; adding more Pods to an exhausted host may not help. I would compare measured cost per supported workload and recovery behavior, not assume “horizontal” always means cheaper or more available. The deployment choice should follow both capacity and failure-domain requirements.

#### 112. How much spare capacity is needed to survive one instance failure?

I would size against a tested safe operating limit, not the crash point. As a hypothetical example, if one Pod safely serves 60 workload-equivalent connections and peak demand is 150, three Pods provide 180 capacity while healthy but only 120 after one fails. Four provide 240 healthy and 180 after one fails, satisfying the basic condition `(replicas - 1) × safe_capacity >= peak_demand`.

That calculation still assumes distribution, quick enough reconnect/routing, unchanged message rates and sufficient host/dependency resources. A single hot room or uneven sessions can invalidate equal sharing. Recovery also creates handshake/replay work in addition to steady-state delivery, so a failure test must include that transient load rather than just the new steady state.

Autoscaling lag, image pulls, startup and dependency warmup make spare capacity useful before a reactive scale-out completes. Baatchit's 64 local admission slots are configuration, not a tested safe-capacity number for arbitrary workloads. Its single host cannot meet a host-failure capacity objective by adding same-host replicas, regardless of the arithmetic at Pod level.

#### 113. Why can acceptable per-component latency produce a poor end-to-end tail?

A request can accumulate delays across serial stages or wait for the slowest of parallel dependencies. If each of 100 independent required calls has a 1% chance of exceeding a threshold, the chance that at least one exceeds it is `1 - 0.99^100`, about 63%. Real delays are often correlated, so this is an illustration under stated assumptions, not a measured prediction.

This matters if a proposed send acknowledgment waits for every group member's device receipt. The slowest or disconnected device would dominate the sender's latency and availability. A more practical contract may acknowledge durable acceptance and expose later recipient receipts separately. The product must choose the boundary; a fast database commit alone does not establish fast device delivery.

Baatchit deliberately does not wait for every socket writer in its Redis fanout callback. It measures per-recipient latency in the local harness and closes slow sessions under bounded pressure. I would examine percentiles by stage, replica, room and time window and correlate loss, rather than averaging away one bad segment or using an all-recipient acknowledgment accidentally.

#### 114. How do retries create an outage, and what is a retry budget?

Retries add work exactly when a dependency may already be struggling. If three call layers each make three total attempts, one top-level operation can cause up to 27 bottom-level attempts. Backoff reduces request density, jitter spreads synchronized callers, and a retry budget limits how much extra work the system spends relative to ordinary traffic or a deadline.

I would retry only a defined transient failure when the operation is safe/idempotent or its uncertainty can be reconciled. The total deadline should constrain attempts and waits. A timeout after a side effect is not proof that another attempt is harmless. Centralizing retry responsibility avoids every layer independently multiplying it. [AWS timeout/retry guidance](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/).

Current Baatchit retries browser connection establishment and Redis subscription recovery with bounds/backoff, but does not retry ambiguous chat publication. Those are different operations with different consequences. A future durable submission retry should preserve its stable submission ID and acceptance decision, while optional stale notifications may simply expire. I would test dependency recovery under many simultaneous clients, not just a single successful retry.

#### 115. How do a circuit breaker and a bulkhead differ?

A circuit breaker stops repeatedly calling a dependency after a defined failure pattern and later permits limited probes of recovery. A bulkhead limits the resources one dependency/workload can consume, such as a separate bounded pool for history reads versus live acceptance. A timeout only limits an individual wait; neither protection makes unbounded caller queues safe.

For example, a slow search service should not consume all database connections or worker slots needed to send chat. Separate concurrency budgets and a clear degraded response can preserve the essential path. A circuit breaker can reduce wasted calls, but its thresholds, probe behavior and shared-versus-local state affect recovery and fairness. It can also stay open too long or cause correlated probe bursts if designed poorly.

Baatchit's bounded per-socket writers already provide one form of local isolation; broker failure currently affects the whole room because Redis is required for shared chat. There is no generic circuit-breaker implementation bundled. I would introduce one for an optional future dependency only after defining the fallback and measuring whether the extra state machine improves overload/recovery behavior.

### Deep system design: APIs, quotas and security boundaries

#### 116. Which operations should use HTTP APIs versus the WebSocket protocol?

I would choose by interaction and guarantee. A proposed login, paginated history fetch or attachment-upload authorization can fit request/response HTTP APIs. Live events and interactive socket commands can fit WebSockets. Both need shared authenticated identity, authorization, request IDs, limits and a consistent message model; splitting transports must not create different security rules.

| Operation in a future version | Possible interface | Design concern |
| --- | --- | --- |
| Login/session refresh | HTTPS request | Credential/session lifecycle |
| Send text and receive events | Versioned socket commands/events | Idempotency, acknowledgment and reconnect |
| History page | Cursor-based HTTPS request | Authorization, limits and order |
| Attachment transfer | Scoped object transport | Size, ownership and finalization |
| Receipt/typing update | Bounded socket command | Rate, expiry and device scope |

Binary encoding such as Protobuf can reduce some payload/parse costs, but adds schema/tooling/version work and does not fix ordering or acknowledgment semantics. Compression trades bandwidth for CPU/state and may introduce decompression/resource risks. Current Baatchit uses raw inbound text, strict outbound JSON and disabled WebSocket compression. I would change that only for a measured requirement and update both parsers plus compatibility tests.

#### 117. How would a distributed rate limiter differ from the current token buckets?

Current buckets are local to a socket or backend process. A contractual account/tenant-wide quota across Pods needs shared accounting or a documented approximation. The algorithm determines burst behavior: a fixed window can allow nearly twice its nominal count around a boundary, a sliding log records individual arrivals at greater storage cost, and a token bucket permits a bounded burst with continuous refill.

A shared implementation must make check-and-update atomic at its authoritative scope. It also needs expiry, clock assumptions, retry idempotency where relevant and a failure policy. If the limiter is unreachable, failing open preserves availability but may violate quotas; failing closed protects the quota while rejecting otherwise healthy users. A hierarchical design can combine coarse local protection with tighter shared accounting.

I would scope keys to verified identity and relevant operations, cap cardinality, and test hot accounts and cross-Pod races. Baatchit's app ACL permits only its Pub/Sub commands, so implementing arbitrary limiter keys/scripts in that Redis instance is not an invisible drop-in change. It would require deliberate privilege, availability and resource budgeting, or a separate service/store.

#### 118. How would you isolate several organizations or tenants?

Isolation includes data access, resource consumption and operations. Every message, room, cursor and object reference in a proposed multi-tenant system needs an authenticated tenant context and authorization checks. Deriving access from a client-supplied tenant field without validating membership creates a direct data exposure risk. Indexes/caches/background jobs must preserve the same boundary.

Resource isolation can use per-tenant quotas, bounded queues, fair scheduling and, for selected workloads, separate partitions or deployments. A Kubernetes namespace by itself does not guarantee CPU fairness, network isolation or application authorization; those require configured policies and resource controls. Shared databases/search indexes need tested tenant filtering and a backup/restore policy.

Operational tools and metrics also matter: a high-cardinality label per user/message can overload observability, and an admin debugging one tenant must not expose another's content. I would test cross-tenant access attempts and noisy-neighbor load together. Current Baatchit is one anonymous public room and has no authenticated tenant model, so tenant isolation cannot be inferred from the `baatchit` namespace or Redis channel ACL.

#### 119. What changes when you promise end-to-end encryption?

The promise concerns who can decrypt content, not merely whether a network link or disk is encrypted. A proposed E2EE messenger needs authenticated device keys, key establishment, device verification, message encryption/decryption on clients and a plan for adding/removing devices. Key rotation, recovery and compromised-device handling are central features rather than implementation details.

The server may still learn metadata such as account connections, conversation routing, timing and payload sizes. Search, moderation, attachment scanning, multi-device history and account recovery have to respect what the server can and cannot decrypt. Giving the server a recovery key can fundamentally change the confidentiality promise, and losing client keys may make old content unrecoverable under another design.

I would choose reviewed protocols/libraries and obtain specialist review rather than invent cryptography for an interview extension. Tests should include removed devices, key changes, delayed messages and recovery behavior, and the UI must explain trust changes honestly. Current Baatchit sends plaintext through its server/broker and has no client key system. Gateway TLS is transport protection, not E2EE.

#### 120. How do you rotate credentials and certificates with long-lived connections?

Rotation has both a configuration phase and a connection-lifetime phase. Updating a Secret does not necessarily reload a process or invalidate an already authenticated connection. A TLS certificate replacement may affect new handshakes after reload, while existing sockets keep their established session; an account revocation may require actively closing authorized sessions according to policy.

A planned backend/Redis rotation could introduce a replacement credential, update consumers, establish new healthy connections, retire the old identity and verify no old sessions remain. Overlap reduces interruption but extends the period both credentials work. A compromise may justify immediate revocation and deliberate disruption. The URL/ACL pair must stay consistent, and logging must not expose either value.

Current bootstrap preserves the existing Redis credential pair, and the documented gateway TLS rotation needs a restart. The app does not implement a general seamless credential-rotation controller or authenticated account revocation. A real procedure should name the exact consumers, reload/reconnect behavior, rollback point and evidence of retirement rather than assuming mounted Secret updates complete the whole lifecycle.

### Deep system design: production behavior and safe change

#### 121. Is the backend stateless if it stores no messages permanently?

“Stateless” needs a boundary. The current backend has no durable chat history, but it holds active socket objects, session IDs, rate buckets, queues, subscriber readiness and process metrics. That is real transient state. Another Pod cannot simply take over an existing socket by receiving a request with the same username.

A useful deployment property is that a replacement process can reconstruct the required service state from configuration and dependencies, while clients establish new sessions. Baatchit supports new-session recovery but cannot reconstruct queued or missed messages. A future durable design could let a client replay after reconnect, yet the live connection tier would still own local transport state.

This matters for load balancing, autoscaling and release language. Adding instances handles new connections; it does not rebalance old ones. Terminating one process needs drain and reconnect capacity even when persistent messages live elsewhere. In an interview, I would say the backend is ephemeral with process-local connection state and no durable chat store, then explain precisely what survives a restart.

#### 122. What is a cache stampede, and how would you prevent it?

A cache stampede happens when many requests miss or expire together and all query the underlying dependency. A popular conversation/profile lookup can turn a healthy cache expiry into a database overload. Merely increasing cache capacity does not prevent synchronized refreshes or the first miss for a newly hot key.

A proposed solution can coalesce concurrent refreshes for the same key, randomize expiry times and cap fallback work. Serving a stale value while refreshing may be acceptable for display metadata but unsafe for a revoked permission. Negative caching can suppress repeated nonexistent-key lookups, yet its TTL and invalidation must allow legitimate new objects/accounts to appear promptly.

Distributed coalescing/leases need ownership checks and expiry; local coalescing only reduces duplicate work inside one process. Cache recovery should not cause every Pod to refill every key at once. Baatchit currently uses Redis for Pub/Sub, not a metadata cache. These mechanisms would be future dependency protection, with explicit freshness/security contracts and load tests for expiry, outage and cold start.

#### 123. How should the system handle a poison message or incompatible event?

A poison event consistently fails processing—for example, malformed data, an unsupported schema or an impossible business transition. Retrying it forever consumes resources without creating progress. The consumer must distinguish transient dependency failures from permanent content/contract failures and preserve a bounded diagnostic path.

In a proposed durable pipeline, invalid work can be quarantined/dead-lettered with schema/version, safe identifiers, failure class and attempt history. Sensitive bodies need careful access/retention. Whether later events may continue depends on ordering semantics: skipping a bad account-update event may make later updates unsafe, while independent notification jobs may continue. A replay tool must not bypass the validation that rejected the event.

Current Baatchit's broker filters oversized/non-object/invalid broadcast data and ignores control probes rather than forwarding them to browsers. There is no durable dead-letter log, and the frontend treats incompatible server envelopes as a protocol error. A future persistent consumer needs operational ownership and remediation rules; adding retries or quietly dropping everything would not establish correctness.

#### 124. How would you run a canary release with persistent WebSockets?

A canary sends a controlled portion of representative traffic to a new version and compares outcomes before wider rollout. With long-lived sockets, a percentage of **new handshakes** is not necessarily the same percentage of active sessions or message work. Existing clients can stay on old Pods for a long time, and one large room can skew the workload.

I would track active session share, release identity, admission outcomes, subscriber health, queue pressure, errors and synthetic delivery latency for each version. The shared bus/protocol must support the mixed population, and a database migration must remain compatible with both. Forcing reconnects can accelerate coverage but adds load and changes user experience; that needs its own budget.

Rollback can restore an old image/config but cannot automatically undo a changed message schema or destructive database migration. Signed artifact verification remains necessary for both canary and stable releases. The current deploy script applies one selected bundle and has prior-bundle restoration; it does not implement canary routing/analysis or prove full-stack zero-downtime releases.

#### 125. What should graceful degradation preserve during overload or partial failure?

I would identify the minimum truthful product promise. A proposed durable messenger might continue accepting committed messages while delaying optional notifications or search indexing. Typing indicators can expire and profile decoration can degrade. Private authorization, durable-acceptance acknowledgment and integrity checks should not be silently bypassed to make a dashboard look healthy.

The client should expose the actual state: pending, unavailable, partial or retryable according to the contract. Accepting a message into volatile memory while labeling it “saved” would change the guarantee at exactly the worst time. Degraded modes also need quotas, time limits and a controlled return to normal so accumulated optional work does not overwhelm recovery.

Baatchit currently depends on Redis to provide one shared room, so broker failure closes sessions and makes the backend unready instead of presenting disconnected local room fragments as normal shared chat. A future fallback mode would need a versioned semantic/UI decision and tests. Feature flags can select modes, but their control path must itself be secure, bounded and observable.

### Deep system design: architecture choices and final review

#### 126. How would you separate the control plane from the data plane?

The data plane carries ordinary user work: admitting sessions, accepting messages and delivering events under an established policy. The control plane manages configuration, placement, membership of infrastructure, rollout decisions and administrative policy. Keeping those paths distinct can prevent a slow configuration service from becoming a dependency of every socket write.

A proposed backend might consume a versioned configuration snapshot and continue using a last-known-good safe policy during a short control outage. That is appropriate only for properties whose staleness is allowed. Credential revocation or shard ownership may require expiry/fencing and a fail-closed boundary; a stale snapshot cannot justify conflicting authority indefinitely.

Configuration publication needs validation, rollback, access control and an audit trail. The current app reads settings at startup and uses explicit signed release/configuration artifacts; it is not a dynamic control-plane service. Kubernetes orchestration and readiness also do not by themselves provide an application-level room-placement authority. I would draw which calls occur on every message and which occur only on controlled updates, then test failure of each path separately.

#### 127. When would you choose Redis Pub/Sub, a work queue or a partitioned log?

I would compare retention, audience, ordering scope, replay and acknowledgment requirements before comparing products. A live broadcast bus fits currently connected subscribers; a work queue fits tasks that one worker should process with retries; a retained partitioned log fits ordered replay/projections at a chosen partition boundary. A product name alone does not define those semantics.

| Model | Candidate role | Required care |
| --- | --- | --- |
| Live Pub/Sub | Current Baatchit room fanout | Missed subscriptions have no replay |
| Acknowledged work queue | Future scan/push jobs | Idempotent consumers, retries, poison work |
| Retained partitioned log | Future durable event feed/projections | Partition ordering, retention, cursor recovery |

RabbitMQ distinguishes publisher confirms from consumer acknowledgments; neither is a browser read receipt. [RabbitMQ confirmation model](https://www.rabbitmq.com/docs/confirms). Kafka's partitioned-log/consumer design has different ordering and assignment semantics; one consumer group is not a broadcast copy to every connection server. [Kafka design](https://kafka.apache.org/41/design/design/).

I would avoid choosing a larger broker only to claim enterprise scale. The application still needs its acceptance boundary, audience routing and failure model. Current Redis Pub/Sub is a deliberate ephemeral choice; future durable history or background jobs may justify different components with separate operational budgets.

#### 128. How do batching and compression trade throughput against latency?

Batching amortizes fixed costs by processing several events together, but waiting to fill a batch adds latency. A batch policy therefore needs both size/byte and maximum-wait bounds. A large batch can also monopolize a worker, create a burst into downstream queues and increase the amount of uncertain work after failure.

Compression reduces wire bytes when content is compressible while adding CPU, memory and sometimes state/security concerns. Small chat events may not gain enough to justify the overhead, whereas larger history pages might. The relevant measurement includes end-to-end tail latency, CPU/throttling, bytes and recovery behavior under realistic payloads, not only compression ratio on repeated dummy text.

Baatchit disables WebSocket compression and sends serialized events through independent writers. A proposed batching change must preserve per-session ordering, session-first behavior, frame-size limits and slow-client isolation. A faster average benchmark is not sufficient if optional batching causes missed two-second delivery deadlines or makes a hot room starve others. I would make one bounded change at a time and compare the same workload.

#### 129. How would you aggregate metrics without hiding important failures?

I would define the unit and denominator of every signal. Connection count is a gauge; publication/delivery outcomes are counters; latency is a distribution with a stated start/end boundary. A recipient delivery ratio needs expected eligible deliveries as well as observed ones. Measuring only successful sends can make a failing service look fast.

Percentiles from separate Pods cannot generally be averaged into a global p99. Compatible histogram buckets can be aggregated before calculating a quantile, with attention to bucket resolution and population. Labels should separate meaningful bounded dimensions such as release/Pod/outcome, while avoiding message IDs, arbitrary usernames and unbounded room IDs as metric labels. Sensitive correlation can use controlled logs/traces instead.

Baatchit's existing metrics are private and process-local, and its publish counter includes heartbeat publications. A future collector should attach target identity, track restarts/resets and combine infrastructure signals with a synthetic full chat path. Alert thresholds/error budgets should follow a defined SLO and operator response, not just copy the healthy local benchmark into a production alarm.

#### 130. How would you defend a complete system design rather than list technologies?

I would organize the explanation around decisions: the user promise, workload assumptions, state ownership, acceptance point, delivery semantics, scaling unit and failure/recovery boundary. Then I would trace one send from the browser through validation, persistence if required, fanout and recipient acknowledgment, and repeat the trace with a failure immediately before and after acceptance.

| Design question | Evidence a strong answer supplies |
| --- | --- |
| Why this architecture? | Requirements and access patterns it satisfies |
| Where is correctness enforced? | Transaction/invariant, authorization and idempotency boundaries |
| What scales independently? | Connections, storage writes, audiences, history and background work |
| What can be lost or duplicated? | Named acknowledgment/retry/replay semantics |
| What fails together? | Shared dependencies and real fault domains |
| How will it be operated? | Limits, signals, restoration procedure and tests |
| What happens next? | Measured trigger and safe migration/rollback plan |

For Baatchit, the defensible current claim is a locally tested ephemeral shared room across two backend processes, with bounded resource controls and explicit single-host/Redis limitations. Persistent, sharded, encrypted or regional versions remain proposals until built and verified.

I would close the discussion by identifying the largest unresolved risk and the smallest meaningful experiment that resolves it. Choosing fewer components with clear guarantees can be a stronger design than a larger diagram whose storage, retries and authorization disagree.

## 17. Practice exercises

These are **optional local learning exercises**, not new implementation or claims of completed tests. Use the disposable `baatchit` cluster or the isolated test environment, keep the kubeconfig/context explicit, and record the original setup so it can be restored. Existing tests are a useful reference; these exercises should produce explanations and evidence, not just “it worked.”

### Exercise 1: Trace one message through the code

Open two tabs and give them different names. Confirm they are connected before sending a distinctive plain-text message. Explain the browser draft update and `Connection.send` check, gateway WebSocket routing, server validation/event creation, Redis publication, subscriber consumption, per-session queue and final safe DOM rendering. Identify the sending and receiving session Pod IDs so you know whether the experiment actually crossed replicas.

Use [useChat.js](../frontend/src/useChat.js), [connection.js](../frontend/js/connection.js), [routes.conf](../gateway/routes.conf), [sessions.py](../backend/app/sessions.py), [broker.py](../backend/app/broker.py), [protocol.py](../backend/app/protocol.py) and [MessageList.jsx](../frontend/src/components/MessageList.jsx). A strong explanation says who owns each piece of state and why the sender does not get a separate local echo. Deliverable: a sequence diagram plus the difference between browser send success and recipient receipt.

### Exercise 2: Observe Redis outage and recovery

Start from a healthy local environment, attach clients to both replicas and record readiness/connection state. In a controlled local experiment make Redis unavailable, then restore it. The [real runtime integration suite](../tests/integration/test_runtime.py) already provides an isolated reference for this behavior; it does not require disrupting a cloud environment.

Record when each backend becomes unready, the socket close codes, whether new admission fails, and when a new subscription generation becomes ready after restoration. Expected behavior is `1011` for active sessions affected by broker failure, degraded `/health` and a still-responsive `/live`. Browser recovery is bounded by retry policy; a paused client needs manual retry. Explain why messages from the gap cannot be replayed. Do not report the 15-second/60-second recovery targets as achieved unless you actually time that environment.

### Exercise 3: Compare graceful backend replacement with a crash

Keep the two clients' session `container_id` values and `connection_id` values. Replace one backend Pod in the disposable cluster and observe that a new Pod is created. For a graceful termination, look for `1012` and a new browser session after reconnect. A forced process failure may instead appear as an abnormal close; the outcome need not be identical.

Measure affected-client count, reconnect time, ready endpoint changes and any missing test messages. Confirm the unaffected client's behavior rather than assuming the other replica guarantees continuity. Explain why a new Pod cannot inherit an old WebSocket or its queue. The deliverable is a failure timeline that distinguishes graceful drain, process crash and loss of the whole host.

### Exercise 4: Demonstrate slow-writer isolation

Read [test_sessions.py](../tests/unit/test_sessions.py), especially the test that blocks one writer after its session event while allowing another writer to complete. This is a deterministic demonstration of the timeout path. Explain how the healthy session proceeds before the blocked writer times out and closes with `1013`.

For a separate transport experiment, a client that does not read must have bounded receive buffering and enough offered traffic for backpressure to reach the server. One tiny message may fit entirely in network buffers and prove nothing. Record queue bytes, write timeout/overflow outcomes and healthy-client latency. Distinguish the server's application queue from library and kernel buffers; do not interpret immediate lack of failure as an unbounded queue.

### Exercise 5: Test admission on one specific replica

To examine the 64-slot default, target **one backend Pod** with valid Origin/subprotocol and keep admitted sockets open. The 65th admission to that same process should be rejected while its 64 slots are occupied; closing a session should eventually make a slot available again. Confirm the session `container_id` on each accepted connection.

Seventy connections through the shared Service do **not** necessarily hit a 64-slot cap because two replicas can share them. The standard load harness also deliberately balances clients and is not a single-replica admission test. Stagger connection attempts or account for the gateway's handshake limiter so a proxy rejection is not confused with backend capacity rejection. Deliverable: accepted count and rejection cause for a clearly identified replica.

### Exercise 6: Explain rate limits with an explicit timeline

Use the bucket rule `min(burst, tokens + elapsed × rate)` with rate two and burst five. Five immediate successful consumes leave zero tokens. A sixth immediate attempt fails and closes that chat socket. If instead the client waits one second after the first five, approximately two tokens refill and two more may be accepted.

A request to “send ten messages in one second” has no single answer without the arrival times. A client that exceeds the bucket at the start is closed and cannot use later refill. For exact arithmetic, use a controllable clock as in the unit-test approach rather than relying on scheduler timing. Then explain how the separate replica publication bucket can reject an otherwise individually compliant socket when many clients publish together.

### Exercise 7: Derive the workload and memory numbers

Calculate these aloud and state the assumption for each:

| Calculation | Result | Interpretation |
| --- | ---: | --- |
| `5 messages/s × 60 s` | 300 messages | Measured short-run publication count |
| `300 × 25 recipients` | 7,500 deliveries | Expected healthy fanout, sender included |
| `5 × 25` | 125 deliveries/s | Aggregate delivery work at the baseline |
| `5 × 1,800 × 25` | 225,000 deliveries | Expected 30-minute workload, not a completed result |
| `64 × 262,144 / 1,048,576` | 16 MiB | Per-replica maximum queued serialized payload budget |
| `2 × 16` | 32 MiB | Same queue-payload budget across two full replicas |
| `32 + 16 + 2 × 128 + 64` | 368 MiB | Sum of application memory requests |
| `64 + 48 + 2 × 256 + 128` | 752 MiB | Sum of application memory limits |

Explain why the queue-payload budget excludes in-flight sends and other memory; why application requests exclude Kubernetes/OS overhead; and why 225,000 correlated delivery observations do not establish an availability guarantee.

### Exercise 8: Design replay without implementing it

Sketch a proposed durable message record with a stable event ID, room ID, ordered position, sender identity and client submission ID. Define the acknowledgment point and idempotent retry behavior. Draw the save/outbox/fanout path and the reconnect path from the client's last confirmed cursor.

Choose either one continuous durable-log reader or a carefully bounded replay-to-Pub/Sub handoff. Explain how it handles a new event during replay, duplicate dispatcher delivery, a missing/expired cursor and a crash between commit and notification. If choosing Streams, explain why one shared consumer group does not automatically broadcast every event to all backend replicas. Deliverable: failure cases, retention/security implications and a migration/rollback outline; no new code is required.

### Exercise 9: Write a concurrency history

Choose a hypothetical shared admission counter or versioned message edit. Write two operations as read → suspend → check/update → result, and show an interleaving that violates the intended rule. Then identify the smallest local lock/atomic transaction boundary that protects it. Explain which guarantees disappear when the operations run in different Pods and how cancellation affects reservations.

### Exercise 10: Review a shard-movement failure

Sketch old owner A, destination B and routing epoch 7. Mark a message accepted before snapshot, one during catch-up and one immediately after cutover. Pause A and let it resume with its old epoch. Explain how the write path rejects stale ownership, how readers find the correct copy, and what rollback must preserve after B has accepted new writes. A changed hash function alone is not an acceptable migration explanation.

### Exercise 11: Separate quorum from application delivery

For a proposed five-voter replicated log, identify a three-voter majority and explain which partition may continue under the chosen consensus protocol. Then trace a committed message whose browser disconnects before receipt. State what the storage decision proves, what the user still lacks, and how replay/idempotency would bridge that gap. Do not infer a correct consensus algorithm from quorum arithmetic alone.

### Exercise 12: Build one end-to-end resource budget

Use explicitly hypothetical tested Pod capacity, peak clients, send rate, audience size, database pool and per-hop deadlines. Calculate normal and one-Pod-failed capacity, total possible database connections across replicas, fanout bytes and worst allowed queue wait. Identify which assumption would fail first if a hot room doubles traffic. List the actual measurements needed before those numbers become a deployment claim.

## 18. Number cheat sheet

A configuration default is a limit chosen in code; a measurement is an observed result under recorded conditions; a target remains to be verified. Keep those categories distinct in an interview.

| Fact | Value | Authority or meaning | Important qualification |
| --- | --- | --- | --- |
| Connections per backend | 64; 128 nominal across two | [Settings](../backend/app/settings.py) | Routing imbalance and resource pressure can constrain usable capacity |
| Per-socket input budget | 2 messages/s; burst 5 | Token bucket | Whitespace-only text also consumes a socket token |
| Per-replica publication budget | 20/s; burst 40 | Chat + advisory publications | Process-local; broker control probes are outside this session bucket |
| Queue per socket | 32 events and 262,144 bytes | Serialized UTF-8 payload accounting | First exhausted limit closes the slow session; not total socket/RSS memory |
| Aggregate queue payload cap | 16 MiB/backend; 32 MiB across two | `64 × 256 KiB` per backend | A configured upper budget, not observed memory consumption |
| Socket write deadline | 2 seconds | Backend settings | Applies to a send; queue wait and transport buffers are separate |
| Incoming WebSocket size | 16,384 bytes | [Canonical entrypoint](../backend/app/run.py) | Reassembled transport message; fragmentation does not bypass it |
| Normalized text limit | 2,000 Unicode code points | [Validation](../backend/app/validation.py) | Code points are not necessarily visible grapheme count |
| Browser event limit | 500 | [State store](../frontend/js/state.js) | In-memory events, not durable or shared history |
| Browser transport buffer guard | 65,536 bytes | [Connection client](../frontend/js/connection.js) | Sends are refused if `bufferedAmount` is already above this value |
| Subscriber probe/staleness | About 5 / 10 seconds | Broker settings | Not an exact end-to-end outage-detection SLA |
| Browser normal retry | 500 ms base; 15 s cap; 10 attempts | Full jitter | Stable 30-second session resets the counter |
| Planned-restart retry | Random 0–500 ms | Close code `1012` | Faster retry may need wider jitter at much larger scale |
| Backend shutdown/Pod grace | 10 / 20 seconds | Runtime setting / manifest | Does not promise flushing or replaying queued messages |
| App memory requests/limits | 368 / 752 MiB | [Workload manifests](../k8s/base/workloads.yaml) | Excludes OS, Kubernetes/system Pods and other host overhead |
| Redis memory setting | 48 MiB | [redis.conf](../k8s/base/redis.conf) | Separate from 128 MiB container limit and Pub/Sub buffer caps |
| Redis Pub/Sub buffer limits | 4 MiB hard; 1 MiB soft for 10 s | Redis config | Bounds Redis subscriber buffering; not the backend socket queue |
| Recorded automated tests | 42 = 26 + 6 + 9 + 1 | [Dated local evidence](IMPLEMENTATION_STATUS.md) | Python unit + JS + real Redis integration + browser; not rerun by this document edit |
| Short local load | 25 clients; 5 aggregate messages/s; 512-byte payloads | Recorded implementation baseline | Five-second warmup, 60-second measurement, 13/12 replica split |
| Recorded delivery result | 7,500/7,500; zero duplicates/errors | 300 messages × 25 recipients | Healthy local experiment; not exactly-once or AWS certification |
| Recorded p95/p99 | Approximately 16 / 16 ms | Actual-send-to-receipt observations | Local Python client, correlated deliveries, no DOM-render measurement |
| Full workload target | 120 s warmup + 1,800 s measurement | 25 clients; 5 aggregate messages/s | 9,000 messages and 225,000 expected deliveries; AWS run pending |
| Delivery/latency targets | ≥99.9% within 2 s; p95 <250 ms; p99 <1,000 ms | [Requirements](REQUIREMENTS.md) | Targets, not measured AWS guarantees |
| Host headroom target | ≥512 MiB `MemAvailable` | Host-level measurement | Not derivable from Pod request/limit totals alone |

The workload calculation assumes all 25 clients remain connected for every measured message. Fault experiments need an explicitly stated expected-delivery population; silently removing failed clients or missing events from the denominator can make a bad run appear successful.

## 19. Where to read next

Use executable code to answer “what does it do now?”, [implementation status](IMPLEMENTATION_STATUS.md) for “what has been checked?”, and the design guides for proposed scope/acceptance. Some historical specifications predate implementation; reconcile them against current defaults and evidence rather than repeating every proposal as a fact.

| Question you need to answer | Read these sources | What to extract |
| --- | --- | --- |
| What is implemented and which checks passed? | [Implementation status](IMPLEMENTATION_STATUS.md) | Dated measurements, test counts, pending cloud acceptance |
| How do I run and inspect it? | [Development](DEVELOPMENT.md), [local launcher](../scripts/local.py) | Prerequisites, explicit cluster context, startup and local credentials |
| What goes over the wire? | [API specification](API_SPECIFICATION.md), [schema](../schemas/events-v1.schema.json), [server models](../backend/app/protocol.py), [browser parser](../frontend/js/protocol.js) | Field sets, version, validation, close codes and compatibility |
| What is the real backend lifecycle? | [Main](../backend/app/main.py), [sessions](../backend/app/sessions.py), [broker](../backend/app/broker.py), [entrypoint](../backend/app/run.py) | Admission, session-first ordering, publication/fanout and shutdown |
| Which defaults and secrets matter? | [Configuration](CONFIGURATION.md), [settings](../backend/app/settings.py), [Secret bootstrap](../scripts/bootstrap_secrets.py) | Rates, bounds, exact origins, URI source and coordinated credential handling |
| How does the browser behave? | [Frontend guide](FRONTEND.md), [connection](../frontend/js/connection.js), [state](../frontend/js/state.js), [React message list](../frontend/src/components/MessageList.jsx) | Draft/retry policy, memory bound, DOM safety, keyboard flow |
| What actually runs in Kubernetes? | [Kubernetes guide](KUBERNETES.md), [workloads](../k8s/base/workloads.yaml), [services](../k8s/base/services.yaml), [network policies](../k8s/base/network-policies.yaml) | Four Deployments/five app Pods, resources, probes and permitted paths |
| What is the AWS target? | [Infrastructure](INFRASTRUCTURE.md), [workload Terraform](../infra/workload/main.tf), [state bootstrap](../infra/bootstrap-state/main.tf), [AWS requirements](AWS_FREE_TIER_REQUIREMENTS.md) | Declared resources, account-specific worksheet, host limits and pending apply |
| How are releases trusted and restored? | [Deployment](DEPLOYMENT.md), [release validator](../scripts/release.py), [publisher](../scripts/publish.sh), [deployer](../scripts/deploy.py) | Digests, signatures/trusted identity, artifact retention and restoration conditions |
| How can I verify the important claims? | [Testing](TESTING.md), [session tests](../tests/unit/test_sessions.py), [runtime tests](../tests/integration/test_runtime.py), [browser test](../tests/browser/test_ui.py), [load harness](../scripts/load.py) | Checked behaviors, fault injection, observation boundaries and missing coverage |
| How would the architecture evolve? | [Architecture](ARCHITECTURE.md), [HLD/LLD index](design/README.md), [evolution proposals](design/ARCHITECTURE_EVOLUTION.md) | Requirements, migration stages, new failure modes and assumptions to measure |
| What security and operational work remains? | [Security](SECURITY.md), [operations](OPERATIONS.md), [release checklist](RELEASE_CHECKLIST.md) | Threats, residual risks, runbooks and acceptance evidence |

For general concepts referenced in the answers, consult the primary references linked at the relevant question: Redis Pub/Sub, XREAD/XREADGROUP, browser WebSocket API, Kubernetes Pod lifecycle, OWASP WebSocket security and wrk2 measurement notes. Future architecture examples in this guide are design reasoning, not installed features or commands executed during this documentation update.

## Glossary

- **ASGI:** the asynchronous interface between Python application and server. In Baatchit, FastAPI/Starlette handles application events while Uvicorn manages HTTP/WebSocket transport.
- **WebSocket:** a long-lived bidirectional connection established by an HTTP upgrade. An open socket does not itself prove an application session, delivery acknowledgment or verified identity.
- **Subprotocol:** the application contract selected during a WebSocket handshake. `chat.v1` tells the peers which protocol to parse; it is public version metadata rather than a credential.
- **Session:** one admitted socket with a UUIDv4 `connection_id`, user label and owning backend. Reconnecting creates another session; it does not restore a durable conversation.
- **Event ID:** a server-generated UUIDv4 identifying one broadcast for correlation. It is not ordered, and merely including it does not implement deduplication.
- **Pub/Sub:** live distribution to current subscribers. The current Redis channel does not retain a log for disconnected subscribers to replay.
- **Fanout:** one event becoming multiple recipient deliveries. At five aggregate messages/s and 25 clients, the baseline requires 125 deliveries/s.
- **Backpressure:** controlling how much work can accumulate when a recipient is slow. Baatchit bounds queues and closes a slow socket rather than building unlimited backlog.
- **Queue payload budget:** the accounted bytes of serialized messages waiting in one application queue. It excludes an item already being sent and Python/transport/kernel overhead.
- **Token bucket:** a limiter that refills tokens at a fixed rate up to a burst ceiling. A request consumes a token, so instantaneous bursts and sustained rate are different limits.
- **Monotonic clock:** a clock for elapsed time that is independent of wall-clock adjustments. The app uses it for rate accounting, subscriber freshness and client latency measurements.
- **Readiness:** whether a Pod should receive new application traffic. Baatchit's backend checks drain state, Redis connectivity and subscriber progress.
- **Liveness:** whether the process responds well enough to keep running. It is independent of Redis readiness to avoid dependency-induced restart loops.
- **Drain:** stop new admissions and begin closing existing work during shutdown. Baatchit's `1012` drain does not transfer sockets or persist their pending deliveries.
- **Jitter:** randomness in retry delays that reduces synchronized reconnect attempts. It helps distribute load but does not enforce compliant behavior in malicious clients.
- **At-most-once / at-least-once:** delivery models allowing loss without broker replay / allowing retries and therefore duplicates under defined assumptions. Neither automatically describes whether a human read a browser message.
- **Acknowledgment:** an explicit statement that a specified stage completed. Browser buffering, durable server acceptance, device receipt and read status need different acknowledgments.
- **Idempotency:** safely repeating a request without creating a new logical effect. Reliable message retries need a stable submission ID and a recorded server decision, not only a random broadcast ID.
- **Deduplication:** suppressing repeated copies of an already processed event. The current browser validates IDs but does not maintain a durable deduplication record.
- **Replay cursor:** an ordered position after which a client requests missed events. Baatchit has no current cursor/history API; UUIDv4 IDs alone do not define an interval.
- **Transactional outbox:** a proposed way to save a message and a notification task in the same database transaction, then deliver that task with retries. Consumers still need idempotency.
- **SLO / SLI:** the objective and the actual measured signal used to assess it. “99.9% timely deliveries” needs a clear denominator, time window and treatment of loss.
- **Percentile:** a rank in an observation distribution. A p99 over successful deliveries must be interpreted alongside missing deliveries, errors, sample correlation and workload duration.
- **Coordinated omission:** a measurement bias where generator slowdown hides delays that intended requests would have experienced. The current harness records actual send-to-receipt time and is not fully corrected for it.
- **RSS / MemAvailable:** process resident memory / Linux's estimate of host memory available for new work. A Pod limit and the host's 512 MiB headroom target measure different things.
- **K3s / k3d:** the lightweight Kubernetes distribution / a way to run it inside Docker locally. The AWS K3s target still shares one EC2 failure domain.
- **Kubernetes Service:** a stable endpoint for routing to selected Pods. It does not replicate socket lists or broadcast application messages between backend processes.
- **Kustomize:** builds environment-specific manifests from common Kubernetes resources and patches. The raw AWS overlay has placeholders that the release renderer must replace.
- **NetworkPolicy / ACL:** network-level permission to connect / application-level permission to execute commands or use channels. Baatchit uses both for Redis isolation.
- **Secret / ConfigMap:** Kubernetes objects for sensitive configuration / ordinary configuration. Secret handling still needs appropriate storage encryption, access restrictions and rotation.
- **SBOM:** a software bill of materials describing packaged components. It helps assess exposure but does not itself certify that those components are safe.
- **Digest pin:** an immutable image content reference such as `@sha256:...`. It identifies the exact artifact; trust still requires approved origin/signature and testing.
- **Cosign identity:** the expected signer/workflow checked when verifying an artifact. The deployer gets that trust expectation from operator configuration, not from the artifact being verified.
- **RTO / RPO:** target recovery duration / tolerable data loss at a defined recovery boundary. Current chat has no durable recovery source, and cloud recovery targets remain unverified.
- **Concurrency / parallelism:** overlapping progress of tasks / simultaneous execution on multiple execution resources. Async I/O concurrency alone does not supply parallel Python CPU execution.
- **Race condition:** an outcome that depends on an unsafe interleaving of operations. An `await` can split a logical check-and-update even on one event-loop thread.
- **Optimistic / pessimistic concurrency:** detect a conflicting version at update time / reserve access while a critical operation runs. Their scope must match the state being protected.
- **Deadlock / starvation:** a cycle where operations cannot proceed / an operation repeatedly denied useful progress while others continue. Timeouts and fairness policies address different parts of these problems.
- **Semaphore / pool:** a bound on simultaneous work / a bounded set of reusable dependency connections. Neither automatically bounds waiting callers.
- **Shard:** a subset of data assigned to an owner. A shard is distinct from a copy of the same data and from a backend's live socket list.
- **Consistent hashing:** a placement strategy that limits remapping when membership changes. It does not itself migrate data, fix a single hot key or establish authority.
- **Routing epoch / fencing token:** a version of ownership that protected operations validate to reject stale owners. A heartbeat nonce is not automatically a fencing mechanism.
- **Replication lag:** the delay between an authoritative change and a replica applying/serving it. A successful primary write can therefore be absent from a replica read.
- **Quorum / consensus:** a required participant set / a protocol for agreeing on decisions despite defined failures. A majority count without protocol rules is insufficient.
- **Split brain:** conflicting sides acting as authoritative owners. Safe failover needs fencing and a known acceptance/replication boundary.
- **Head-of-line blocking:** later work waiting behind earlier incomplete work, whether in an ordered transport or application queue. Independent queues isolate some boundaries but not all shared resources.
- **MVCC:** database concurrency using multiple versions/snapshots. The isolation level still determines which multi-operation anomalies are possible.
- **Write/read/space amplification:** extra physical writes, reads or stored copies relative to logical application data. Indexes, replication and compaction change these costs.
- **CDC / event sourcing:** propagating committed database changes / using a domain-event history as authoritative state. Neither term is interchangeable with a transactional outbox.
- **Retry budget:** an explicit bound on extra attempts so failures do not multiply into uncontrolled load. Deadline, idempotency and backoff rules still apply.
- **Circuit breaker / bulkhead:** temporarily limit calls to a failing dependency / isolate resource consumption between workloads. A useful fallback and bounded waiters are still required.
- **Cache stampede:** many misses/expirations creating simultaneous origin requests. Refresh coalescing, expiry jitter and fallback budgets can reduce it.
- **Canary release:** expose a representative subset to a new version and compare defined outcomes. WebSocket handshake share may differ from active-session or message-work share.
- **Control plane / data plane:** managing configuration, authority and placement / serving ordinary user operations under that policy. The allowed behavior during control outages must be explicit.
