# Release Readiness and Cryptographic Evidence Checklist

**Design Revision:** 4 (2026-10-25)  
**Document Status:** Production Verification Standard & Audit Control Gate  
**Scope:** Distributed WebSocket Chat Service (Docker Compose on AWS EC2 `t3.micro`)  
**Parent Documentation:** [Requirements Master](REQUIREMENTS.md) | [CI/CD Pipelines](CICD.md) | [Deployment Specification](DEPLOYMENT.md) | [Decisions & Risks](DECISIONS_AND_RISKS.md)

---

## 1. Governance & Verification Protocol

This document establishes the mandatory verification protocol required to promote an implementation of the distributed WebSocket chat application from local development through continuous integration to production cloud deployment and final infrastructure teardown.

Every checkbox represents an immutable gate. Items remain strictly **unchecked (`[ ]`)** until active implementation source code exists and verifiable cryptographic and diagnostic artifacts are archived in the release evidence log.

### 1.1 Acceptance Criteria Mapping Matrix

| Stage | Focus Scope | Mandatory Criteria Gates |
| :--- | :--- | :--- |
| **Gate 1: Local Engineering** | Functional distributed correctness, protocol schema, sanitization. | **AC-01**, **AC-02**, **AC-03**, **AC-04**, **AC-05**, **AC-06**, **AC-07**, **AC-12**, **AC-17** |
| **Gate 2: Candidate Pipeline** | Container builds, CVE scans, SBOMs, Cosign keyless signatures, manifests. | **AC-08**, **AC-15** |
| **Gate 3: Cloud Provisioning** | Terraform infrastructure, IMDSv2, isolated security groups, S3 locking. | **AC-10**, **AC-11** |
| **Gate 4: Production Deployment** | Advisory lock, digest pulling, in-place update, cross-messaging, rollback drill. | **AC-09**, **AC-13**, **AC-14**, **AC-16**, **AC-18** |
| **Gate 5: Clean Teardown** | Zero lingering cloud resources, cost auditing, verified state destruction. | **AC-11** |

---

## 2. Gate 1: Local Engineering & Architectural Parity

- [ ] **Dual-Replica Backend Topology (AC-01):** Docker Compose initializes exactly two independent backend replicas (`backend-1`, `backend-2`), one Redis broker, and one Nginx edge gateway (`total containers = 4`).
- [ ] **Cross-Replica Pub/Sub Fan-Out (AC-02):** Client A connected to `backend-1` transmits a message; Client B connected to `backend-2` receives the broadcast within $\le 500\text{ ms}$.
- [ ] **Zero Duplicate Deliveries (AC-03):** Neither the publisher nor subscribed peers receive duplicate frame deliveries under normal network conditions.
- [ ] **Strict Envelope Contract (AC-04):** All ingress and egress frames conform to `events-v1.schema.json` with mandatory subprotocol `Sec-WebSocket-Protocol: chat.v1`.
- [ ] **Redis Partition Resilience (AC-05):** Simulating Redis failure (`docker pause chat-app-redis`) causes `/health/readiness` to return HTTP `503` within $2.0\text{ seconds}$ and terminates WebSocket sessions with close code `1013`. Redis unpause restores readiness automatically.
- [ ] **Zero-Downtime Backend Rejuvenation (AC-06):** Recreating a backend container causes Nginx dynamic DNS resolver (`127.0.0.11`) to discover the new container IP within $5.0\text{ seconds}$ without dropping traffic routed to the surviving replica.
- [ ] **Input Sanitization & XSS Neutralization (AC-07):** Frontend renders message text exclusively via `element.textContent`; HTML tags (`<script>`, `<iframe>`) are rendered as inert text. Text length $> 500\text{ characters}$ or payload $> 4\text{ KiB}$ is rejected with close code `1008`.
- [ ] **Unicode NFKC Normalization & Trimming (AC-12):** Backend applies RFC 8259 Unicode NFKC normalization and strips leading/trailing CRLF and ASCII whitespace.
- [ ] **Slow-Consumer Backpressure & Buffer Isolation (AC-13):** Client with unconsumed outbound queue $> 128\text{ KiB}$ is terminated with close code `1008` within $1.0\text{ second}$, preserving unhindered delivery to peers.
- [ ] **Network & Redis ACL Segregation (AC-17):** Nginx gateway is physically isolated on `edge_network` and cannot open TCP sockets to Redis (`internal_data`). Redis `chat_backend` ACL user cannot execute administrative commands (`FLUSHALL`, `CONFIG`, `KEYS`).

---

## 3. Gate 2: Release Candidate Build & Supply Chain Attestation

- [ ] **Hermetic Container Builds (AC-08):** Docker images build cleanly from `Dockerfile.backend` and `Dockerfile.gateway` with zero host path dependencies.
- [ ] **Pinned Immutable Base Digests:** All `FROM` lines pin immutable multi-arch SHA-256 digests (`python:3.11.10-slim-bookworm@sha256:...`, `nginx:1.27.3-alpine-slim@sha256:...`, `redis:7.4.1-alpine3.20@sha256:...`).
- [ ] **Automated CVE Vulnerability Scanning (AC-08):** Aquasecurity Trivy scan completes with **zero** `CRITICAL` or `HIGH` vulnerabilities in application dependencies or base OS layers.
- [ ] **Cryptographic SBOM Generation:** CycloneDX JSON Software Bill of Materials generated for both backend and gateway images, detailing all installed packages and file hashes.
- [ ] **Sigstore Cosign Keyless Image Signing (AC-15):** Container images signed keylessly in GitHub Actions using ephemeral OIDC tokens tied to the trusted repository identity (`https://github.com/org/chat_app`).
- [ ] **Cryptographic Release Manifest (`release.json`) (AC-15):** Signed manifest generated containing release ID, Git commit SHA, image digests, configuration SHA-256 hashes, and schema version `2026-10-25.1`.
- [ ] **Tamper Detection Gate:** Tampering with any byte of `docker-compose.prod.yml` or `nginx.conf` causes preflight checksum validation to fail and aborts deployment.

---

## 4. Gate 3: Cloud Infrastructure & Security Hardening

- [ ] **Terraform Infrastructure Verification (AC-10):** `terraform plan` produces clean execution graph without drift. VPC, public subnet, Internet Gateway, Security Group, and EC2 instance are strictly defined.
- [ ] **State Backend Locking & Encryption:** S3 remote state bucket enforces AES256 server-side encryption, versioning, and native S3 concurrency locking (`use_lockfile = true`).
- [ ] **Strict Security Group Ingress:** Security Group allows ingress strictly on port `80` (HTTP ACME redirect), port `443` (HTTPS/WSS), and port `22` restricted to authorized deployer CIDR. Redis port `6379` has zero public ingress.
- [ ] **IMDSv2 Enforcement:** EC2 metadata options enforce `http_tokens = "required"` and `http_put_response_hop_limit = 1`, blocking SSRF credential theft.
- [ ] **Cloud-Init Bootstrap Validation:** Target EC2 host bootstraps cleanly; Docker CE 27.x and Docker Compose plugin install without interactive prompts; deployment directory layout created with strict permissions (`0700` on secrets).
- [ ] **Host Memory Headroom (NFR-04):** After cloud-init initialization, host available memory exceeds $700\text{ MiB}$ before container startup.

---

## 5. Gate 4: Production Deployment & Verification Gate

- [ ] **Linux Advisory Mutex Acquisition (`flock`):** Deployment harness locks `/home/ubuntu/chat-app/shared/deploy.lock` (fd 200). Concurrent deploy attempts exit immediately with code `75`.
- [ ] **Atomic Symlink Deployment:** Release staged in `/home/ubuntu/chat-app/releases/<RELEASE_ID>/`. Symlink `/home/ubuntu/chat-app/current` swapped atomically upon verification.
- [ ] **Container Memory Envelope (NFR-04):** Live container memory caps verified via `docker stats`:
  - `backend-1` + `backend-2`: $\le 192\text{ MiB}$ each ($\le 384\text{ MiB}$ combined).
  - `redis`: $\le 64\text{ MiB}$.
  - `gateway`: $\le 48\text{ MiB}$.
  - Total container cgroup cap: $496\text{ MiB} \le 528\text{ MiB}$. Host available RAM remains $> 256\text{ MiB}$.
- [ ] **Synthetic Integration Gate Execution (AC-14):** `scripts/verify.sh` executes against live production containers:
  - Both backend replicas return HTTP `200` with `"status":"ready"`.
  - Ingress `https://chat.example.com/health` returns HTTP `200` with `Cache-Control: no-store`.
  - Ingress `https://chat.example.com/metrics` returns HTTP `404` or `403` (segregation verified).
  - Client 1 on Backend 1 and Client 2 on Backend 2 exchange synthetic UUID message token in $< 500\text{ ms}$.
- [ ] **Automated Rollback Rehearsal ($< 10\text{ Minutes}$) (AC-09):** Automated rollback executed via `scripts/rollback.sh <PREVIOUS_RELEASE_ID>`. Reconciles previous containers, swaps symlink, and verifies health in $< 600\text{ seconds}$ (typical duration $< 60\text{ seconds}$).
- [ ] **100-Connection Load & Latency Validation (AC-16, NFR-01, NFR-02):** Headless benchmark verifies 100 concurrent WebSocket sessions across replicas with broadcast delivery latency $p_{99} \le 100\text{ ms}$.

---

## 6. Gate 5: Decommissioning & Infrastructure Teardown

- [ ] **Sanitized Log & Evidence Export:** Deployment audit log (`deploy.log`) and verification outputs exported to local audit archive without secrets or user chat content.
- [ ] **Container Teardown Script Execution:** `scripts/teardown.sh` stops all running containers, purges anonymous volumes, and prunes cached images.
- [ ] **Terraform Clean Destruction (AC-11):** `terraform destroy -auto-approve` destroys all project-created AWS resources:
  - EC2 `t3.micro` instance terminated.
  - Attached 20 GiB gp3 EBS volume deleted.
  - Security groups, Subnets, Route Tables, Internet Gateway, and VPC deleted.
- [ ] **Cloud Inventory Audit:** AWS CLI check confirms zero lingering resources:
  ```bash
  aws ec2 describe-instances --filters "Name=tag:Project,Values=chat-app" "Name=instance-state-name,Values=running,stopped"
  ```
  *Expected result:* Empty list (`[]`).
- [ ] **Billing Overrun Verification:** AWS Cost Explorer reviewed to confirm total billing remained within the planned budget envelope ($< \$0.50$ for demonstration run).

---

## 7. Cryptographic Release Evidence Record Template

The following record must be completed, signed, and committed to the deployment history upon every production promotion.

```markdown
# Release Evidence Record: [RELEASE_ID]

- **Release Identifier:** rel-20261025-143000-a1b2c3d
- **Source Commit Git SHA:** 3f8a9b2c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a
- **Timestamp (UTC):** 2026-10-25T14:35:10Z
- **Deployment Engineer:** Senior Systems Architect (@ops-lead)
- **Target Host IP / FQDN:** 54.210.88.192 / chat.example.com
- **AWS Region / Instance:** us-east-1 / t3.micro (i-0a1b2c3d4e5f67890)

### Artifact Cryptographic Identifiers
| Component | Image Tag | Immutable SHA-256 Digest | Cosign Signature Verified |
| :--- | :--- | :--- | :---: |
| Backend | ghcr.io/org/chat-backend:v1.0.0 | sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069 | [x] YES |
| Gateway | ghcr.io/org/chat-gateway:v1.0.0 | sha256:9b1a5e128d3f66c1f24d3527d76a26df85b73e51a6d0c7a82b3d11b2c4e5f6a7 | [x] YES |
| Redis | docker.io/library/redis:7.4.1-alpine3.20 | sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | [x] YES |

### Configuration & Manifest Hashes
- **release.json SHA-256:** `4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a`
- **docker-compose.prod.yml SHA-256:** `e2c0e6629938b25da112837ff4d46b8bb89252a926fa9b8cfd60f4c9c2794eb8`
- **nginx.conf SHA-256:** `a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e`

### Verification Outcomes
| Test Suite / Inspection | Expected Value | Observed Value | Gate Result |
| :--- | :--- | :--- | :---: |
| Trivy Vulnerability Scan | 0 High / 0 Critical | 0 High / 0 Critical | **PASSED** |
| Per-Replica Health (/health/readiness) | HTTP 200 / status: ready | HTTP 200 / status: ready | **PASSED** |
| Gateway Ingress Health (/health) | HTTP 200 / no-store | HTTP 200 / no-store | **PASSED** |
| Diagnostic Segregation (/metrics) | HTTP 404 / 403 at gateway | HTTP 404 Not Found | **PASSED** |
| Cross-Replica Synthetic Delivery | Latency $\le 500\text{ ms}$ | $18.4\text{ ms}$ | **PASSED** |
| Host Available Memory | $\ge 256\text{ MiB}$ | $312\text{ MiB}$ free | **PASSED** |
| Rollback Execution Drill | Duration $< 600\text{ seconds}$ | $44.2\text{ seconds}$ | **PASSED** |

### Release Sign-off
- **Release Engineer:** Approved (2026-10-25T14:40:00Z)
- **Security Auditor:** Approved (2026-10-25T14:41:15Z)
- **Status:** **PROMOTED TO PRODUCTION (VERIFIED)**
```

---
*End of Release Readiness and Cryptographic Evidence Checklist.*

