# Architecture Decisions and Risks

**Design revision 5 — 2026-10-26. Status: selected design; implementation and verification pending.** Earlier claims of tested versions, closed account decisions and guaranteed recovery are superseded.

## Decision register

| ID | Current decision | Consequence |
| --- | --- | --- |
| ADR-01 | One EC2 K3s server/worker; local k3d | Replaces Compose baseline; host failure stops the app. |
| ADR-02 | Two backend Pods, one worker each | Demonstrates cross-process fan-out; local session state stays per Pod. |
| ADR-03 | Redis Pub/Sub, default `global_chat_channel` | At-most-once live delivery; no history/replay. |
| ADR-04 | Separate Nginx gateway and static frontend | Gateway terminates TLS and uses Kubernetes Services. |
| ADR-05 | Native HTML/CSS/JavaScript | Explicit accessible UI and safe rendering without framework requirement. |
| ADR-06 | Terraform for AWS | Reproducible intent; teardown still requires inventory verification. |
| ADR-07 | Builds and load generators off AWS node | Runtime resources remain available to K3s/application. |
| ADR-08 | Containerized tests plus k3d integration | Local parity helps; AWS network/performance need separate evidence. |
| ADR-09 | Versioned `chat.v1` protocol | Session-first ordering and strict schemas remain stable. |
| ADR-10 | One writer and bounded queue per socket | 32 events / 262144 bytes; slow readers close with 1013. |
| ADR-11 | Private health/liveness/metrics | Public gateway blocks detailed diagnostics. |
| ADR-12 | Immutable release image digests | Verify identity and config together; no floating AWS release tags. |
| ADR-13 | Kubernetes rollout and complete bundle rollback | Replaces Compose/symlink deployment; updates are not atomic. |
| ADR-14 | Measured NFR targets | 25 clients, 5 messages/s, p95<250ms, p99<1000ms; 512 MiB node headroom. |
| ADR-15 | Default-deny NetworkPolicies | Replaces Docker bridge networks; test actual enforcement and SNAT. |
| ADR-16 | API normalization and bounded retries | No NFKC; browser retries at most 10 with full jitter. |
| ADR-17 | Verify release manifest and permitted resources | Signature validity alone cannot authorize arbitrary cluster changes. |
| ADR-18 | Cosign identity verification | Configure trusted workflow/issuer independently; no blind signature acceptance. |
| ADR-19 | Private versioned S3 state with native locking | Terraform >=1.10; state remains sensitive and has its own lifecycle. |
| ADR-20 | Serialized deployment entry point and journal | CI concurrency/host lock require restricted bypass paths. |
| ADR-21 | Kubernetes is primary, K3s over EKS | Supersedes optional-kind proposal; no EKS cluster fee, but AWS usage costs remain. |

## Open implementation decisions

These are not closed merely because a candidate appears in documentation.

| ID | Required resolution | Evidence |
| --- | --- | --- |
| OPEN-01 | Supported dependencies, base images and platform versions | Locked versions/digests and compatibility/security checks. |
| OPEN-02 | Service DNS, ServiceLB/SNAT and NetworkPolicy behavior | Local and AWS positive/negative connectivity tests. |
| OPEN-03 | Real hostname, TLS issuance and renewal | Trusted browser connection and renewal rehearsal. |
| OPEN-04 | Deployer network route and credentials | Restricted SSH/API path and least-privilege RBAC tests. |
| OPEN-05 | Validated node and workload limits | Acceptance load and resource measurements. |
| OPEN-06 | State bucket bootstrap and recovery | Versioning/locking/access checks and recovery procedure. |
| OPEN-07 | GHCR visibility and pull credentials | Tested image pull, revocation and retention. |
| OPEN-08 | Actual AWS instance eligibility and credit budget | Account plan, balance/expiry, regional quote and duration. |
| OPEN-09 | Release trust policy and rollback compatibility | Wrong-signer/config rejection and full restore rehearsal. |
| OPEN-10 | Operational/teardown owner and alerts | Named owner, delivery test and scheduled end time. |
| OPEN-11 | Redis pool, buffer and heartbeat control format | Bounded settings, ACL review and generation tests. |
| OPEN-12 | ASGI denial and shutdown ordering | Real-server handshake, signal and grace-window tests. |

## Risk register

| Risk | Impact | Mitigation and residual limitation |
| --- | --- | --- |
| Node/control-plane loss | Complete outage | Rebuild/restore procedure; no multi-node HA claim. |
| Platform/application memory pressure | Evictions, slow delivery or OOM | Measured 4-GiB candidate, limits and 512-MiB headroom target; platform overhead remains. |
| Credit expiry or unexpected services | Charges or interrupted experiment | Actual account review, reserve, alerts and verified teardown; alerts are not caps. |
| Redis/subscriber outage | Lost events and unavailable sessions | Generation-aware health/recovery; no replay. |
| Bad rollout/configuration | Partial deployment | Signed bundles, journal and verified prior bundle; rollback is not atomic. |
| Secret or admin compromise | Cluster/data exposure | Restricted RBAC, mounted encrypted Secrets, revocation; node admin is trusted. |
| Incorrect policy/SNAT assumptions | Exposure or blocked ingress | Test real ServiceLB path; manifests alone prove nothing. |
| Supply-chain vulnerability | Compromised workload | Locks, scans, trusted provenance and review; signatures do not remove defects. |
| Browser injection/abuse | User impact or resource exhaustion | Inert rendering, CSP, validation and bounded queues; no authenticated abuse identity. |
| Disk/cache growth | Node failure | Log/image retention, disk monitoring and protected rollback artifacts. |
| Concurrent operator bypass | Conflicting releases | Single controlled entry point and audit; advisory locking alone is insufficient. |

## Change policy

Protocol/schema changes require API and browser compatibility review. Topology changes update Kubernetes, infrastructure, cost and test guides together. Higher performance claims require new measurements. Keep historical source discussions and old image files for provenance, but README links only to the current design.

