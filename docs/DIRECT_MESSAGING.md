# Session-based direct messaging

**Status: implemented, 28 October 2026.** Baatchit supports a public General room and ephemeral one-to-one conversations between currently connected `chat.v2` sessions. This document records the current protocol and its limits. The original [v1 specification](API_SPECIFICATION.md) remains valid for legacy public chat.

## What a user can do

1. Connect to the application using a temporary display name.
2. Select an available person in **Direct messages**. Each entry represents one live browser session; the short ID helps distinguish identical names.
3. Send messages in that conversation. The General room and each direct conversation have separate drafts and displayed messages.
4. Return to General, select another person, or read an unread direct message using the badge.
5. If a person disconnects, their existing direct thread remains in the current tab and is marked offline. Sending is disabled until that specific session is available. A reconnect creates a **new** session and appears as a separate entry.

Only the sender's session and the selected recipient session are sent the direct event. The server does not broadcast its body to other WebSocket sessions. Other connected users can still see the presence list. `chat.v1` clients participate in General only and do not receive direct events or the v2 presence list.

Messages and session lists are temporary. No database, history replay, offline delivery, accounts, multi-device identity, receipts or end-to-end encryption are implemented. Refreshing the browser loses its memory. The 500-event browser cap is shared by public and direct events, so activity in one conversation can evict older events from another.

## Privacy and identity boundaries

- The server generates each connection UUID and derives the sender UUID/name from the accepted socket. A client cannot add a sender field to a valid v2 command.
- The target is a live session UUID from the current presence view. A stale target can disappear before delivery. A display name is only a user-selected label and can be impersonated.
- All backend replicas subscribe to the same Redis channel and receive the plaintext direct event. Redis and trusted backend/service operators can inspect it; routing filters prevent delivery to unrelated browser sessions.
- Public deployment uses TLS at the gateway when configured. Local HTTP is not encrypted, and TLS terminates at the gateway. This is **not end-to-end encryption**.
- Origin checks restrict browser origins but are not user authentication. A non-browser client can supply headers and choose a display name. Do not use these direct messages for sensitive information where verified identity or strong confidentiality is required.
- A sender's returned event confirms that its own socket received a broker event. It is not an acknowledgment that the recipient read, received or stored the message.

Production private messaging would need authenticated accounts and devices, authorization, secure credential and key management, abuse controls, durable storage/replay if required, and a reviewed end-to-end encryption design if that is a product requirement.

## Handshake and compatibility

The browser offers `chat.v2, chat.v1` in that order. The server selects `chat.v2` whenever it is offered, otherwise `chat.v1`, and denies unsupported subprotocols before upgrade. The first outbound event is the existing strict `session` envelope, including the server-generated `connection_id`.

- **v1:** inbound text frames are plain chat text; outbound events are `session`, `chat` and `system`.
- **v2:** inbound text frames contain JSON commands; outbound events include the existing v1 envelopes plus `peers`, `private` and `notice` described below. These added envelopes retain `schema_version: 1`; the negotiated **subprotocol** distinguishes the expanded contract.
- All replicas must be updated for consistent v2 availability. During a mixed rollout, an older replica can select v1, so a browser routed there has public chat only.
- [events-v1.schema.json](../schemas/events-v1.schema.json) covers the original envelopes. It does not describe the new v2-only envelopes; the strict models in [protocol.py](../backend/app/protocol.py), client parser in [protocol.js](../frontend/js/protocol.js) and examples below describe them.

All commands have exact field sets; extra fields, invalid JSON, invalid UUIDs and an attempt to address the sender's own session cause policy close `1008`. The existing 16 KiB frame bound, text normalization, 2,000-code-point limit, per-socket and per-replica rate limits, and bounded writer queues still apply. Binary frames are rejected.

## Client to server

Public message:

~~~json
{"type":"chat","text":"Hello everyone"}
~~~

Direct message:

~~~json
{
  "type": "private",
  "to": "a4f642d5-1e2b-48e3-a9a2-8879d7a11001",
  "client_id": "a4f642d5-1e2b-48e3-a9a2-8879d7a11002",
  "text": "Hello Bob"
}
~~~

`to` is the recipient's UUIDv4 connection ID from the latest peer list. `client_id` is a client-generated UUIDv4 used only to correlate the sender's draft with an echo or rejection. It is **not** a durable idempotency key, a delivery receipt, or proof of identity.

## Server to client

The peer list is sent only to v2 sessions after the initial session event and whenever the visible list changes. It excludes the receiving session:

~~~json
{
  "schema_version": 1,
  "type": "peers",
  "peers": [{"connection_id":"a4f642d5-1e2b-48e3-a9a2-8879d7a11001","user":"Bob"}]
}
~~~

Direct event, delivered to the sender and recipient sessions:

~~~json
{
  "schema_version": 1,
  "type": "private",
  "event_id": "a4f642d5-1e2b-48e3-a9a2-8879d7a11003",
  "sent_at": "2026-10-28T10:00:00.000Z",
  "user": "Alice",
  "text": "Hello Bob",
  "container_id": "backend-a",
  "time": "10:00:00 UTC",
  "sender_id": "a4f642d5-1e2b-48e3-a9a2-8879d7a11004",
  "recipient_id": "a4f642d5-1e2b-48e3-a9a2-8879d7a11001",
  "recipient_user": "Bob",
  "client_id": "a4f642d5-1e2b-48e3-a9a2-8879d7a11002"
}
~~~

If the backend no longer knows the target, it sends only the sender a `notice` with `schema_version`, `type`, `client_id` and `message`. Nothing is published as a direct event in that case. An independently stale presence snapshot can still allow a publish after the recipient has disappeared, so no delivery guarantee follows from a sender echo.

The client rejects an unexpected direct event when its current session UUID matches neither endpoint. It renders message text as React text, not HTML.

## Presence and cross-replica routing

Each backend periodically publishes an internal `_presence` snapshot of its active v2 sessions to the existing Redis Pub/Sub channel. A snapshot has a process UUID, increasing sequence and at most 256 session records. Join/leave updates trigger a coalesced snapshot; otherwise the interval is three seconds. Backends retain at most 128 remote snapshots, discard stale snapshots after 12 seconds and expose at most 512 peers per client. Presence is advisory and eventually consistent; it is not an authentication or precise online-count authority.

When a v2 command arrives, the serving backend derives the sender from its local session and validates that the recipient is in its current bounded presence view. It publishes a strict `private` event. Every backend validates the event, then delivers it only to local sockets whose server-assigned IDs match `sender_id` or `recipient_id`. The same Redis ACL and Pub/Sub channel are used; no new Redis keys or persistence are required.

A crashed replica may remain visible until its snapshot expires. Pub/Sub has no replay; a disconnect, overload, timeout or Redis failure can lose a message. Redis loss closes sockets and clears the local presence cache. Reconnects create new session IDs and do not restore missed messages.

## Drafts and failure handling

- Drafts are maintained separately for General and each selected session in browser memory.
- A direct send holds its draft while awaiting the sender's matching event. It clears that draft only when the matching `client_id` returns and the user has not edited the draft.
- If the server rejects a stale recipient, the matching notice clears the pending state and leaves the draft.
- After eight seconds with no matching event, the UI marks delivery unconfirmed and retains the draft. Retrying can duplicate a message if the first publish succeeded but its echo was lost.
- A lost socket cancels the wait and retains the draft. No automatic resend occurs.
- Public send behavior remains unchanged: the draft clears after the browser buffers the frame and the UI notes that delivery is unconfirmed.

## Running and verification

Frontend-only Vite preview displays the layout but cannot connect or send. To use direct messaging, run the full local stack using [Development](DEVELOPMENT.md); stop the Vite preview first if it occupies port 8080. Open two tabs and choose distinct names, wait for the other session in the sidebar, then select it. A third tab should see public messages but not the private conversation. A different device needs a reachable deployment and configured allowed origin; `127.0.0.1` refers to each device itself.

Local checks for this change:

- Python unit tests and JavaScript protocol/connection tests.
- Chromium tests with intercepted WebSockets for selection, separate drafts, unread counts and offline state.
- Two real ASGI servers and four real WebSocket clients connected through a local RESP Pub/Sub **test double**: public compatibility, cross-replica direct routing, observer/legacy isolation, stale-recipient rejection and forged-sender rejection.
- A real Redis container integration test is included in `tests/integration/test_runtime.py`, but was not run locally for this change because the Docker engine was unavailable. Kubernetes, AWS, vulnerability scanning and load results from earlier versions do not establish those results for this feature.
