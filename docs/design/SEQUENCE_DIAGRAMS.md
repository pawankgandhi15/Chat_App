# Sequence Diagrams

**Status: design documentation only. Baseline: design revision 5. Updated: 2026-10-26.**

These diagrams express intended behavior. Exact wire fields and close codes remain in [API](../API_SPECIFICATION.md); task ownership is in [LLD](LLD.md).

## Connect and initialize

```mermaid
sequenceDiagram
    participant C as Browser
    participant G as Gateway
    participant B as Selected backend
    participant W as Session writer
    participant R as Redis
    C->>G: Upgrade /ws/name with chat.v1
    G->>B: Forward through backend Service
    B->>B: Validate and reserve admission
    alt Invalid or not ready
        B-->>C: Deny before upgrade
        B->>B: Release any reserved capacity
    else Accepted
        B-->>C: Upgrade with chat.v1
        B->>W: Initialize private session event
        W-->>C: Session event first
        B->>B: Activate session for fan-out
        B->>R: Publish advisory join
        C->>C: Enable send
    end
```

The diagram abbreviates return traffic through the gateway. An initializing session is not yet a broadcast recipient.

## Cross-replica message delivery

```mermaid
sequenceDiagram
    participant A as Client A
    participant B1 as Backend 1
    participant R as Redis
    participant B2 as Backend 2
    participant B as Client B
    A->>B1: Raw text
    B1->>B1: Charge budget, normalize, validate, envelope
    B1->>R: Publish event
    R-->>B1: Subscriber receives event
    R-->>B2: Subscriber receives event
    B1->>B1: Bounded enqueue
    B2->>B2: Bounded enqueue
    B1-->>A: Writer sends one Redis echo
    B2-->>B: Writer sends same event_id
```

No direct local echo is added before Redis fan-out. This shows healthy behavior, not exactly-once delivery during faults.

## Dependency loss and recovery

```mermaid
sequenceDiagram
    participant C as Browser
    participant B as Backend
    participant R as Redis
    participant K as Kubernetes
    R--xB: Subscription breaks or stalls
    B->>B: Mark DEGRADED after failure detection
    K->>B: Readiness probe
    B-->>K: 503
    B-->>C: Close affected socket with 1011
    C->>C: Bounded retry with jitter
    loop Until restored or process stops
        B->>R: Reconnect with new generation
    end
    R-->>B: Subscription acknowledgment and nonce probe
    B->>B: Mark READY only for current generation
    K->>B: Readiness probe
    B-->>K: 200
    C->>B: New connection attempt through gateway
    B-->>C: New session
```

There is no historical replay after recovery. Browser retries may pause after exhaustion; a paused user needs manual retry.

## Controlled deployment and restoration

```mermaid
sequenceDiagram
    participant O as Operator or CI
    participant V as Release verifier
    participant K as Kubernetes
    participant T as Behavioral checks
    O->>V: Candidate bundle and trusted verification policy
    V->>V: Check identity, hashes and permitted resources
    alt Verification fails
        V-->>O: Reject without apply
    else Verification passes
        V->>K: Apply reviewed bundle
        K-->>V: Rollout state
        V->>T: TLS, session and cross-Pod checks
        alt Checks pass
            T-->>O: Record accepted release and evidence
        else Checks fail
            V->>K: Reapply prior compatible verified bundle
            V->>T: Verify restored behavior
            T-->>O: Record restored or unresolved incident
        end
    end
```

Applying multiple Kubernetes resources is not atomic. The journal and live state must be reconciled after interruption; a failed restoration stays an incident.
