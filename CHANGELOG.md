# Changelog

This file records actual repository changes. Planned application features remain in the [implementation plan](docs/IMPLEMENTATION_PLAN.md) until they are implemented and verified.

## Unreleased

### Baatchit project identity — 2026-10-27

- Renamed the app to Baatchit across the browser title, wordmark, favicon, package metadata, guides, diagrams, infrastructure names, scripts and test references.
- Updated the README, local cluster/namespace/context, image names and release prefix consistently; kept the existing GitHub repository URL and signing identity valid.
- Added environment migration notes and refreshed the architecture images using built-in imagegen with name-only edits.

### Runnable application and deployment tooling — 2026-10-27

- Implemented the FastAPI/Redis chat backend, responsive browser UI and Nginx gateway with the chat.v1 contract, bounded queues/rates, reconnect behavior, dependency readiness and signal draining.
- Added container builds, hash-locked dependencies, k3d/K3s manifests, restricted containers, paired Redis Secrets and tested network isolation.
- Added Terraform roots, validation/release/deployment workflows, signed bundle checks, SBOM/scan gates and previous-release restoration tooling.
- Added unit, JavaScript, real-container, browser, smoke and load checks. Local 25-client short-run results are recorded in `docs/IMPLEMENTATION_STATUS.md`.
- Updated the README and operational guides with working commands. AWS provisioning, remote release execution and cloud acceptance remain pending.

### Expanded architecture templates — 2026-10-26

- Expanded the change proposal with evidence, scope/invariants, HLD/LLD interfaces, compatibility matrices, capacity, failure analysis, security, costs, observability, migration and recovery worksheets.
- Expanded the ADR with decision drivers, alternatives, assumptions, residual risks, adoption/reversal, verification obligations, review outcomes and supersession history.
- Added a template usage guide covering document selection, copying/link repair, status conventions and an explicitly unverified example; updated the design handbook index. No implementation or architecture decision was made by these template changes.

### System design handbook — 2026-10-26

- Added `docs/design/` with HLD, LLD, sequence diagrams, data/protocol design, capacity calculations, staged architecture evolution, migration guidance and review traceability.
- Added reusable architecture change proposal and ADR templates; linked the handbook from the README and architecture guide.
- Aligned backend module names with the planned source layout and clarified private health routing. Future scaling options remain proposals; no runtime implementation or infrastructure was added.

### Kubernetes design migration — 2026-10-26

- Promoted Kubernetes to the primary design: local k3d and single-node AWS K3s with containerd.
- Replaced Compose deployment, network, configuration and rollback instructions with Kubernetes contracts; retained the chat.v1 protocol.
- Updated sizing to a measured 2-vCPU/4-GiB candidate, account-specific AWS eligibility and a $100 credit worksheet with a proposed reserve.
- Reconciled acceptance limits, security boundaries, implementation gates and operational procedures; no runtime or AWS resources were created.
- Added the K3s architecture image and generation prompt; earlier images remain historical.


### Added

- Initial optional Kubernetes guide and credit worksheet (2026-10-26), superseded by the primary K3s design above.
- Dedicated frontend/UI/UX and backend engineering guides, with technology choices, interaction contracts, module responsibilities, security, testing and handoff requirements (2026-10-26).
- AWS Free Tier requirements guide with account-specific eligibility, resource prerequisites, cost controls and teardown checks; corrected the infrastructure cost assumptions (2026-10-26).
- Technology overview describing the stack and original version references.
- Requirements, architecture, API contract and intended project structure.
- Implementation milestones, configuration reference and local development guide.
- Testing, security, infrastructure and CI/CD plans.
- Deployment, rollback, operations, troubleshooting and decision/risk guides.
- Contribution guidance, release checklist and future demonstration guide.
- README links providing one entry point to the project documentation.

### Updated - 2026-10-26

- Reorganized the README with a clear project status, architecture diagram, planned stack, reading paths, grouped documentation index and implementation roadmap.
- Added an AWS architecture illustration for the planned Mumbai-region single-host deployment.
- Refined the architecture illustration with security-group rules, explicit Docker network membership, EC2/EBS details and independent Terraform provisioning/state connections; retained the original image and saved the generation prompt.
- Featured the updated AWS architecture image near the top of the README with an accessible description and a full-size link.
- Corrected README capability and capacity wording to distinguish proposed design from verified implementation and align the candidate workload with the requirements.

### Clarified

- The runtime target has four Compose services and five application containers because the backend has two replicas.
- Backend work needs a minimal container test target before its tests can run; runtime hardening follows in the containerization phase.
- Original code snippets and version references are historical design inputs; current guides identify proposed corrections.
- Readiness, safe message rendering, release identity and failure recovery are requirements awaiting implementation.

### Expanded Design - 2026-10-25

- Reviewed and advanced all 17 guides under `docs/` as design revision 2.
- Specified `chat.v1`, separate session/broadcast envelopes, event correlation, message fragmentation limits and bounded reconnect behavior.
- Added candidate admission/rate/queue/memory defaults, measurable performance/recovery objectives and concurrency/shutdown invariants.
- Added subscriber-heartbeat readiness, private liveness/metrics, structured logging and operational response thresholds.
- Defined digest-selected releases, unique build identities, manifest validation, SBOM/provenance evidence and interrupted-deployment recovery.
- Expanded Redis/browser/container controls, state recovery, deployment access choices and infrastructure drift guidance.
- Extended failure/property-boundary/load tests, acceptance criteria, release evidence and advanced demo scenarios.

These entries describe documentation changes. None of the proposed controls, targets or runtime capabilities has been implemented or measured.

### Design Elevation - Revision 4 (2026-10-25)

- Comprehensively updated all 17 specification documents in `docs/` to **Design Revision 4**, establishing a production-grade, enterprise architectural blueprint.
- **Requirements (`REQUIREMENTS.md`):** Formally codified FR-01..18, Acceptance Criteria AC-01..18, Non-Functional Requirements NFR-01..08, and comprehensive Fault Tolerance Matrix.
- **Architecture (`ARCHITECTURE.md`):** Added Mermaid sequence diagrams (Handshake, Distributed Fan-Out, Graceful Drain), asyncio task tree hierarchy, dynamic Nginx upstream DNS resolution (`127.0.0.11`), and mathematical memory model.
- **API Specification (`API_SPECIFICATION.md`):** Integrated complete Draft 2020-12 `events-v1.schema.json`, OpenMetrics format for `/metrics`, RFC 6455 close code matrix (1000..1013), and exact Unicode normalization algorithms.
- **Technologies (`TECHNOLOGIES.md`):** Pinned production compatibility locks (Python 3.11.10, FastAPI 0.115.4, Uvicorn 0.32.0, Nginx 1.27.3, Redis 7.4), architectural trade-off analysis, multi-stage Docker build diagrams, and supply-chain tooling.
- **Configuration (`CONFIGURATION.md`):** Added parameter master table, production `docker-compose.prod.yml`, hardened `redis.conf` and `users.acl`, and hardened `nginx.conf`.
- **Project Structure (`PROJECT_STRUCTURE.md`):** Documented complete file layout, exported symbol contracts for all Python modules, and test directory hierarchy.
- **Implementation Plan (`IMPLEMENTATION_PLAN.md`):** Added executable test commands and Definition of Done (DoD) verification gates across Phases 0 to 6.
- **Development Guide (`DEVELOPMENT.md`):** Added containerized test runner commands, interactive CLI recipes (`websocat`, `redis-cli`), slow-consumer simulation, and WSL2/Linux line-ending guides.
- **Testing Specification (`TESTING.md`):** Added property-based fuzzing with `hypothesis`, concrete `pytest-asyncio` integration fixtures, chaos engineering fault injections, and monotonic latency calculation formulas.
- **Security Specification (`SECURITY.md`):** Added formal STRIDE threat model, CSP Level 3 policy headers, container capability drops (`cap_drop: [ALL]`), Redis ACL sandboxing, and secret rotation runbooks.
- **Infrastructure Blueprint (`INFRASTRUCTURE.md`):** Added complete Terraform HCL definitions (VPC, Subnet, SG, EC2, IMDSv2, EBS gp3), hardened `user_data.sh` cloud-init script, S3 native locking (`use_lockfile = true`), and AWS billing cost calculations.
- **CI/CD Pipelines (`CICD.md`):** Added production GitHub Actions YAML workflows (`test.yml`, `build.yml`), Trivy scanning, CycloneDX SBOM generation, Cosign keyless signing, and `release.json` manifest verification.
- **Deployment & Rollback (`DEPLOYMENT.md`):** Added atomic symlink layout (`current -> releases/<RELEASE_ID>`), `scripts/deploy.sh` with `flock` locking, `scripts/verify.sh` synthetic integration gate, and `scripts/rollback.sh` executing in $< 600\text{ seconds}$ (**AC-09**).
- **Operations & Troubleshooting (`OPERATIONS.md`):** Added complete OpenMetrics telemetry catalog, Alertmanager alerting rules YAML, diagnostic terminal recipes, and incident response runbooks.
- **Decisions & Risks (`DECISIONS_AND_RISKS.md`):** Expanded Architecture Decision Records ADR-01 through ADR-20, resolved open items OPEN-01 through OPEN-10, and added quantitative Risk Register.
- **Release Checklist (`RELEASE_CHECKLIST.md`):** Formally mapped AC-01 through AC-18 across 5 readiness gates and provided a complete Cryptographic Release Evidence Record template.
- **Demonstration Guide (`DEMO_GUIDE.md`):** Documented 5 scripted live demonstration protocols (cross-messaging, XSS neutralization, Redis chaos injection, slow consumer eviction, automated rollback) and deep technical defense Q&A.

### Project State

Documentation and design only. No application implementation, container configuration, Terraform resources, CI/CD workflow or deployed release has been produced. Runtime acceptance checks have not been run.

## Future Release Entries

When a verified release exists, add its identifier and release date above older entries. Summarize implemented behavior, fixes, configuration changes, validation evidence and material limitations. Link to its sanitized release record where available.

Keep proposed work out of completed-release entries. Do not assign a release version or claim a deployment solely because documentation exists.
