# Chat_App

A planned Docker-only real-time chat application demonstrating WebSockets, distributed messaging and a complete DevOps workflow on AWS.

**Status: documentation and design only.** Application code, Dockerfiles, Compose files, Terraform resources and CI/CD workflows have not been implemented. Commands shown in these guides are instructions for a future implementation, not commands that have been executed or can run against the current repository.

## Project Goal

Run a browser chat interface, two FastAPI backend replicas, Redis Pub/Sub and an Nginx gateway in five containers on a single EC2 instance. Use Terraform for infrastructure, GitHub Actions for CI/CD, Docker Hub for images and Trivy for vulnerability scanning.

## Documentation

| Document | Purpose |
| --- | --- |
| [Technologies](docs/TECHNOLOGIES.md) | Advanced stack, compatibility policy, optional integrations and historical version references. |
| [Frontend technology and UI/UX](docs/FRONTEND.md) | Screen layout, visual design, accessibility, browser state, integration and frontend delivery requirements. |
| [Backend engineering](docs/BACKEND.md) | Backend stack, modules, messaging, concurrency, validation, security, observability and testing. |
| [Requirements](docs/REQUIREMENTS.md) | Features, boundaries and acceptance criteria. |
| [Architecture](docs/ARCHITECTURE.md) | Components, message flow, networking and failure behavior. |
| [API specification](docs/API_SPECIFICATION.md) | HTTP health checks, WebSocket messages and connection behavior. |
| [Project structure](docs/PROJECT_STRUCTURE.md) | Intended source files and the responsibility of each. |
| [Implementation plan](docs/IMPLEMENTATION_PLAN.md) | Ordered milestones and completion checks. |
| [Configuration](docs/CONFIGURATION.md) | Environment settings, Terraform inputs and CI secrets. |
| [Development guide](docs/DEVELOPMENT.md) | Future local setup, contribution workflow and debugging. |
| [Testing plan](docs/TESTING.md) | Unit, integration, browser, deployment and recovery checks. |
| [Security plan](docs/SECURITY.md) | Application, container, infrastructure and pipeline controls. |
| [Infrastructure plan](docs/INFRASTRUCTURE.md) | AWS resources, Terraform state and cost management. |
| [AWS Free Tier requirements](docs/AWS_FREE_TIER_REQUIREMENTS.md) | Account eligibility, required resources, access prerequisites, cost checks and teardown readiness. |
| [CI/CD plan](docs/CICD.md) | Validation, image publishing and release gates. |
| [Deployment guide](docs/DEPLOYMENT.md) | First deployment, updates, verification and rollback. |
| [Operations and troubleshooting](docs/OPERATIONS.md) | Monitoring, incident response, recovery and teardown. |
| [Decisions and risks](docs/DECISIONS_AND_RISKS.md) | Design choices, known defects and decisions still to resolve. |
| [Contribution guide](CONTRIBUTING.md) | Documentation changes, future contribution workflow and review expectations. |
| [Release checklist](docs/RELEASE_CHECKLIST.md) | Stage-specific readiness checks and a reusable release evidence record. |
| [Demo guide](docs/DEMO_GUIDE.md) | Future demonstration sequence, evidence capture and interview talking points. |
| [Changelog](CHANGELOG.md) | Actual documentation changes and future release-history conventions. |
| [Original planning document](gemini-code-1792827209365.md) | Original discussion and illustrative implementation snippets. |

## How to Read These Guides

Start with requirements and architecture, then read the implementation plan. Consult the API, configuration and security guides before writing code. Use the testing, deployment and operations guides to define completion evidence.

The original planning document is historical context. The guides under `docs/` define **Design Revision 4 (2026-10-25)** and provide a production-grade, highly rigorous, enterprise-ready architectural blueprint with concrete Draft 2020-12 schemas, mathematical memory models, hardened Terraform HCL, production Compose/Nginx/Redis configurations, STRIDE security modeling, and automated rollback playbooks. Nothing marked as a target, requirement, or checklist is a claim of completed code implementation.

## Advanced Design Coverage (Revision 4)

- **Formal Event Wire Schema:** Draft 2020-12 `events-v1.schema.json` with strict RFC 6455 close codes (1000..1013) and Unicode NFKC normalization.
- **Mathematical Memory & Concurrency Bounds:** Concrete memory allocation formulas ($< 528\text{ MiB}$ total container cgroup cap leaving $> 256\text{ MiB}$ host free RAM for 100 concurrent clients).
- **Hardened Multi-Tier Infrastructure:** Complete Terraform HCL configurations for AWS EC2 `t3.micro` with IMDSv2, isolated security groups, and native S3 state locking (`use_lockfile = true`).
- **Cryptographic Supply Chain:** Sigstore Cosign keyless signing via GitHub Actions OIDC workload identity, CycloneDX SBOM generation, Trivy CVE gates, and signed `release.json` manifests.
- **Atomic Host Deployments & Fast Rollback:** Linux kernel advisory mutex (`flock -n 200`), atomic symlink swapping (`current -> releases/<RELEASE_ID>`), synthetic cross-replica verification gates, and automated rollback within $< 600\text{ seconds}$ (**AC-09**).
- **Production Observability & Threat Modeling:** OpenMetrics telemetry catalog, Alertmanager alerting rules, STRIDE threat analysis, CSP Level 3 policy headers, and concrete incident response runbooks.

The numerical defaults and objectives are formal engineering baselines awaiting code implementation. Requirements owns the objectives, API owns the wire contract, configuration owns defaults, and testing owns the evidence method.

## Scope and Constraints

- All application services and backend test execution are intended to run in containers.
- Docker and infrastructure administration tools may run on the developer or CI host.
- The first version provides one anonymous global chat channel with no stored history.
- Backend replication is within one host; the design does not provide host-level high availability.
- Resource use and AWS eligibility must be measured or checked; zero cost and fixed memory use are not guaranteed.
- Kubernetes, EKS, a managed load balancer and a persistent chat database are outside the initial scope.
