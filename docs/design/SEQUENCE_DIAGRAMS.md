# System Sequence Diagrams

**Status: Production Architecture Specification. Baseline: Design Revision 5. Updated: 2026-10-26.**

This document provides definitive, end-to-end execution sequence diagrams for all critical connection, messaging, failure recovery, eviction, and release workflows in Chat App.

---

## 1. Connection Admission & Handshake Sequence

Demonstrates connection establishment, origin/username validation, atomic slot reservation, private `session` envelope dispatch, broadcast activation, and advisory `system` join publication.

```mermaid
sequenceDiagram
    autonumber
    participant C as Browser Client
    participant GW as Nginx Gateway Pod
    participant BE as FastAPI Backend Pod
    participant W as Session Writer Task
    participant R as Redis Broker Pod

    C->>GW: GET /ws/alice HTTP/1.1<br/>Upgrade: websocket<br/>Sec-WebSocket-Protocol: chat.v1<br/>Origin: https://chat.example.com
    Note over GW: Validates TLS & sanitizes headers
    GW->>BE: Forward Upgrade via backend ClusterIP :8000
    
    Note over BE: Validation & Admission Gate
    BE->>BE: 1. Validate Origin against allowlist
    BE->>BE: 2. Check regex: ^[a-zA-Z0-9_\-]{1,32}$
    BE->>BE: 3. Verify process readiness (state == READY)
    BE->>BE: 4. Atomic check: current_sessions < 64

    alt Admission Denied (Full or Invalid)
        BE-->>GW: HTTP 403 Forbidden / 429 Too Many Requests
        GW-->>C: HTTP 403 / 429 Response (Handshake Denied)
    else Admission Accepted
        BE->>BE: Reserve session slot (atomic increment)
        BE-->>GW: HTTP 101 Switching Protocols<br/>Upgrade: websocket<br/>Sec-WebSocket-Protocol: chat.v1
        GW-->>C: HTTP 101 Switching Protocols
        
        Note over BE,W: Phase 1: Unicast Initialization (State: INITIALIZING)
        BE->>W: Spawn Writer Task & create DeliveryQueue
        W->>C: Direct unicast "session" envelope<br/>{"type":"session","connection_id":"...","user":"alice"}
        
        Note over BE: Phase 2: Broadcast Activation (State: ACTIVE)
        BE->>BE: Register session in active broadcast set
        BE->>R: PUBLISH global_chat_channel<br/>{"type":"system","text":"alice joined the chat"}
        C->>C: Enable UI send button and draft input
    end
```

---

## 2. Distributed Cross-Replica Message Fan-Out Sequence

Demonstrates message ingestion, token bucket charge, envelope serialization, Redis publication, and symmetric fan-out across independent backend replicas.

```mermaid
sequenceDiagram
    autonumber
    participant A as Client A (on Backend 1)
    participant B1 as FastAPI Backend 1
    participant R as Redis Pub/Sub Bus
    participant B2 as FastAPI Backend 2
    participant B as Client B (on Backend 2)

    A->>B1: Raw text frame: "Hello, distributed mesh!"
    Note over B1: Ingestion & Validation
    B1->>B1: 1. Check socket TokenBucket (capacity 5, refill 1/s)
    B1->>B1: 2. Enforce length <= 16 KiB & normalize Unicode (NFC)
    B1->>B1: 3. Construct immutable chat event with event_id UUIDv4
    
    Note over B1,R: Distributed Broker Bus
    B1->>R: PUBLISH global_chat_channel {"type":"chat","user":"A",...}
    
    par Subscriber Fan-Out to Replicas
        R-->>B1: Deliver event to Backend 1 subscriber
        Note over B1: AsyncIO Dispatcher iterates local sessions
        B1->>B1: Enqueue to Client A DeliveryQueue
        B1-->>A: Writer flushes JSON frame (Sender Echo)
    and
        R-->>B2: Deliver event to Backend 2 subscriber
        Note over B2: AsyncIO Dispatcher iterates local sessions
        B2->>B2: Enqueue to Client B DeliveryQueue
        B2-->>B: Writer flushes JSON frame
    end
```

---

## 3. Slow Consumer Detection & Bounded Queue Eviction Sequence

Demonstrates backpressure enforcement, queue saturation detection, socket write timeout, and deterministic client eviction via close code `1013` (Try Again Later) without impacting neighbor sessions.

```mermaid
sequenceDiagram
    autonumber
    participant R as Redis Pub/Sub Bus
    participant BE as FastAPI Backend Pod
    participant W as Slow Client Writer Task
    participant Slow as Congested Client
    participant Fast as Healthy Client

    Note over Slow: High latency or TCP window stall
    loop Broadcast Influx from Redis
        R-->>BE: Inbound broadcast events
        BE->>Fast: Enqueue and flush successfully
        BE->>BE: Check Slow Client DeliveryQueue
    end

    alt Outbound Queue Saturation (Items > 32 OR Bytes > 256 KiB)
        Note over BE: Backpressure Triggered
        BE->>BE: DeliveryQueue.try_enqueue() returns False
        BE->>BE: Mark session state = SLOW_CONSUMER
        BE->>W: Signal immediate eviction
    else Socket Write Timeout (Elapsed > 2.0s)
        W->>Slow: Attempt raw frame flush
        Note over W: Socket flush times out after 2.0s
        W->>BE: Notify write timeout breach
    end

    Note over BE,W: Deterministic Eviction (Close Code 1013)
    BE->>BE: Unregister session from broadcast registry
    W->>Slow: Send WebSocket Close Frame (Code 1013: Try Again Later)
    Slow->>Slow: Transition UI to reconnecting with backoff
    W->>W: Purge DeliveryQueue & decrement pending byte accounting
    BE->>BE: Decrement active_session count & release admission slot
    Note over BE,Fast: Healthy Client Continues Operating with Zero Delay
```

---

## 4. Rolling Deployment & Graceful Drain Sequence

Demonstrates Kubernetes zero-downtime rolling deployment, readiness probe failure, asynchronous endpoint removal, and client handoff via close code `1012` (Service Restart).

```mermaid
sequenceDiagram
    autonumber
    participant K8s as K3s Kubelet
    participant SLB as ServiceLB / Gateway
    participant BE1 as Backend Pod 1 (Terminating)
    participant C as Connected Client
    participant BE2 as Backend Pod 2 (Surviving)

    K8s->>BE1: SIGTERM Signal Dispatched
    Note over BE1: 1. Set process_state = DRAINING
    BE1->>BE1: Fail readiness (/health returns HTTP 503)
    
    par Endpoint De-registration
        K8s->>SLB: Asynchronously remove Pod 1 IP from Service endpoints
        SLB->>SLB: Stop routing new HTTP/WS handshakes to Pod 1
    and Coordinated Drain Window (10s Budget)
        Note over BE1: 2. Send Close Code 1012 to Active Sockets
        BE1->>C: Close Frame 1012 (Service Restart)
        C->>C: Calculate exponential backoff with full jitter (0.5s - 15s)
        BE1->>BE1: Await task cancellations & purge memory queues
        BE1->>BE1: Unsubscribe Redis & close connection pool
    end

    BE1-->>K8s: Process exits cleanly (Exit Code 0 within 20s grace)
    
    Note over C,BE2: Reconnection to Surviving / New Replica
    C->>SLB: New WebSocket Upgrade Request
    SLB->>BE2: Forward handshake to healthy Backend Pod 2
    BE2->>BE2: Validate & reserve admission slot
    BE2-->>C: HTTP 101 Switching Protocols + Session Envelope
    C->>C: Session restored; unsent drafts preserved
```

---

## 5. Redis Heartbeat Stalling & Degraded Recovery Sequence

Demonstrates watchdog probe monitoring, stale nonce detection, readiness degradation, and automatic generational reconnect.

```mermaid
sequenceDiagram
    autonumber
    participant K8s as K3s Kubelet Prober
    participant BE as FastAPI Backend Pod
    participant R as Redis Broker Pod
    participant C as Connected Client

    Note over BE: Steady State: Generation 1
    loop Every 5 Seconds
        BE->>R: PUBLISH probe:gen1:<uuid>
        R-->>BE: Echo probe back to subscriber
        BE->>BE: Update last_echo_timestamp = now()
    end

    Note over R: Redis Network Partition / Event Loop Hang
    BE-xR: PUBLISH probe:gen1:<uuid> (Message Dropped / Stalled)
    
    Note over BE: Stale Heartbeat Threshold (10.0s Elapsed)
    BE->>BE: now() - last_echo_timestamp > 10.0s
    BE->>BE: Set process_state = DEGRADED
    
    K8s->>BE: GET /health (Readiness Probe)
    BE-->>K8s: HTTP 503 Service Unavailable
    Note over K8s: Pod 1 removed from gateway routing endpoints
    
    BE->>C: Send Close Frame 1011 (Internal Error)
    
    Note over BE: Generational Reconnect Loop
    BE->>BE: Cancel Generation 1 subscriber task
    BE->>R: Re-establish TCP socket & SUBSCRIBE (Generation 2)
    R-->>BE: Subscription Acknowledged
    BE->>R: PUBLISH probe:gen2:<new_uuid>
    R-->>BE: Echo probe:gen2:<new_uuid>
    
    Note over BE: Restored Health
    BE->>BE: Set process_state = READY (Generation 2 Active)
    K8s->>BE: GET /health (Readiness Probe)
    BE-->>K8s: HTTP 200 OK
    Note over K8s: Pod 1 re-added to gateway routing endpoints
```

---

## 6. Rate Limit Throttling Sequence

Demonstrates token bucket depletion under inbound spam and client throttling.

```mermaid
sequenceDiagram
    autonumber
    participant C as Flooding Client
    participant BE as FastAPI Backend Pod
    participant R as Redis Pub/Sub Bus

    Note over BE: Socket TokenBucket: Capacity 5, Refill 1/s
    loop 5 Rapid Messages (< 500 ms)
        C->>BE: Inbound text frame
        BE->>BE: TokenBucket.consume(1.0) -> True
        BE->>R: PUBLISH to Redis
    end

    Note over BE: Bucket Depleted (tokens = 0.0)
    C->>BE: 6th Inbound text frame (Burst limit exceeded)
    BE->>BE: TokenBucket.consume(1.0) -> False (Throttled)
    BE->>BE: Increment rate_limit_violations_total metric
    BE-->>C: Drop frame without closing socket (Client throttled)
    
    Note over C: Client waits 1.0 second for token refill
    C->>BE: Inbound text frame after 1.0s
    BE->>BE: TokenBucket.consume(1.0) -> True (Refilled)
    BE->>R: PUBLISH to Redis
```

---

## 7. Verified CI/CD Deployment & Automated Rollback Sequence

Demonstrates supply-chain verification, immutable OCI deployment, end-to-end smoke testing, and deterministic rollback to the prior release bundle.

```mermaid
sequenceDiagram
    autonumber
    participant CI as GitHub Actions CI
    participant Verifier as Deployment Verifier
    participant K8s as K3s API Server
    participant Tests as E2E Behavioral Harness

    CI->>Verifier: Candidate Release Manifest (Digest: sha256:abc...)
    Note over Verifier: Supply-Chain Verification Gate
    Verifier->>Verifier: 1. Verify Cosign image signature
    Verifier->>Verifier: 2. Check immutability & pinned digests
    Verifier->>Verifier: 3. Validate against K8s base schemas
    
    Verifier->>K8s: kubectl apply -k k8s/overlays/aws/
    K8s-->>Verifier: Workload rollouts initiated
    
    Note over Verifier,Tests: Post-Deployment Smoke Verification (10m Budget)
    Verifier->>Tests: Execute automated test suite
    Tests->>K8s: Verify 5 Application Pods in Ready state
    Tests->>Tests: Verify public TLS certificate validity
    Tests->>Tests: Perform bidirectional WebSocket message exchange
    
    alt All Smoke Tests Pass
        Tests-->>Verifier: 100% Behavioral Checks Successful
        Verifier-->>CI: Deployment Accepted & Recorded in S3
    else Behavioral Checks Fail (Timeout / Disconnects)
        Tests-->>Verifier: Test Failure: Cross-Replica Echo Timed Out
        Note over Verifier: Trigger Deterministic Rollback (< 10m Target)
        Verifier->>K8s: kubectl apply -f release-manifest-previous.yaml
        K8s-->>Verifier: Previous release restored
        Verifier->>Tests: Re-execute smoke verification against restored release
        Tests-->>Verifier: Restored release healthy
        Verifier-->>CI: Deployment Aborted: Incident Logged & Prior Release Restored
    end
```
