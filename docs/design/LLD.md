# Low-Level Design

**Status: design documentation only. Baseline: design revision 5. Updated: 2026-10-26.**

The interfaces below are **conceptual contracts for future code**, not existing functions. [API](../API_SPECIFICATION.md) owns external behavior; [configuration](../CONFIGURATION.md) owns defaults. Source names follow [project structure](../PROJECT_STRUCTURE.md).

## Backend modules and interfaces

| Module | Proposed interface / responsibility | Ownership and invariant |
| --- | --- | --- |
| `main.py` | Build app, routes and lifecycle wiring | One process lifecycle per Pod; no hidden Redis singleton per request. |
| `settings.py` | Load and validate immutable Settings | Resolve exactly one credential source; never log resolved secrets. |
| `validation.py` | Validate username; normalize and validate text | Pure operations; preserve API normalization and exact limits. |
| `protocol.py` | Build session/chat/system events; validate/serialize | Server assigns event IDs and timestamps; session is never broadcast. |
| `sessions.py` | Reserve, register, enqueue, write, close and release sessions | Exactly one admission reservation and writer per connection. |
| `limits.py` | TokenBucket.consume; bounded queue accounting | Monotonic time; updates cannot oversubscribe under concurrent tasks. |
| `broker.py` | Publish, supervise subscription, probe generation, reconnect | Dedicated subscriber and bounded publisher pool; no blind ambiguous retries. |
| `health.py` | Readiness snapshot and process liveness | Readiness requires current subscriber health; liveness does not depend on Redis. |
| `telemetry.py` | Bounded-label metrics and redacted lifecycle logs | No message bodies, username paths or secrets. |

Keep process lifecycle state in one explicit object wired by the app, rather than unrelated flags in each module. Inject clock, ID provider and broker adapter for deterministic unit tests; retain real-transport integration tests.

## Internal objects

| Object | Fields / conceptual state | Lifetime |
| --- | --- | --- |
| ProcessState | STARTING, READY, DEGRADED or DRAINING; release; subscriber generation | One process. |
| Session | connection_id, display_name, phase, writer/reader task references, queue, reserved slot | One accepted socket attempt through cleanup. |
| DeliveryQueue | FIFO entries, pending event count, pending UTF-8 bytes, closed flag | One session; mutation serialized. |
| TokenBucket | refill rate, burst, tokens, last monotonic timestamp | Per socket or per-replica publisher budget. |
| BrokerState | subscriber connection, generation, acknowledged subscription, last successful probe | Replaced on reconnect; old generation cannot make new state ready. |
| Event | Immutable validated fields and serialized payload | Constructed once; shared safely between local queues where possible. |

Internal session phases are ADMITTED → INITIALIZING → ACTIVE → CLOSING → CLOSED. These are separate from the browser state machine.

## Admission and initialization

1. Validate origin, subprotocol, username, process readiness and available capacity.
2. Reserve the slot before accepting; use an atomic critical section so concurrent handshakes cannot exceed the ceiling.
3. Create a connection UUID, queue and one writer. Keep the session INITIALIZING.
4. The writer sends the private session envelope first. Do not expose the session as ACTIVE until this write succeeds.
5. Register it for broadcast fan-out and enable normal receive handling; publish the advisory join after initialization.
6. On any failure, enter the same idempotent close/release path.

Define registration and activation as one serialized transition. Initializing sessions receive no chat broadcasts; if future requirements need gap-free delivery across this boundary, they require replay semantics. Do not silently claim that every event during handshake is delivered.

## Message processing

For each inbound frame, enforce transport rules and charge the socket budget, including normalized-empty messages. Normalize newlines and trim only the API's boundary characters. Validate controls and code points. Empty normalized input is ignored; valid nonempty input proceeds to the shared per-replica publication budget.

Construct and serialize the event once. Publish with a bounded timeout. A timeout can mean unknown publication outcome, so do not automatically resend. Successful publish does not prove browser receipt.

Subscriber processing validates public events, separates internal probe traffic and takes a safe snapshot of ACTIVE local sessions. For each session, attempt bounded enqueue without awaiting socket I/O. Only its writer sends data frames.

## Queue and cleanup algorithm

Queue admission checks both proposed new event count and UTF-8 byte total in one serialized operation. Defaults are 32 events and 262144 bytes. Reserve accounting before insertion; release queued accounting on dequeue, eviction or cancellation exactly once.

One dequeued event can be in flight while the queue is full. Memory measurements must include that event, serialization, transport buffers and socket state; the queue-byte limit alone is not total session memory.

The writer has a 2s send timeout. Overflow or timeout starts close code 1013 for that session. Coordinate WebSocket close through a single close owner to avoid concurrent data/close writes. A slow session must not block the subscriber or another writer.

Close is idempotent: prevent new enqueue, unregister, stop/cancel and await tasks with bounds, release retained queue accounting, close transport, release admission once, then mark CLOSED. Advisory leave publication is best effort and must not block cleanup indefinitely.

## Health and shutdown

A publisher PING is insufficient for readiness. Require subscription acknowledgment and a fresh nonce probe in the current generation; defaults are 5s interval and 10s stale threshold. DEGRADED rejects admission and follows the documented dependency-failure close policy.

DRAINING is terminal for the process. Reject admission, fail readiness and close sockets with 1012 within the 10s drain budget. Finish within the 20s Pod grace including hooks. Verify server signal ordering and asynchronous Service endpoint removal in real integration tests.

## Browser modules

| Module | Responsibilities and invariants |
| --- | --- |
| `protocol.js` | Validate server envelopes and subprotocol; no guessed field defaults. |
| `connection.js` | Own socket, retry timer and connection generation; ignore callbacks from stale sockets. |
| `state.js` | Own draft, connection state and bounded display history. |
| `view.js` | Render via textContent; preserve reading position, keyboard access and focus. |
| `app.js` | Wire user actions and module lifecycle; no hidden automatic resend. |

Allow sending only after a valid session event. Keep retries, terminal close behavior and the special planned-restart path aligned with [API](../API_SPECIFICATION.md). Preserve unsent drafts, never replay uncertain sends automatically, and do not identify an own message solely by display name.

## Implementation blockers and tests

Settle bounded Redis pool size, internal heartbeat format/ACL, transport buffering, ASGI denial support and shutdown ordering before code acceptance. Test reservation races, session-first ordering, queue-byte release, stale callbacks/probes, ambiguous publication and repeated cleanup. See [review checklist](DESIGN_REVIEW_CHECKLIST.md).
