# Architecture Decisions, Open Items & Risk Register

**Design Revision 5 — 2026-10-26. Status: Authoritative Decision & Risk Ledger.** This document records the architectural decision register (ADR-01 to ADR-21), unresolved implementation items (OPEN-01 to OPEN-12), and the system risk register for Chat App.

---

## 1. Architectural Decision Register (ADR-01 to ADR-21)

| ADR ID | Decision Title | Architectural Choice & Boundary | Key Drivers & Justification | Trade-offs & Accepted Limitations |
| :--- | :--- | :--- | :--- | :--- |
| **ADR-01** | Orchestration Substrate | Deploy K3s Kubernetes on single EC2 node; local k3d. | Eliminates $73/mo EKS fee; provides native declarative manifests. | Host node remains a single point of failure (SPOF). |
| **ADR-02** | Multi-Replica Backend | Run 2 FastAPI backend Pods with 1 Uvicorn worker each. | Proves cross-process fan-out; eliminates multi-thread GIL contention. | Does not provide host-level high availability. |
| **ADR-03** | Ephemeral Broker | Redis 7 in-memory Pub/Sub via `global_chat_channel`. | Lightweight memory ($< 35\text{ MiB}$); sub-millisecond event dispatch. | At-most-once delivery; zero message replay after disconnect. |
| **ADR-04** | Ingress & Reverse Proxy | Nginx Gateway terminates TLS and proxies WebSockets. | Centralized TLS termination; isolates backend from public internet. | Singleton gateway is a single point of failure in baseline. |
| **ADR-05** | Native Presentation | Semantic HTML5, CSS3, native Vanilla ES6 JavaScript. | Zero build steps; zero external CDNs; eliminates XSS via `textContent`. | Manual DOM state management without framework abstractions. |
| **ADR-06** | Infrastructure as Code | Terraform 1.10+ with AWS Provider and S3 backend. | Declarative cloud management; native S3 locking (`use_lockfile`). | Requires manual verification of destroyed residual assets. |
| **ADR-07** | Off-Node Builds & Tests | Image builds and load generators run off the AWS node. | Conserves 2-vCPU / 4-GiB resources strictly for runtime workloads. | Requires developer workstation or external CI runner. |
| **ADR-08** | Testing Parity | Local testing via k3d; automated Playwright browser tests. | Matches production Kubernetes API locally without cloud charges. | Docker networking differs from AWS EC2 public WAN routing. |
| **ADR-09** | Wire Protocol Standard | Versioned `chat.v1` protocol; plain text client frames. | Enforces strict discriminated schemas; prevents client tampering. | Incompatible with unversioned legacy chat clients. |
| **ADR-10** | Single-Writer & Queues | Exactly one asyncio writer task per socket; bounded deques. | Eliminates concurrent socket writes; isolates slow consumers (`1013`). | Queued events dropped when buffer limits are breached. |
| **ADR-11** | Private Telemetry | Cluster-private `/metrics`, `/health`, and `/live`. | Protects internal operational metrics and infrastructure details. | Requires authorized port-forwarding or private scrapers. |
| **ADR-12** | Immutable Image Digests | Pinned `@sha256:...` digests in all Kubernetes manifests. | Guarantees build immutability; eliminates mutable tag drift. | Requires automated tooling to update digests in manifests. |
| **ADR-13** | Deployment Strategy | Rolling update (`maxSurge: 0`, `maxUnavailable: 1`). | Prevents memory spikes on 4-GiB host; clean connection drain (`1012`). | Brief capacity reduction during single-replica replacement. |
| **ADR-14** | Acceptance Targets | 25 clients, 5 msg/s, p95 $< 250\text{ ms}$, $\ge 512\text{ MiB}$ headroom. | Realistic, verifiable benchmarks for resource-constrained demo. | Higher concurrency targets require multi-node cluster (Stage C). |
| **ADR-15** | Zero-Trust Network | Default-deny Kubernetes `NetworkPolicies` cluster-wide. | Enforces least-privilege packet routing; isolates Redis. | Requires maintaining explicit ingress/egress policy manifests. |
| **ADR-16** | Input Normalization | Unicode NFC, newline conversion, boundary trimming, 2000 code points. | Eliminates Unicode spoofing and oversized payloads without NFKC. | Non-ASCII control codes rejected. |
| **ADR-17** | Supply Chain Gate | Cosign image signing; Syft SBOM; Trivy CVE gating. | Enforces SLSA Level 3 supply-chain integrity. | Build pipeline fails if base images contain unfixed CVEs. |
| **ADR-18** | Host Port Ingress | K3s ServiceLB binds host ports 80/443 directly. | Eliminates AWS Application Load Balancer control-plane costs. | Host ports cannot be shared with other host services. |
| **ADR-19** | Remote State Locking | Native S3 locking with `use_lockfile = true`. | Eliminates DynamoDB billable table provisioning. | Requires Terraform 1.10 or newer. |
| **ADR-20** | Secret File Mounts | Credentials mounted exclusively via Secret volumes (`REDIS_URL_FILE`). | Prevents secret exposure in process tables and environment strings. | Requires application file-reading logic at startup. |
| **ADR-21** | Instance Selection | Evaluate EC2 `c7i-flex.large` (2 vCPU / 4 GiB candidate). | Newer-account Free Tier eligible; ample memory for K3s + workloads. | Regional availability and account eligibility must be verified. |

---

## 2. Open Implementation Decisions Register (OPEN-01 to OPEN-12)

| Open ID | Technical Concern | Validation Methodology | Target Milestone | Assigned Owner |
| :--- | :--- | :--- | :--- | :--- |
| **OPEN-01** | Dependency Version Locks | Generate cryptographic hashes in `requirements.lock`. | Phase 0 | Backend Lead |
| **OPEN-02** | K3s ServiceLB SNAT & Origin | Verify client IP preservation and Origin header in k3d. | Phase 3 | Platform Lead |
| **OPEN-03** | Let's Encrypt Automated TLS | Test cert-manager DNS-01 / HTTP-01 challenge on AWS. | Phase 5 | Security Lead |
| **OPEN-04** | Deployer CI/CD Network Route | Configure runner egress CIDR or operator bastion access. | Phase 4 | DevOps Lead |
| **OPEN-05** | Measured Node Memory Usage | Measure baseline memory under 25-client soak test. | Phase 6 | Test Lead |
| **OPEN-06** | S3 State Bucket Bootstrap | Run `infra/bootstrap-state/` and test state locking. | Phase 5 | Cloud Lead |
| **OPEN-07** | GHCR Private Image Secrets | Verify `imagePullSecrets` rotation and admission. | Phase 4 | DevOps Lead |
| **OPEN-08** | Actual AWS Credit Verification | Audit AWS Billing Console for $100 credit entitlement. | Phase 5 | Financial Owner |
| **OPEN-09** | 10-Minute Rollback Script | Rehearse `scripts/rollback.sh` in local k3d. | Phase 4 | DevOps Lead |
| **OPEN-10** | AWS Cost Alert Destination | Subscribe verified operator email to SNS billing topic. | Phase 5 | Operations Lead |
| **OPEN-11** | Redis Pub/Sub Buffer Tuning | Stress-test slow consumers against 32MB output buffer. | Phase 1 | Backend Lead |
| **OPEN-12** | ASGI WebSocket Denial Testing | Verify Starlette HTTP 403 pre-upgrade rejection. | Phase 1 | Backend Lead |

---

## 3. Comprehensive Risk Register & Mitigations

| Risk ID | Risk Category | Risk Description & Potential Impact | Probability | Impact | Mitigation Mechanism & Operational Boundary |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **RSK-01** | Reliability | Single EC2 host failure causes complete cluster outage. | Medium | Critical | Automated Terraform re-provisioning; evolution roadmap defines Multi-AZ HA (Stage D). |
| **RSK-02** | Capacity | Memory leak in AsyncIO queues breaches 512 MiB node headroom floor. | Medium | High | Double-accounting deques ($N \le 32$, $B \le 256\text{ KiB}$); cgroup limit caps; automated eviction. |
| **RSK-03** | Financial | Runaway cloud charges exceed $100 credit allocation. | Low | High | Minimal resource set (\$39.79/mo gross); AWS Budgets alerts at 50%, 75%, 90%; mandatory reserve. |
| **RSK-04** | Messaging | Redis broker failure causes silent message loss. | Low | Medium | Generational nonce watchdog prober fails readiness within 10s; clients disconnect and back off. |
| **RSK-05** | Delivery | Bad container release introduces syntax error or regression. | Low | High | Cryptographically signed release bundles; automated 10-minute rollback runbook (`rollback.sh`). |
| **RSK-06** | Security | Malicious user injects XSS payloads into public chat. | High | High | Strict `textContent` DOM rendering; zero `innerHTML`; Content Security Policy headers. |
| **RSK-07** | Network | Unintended public exposure of Redis or internal metrics. | Low | Critical | Default-deny Kubernetes `NetworkPolicies`; security group blocks ports 6379, 8000, 6443 publicly. |
| **RSK-08** | Supply Chain | Compromised third-party dependency introduces backdoor. | Low | Critical | Pinned hash lockfiles; Trivy CVE scans gate build; Cosign cryptographic signatures. |
