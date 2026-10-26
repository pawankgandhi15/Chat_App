# Testing and Evidence Plan

**Design revision 5 — 2026-10-26. Status: no tests implemented or executed.** [Requirements](REQUIREMENTS.md) owns AC-01 through AC-18 and NFR-01 through NFR-08; [API](API_SPECIFICATION.md) owns protocol expectations.

## Test layers

| Layer | Behaviors to prove | Environment |
| --- | --- | --- |
| Unit/property | Normalization, Unicode boundaries, settings, event schemas, limiter clocks, queue accounting | Isolated test container; deterministic clocks where appropriate. |
| Transport contract | Upgrade denial, subprotocol, session-first ordering, frames/close codes, fragmentation | Real selected ASGI/WebSocket server. |
| Integration | Cross-Pod fan-out, one sender echo, Redis ACL, heartbeat generations | Local k3d with real Redis and two backend Pods. |
| Browser | Accessibility, safe rendering, retries, drafts, scroll behavior, protocol errors | Browser automation against gateway. |
| Kubernetes | Selectors, probes, policy enforcement, rollout, resource bounds, complete rollback | Pinned k3d; repeat AWS-specific paths on EC2. |
| Infrastructure/security | Terraform plan, SG boundaries, public TLS, RBAC and signature rejection | Static validation plus authorized temporary AWS environment. |
| Load/recovery | Quantitative objectives, failure timelines, node/Pod pressure | Off-node generator against exact candidate deployment. |

## Protocol and lifecycle cases

Test username boundaries, allowed ASCII syntax, astral Unicode code points, CRLF/lone-CR normalization, ASCII-only boundary trimming and prohibited C0/DEL controls. Do not test against an invented NFKC rule. Distinguish application code-point policy from reassembled transport bytes; fragmented and binary frames need actual transport tests.

Verify the first frame is a private session envelope with a new connection UUID and correct replica. Concurrent broadcasts must not overtake it. Validate timestamp consistency and event UUIDs. Test sender echo exactly once via Redis, duplicate display names, malformed server events and browser history capped at 500 entries.

Test concurrent admission near the configured ceiling, token-bucket refill/burst edges, event and byte queue bounds, cleanup under cancellation and ambiguous publish timeout without blind retry. The 64-per-replica ceiling is not a tested-capacity claim.

## Distributed delivery

Connect clients through the real gateway, inspect session `container_id`, and establish coverage of both backend Pods. Do not assume round-robin assignment. Publish uniquely identifiable test payloads and correlate server event IDs per recipient. Verify all healthy recipients, including the sender, receive one copy.

For targeted diagnostics, direct Pod access may isolate a component, but it cannot replace the gateway end-to-end acceptance test.

## Fault matrix

| Fault | Assert |
| --- | --- |
| Redis process/network loss | Readiness fails, new admission stops, affected sockets close with 1011. |
| Subscriber stall with publisher PING healthy | Freshness fails readiness; old-generation nonce cannot restore it. |
| Redis restored | Readiness <=15s; actively retrying browsers establish a live session <=60s. |
| Planned backend termination | Admission stops; 1012 drain <=10s; cleanup within total 20s grace. |
| Forced backend crash | Affected sockets drop; remaining ready endpoint works; retry eventually succeeds. |
| Slow recipient | 1013 on overflow/write timeout; healthy peers remain within measured targets. |
| Bad image/config/policy | Deployment fails verification; previous complete bundle restores <=10 minutes. |
| Concurrent/interrupted deployment | One supported operation proceeds; journal/live-state reconciliation prevents false success. |
| Node pressure | Events and metrics expose pressure; no OOM/evictions in accepted baseline run. |

A fault experiment cannot be counted as part of the healthy delivery SLO. Report expected gaps separately; the system offers no replay.

## Candidate load experiment

- 25 simultaneous clients distributed 12/13 across backend Pods.
- Aggregate 5 chat messages/s with 512-byte test payloads.
- 2-minute warmup, then 30-minute steady observation.
- Measure send-to-recipient latency using one external generator's monotonic clock.
- Targets: p95 <250ms, p99 <1000ms; >=99.9% expected deliveries within 2s; zero duplicate event IDs per recipient.
- Healthy expected deliveries are messages successfully published × continuously connected recipients. Record attempted sends, rejected/ambiguous publications and connectivity separately so they cannot disappear from the result.
- Node MemAvailable >=512 MiB during steady state; no OOM, swap thrashing or pressure-related evictions. Capture CPU, RSS, descriptors, disk and rollout peaks.

Record exact instance, OS, K3s, image digests, configuration, origins, generator placement and network conditions. C7i-flex performance characteristics differ from T3 credits; report the selected family accurately.

## Network and security tests

Positive paths: browser→gateway, gateway→frontend/backend, backend→Redis and required DNS/probes. Negative paths: public→API/backend/Redis/diagnostics, gateway/frontend→Redis, unauthorized Redis channels/commands and excessive deployer RBAC.

Verify policy enforcement against Service and Pod addresses and actual ServiceLB source NAT. Check secret values are absent from images, manifests, logs and reports. Reject wrong signer, modified configuration, mutable release image references and unsafe resource kinds.

## Evidence package

Keep sanitized test summary, command/tool versions, environment IDs, raw latency samples, event counts, failures, Pod events, node measurements, release/config hashes and rollback timelines. Link evidence to acceptance IDs. Mark missing evidence pending; do not substitute screenshots or a green readiness endpoint for behavioral results.

Static documentation/link validation can run now. Runtime tests require implementation; [release checklist](RELEASE_CHECKLIST.md) tracks those gates.

