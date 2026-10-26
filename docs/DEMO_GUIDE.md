# Demonstration Guide

**Design revision 5 — 2026-10-26. Status: script for a future working implementation.** No live URL or cluster exists.

## Preparation

Use the accepted release and sanitized evidence. Confirm context, namespace, five ready application Pods, current credit/runtime window and rollback bundle. Use local k3d for routine demos; AWS demonstrations require the budget and teardown gates.

Explain the topology: gateway + frontend + two backend Pods + Redis, with additional K3s system Pods on one EC2 node. This proves distributed application messaging within one failure domain.

## Scenario 1 — Browser experience and protocol

Open the app in two independent browser sessions. Show keyboard navigation, labeled composer, connection state and safe text. Inspect the negotiated `chat.v1` subprotocol and first private `session` envelope.

Check the actual `container_id` values; reconnect until both backend Pods are represented. Send a unique message and show one copy per client, including the sender. Do not claim two tabs necessarily mean two replicas.

## Scenario 2 — Input safety and honest identity

Send HTML-looking text and show inert rendering. Exercise allowed Unicode and boundaries, then rejected invalid input. Duplicate display names should not create a verified identity or reliable own-message classification.

Scroll upward while messages arrive: the reading position remains stable and a new-message indicator appears. Explain the 500-entry browser history cap and lack of server replay.

## Scenario 3 — Planned replacement and failure

In the disposable demo environment, perform the rehearsed backend rollout. Show ready endpoint changes, 1012 planned drain and bounded browser retries. Compare with a forced Pod crash, which can produce an abnormal disconnect.

Restart Redis through the controlled test procedure. Show readiness failing, disabled sending, subscriber recovery and fresh sessions. Messages lost during the gap are not reconstructed.

## Scenario 4 — Boundaries and capacity evidence

Show successful allowed network paths and failed gateway/frontend-to-Redis and public diagnostic/API access. Present measured node and Pod usage, not a screenshot of requested limits as if it were real memory consumption.

Show the recorded 25-client, aggregate 5-message/s, 30-minute healthy run, latency percentiles, delivery counts and node headroom. Label all unrun scenarios pending.

## Scenario 5 — Failed release and rollback

Use a deliberately invalid test release in the disposable environment. Demonstrate verification failure or failed rollout, then restore the complete previous bundle. Show image IDs/config hashes and cross-replica messaging after restoration, with measured recovery time.

Do not alter real credentials or apply destructive fault injection to an unrelated environment during a presentation.

## Explain the trade-offs

- Kubernetes reconciles Pods and Services; it does not make one EC2 host highly available.
- K3s avoids the EKS cluster fee; AWS infrastructure still has a gross usage cost.
- Redis Pub/Sub is ephemeral and at-most-once.
- TLS protects transport, not end-to-end secrecy or user identity.
- Resource limits and retries bound behavior but do not prove unlimited scalability.

## Finish

Capture sanitized results, stop synthetic clients, restore the accepted release if needed and complete the scheduled AWS teardown. Record remaining resources and later billing. Link the release evidence rather than presenting this guide as proof of implementation.

