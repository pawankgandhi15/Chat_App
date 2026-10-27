# Chat App · Common Room

**A real-time chat application built with FastAPI, Redis and Kubernetes.**

Open one shared room, choose a temporary display name and exchange live text messages across two backend replicas. The responsive interface preserves unsent drafts through reconnects and renders messages safely as text.

[Run locally](docs/DEVELOPMENT.md) · [Implementation evidence](docs/IMPLEMENTATION_STATUS.md) · [API contract](docs/API_SPECIFICATION.md) · [System design](docs/design/README.md)

## Run locally

Requires Python 3.12, Node.js 24, Docker with Linux containers, k3d 5.9.0 and kubectl 1.37.x. From the repository root in PowerShell:

~~~powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.venv\Scripts\python.exe scripts/local.py up
~~~

Open **http://localhost:8080** in two tabs. No AWS account is needed. The launcher builds the images, creates the local cluster and waits for all services.

For Linux/macOS setup, tests, troubleshooting and cleanup, see [Development](docs/DEVELOPMENT.md). To stop the local environment:

~~~powershell
.venv\Scripts\python.exe scripts/local.py down
~~~

## What is implemented

- **Live messaging:** session-first `chat.v1` WebSockets and Redis Pub/Sub fanout across backend replicas.
- **Responsive interface:** keyboard controls, connection feedback, safe text rendering and mobile layout.
- **Recovery:** bounded retries, retained unsent drafts and no automatic message resending.
- **Resource controls:** connection/rate limits, bounded queues, send deadlines and slow-client isolation.
- **Kubernetes:** four Deployments, five application Pods, readiness/liveness probes and enforced network isolation.
- **Delivery tooling:** Terraform, validation workflows, scanned/signed release bundles and previous-bundle restoration.

The local application is implemented and tested. AWS provisioning, GitHub release execution and cloud acceptance remain pending. Detailed results and limits are recorded in [Implementation status](docs/IMPLEMENTATION_STATUS.md).

## Architecture

![AWS K3s deployment design: one EC2 node with gateway, frontend, two backend Pods and Redis; private Terraform state in S3.](docs/images/aws-k3s-architecture.png)

*AWS deployment design; cloud resources have not been provisioned. [View full-size](docs/images/aws-k3s-architecture.png).*

~~~mermaid
flowchart LR
    Browser -->|HTTP / WebSocket| Gateway[Nginx gateway]
    Gateway --> Frontend[Static frontend]
    Gateway --> BackendA[FastAPI replica A]
    Gateway --> BackendB[FastAPI replica B]
    BackendA <-->|Pub/Sub| Redis
    BackendB <-->|Pub/Sub| Redis
~~~

A backend validates each message, assigns its event ID and publishes it once. Both backends consume the event and deliver it to their connected clients. Each socket has an independent bounded writer queue.

Local development uses k3d. The AWS target uses K3s/containerd on one EC2 host, with K3s ServiceLB exposing only the gateway. Redis and backend diagnostics stay private. Two backend Pods demonstrate distributed messaging; they do not provide host-level high availability.

## Technology stack

| Layer | Implementation |
| --- | --- |
| Interface | HTML, CSS, native JavaScript modules |
| API and transport | Python 3.12, FastAPI, Uvicorn, Pydantic, WebSockets |
| Messaging | Redis Pub/Sub and redis.asyncio |
| Web serving | Nginx static server and reverse proxy |
| Runtime | Docker/OCI, k3d, K3s, containerd, Kustomize |
| Infrastructure code | Terraform for EC2, EBS, VPC and S3 state |
| Delivery | GitHub Actions, GHCR, Trivy, Cosign |
| Verification | pytest, Hypothesis, Node test runner, Playwright |

Python dependencies are hash-locked; container bases are pinned by digest. See [Configuration](docs/CONFIGURATION.md) for actual settings and [Technologies](docs/TECHNOLOGIES.md) for design rationale.

## Verification

Local checks passed: **26 Python unit tests, 6 JavaScript tests, 9 real-container integration tests and the Chromium desktop/mobile flow**. Public smoke tests, Kubernetes network checks, both Kustomize overlays and both Terraform roots also passed their applicable checks.

A short local run with **25 clients**, **5 aggregate messages/second** and **512-byte payloads** delivered all **7,500 expected events** during 60 seconds, with no duplicates and approximately **16 ms p95/p99** client-observed latency. This is local evidence, not a measured AWS capacity claim. The longer cloud test and node-memory target remain pending.

~~~powershell
.venv\Scripts\python.exe -m pytest tests/unit -q
node --test tests/frontend/*.test.js
.venv\Scripts\python.exe scripts/smoke.py
~~~

See [Development](docs/DEVELOPMENT.md) for the complete test commands and [Implementation status](docs/IMPLEMENTATION_STATUS.md) for evidence boundaries.

## Repository layout

~~~text
backend/             FastAPI application and locked runtime dependencies
frontend/            Browser interface, modules and static server
gateway/             Local/HTTPS Nginx routing
redis/               Digest-pinned Redis release image
k8s/                 Base workloads, policies, platform resources and overlays
platform/k3d/        Disposable local cluster definition
infra/               Separate Terraform state and workload roots
scripts/             Local setup, checks, load, release and deployment tools
schemas/             Event and release contracts
tests/               Unit, JavaScript, integration and browser tests
.github/workflows/   Validation, manual release and manual deployment
docs/                Requirements, operational guides and HLD/LLD handbook
~~~

## Documentation

### Product and Architecture

| Guide | Contents |
| --- | --- |
| [Requirements](docs/REQUIREMENTS.md) | User journeys, scope, acceptance criteria and measurable objectives |
| [Architecture](docs/ARCHITECTURE.md) | Service topology, event flow, concurrency and failure behavior |
| [System Design: HLD, LLD and Future Growth](docs/design/README.md) | Detailed design, sequence/data models, capacity planning, upgrade stages, migration and review templates |
| [Frontend & UI/UX](docs/FRONTEND.md) | Screen design, accessibility, browser state and integration |
| [Backend](docs/BACKEND.md) | Modules, messaging, validation, recovery and service engineering |
| [API Specification](docs/API_SPECIFICATION.md) | Routes, event schemas, input rules and close codes |
| [Technologies](docs/TECHNOLOGIES.md) | Stack choices, compatibility considerations and candidate versions |
| [Project Structure](docs/PROJECT_STRUCTURE.md) | Module responsibilities and future layout proposals |
| [Decisions and Risks](docs/DECISIONS_AND_RISKS.md) | Architectural decisions, trade-offs and implementation risks |

### Development and Quality

| Guide | Contents |
| --- | --- |
| [Implementation Plan](docs/IMPLEMENTATION_PLAN.md) | Ordered milestones and verification gates |
| [Development](docs/DEVELOPMENT.md) | Working local setup, container workflows and debugging |
| [Configuration](docs/CONFIGURATION.md) | Environment settings, defaults and configuration examples |
| [Testing](docs/TESTING.md) | Unit, contract, integration, load and failure testing |
| [Security](docs/SECURITY.md) | Threat model, access boundaries, secret handling and release controls |

### Infrastructure and Operations

| Guide | Contents |
| --- | --- |
| [AWS Free Tier Requirements](docs/AWS_FREE_TIER_REQUIREMENTS.md) | Account eligibility, resources, access, cost review and teardown |
| [Kubernetes deployment](docs/KUBERNETES.md) | Primary k3d/K3s topology, Pods, Services, policies, probes and resource planning |
| [Infrastructure](docs/INFRASTRUCTURE.md) | AWS topology, Terraform design and state management |
| [CI/CD](docs/CICD.md) | Validation, image publication and delivery pipeline design |
| [Deployment](docs/DEPLOYMENT.md) | First deployment, release verification and rollback |
| [Operations](docs/OPERATIONS.md) | Monitoring, troubleshooting, recovery and cleanup |
| [Release Checklist](docs/RELEASE_CHECKLIST.md) | Readiness gates and release evidence |
| [Demo Guide](docs/DEMO_GUIDE.md) | Planned demonstration scenarios and evidence capture |

For change history, see [CHANGELOG.md](CHANGELOG.md). The [original planning discussion](gemini-code-1792827209365.md) provides historical context. When examples or summaries differ, requirements own scope and targets, the API specification owns the wire contract, and configuration owns defaults; reconcile conflicts before implementation.

## Scope and deployment

This is an anonymous, ephemeral global chat. Accounts, private conversations, attachments, durable history and read receipts are outside the current scope. Display names are not verified identities. Messages missed while disconnected cannot be recovered.

The AWS Terraform defaults target a single 2-vCPU/4-GiB candidate in Mumbai. Review account eligibility, actual prices, credits and teardown arrangements before provisioning. K3s avoids a managed Kubernetes control plane, but EC2 and related resources still consume credits or money.

[Deployment](docs/DEPLOYMENT.md) describes the concrete provisioning and signed-release workflow. [AWS requirements](docs/AWS_FREE_TIER_REQUIREMENTS.md) provides the account/cost worksheet. No infrastructure is created by the local startup command.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md). Keep implementation, wire contracts and documentation aligned, add checks for meaningful behavior changes, and distinguish measurements from targets.

See [CHANGELOG.md](CHANGELOG.md) for repository changes. The [original planning discussion](gemini-code-1792827209365.md) and unimplemented expansion plans remain historical/design context.
