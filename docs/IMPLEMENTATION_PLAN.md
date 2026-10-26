# Implementation Plan

**Status:** Future execution roadmap. All checkboxes begin unchecked until verified by test artifacts. See the [documentation index](../README.md).

**Design Revision 4 (2026-10-25):** Step-by-step engineering roadmap with granular sub-tasks, automated verification commands, and verifiable Definition of Done (DoD) gates.

---

## Phase 0: Architecture Confirmation & Contract Finalization

- [ ] **Contract Schema Review:** Freeze `events-v1.schema.json` and `release-v1.schema.json`.
- [ ] **Dependency Baseline Lock:** Confirm pinned versions in [TECHNOLOGIES.md](TECHNOLOGIES.md) (Python 3.11.10, FastAPI 0.115.4, Uvicorn 0.32.0, Nginx 1.27.3, Redis 7.4).
- [ ] **Risk Register Alignment:** Confirm resolution deadlines for OPEN-01 through OPEN-10 in [DECISIONS_AND_RISKS.md](DECISIONS_AND_RISKS.md).
- [ ] **Origin & Domain Boundary:** Record explicit local origin (`http://localhost`) and public production hostname (`chat.example.com`).
- [ ] **Resource Envelope Confirmation:** Confirm memory ceilings (192 MiB backend, 64 MiB Redis, 48 MiB gateway, 32 MiB frontend).

**Verification Command:**
```bash
# Validate JSON schemas against Draft 2020-12
check-jsonschema --schemafile schemas/events-v1.schema.json tests/fixtures/events/*.json
```
**Exit Gate (DoD):** All schemas pass validation; zero unresolved P0/P1 design blockers.

---

## Phase 1: Backend Core Implementation & Containerized Unit Tests

- [ ] **Pydantic Settings:** Implement `backend/app/settings.py` with strict regex and range validators.
- [ ] **Protocol Envelopes & Normalization:** Implement `backend/app/protocol.py` with CRLF normalization, boundary whitespace trimming, code point counting, and UUIDv4 event ID generator.
- [ ] **Token Bucket & Admission Control:** Implement `backend/app/limits.py` with monotonic clock token buckets for socket rate limits and replica-wide publication limits.
- [ ] **Connection Manager:** Implement `backend/app/manager.py` with `ClientSession` paired tasks (`SocketReaderTask`, `SocketWriterTask`) and bounded queues (32 events / 256 KiB).
- [ ] **Redis Bus Adapter:** Implement `backend/app/messaging.py` using `redis.asyncio` with subscriber iteration and generation-nonce heartbeats.
- [ ] **Dependency Supervisor & Lifespan:** Implement `backend/app/lifecycle.py` with startup checks, periodic heartbeats, `/health` and `/live` endpoints, and SIGTERM drain handler.
- [ ] **ASGI App Factory:** Implement `backend/app/main.py` assembling routers, denial-response origin checks, and `/metrics` OpenMetrics endpoint.
- [ ] **Multi-stage Backend Dockerfile:** Create `backend/Dockerfile` with builder and unprivileged runtime stages (`UID 10001`).

**Verification Commands:**
```bash
# Execute unit tests inside ephemeral test container
docker build -t chatapp-backend:test --target builder backend/
docker run --rm chatapp-backend:test pytest tests/unit -v --cov=app
```
**Exit Gate (DoD):** Unit test suite achieves $\ge 90\%$ branch coverage; all Unicode normalization fixtures pass; connection slots and tasks clean up deterministically on test disconnect.

---

## Phase 2: Accessible Vanilla Frontend Implementation

- [ ] **Accessible HTML5 Shell:** Create `frontend/index.html` with semantic structure, ARIA live regions, labels, and zero inline scripts/styles (pure CSP compliance).
- [ ] **Modern Responsive CSS:** Create `frontend/assets/styles.css` with CSS custom properties, accessible dark mode, micro-animations, and fluid layout.
- [ ] **Frontend State Machine:** Implement `frontend/assets/app.js` with five unambiguous states (`CONNECTING`, `CONNECTED`, `RECONNECTING`, `PAUSED`, `POLICY_ERROR`).
- [ ] **Safe DOM Renderer:** Implement `SafeDOM` module in `app.js` using `document.createElement()` and `textContent` (strictly zero `innerHTML`).
- [ ] **Jittered Backoff & Reconnect:** Implement full-jitter exponential backoff timer ($0 \text{ to } \min(30, 2^{\text{attempt}})$), pausing after 10 attempts.
- [ ] **DOM Message Pruning:** Implement ring buffer pruning maintaining at most 500 message nodes in the chat scrollback.
- [ ] **Frontend Dockerfile:** Create `frontend/Dockerfile` using `nginx:1.27.3-alpine` unprivileged mode.

**Verification Commands:**
```bash
# Lint frontend assets and verify CSP compliance
htmlhint frontend/index.html
eslint frontend/assets/app.js
```
**Exit Gate (DoD):** Synthetic XSS payload strings render as inert text; keyboard navigation operates cleanly without mouse input; disconnect backoff matches mathematical jitter curve.

---

## Phase 3: Multi-Container Networking & Cross-Replica Integration

- [ ] **Compose Configurations:** Create `docker-compose.yml`, `docker-compose.test.yml`, and `docker-compose.prod.yml`.
- [ ] **Network Segmentation:** Configure `edge_network` (bridge) and `data_network` (internal bridge, blocking egress).
- [ ] **Redis Configuration & ACLs:** Create `redis/redis.conf` (persistence disabled, 64MB cap) and `redis/users.acl`.
- [ ] **Nginx Dynamic Gateway:** Create `nginx/nginx.conf` with dynamic upstream resolution (`resolver 127.0.0.11 valid=5s`), rate limiting, and security headers.
- [ ] **Cross-Replica Messaging Test:** Execute automated pytest scenario verifying Client A (Replica 1) and Client B (Replica 2) exchange messages via Redis.
- [ ] **Slow Consumer Isolation Test:** Inject a non-reading WebSocket client; verify that outbound queue overflows (32 events) and triggers close code 1013 without delaying neighbor sockets.
- [ ] **Network Isolation Verification:** Prove that `curl` from inside `frontend` or `gateway` container to `redis:6379` fails with network unreachable.

**Verification Commands:**
```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml up -d --scale backend=2 --wait
docker compose -f docker-compose.test.yml run --rm test-runner pytest tests/integration -v
docker compose down
```
**Exit Gate (DoD):** AC-01 through AC-07, AC-12, AC-13, AC-14, and AC-17 pass with zero failures.

---

## Phase 4: AWS Infrastructure as Code (Terraform)

- [ ] **VPC & Subnet Topology:** Define VPC (`10.0.0.0/16`), public subnet (`10.0.1.0/24`), IGW, and route table in `terraform/main.tf`.
- [ ] **Security Group Hardening:** Enforce strict ingress (ports 80/443 public, port 22 restricted to explicit operator CIDR; backend/Redis ports closed).
- [ ] **EC2 Instance & EBS gp3:** Declare `t3.micro` instance with encrypted 20 GB `gp3` root volume and IMDSv2 enforced (`http_tokens = "required"`).
- [ ] **Cloud-Init Bootstrap Script:** Create `terraform/user_data.sh` installing Docker Engine, Compose v2, and configuring log rotation.
- [ ] **Remote State & Locking:** Configure S3 backend with native state locking (`use_lockfile = true`) in `terraform/main.tf`.
- [ ] **Outputs & Documentation:** Expose `public_ip`, `ssh_connection_string`, and `health_check_url`.

**Verification Commands:**
```bash
cd terraform/
terraform fmt -check
terraform validate
tflint
terraform plan -out=chat.plan
```
**Exit Gate (DoD):** `terraform plan` executes cleanly with zero syntax/lint warnings; security group rules verify strict port isolation.

---

## Phase 5: Secure CI/CD Automation & Supply Chain Provenance

- [ ] **PR Validation Pipeline (`test.yml`):** Run unit tests, contract checks, and Compose validation on pull requests.
- [ ] **Build & Scan Pipeline (`build.yml`):** Build multi-stage OCI images for `linux/amd64`; run Trivy vulnerability scanner (fail on High/Critical CVEs with fixes).
- [ ] **SBOM Generation & Attestation:** Generate CycloneDX SBOM; attach Cosign keyless signatures via GitHub Actions OIDC identity.
- [ ] **Release Packaging Script (`scripts/package-release.sh`):** Generate cryptographically verified `release.json` containing image SHA-256 digests and config hashes.
- [ ] **Atomic Deployment Script (`scripts/deploy.sh`):** Implement host-side file locking (`flock`), release directory staging (`releases/<release_id>`), atomic symlink swap (`current`), and automatic rollback.

**Verification Commands:**
```bash
act pull_request -W .github/workflows/test.yml
bash scripts/package-release.sh --dry-run
```
**Exit Gate (DoD):** Passing CI run produces signed container digests, validated `release.json`, and zero High/Critical CVEs.

---

## Phase 6: Public Deployment, Load Verification & Teardown

- [ ] **Host Bootstrap Execution:** Run `terraform apply` to provision EC2; wait for cloud-init completion.
- [ ] **TLS Certificate Issuance:** Provision Let's Encrypt certificate via Certbot for `chat.example.com`.
- [ ] **First Release Deployment:** Execute `scripts/deploy.sh` to stage release `current`; verify two healthy backend replicas.
- [ ] **Baseline Performance Benchmark (NFR-01 to NFR-08):** Execute external load generator (25 clients, 5 msg/s, 30 minutes); capture latency percentiles (p95 < 250ms).
- [ ] **Disaster Recovery & Rollback Drill:** Trigger synthetic deployment failure; verify automatic rollback to prior release within 10 minutes (AC-09).
- [ ] **Clean Infrastructure Teardown:** Execute `terraform destroy`; verify zero remaining AWS billable resources (AC-11).

**Verification Commands:**
```bash
# Run baseline load experiment from external node
k6 run tests/load/baseline.js --env TARGET_URL=wss://chat.example.com/ws
terraform destroy -auto-approve
```
**Exit Gate (DoD):** All acceptance criteria (AC-01 through AC-18) validated with empirical evidence artifacts; cloud infrastructure cleanly destroyed.

---

## Related Guides

[Requirements](REQUIREMENTS.md) | [Architecture](ARCHITECTURE.md) | [Development](DEVELOPMENT.md) | [Testing](TESTING.md) | [Deployment](DEPLOYMENT.md)

