# Chat App

**Real-time messaging with FastAPI, Redis and Docker — designed for deployment on AWS.**

A documented engineering project exploring WebSocket communication across backend replicas, an accessible browser experience, and automated infrastructure and delivery on a single EC2 host.

[Architecture](docs/ARCHITECTURE.md) · [Frontend & UI/UX](docs/FRONTEND.md) · [Backend](docs/BACKEND.md) · [Implementation plan](docs/IMPLEMENTATION_PLAN.md) · [AWS requirements](docs/AWS_FREE_TIER_REQUIREMENTS.md)

## AWS Architecture Diagram

![Planned Chat App architecture in AWS Mumbai: browser users connect through an Internet Gateway to a single EC2 instance running an Nginx gateway, static frontend, two FastAPI replicas and Redis. Terraform provisions infrastructure through AWS APIs and stores state separately in S3.](docs/images/aws-single-host-architecture-v2.png)

*Planned single-host deployment in `ap-south-1` (Mumbai). [Open the full-size diagram](docs/images/aws-single-host-architecture-v2.png).*

## Project Status

**Current phase: documentation and design.** This repository contains requirements, technical specifications and implementation plans. Application source code, Docker configurations, Terraform resources and CI/CD workflows have yet to be implemented.

| Area | Status |
| --- | --- |
| Product requirements, architecture and API contract | Documented; implementation review pending |
| Frontend, UI/UX and backend specifications | Documented |
| Infrastructure, security and delivery plans | Documented |
| Application and automation | Planned |
| Runtime tests, performance measurements and deployment | Pending implementation |

Code blocks in the guides are proposed examples. There is no runnable application or deployed demo yet; performance and reliability objectives require test evidence.

## Overview

The planned application provides one anonymous global chat channel. A visitor receives a temporary display name, connects through a WebSocket and exchanges text messages with other connected visitors. Redis Pub/Sub distributes events between two backend replicas so clients can communicate regardless of which replica serves their connection.

The project brings application development and operations into one workflow: define the protocol, implement and test the services in containers, provision infrastructure, publish verified images, and rehearse deployment and recovery.

### Planned Capabilities

- **Live messaging:** A versioned `chat.v1` WebSocket protocol, structured server events and messaging across backend replicas.
- **Accessible interface:** Responsive layout, keyboard interaction, safe text rendering and clear connection states.
- **Connection recovery:** Bounded retries, preserved unsent drafts and manual reconnection after retry exhaustion.
- **Controlled resource use:** Connection limits, rate limits, bounded delivery queues and slow-client isolation.
- **Operational visibility:** Dependency-aware readiness, private liveness/metrics endpoints and structured logs.
- **Repeatable delivery:** Container images selected by digest, Terraform infrastructure, CI checks and verified rollback procedures.

## Architecture

The deployment target is **five application containers across four Compose services** on one EC2 instance. The backend service runs as two replicas.

1. Nginx serves as the public entry point and routes static requests and WebSocket connections.
2. Each backend validates incoming messages and publishes a server-generated event to Redis.
3. Both backends consume the event and deliver it through bounded queues to their connected clients.

Only the gateway publishes application ports on the host. Redis uses an internal data network; gateway and frontend have no direct Redis connection. Terraform stores infrastructure state and lockfiles in S3, outside the chat message path. Backend replication demonstrates distributed messaging within one host and does not provide host-level high availability.

See the [architecture guide](docs/ARCHITECTURE.md) for networking, lifecycle and failure behavior, and the [API specification](docs/API_SPECIFICATION.md) for the wire contract.

## Planned Technology Stack

| Layer | Technologies | Purpose |
| --- | --- | --- |
| Browser interface | HTML, CSS, native JavaScript | Responsive chat UI and browser connection state |
| Real-time transport | WebSockets, `chat.v1` | Persistent browser-to-backend communication |
| Backend | Python, FastAPI, Uvicorn, Pydantic | Async sessions, validation and event handling |
| Messaging | Redis Pub/Sub, `redis.asyncio` | Live event distribution across replicas |
| Web serving | Nginx | Static assets, TLS termination and reverse proxying |
| Containers | Docker, Docker Compose v2 | Local integration and single-host deployment |
| Infrastructure | AWS EC2, EBS, VPC, S3, Terraform | Compute, networking, storage and infrastructure state |
| Delivery | GitHub Actions, OCI image registry | Automated checks, builds and release delivery |
| Quality and security | pytest, Hypothesis, Trivy, Cosign | Behavior testing, image scanning and artifact verification |

The [technology guide](docs/TECHNOLOGIES.md) records design choices and candidate versions. Dependency compatibility, security updates and the registry configuration must be reconciled and locked during implementation.

## Explore the Project

Clone the documentation repository:

```bash
git clone https://github.com/pawankgandhi15/Chat_App.git
cd Chat_App
```

Choose a starting point:

| Your goal | Read first |
| --- | --- |
| Understand the product and scope | [Requirements](docs/REQUIREMENTS.md) → [Architecture](docs/ARCHITECTURE.md) |
| Design the interface | [Frontend & UI/UX](docs/FRONTEND.md) → [API specification](docs/API_SPECIFICATION.md) |
| Build the messaging services | [Backend](docs/BACKEND.md) → [Configuration](docs/CONFIGURATION.md) |
| Plan implementation work | [Implementation plan](docs/IMPLEMENTATION_PLAN.md) → [Development guide](docs/DEVELOPMENT.md) |
| Prepare an AWS environment | [AWS Free Tier requirements](docs/AWS_FREE_TIER_REQUIREMENTS.md) → [Infrastructure](docs/INFRASTRUCTURE.md) |

The repository currently contains:

```text
Chat_App/
├── README.md                       # Project overview and navigation
├── CONTRIBUTING.md                 # Contribution and review guidance
├── CHANGELOG.md                    # Documentation change history
├── docs/                           # Product and engineering specifications
└── gemini-code-1792827209365.md      # Original planning discussion
```

The future source layout is described in [Project Structure](docs/PROJECT_STRUCTURE.md). Setup and deployment commands in the guides become usable after their referenced source files and prerequisites exist.

## Documentation

### Product and Architecture

| Guide | Contents |
| --- | --- |
| [Requirements](docs/REQUIREMENTS.md) | User journeys, scope, acceptance criteria and measurable objectives |
| [Architecture](docs/ARCHITECTURE.md) | Service topology, event flow, concurrency and failure behavior |
| [Frontend & UI/UX](docs/FRONTEND.md) | Screen design, accessibility, browser state and integration |
| [Backend](docs/BACKEND.md) | Modules, messaging, validation, recovery and service engineering |
| [API Specification](docs/API_SPECIFICATION.md) | Routes, event schemas, input rules and close codes |
| [Technologies](docs/TECHNOLOGIES.md) | Stack choices, compatibility considerations and candidate versions |
| [Project Structure](docs/PROJECT_STRUCTURE.md) | Planned files and module responsibilities |
| [Decisions and Risks](docs/DECISIONS_AND_RISKS.md) | Architectural decisions, trade-offs and implementation risks |

### Development and Quality

| Guide | Contents |
| --- | --- |
| [Implementation Plan](docs/IMPLEMENTATION_PLAN.md) | Ordered milestones and verification gates |
| [Development](docs/DEVELOPMENT.md) | Future local setup, container workflows and debugging |
| [Configuration](docs/CONFIGURATION.md) | Environment settings, defaults and configuration examples |
| [Testing](docs/TESTING.md) | Unit, contract, integration, load and failure testing |
| [Security](docs/SECURITY.md) | Threat model, access boundaries, secret handling and release controls |

### Infrastructure and Operations

| Guide | Contents |
| --- | --- |
| [AWS Free Tier Requirements](docs/AWS_FREE_TIER_REQUIREMENTS.md) | Account eligibility, resources, access, cost review and teardown |
| [Infrastructure](docs/INFRASTRUCTURE.md) | AWS topology, Terraform design and state management |
| [CI/CD](docs/CICD.md) | Validation, image publication and delivery pipeline design |
| [Deployment](docs/DEPLOYMENT.md) | First deployment, release verification and rollback |
| [Operations](docs/OPERATIONS.md) | Monitoring, troubleshooting, recovery and cleanup |
| [Release Checklist](docs/RELEASE_CHECKLIST.md) | Readiness gates and release evidence |
| [Demo Guide](docs/DEMO_GUIDE.md) | Planned demonstration scenarios and evidence capture |

For change history, see [CHANGELOG.md](CHANGELOG.md). The [original planning discussion](gemini-code-1792827209365.md) provides historical context. When examples or summaries differ, requirements own scope and targets, the API specification owns the wire contract, and configuration owns defaults; reconcile conflicts before implementation.

## Implementation Roadmap

| Phase | Deliverable | Completion evidence |
| --- | --- | --- |
| 1. Confirm contracts | Consistent schemas, configuration and dependency choices | Reviewed contracts and resolved implementation blockers |
| 2. Build the application | Backend messaging and accessible frontend | Unit, contract and browser checks |
| 3. Integrate containers | Five-container stack with isolated networks | Cross-replica messaging and failure tests |
| 4. Prepare infrastructure and delivery | Terraform and CI/CD workflows | Reviewed plans, verified artifacts and deployment checks |
| 5. Validate operations | Recovery, capacity and rollback procedures | Recorded measurements and a successful rollback rehearsal |

All phases remain planned. The [implementation plan](docs/IMPLEMENTATION_PLAN.md) contains the detailed tasks and acceptance gates.

## Scope and Validation

The initial scope is text messaging in one anonymous global channel. Accounts, private conversations, attachments, durable history, read receipts and multi-host orchestration are deferred. Messages missed during a disconnection are not replayed by the planned Pub/Sub design.

The requirements define an initial experiment with **25 concurrent clients and 5 aggregate messages per second**, followed by latency, delivery, resource and recovery checks. These are validation targets, not measured capacity. See [Requirements](docs/REQUIREMENTS.md) and [Testing](docs/TESTING.md) for the full conditions.

AWS deployment targets a single `t3.micro` in Mumbai (`ap-south-1`). Actual eligibility, credits, resource prices and runtime usage must be checked for the account; the project does not guarantee zero cost. Use the [AWS requirements guide](docs/AWS_FREE_TIER_REQUIREMENTS.md) before provisioning.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before making changes. Documentation contributions should keep contracts consistent, distinguish proposed behavior from verified results, and update related guides when scope or defaults change.

Report issues with the affected document, expected behavior and a concise reproduction or example. Implementation contributions should identify the relevant acceptance criteria and include evidence from the applicable checks.
