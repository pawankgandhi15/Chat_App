# Technology Choices

**Design revision 5 — 2026-10-26. Status: planned.** No dependency lockfiles, application code or deployed services exist.

| Layer | Selected technology | Reason and boundary |
| --- | --- | --- |
| Browser | Semantic HTML, CSS, native JavaScript | Small accessible interface; no framework or CDN dependency required. |
| Transport | WebSocket with `chat.v1` | Versioned session-first JSON events; client messages are plain text. |
| Backend | Python, FastAPI, Uvicorn, Pydantic | Async connection handling, configuration and input validation; one worker per Pod. |
| Broker client | `redis.asyncio` | Separate publisher pool and subscriber connection; bounded timeouts. |
| Shared messaging | Redis Pub/Sub | Ephemeral fan-out across replicas; at-most-once delivery, no replay. |
| HTTP gateway and assets | Nginx, separate gateway/frontend images | TLS and WebSocket proxying separate from static content. |
| Image tooling | Docker / BuildKit, OCI images | Build off the AWS node; select release images by digest. |
| Local orchestration | k3d | K3s in local Docker; verify manifests without AWS usage. |
| Cloud orchestration | K3s with containerd | Kubernetes on one EC2 server/worker; no EKS cluster fee. |
| Configuration packaging | Kustomize / kubectl | Shared base and explicit local/AWS overlays. |
| Cloud | EC2, encrypted gp3 EBS, VPC, S3 | One public node; S3 stores Terraform state, not chat messages. |
| Infrastructure | Terraform with AWS provider | Reviewed plans, private versioned remote state and native S3 locking. |
| Delivery | GitHub Actions and GHCR | Build, scan, sign and verify release artifacts; pull access must be configured. |
| Verification | pytest, Hypothesis, browser automation, schema/policy checks | Contract, lifecycle, UI and Kubernetes behavior evidence. |
| Supply chain | Trivy, SBOM generation, Cosign | Scan and verify artifacts against trusted identity and digest. |
| Diagnostics | Structured JSON logs, private Prometheus-format endpoint | Bounded labels and retention; no message payload logging. |

## Version policy

Earlier documents named illustrative 2024 package versions. They were never installed or tested and are not a supported version matrix. During implementation, select supported releases, review vulnerabilities and licenses, and record exact versions with dependency hashes and base-image digests.

Keep local k3d's K3s image aligned with the EC2 K3s version. Select kubectl within the supported Kubernetes version-skew policy. Pin GitHub Actions by commit and review updates. Terraform must support `use_lockfile` (1.10 or newer); lock the chosen provider and validate it.

A release record must include Python and locked dependencies; Redis and Nginx image digests; K3s/Kubernetes/containerd; k3d and Docker test environment; Terraform/provider versions; and signing/scanning tools. Upgrade compatibility needs tests, especially WebSocket shutdown, Redis subscriber recovery and NetworkPolicy enforcement.

## Cost and capacity

The target node is a measured 2-vCPU/4-GiB candidate, with `c7i-flex.large` evaluated against actual account eligibility and regional pricing. Docker Compose is superseded as the project orchestrator. Kubernetes adds platform overhead and maintenance; two backend Pods on one node do not provide host availability.

Detailed sources and version-dependent behavior are recorded in [Kubernetes](KUBERNETES.md), [AWS requirements](AWS_FREE_TIER_REQUIREMENTS.md) and [infrastructure](INFRASTRUCTURE.md).

## Scope exclusions

No managed EKS, NAT Gateway, AWS load balancer, managed Redis, database, HPA or multi-node deployment is included in this baseline. Authentication, durable history and multi-room messaging require separate product and security designs.

## Ownership of contracts

Use [API](API_SPECIFICATION.md) for wire behavior, [configuration](CONFIGURATION.md) for defaults, [requirements](REQUIREMENTS.md) for acceptance targets and [testing](TESTING.md) for evidence. These documents describe intended behavior, not completed functionality.

