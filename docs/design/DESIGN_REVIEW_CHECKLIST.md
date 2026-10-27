# Design Review & Acceptance Traceability Checklist

**Status: Production Architecture Specification. Baseline: Design Revision 5. Updated: 2026-10-26.**

This document provides the authoritative engineering review gates, acceptance traceability matrices, and automated verification commands required to evaluate and approve architecture proposals, software implementations, and release artifacts for Baatchit.

---

## 1. Architectural Review Gates

Before code implementation commences or an architecture proposal is marked `Accepted`, it must satisfy all 25 criteria across five engineering disciplines:

### 1.1 Macro-Architecture & Distributed Systems
- [ ] **Boundary Separation:** Clear separation between presentation (browser/frontend), reverse proxy (gateway), application logic (backend), and message brokering (Redis).
- [ ] **Symmetric Fan-Out:** All message delivery (including sender echos) traverses the broker bus; no unmediated inter-pod or direct local-echo bypasses exist.
- [ ] **Decoupled Concurrency:** The broker subscriber loop operates asynchronously and never blocks on socket network I/O or individual slow clients.
- [ ] **Finite Failure Domains:** Explicit documentation of single points of failure (EC2 host, K3s control plane, singleton Redis) without false claims of high availability.
- [ ] **Evolutionary Alignment:** Upgrades align cleanly with Stages A through F defined in [Architecture Evolution](ARCHITECTURE_EVOLUTION.md).

### 1.2 Protocol, Schemas & State Management
- [ ] **Strict Wire Schemas:** Envelopes reject extraneous properties (`extra="forbid"`) and adhere strictly to `chat.v1` JSON contracts.
- [ ] **Input Sanitization:** Unicode NFC normalization, strict newline normalization, unprintable control code stripping, and code point bounds (1–2,000) enforced.
- [ ] **Single-Writer Pattern:** Exactly one asyncio writer task owns raw WebSocket frame transmission per active connection.
- [ ] **Double-Accounting Deques:** Outbound delivery queues strictly enforce limits on both item count ($N \le 32$) and byte volume ($B \le 256\text{ KiB}$).
- [ ] **Monotonic Token Buckets:** All rate limiters rely exclusively on monotonic time (`time.monotonic()`) to eliminate clock-skew vulnerabilities.

### 1.3 Security, Privacy & Zero-Trust Compliance
- [ ] **Default-Deny NetworkPolicies:** All inter-pod communication is blocked by default; only explicit whitelist flows (gateway $\to$ backend, backend $\to$ Redis) are permitted.
- [ ] **Private Service Isolation:** Backend (`:8000`), Redis (`:6379`), and metrics (`:8000/metrics`) ports are inaccessible from the public internet.
- [ ] **Rootless Container Execution:** Pods declare `securityContext.runAsNonRoot: true`, unprivileged UIDs, read-only root filesystems, and dropped capabilities (`drop: ["ALL"]`).
- [ ] **Redacted Logging:** Structured JSON logs strictly redact user message bodies, raw client IP addresses, and authentication credentials.
- [ ] **Secrets Management:** Redis passwords and TLS keys are mounted exclusively via Kubernetes Secret volumes; secrets never appear in container environment strings or logs.

### 1.4 Capacity, Sizing & Financial Governance
- [ ] **Formally Modeled Memory:** Resource requests and limits derived from mathematical models (accounting for OS, K3s, runtime, base heap, and per-socket buffers).
- [ ] **Headroom Floor Guaranteed:** Sizing models maintain at least $512\text{ MiB}$ free `MemAvailable` under peak steady-state load (NFR-06).
- [ ] **Linux Kernel Socket Tuning:** Sysctl parameters (`somaxconn`, `tcp_max_syn_backlog`, `tcp_tw_reuse`, `nofile`) documented and configured.
- [ ] **Hard Spending Ceiling:** Cloud infrastructure costs modeled within the $\$100$ credit boundary, maintaining at least a $\$20$ reserve.
- [ ] **Teardown Automation:** Clear procedures and schedules established to destroy cloud infrastructure upon test completion.

### 1.5 Release Engineering & Operational Resilience
- [ ] **Supply-Chain Provenance:** Container images pinned by immutable SHA-256 digests and signed via Cosign.
- [ ] **Deterministic Rollback:** Tested automated rollback procedure capable of restoring the prior release bundle within 10 minutes.
- [ ] **Coordinated Drain:** Backend handles `SIGTERM` by failing readiness immediately and executing a paced `1012` close frame drain across 10 seconds.
- [ ] **Readiness Probe Freshness:** Readiness `/health` requires an active Redis subscription and fresh probe nonce echo within 10 seconds.
- [ ] **Client Resiliency:** Browser client implements exponential backoff with full jitter, preserves unsent drafts, and caps rendered DOM nodes at 500.

---

## 2. Acceptance Criteria Traceability & Verification Runbook

Every implemented requirement must be proven through reproducible automated verification commands:

| Criterion ID | Target Requirement | Automated Verification Command / Harness | Expected Pass Output |
| :--- | :--- | :--- | :--- |
| **AC-01** | Baseline Topology Spin-Up | `kubectl get pods -n baatchit -l app.kubernetes.io/part-of=baatchit` | Exactly 5 application Pods in `Running` state (`1/1 Ready`). |
| **AC-02** | Cross-Replica Messaging | `pytest tests/e2e/test_cross_replica_fanout.py` | Client A on Pod 1 receives message from Client B on Pod 2 with matching `event_id`. |
| **AC-03** | Ingress TLS Termination | `curl -vk https://${PUBLIC_IP}/ 2>&1 \| grep 'SSL connection using'` | Valid TLS 1.2/1.3 handshake with configured cipher suite. |
| **AC-04** | Protocol Negotiation | `wscat -c wss://${PUBLIC_IP}/ws/alice -s invalid.v1` | Handshake rejected with HTTP 400 or HTTP 403. |
| **AC-05** | Redis Failure Recovery | `kubectl delete pod -n baatchit -l app=redis` | Backend transitions to 503 within 10s; recovers to 200 after Redis restarts. |
| **AC-06** | Rolling Deployment Drain | `kubectl rollout restart deployment/backend -n baatchit` | Connected clients receive close code `1012` and reconnect without dropped messages. |
| **AC-07** | Strict Wire Validation | `pytest tests/unit/test_protocol_schemas.py` | Envelopes with extra fields raise `ValidationError`. |
| **AC-08** | Digest Immutability | `kubectl get deployment backend -n baatchit -o jsonpath='{.spec.template.spec.containers[0].image}'` | Image pinned by `@sha256:...` digest, not mutable tag. |
| **AC-09** | Rollback Execution | `bash deploy/rollback.sh` | Cluster restores prior release bundle within 10 minutes. |
| **AC-10** | Slow Consumer Eviction | `python tests/chaos/flood_slow_consumer.py` | Slow client disconnected with WebSocket code `1013`; fast client unaffected. |
| **AC-11** | Clean Cloud Teardown | `terraform destroy -auto-approve` | Zero lingering billable EC2 instances, EBS volumes, or Elastic IPs. |
| **AC-12** | Input Code Point Limits | `pytest tests/unit/test_text_normalization.py` | Strings $> 2000$ code points or empty whitespace strings rejected. |
| **AC-13** | Rate Limiting Enforcement | `python tests/chaos/burst_rate_limit.py` | Inbound messages $> 5\text{ msg/s}$ throttled; socket remains open. |
| **AC-14** | NetworkPolicy Isolation | `kubectl exec -n baatchit deploy/gateway -- nc -zvw1 redis 6379` | Connection times out / rejected (exit code 1). |
| **AC-15** | Supply-Chain Signing | `cosign verify --key cosign.pub ${BACKEND_IMAGE}` | Verification successful, signature verified. |
| **AC-16** | Headroom Compliance | `ssh ec2-user@${NODE_IP} "free -m \| awk '/Mem:/ {print \$7}'"` | Available memory $\ge 512\text{ MiB}$ under 25-client steady load. |
| **AC-17** | Private Telemetry Denied | `curl -I https://${PUBLIC_IP}/metrics` | Gateway returns HTTP 403 or HTTP 404. |
| **AC-18** | Heartbeat Nonce Probing | `pytest tests/integration/test_broker_watchdog.py` | Stale nonce $> 10\text{s}$ triggers readiness probe failure. |

---

## 3. Quantitative Non-Functional Verification (NFR Matrix)

| NFR ID | Target Objective | Measurement Tool / Methodology | Verification Criterion |
| :--- | :--- | :--- | :--- |
| **NFR-01** | End-to-End Delivery Latency | Distributed WebSocket load generator (k6 / Locust): 25 clients, 5 msg/s for 30 minutes. | P95 latency $< 250\text{ ms}$; P99 latency $< 1,000\text{ ms}$. |
| **NFR-02** | Delivery Completeness | Automated message delivery auditor comparing published vs received event IDs. | $\ge 99.9\%$ expected deliveries completed within $2.0\text{ seconds}$. |
| **NFR-03** | Zero Data Corruption | SHA-256 payload checksum validation on all client receipts. | $100\%$ byte integrity match across all received frames. |
| **NFR-04** | Client Memory Cap | Browser memory profiling during 1,000-message soak test. | Rendered DOM message nodes $\le 500$; memory remains flat. |
| **NFR-05** | Handshake Latency | TCP + TLS + WebSocket upgrade round-trip latency. | P95 connection handshake completion $< 500\text{ ms}$. |
| **NFR-06** | Node Memory Headroom | Prometheus node exporter polling `node_memory_MemAvailable_bytes`. | Floor $\ge 512\text{ MiB}$ maintained at all times. |
| **NFR-07** | Pod Resource Boundaries | Kubernetes cgroup monitoring (`container_memory_working_set_bytes`). | Backend Pods stay under $256\text{ MiB}$ limit; zero OOM kills. |
| **NFR-08** | Cloud Spend Ceiling | AWS Cost Explorer API / billing telemetry. | Total gross accumulated charges $\le \$100.00$. |

---

## 4. Design Review Sign-Off Template

```markdown
### Architecture Review & Verification Record

* **Review Date:** YYYY-MM-DD
* **Proposal / ADR Reference:** PROPOSAL-XX / ADR-XX
* **Target Baseline Revision:** Design Revision 5
* **Reviewers:**
  * Technical Lead: [Name / Signature]
  * Security Reviewer: [Name / Signature]
  * Infrastructure / Cloud Owner: [Name / Signature]

#### Review Decision:
* [ ] **APPROVED WITHOUT CONDITIONS:** Architecture ready for implementation.
* [ ] **APPROVED WITH CONDITIONS:** Architecture approved subject to resolving items below.
* [ ] **REJECTED:** Architecture requires fundamental revision.

#### Mandatory Pre-Implementation Conditions:
1. _________________________________________________________________
2. _________________________________________________________________

#### Empirical Verification Results:
* **Staging Rehearsal Date:** YYYY-MM-DD
* **All AC Tests Passed:** YES / NO (Attach test output logs)
* **All NFR Targets Met:** YES / NO (Attach k6 / Prometheus benchmark report)
```
