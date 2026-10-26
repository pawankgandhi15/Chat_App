# Live Demonstration & Presentation Guide

**Design Revision 5 — 2026-10-26. Status: Demonstration Script Specification.** This document provides the step-by-step presentation script, audience walkthroughs, CLI execution commands, and talking points for demonstrating Chat App.

---

## 1. Demonstration Setup & Pre-Flight Checklist

Before presenting the live demonstration, ensure the following prerequisites are met:

- [ ] Cluster is active with 5 application Pods in `1/1 Ready` state (`kubectl get pods -n chat-app`).
- [ ] Public HTTPS/WSS endpoint is accessible via browser (`https://chat.example.com` or local `https://localhost:8443`).
- [ ] Two independent browser windows (one standard, one incognito/private) open side-by-side.
- [ ] Terminal split open with live logs streaming: `kubectl logs -n chat-app -l app=backend -f --tail=20`.
- [ ] Rollback release manifest staged and ready: `/opt/chat-app/releases/release-manifest-previous.yaml`.

---

## 2. Live Demonstration Scenarios

### Scenario 1: Distributed Cross-Replica Fan-Out & Handshake Inspection
* **Goal:** Prove that two independent clients land on different backend replicas and exchange messages symmetrically over Redis Pub/Sub without local duplicate echos.
* **Execution Walkthrough:**
  1. Open Browser Window 1. Enter username `alice_99`. Click **Connect**.
  2. Open Browser Window 2 (Incognito). Enter username `bob_12`. Click **Connect**.
  3. Inspect Browser Network Tabs:
     * Point out `Sec-WebSocket-Protocol: chat.v1` negotiation.
     * Point out the private `session` envelope arriving first, displaying distinct `container_id` values (e.g., `backend-replica-1` vs `backend-replica-2`).
  4. Alice sends: `"Hello, distributed real-time mesh!"`.
  5. Verify both Alice and Bob receive the message simultaneously with the exact same `event_id` and UTC timestamp.
* **Key Talking Point:** *"Notice that Alice receives her own message through the Redis broker bus, not via a local in-memory echo. This guarantees identical delivery ordering across all replicas."*

---

### Scenario 2: XSS Neutralization, Unicode Normalization & Bounded History
* **Goal:** Demonstrate enterprise input sanitization and browser memory bounding.
* **Execution Walkthrough:**
  1. Alice sends an XSS payload: `<script>alert('XSS Compromised')</script>`.
  2. Observe that both browsers render the string as inert, harmless text via `textContent`. Zero alert dialogs trigger.
  3. Alice sends a 4-byte astral Unicode emoji message: `"Testing code point math: 🚀🎉🔥"`.
  4. Show that character counters and backend validation accurately compute code point scalar values, not UTF-16 code units.
  5. Highlight the DOM message log: explain that displayed messages are capped at 500 nodes (FIFO eviction) to prevent browser memory exhaustion.
* **Key Talking Point:** *"Input validation counts Unicode scalar values rather than byte lengths, and rendering avoids innerHTML entirely, neutralizing injection vectors by design."*

---

### Scenario 3: Zero-Downtime Rolling Deployment & Connection Drain
* **Goal:** Demonstrate seamless Kubernetes workload replacement using close code `1012` (Service Restart).
* **Execution Walkthrough:**
  1. While both Alice and Bob are actively connected, initiate a rolling restart in the terminal:
     ```bash
     kubectl rollout restart deployment/backend -n chat-app
     ```
  2. Watch the terminal logs show:
     * Pod 1 receives `SIGTERM`.
     * Readiness probe flips to HTTP 503; Pod is removed from ServiceLB endpoints.
     * Pod 1 emits close frame `1012` to active sockets across a 10s drain window.
  3. Observe the browser UI transition briefly to `Reconnecting (Attempt 1/10)` and re-establish a session on the newly ready Pod with zero lost drafts.
* **Key Talking Point:** *"Connections are not violently severed. The application coordinates a paced drain using WebSocket close code 1012, allowing clients to reconnect with full jitter to newly ready replicas."*

---

### Scenario 4: Redis Broker Outage & Generational Recovery
* **Goal:** Prove self-healing resilience when the underlying event broker fails.
* **Execution Walkthrough:**
  1. Terminate the Redis broker Pod:
     ```bash
     kubectl delete pod -n chat-app -l app=redis
     ```
  2. Observe backend watchdog logs:
     * Nonce probe fails after 10s stale threshold.
     * Backends transition to `DEGRADED`; readiness probe returns HTTP 503.
     * Sockets terminate with close code `1011` (Internal Error); UI displays `Reconnecting`.
  3. Redis Pod restarts automatically via Deployment controller.
  4. Backends execute generational reconnection (Generation ID increments) and confirm probe nonces.
  5. Readiness probe returns HTTP 200; client connections re-establish automatically.
* **Key Talking Point:** *"The backend does not rely on simple ping commands. It uses generational nonce probes to ensure the subscriber coroutine is actively consuming events before reporting healthy."*

---

### Scenario 5: Slow Consumer Eviction & Automated 10-Minute Rollback
* **Goal:** Demonstrate backpressure isolation (code `1013`) and automated disaster recovery.
* **Execution Walkthrough:**
  1. Run the slow consumer chaos script:
     ```bash
     python tests/chaos/flood_slow_consumer.py
     ```
  2. Observe the congested client's `DeliveryQueue` saturate ($> 32$ items or $> 256\text{ KiB}$).
  3. The slow client is evicted with close code `1013` (Try Again Later). Alice and Bob continue messaging with zero latency degradation.
  4. Execute emergency rollback runbook:
     ```bash
     bash scripts/rollback.sh
     ```
  5. Show terminal timing: cluster restores the prior verified release bundle within minutes.
* **Key Talking Point:** *"A slow consumer cannot degrade the performance of neighbor sockets. Double-accounting queues enforce strict memory backpressure, and rollback restores the entire bundle in under 10 minutes."*

---

## 3. Post-Demonstration Clean Teardown

If demonstrating on AWS, execute the infrastructure destruction script immediately following the presentation:

```bash
cd infra/workload && terraform destroy -auto-approve
```
