# Architecture Decision Record (ADR) Template

**Template Pack Revision 3 · 2026-10-26. Status: Unfilled Template.**

Use this template to propose, evaluate, and formally record a consequential architectural decision. Keep implementation scripts and deep-dive benchmarks in a linked Change Proposal; focus this record on the context, trade-offs, consequences, and invariants. Read the [Template Guide](README.md) for lifecycle governance rules.

---

## 1. Metadata & Decision State

| Field | Specification to Complete |
| :--- | :--- |
| **ADR Identifier & Title** | `ADR-<number>-<short-slug>` (e.g., `ADR-22-k3s-servicelb-ingress`) |
| **Decision Status** | `DRAFT` / `IN_REVIEW` / `LAST_CALL` / `ACCEPTED` / `REJECTED` / `SUPERSEDED` |
| **Delivery Status** | `NOT_STARTED` / `IN_PROGRESS` / `IMPLEMENTED` / `VERIFIED` / `RETIRED` |
| **Author(s) & Role** | [Name(s) and engineering discipline] |
| **Assigned Reviewers** | Technical Lead: `[Name]` · Security Owner: `[Name]` · Platform Owner: `[Name]` |
| **Creation Date / Decision Date** | Created: `YYYY-MM-DD` · Decided: `YYYY-MM-DD` · Last Reviewed: `YYYY-MM-DD` |
| **Baseline Architecture Revision** | Design Revision 5 (Kubernetes Baseline: local k3d + single-node AWS K3s) |
| **Target Environment** | Local k3d / AWS EC2 Mumbai `ap-south-1` / Production |
| **Related Documents** | Requirements: [`../REQUIREMENTS.md`](../REQUIREMENTS.md) · HLD: [`HLD.md`](HLD.md) · LLD: [`LLD.md`](LLD.md) |
| **Supersedes / Superseded By** | Supersedes: `[None or ADR-XX]` · Superseded by: `[None or ADR-YY]` |
| **Mandatory Revisit Trigger** | [Observable metric or event triggering formal review] |

---

## 2. Executive Decision Statement

> **Context:** In the context of [business problem, system constraint, or architectural driver],
> **We Decided:** We chose [specific architectural option, protocol, or design invariant],
> **To Achieve:** To deliver [primary measurable benefit, latency SLA, or security guarantee],
> **Accepting:** While accepting [acknowledged trade-off, single point of failure, or operational limitation],
> **Revisit When:** We will formally re-evaluate this decision if [quantitative threshold or product requirement occurs].

---

## 3. Context, Problem Statement & Decision Drivers

Provide a concrete, quantifiable description of the problem necessitating this decision. Avoid vague statements; include measured bottlenecks, user impacts, and technical limitations.

### 3.1 Architectural Decision Drivers (ADD)
| Driver ID | Category | Mandatory Constraint or Desired Outcome | Priority | Source & Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **DR-01** | Correctness | E.g., Eliminate frame interleaving on concurrent writes. | High / P0 | [LLD.md](LLD.md) (Single-Writer Principle) |
| **DR-02** | Reliability | E.g., Prevent slow network receivers from exhausting Pod memory. | High / P0 | [REQUIREMENTS.md](../REQUIREMENTS.md) (NFR-06 / FR-15) |
| **DR-03** | Financial | E.g., Operate within the strict $100 AWS credit demo budget. | High / P0 | [AWS_FREE_TIER_REQUIREMENTS.md](../AWS_FREE_TIER_REQUIREMENTS.md) |
| **DR-04** | Performance | E.g., Maintain end-to-end delivery latency p95 < 250 ms. | Medium / P1 | [REQUIREMENTS.md](../REQUIREMENTS.md) (NFR-01) |

### 3.2 Formal Assumptions & Risk Disclosures
| Assumption ID | Statement of Assumption | Validation Methodology | Owner & Due Date | Consequence if Invalidated |
| :--- | :--- | :--- | :--- | :--- |
| **AS-01** | E.g., K3s ServiceLB source NAT does not break origin checking. | Empirical k3d / AWS curl test. | Platform Owner / Due: `YYYY-MM-DD` | Handshakes rejected; require host-port binding. |
| **AS-02** | E.g., Single-node memory headroom remains >= 512 MiB. | Prometheus load benchmark. | Test Owner / Due: `YYYY-MM-DD` | Pod evictions; instance resize required. |

---

## 4. Evaluated Options & Multi-Criteria Decision Analysis (MCDA)

Document all viable architectural candidates, including retaining the baseline.

| Candidate Option | Macro-Architecture & Mechanics | Key Advantages | Acknowledged Drawbacks & Vulnerabilities | Est. Monthly Cost (Gross) | Decision Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Option 1: [Baseline]** | Retain current architecture as specified. | Zero migration risk; zero extra operational effort. | Cannot satisfy Driver DR-XX; bottleneck persists. | $0.00 incremental | Rejected |
| **Option 2: [Selected Candidate]** | E.g., Deploy K3s ServiceLB on node ports 80/443. | Eliminates $25/mo AWS ALB fee; zero external controller. | Single node failure domain; requires host port ownership. | $0.00 incremental | **ACCEPTED** |
| **Option 3: [Alternative Candidate]** | E.g., Provision AWS Network Load Balancer (NLB). | High availability across AZs; preserves client IP. | Incurs ~$18/month hourly fee; exceeds $100 budget. | +$18.00 / month | Rejected (Cost) |

### Weighted Scoring Matrix (Scale 1–5, Higher is Better)
| Evaluation Criteria | Weight | Option 1 (Baseline) | Option 2 (Selected) | Option 3 (Alternative) |
| :--- | :---: | :---: | :---: | :---: |
| **Correctness & Robustness** | 30% | 3 (0.90) | 5 (1.50) | 4 (1.20) |
| **Operational Simplicity** | 25% | 4 (1.00) | 4 (1.00) | 2 (0.50) |
| **Cost & Free Tier Compliance** | 25% | 5 (1.25) | 5 (1.25) | 1 (0.25) |
| **Performance & Latency** | 20% | 2 (0.40) | 4 (0.80) | 5 (1.00) |
| **Weighted Total Score** | **100%** | **3.55** | **4.55** | **2.95** |

---

## 5. Architectural Decision Specification & Boundaries

### 5.1 Concrete Technical Invariants
Describe the exact mechanism, class contracts, or manifest definitions enforcing this decision:
1. **Invariant 1:** [E.g., Inbound client frames must never bypass the validation pipeline in `validation.py`.]
2. **Invariant 2:** [E.g., All WebSocket connections must negotiate `Sec-WebSocket-Protocol: chat.v1`.]
3. **Invariant 3:** [E.g., Memory queues must strictly reject additions when total pending bytes exceed 262,144.]

### 5.2 Explicit System Non-Goals & Exclusions
* [E.g., This decision does NOT provide multi-region replication or durable message persistence.]
* [E.g., This decision does NOT authenticate user identities or guarantee uniqueness of display names.]

---

## 6. Consequences, Trade-offs & Residual Risks

### 6.1 Positive Consequences (Benefits Delivered)
* **Performance:** [E.g., P95 broadcast delivery latency reduced from 350 ms to 130 ms.]
* **Stability:** [E.g., Memory footprint bounded at 256 KiB per session, eliminating OOM crash risks.]
* **Security:** [E.g., Zero public exposure of Redis port 6379 via default-deny NetworkPolicies.]

### 6.2 Negative Consequences & Accepted Technical Debt
* **Operational Complexity:** [E.g., Requires operators to maintain K3s ServiceLB host port bindings.]
* **Failure Boundaries:** [E.g., Single EC2 host remains a single point of failure (SPOF).]

### 6.3 STRIDE Threat Model Assessment
| STRIDE Category | Threat Vector | Mitigation Mechanism | Residual Risk / Review Owner |
| :--- | :--- | :--- | :--- |
| **Spoofing** | E.g., User impersonation via crafted headers. | Gateway sanitizes `X-Forwarded-*`; backend checks Origin. | Anonymous app: display names non-authoritative. |
| **Tampering** | E.g., In-flight payload modification. | Mandatory TLS 1.2/1.3 termination at gateway. | Zero risk outside compromised client host. |
| **Repudiation** | E.g., Denying message publication. | Immutable event IDs, server UTC timestamps, container IDs. | Accepted: no durable audit log in baseline. |
| **Information Disclosure** | E.g., Public telemetry scraping. | Gateway routes block `/metrics` and `/live` externally. | Internal cluster network assumed trusted. |
| **Denial of Service** | E.g., WebSocket queue memory flooding. | Double-accounting bounded deques; eviction code `1013`. | Client throttled without neighbor impact. |
| **Elevation of Privilege** | E.g., Container escape to host node. | Rootless Pod execution; read-only root filesystems. | Linux kernel vulnerability residual risk. |

---

## 7. Capacity, Performance & Financial Modeling

### 7.1 Quantitative Mathematical Impact
* **Memory Formula Impact:** [Show change to $M_{\text{node}}$ equation from [Capacity Planning](../CAPACITY_PLANNING.md)]
* **CPU / Event Loop Impact:** [Quantify estimated microseconds per frame]
* **Network Egress Impact:** [Quantify kilobits/sec under peak concurrent connections]

### 7.2 Financial & Cloud Budget Ledger
| Resource Item | Baseline Gross Monthly Cost | Post-Decision Gross Cost | Incremental Variance | Covered by AWS Credits? |
| :--- | :--- | :--- | :--- | :--- |
| **EC2 Compute** | $34.27 | $34.27 | $0.00 | Yes (Free Tier / Credits) |
| **Load Balancer (ALB)** | $0.00 | $0.00 | $0.00 (ServiceLB used) | Yes (Zero Cost) |
| **EBS Storage (gp3)** | $1.92 | $1.92 | $0.00 | Yes (Credits) |
| **Public IPv4 Address** | $3.60 | $3.60 | $0.00 | Yes (Credits) |
| **Total Monthly Spend** | **$39.79** | **$39.79** | **$0.00** | **Fully within $100 Budget** |

---

## 8. Compatibility, Migration & Rollback Strategy

### 8.1 Wire & Schema Compatibility
* **Backward Compatibility:** [Can legacy clients communicate with the updated server?]
* **Forward Compatibility:** [Can updated clients communicate with legacy backend replicas?]
* **Strict Schema Enforcing:** [Does the Pydantic schema reject unexpected properties?]

### 8.2 Rollback Feasibility & Safety Window
| Rollback Dimension | Feasibility Assessment |
| :--- | :--- |
| **Reversibility Class** | `FULLY_REVERSIBLE` (Stateless in-memory application) |
| **Safe Rollback Window** | Indefinite (No durable database schema migrations to unwind) |
| **Rollback Execution Method** | Automated re-apply of previous verified release bundle: `kubectl apply -f release-manifest-previous.yaml` |
| **Data Loss on Rollback** | Transient in-flight WebSocket connections disconnected; reconnect with backoff. |

---

## 9. Verification & Acceptance Traceability Contract

| Evidence ID | Traceable Requirement / AC | Automated Verification Harness / Script | Acceptance Criteria / Expected Outcome | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **EV-01** | AC-01 (Topology) | `kubectl get pods -n baatchit` | 5 application Pods in `1/1 Ready` state. | `PENDING` |
| **EV-02** | AC-02 (Messaging) | `pytest tests/e2e/test_fanout.py` | Cross-replica messages received in $< 250\text{ ms}$. | `PENDING` |
| **EV-03** | NFR-06 (Headroom) | Prometheus `node_memory_MemAvailable_bytes` | MemAvailable $\ge 512\text{ MiB}$ sustained. | `PENDING` |
| **EV-04** | AC-14 (Isolation) | NetworkPolicy verification script | Direct gateway $\to$ Redis TCP connection fails. | `PENDING` |

---

## 10. Open Questions & Implementation Obligations

| Item ID | Question or Implementation Task | Responsible Owner | Target Milestone | Resolution / Evidence Link |
| :--- | :--- | :--- | :--- | :--- |
| **OQ-01** | Verify K3s Flannel VXLAN MTU on AWS EC2. | Platform Engineer | Pre-Production | `docs/design/EVIDENCE-01.md` |
| **OQ-02** | Benchmark single-worker Uvicorn latency at 64 connections. | Backend Engineer | Staging Rehearsal | `docs/design/BENCHMARK-02.md` |

---

## 11. Review Outcome, Consensus & Recorded Dissent

### 11.1 Review Outcomes
* **Technical Lead Review:** `APPROVED` / `REJECTED` — [Name] (`YYYY-MM-DD`)
* **Security Architecture Review:** `APPROVED` / `REJECTED` — [Name] (`YYYY-MM-DD`)
* **Infrastructure / Cloud Review:** `APPROVED` / `REJECTED` — [Name] (`YYYY-MM-DD`)

### 11.2 Recorded Minority Opinions / Dissent
* *Dissenting Position:* [Record any dissenting viewpoints or alternative arguments raised during review.]
* *Resolution / Counter-Argument:* [Explain why the consensus choice was accepted despite the noted objection.]

---

## 12. Lifecycle Triggers & Revisit Conditions

This ADR must be formally reopened and reconsidered upon the occurrence of any of the following events:
1. **Workload Breach:** Concurrent active connections exceed $128$ sockets (triggering Stage B evolution).
2. **Availability Mandate:** Product requirement mandates multi-AZ $99.99\%$ SLA (triggering Stage D evolution).
3. **Budget Exhaustion:** AWS credit allocation expires or recurring monthly bill exceeds $\$50.00$.
4. **Security Vulnerability:** Critical CVE discovered in core dependency requiring architectural replacement.

---

## 13. Revision History & Audit Trail

| Date | Revision | Author | Description of Changes / Git Commit |
| :--- | :---: | :--- | :--- |
| `YYYY-MM-DD` | `v1.0.0` | `[Author Name]` | Initial formal proposal submitted for review. |
