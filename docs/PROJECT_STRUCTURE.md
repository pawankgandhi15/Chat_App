# Intended Project Structure

**Status:** File map and software architecture contracts for future implementation. See the [documentation index](../README.md).

**Design Revision 4 (2026-10-25):** Exhaustive source tree specification, exported Python symbol contracts, modular frontend component hierarchy, and automated verification script interfaces.

---

## Complete Planned Repository File Tree

```text
repo/
|-- README.md                         # High-level architecture summary & entry point
|-- CONTRIBUTING.md                   # Contributor workflow, linting & review standards
|-- CHANGELOG.md                      # Verifiable documentation & release history
|-- .gitignore                        # Git ignore rules for Python, Terraform, Docker & secrets
|-- .dockerignore                     # Global build context exclusions
|-- docker-compose.yml                # Local developer stack (port 80 published, unauth Redis)
|-- docker-compose.test.yml           # Containerized test runner & ephemeral Redis bus
|-- docker-compose.prod.yml           # Production stack (digest-pinned, dual networks, secrets)
|
|-- docs/                             # Definitive architecture & operational specifications
|   |-- REQUIREMENTS.md               # Functional/operational requirements & acceptance criteria
|   |-- ARCHITECTURE.md               # Topology, sequence diagrams & concurrency model
|   |-- API_SPECIFICATION.md          # Wire protocol, JSON schemas, frame & close code matrix
|   |-- TECHNOLOGIES.md               # Technology choices, trade-offs & version lock baseline
|   |-- FRONTEND.md                   # Frontend technologies, UI/UX and browser engineering
|   |-- BACKEND.md                    # Backend technologies, messaging and service engineering
|   |-- AWS_FREE_TIER_REQUIREMENTS.md  # Account eligibility, resource prerequisites and cost review
|   |-- CONFIGURATION.md              # Environment variables, Compose & service config blueprints
|   |-- PROJECT_STRUCTURE.md          # Module responsibilities & exported symbol contracts
|   |-- IMPLEMENTATION_PLAN.md        # Phased implementation roadmap & verification checks
|   |-- DEVELOPMENT.md                # Local setup, debugging workflows & testing guides
|   |-- TESTING.md                    # Test matrix, property testing, load & chaos methodologies
|   |-- SECURITY.md                   # Threat modeling (STRIDE), hardening & supply chain controls
|   |-- INFRASTRUCTURE.md             # AWS VPC, EC2, Terraform specs & cost calculations
|   |-- CICD.md                       # GitHub Actions pipeline, scanning, SBOM & attestations
|   |-- DEPLOYMENT.md                 # Atomic host deployment, symlinks & rollback runbooks
|   |-- OPERATIONS.md                 # SRE runbooks, Prometheus metrics & Alertmanager rules
|   |-- DECISIONS_AND_RISKS.md        # Architecture Decision Records (ADR) & Risk Register
|   |-- RELEASE_CHECKLIST.md          # Release readiness gates & evidence record template
|   `-- DEMO_GUIDE.md                 # Live demonstration scripts, talking points & Q&A prep
|
|-- schemas/                          # Authoritative machine-readable JSON schemas
|   |-- events-v1.schema.json         # Discriminated session/broadcast event contract
|   `-- release-v1.schema.json        # Release manifest cryptographic integrity schema
|
|-- backend/                          # FastAPI / Uvicorn real-time messaging backend
|   |-- Dockerfile                    # Multi-stage build (builder + distroless/slim runtime)
|   |-- .dockerignore                 # Backend-specific build exclusions
|   |-- requirements.txt              # Production pinned runtime dependencies
|   |-- requirements-dev.txt          # Linting, formatting & test dependencies
|   `-- app/                          # Core Python application package
|       |-- __init__.py               # Package marker; exports __version__
|       |-- main.py                   # App factory, ASGI routing, lifespan context
|       |-- settings.py               # Pydantic Settings with strict regex/range validators
|       |-- protocol.py               # Envelopes, UUIDv4 generation, Unicode normalization
|       |-- lifecycle.py              # Supervisor, state machine (STARTING/READY/DRAINING)
|       |-- limits.py                 # Token-bucket rate limiter & admission tracking
|       |-- observability.py          # Prometheus metrics registry & structured JSON logger
|       |-- manager.py                # ConnectionManager, ClientSession, outbound queues
|       `-- messaging.py              # Redis Pub/Sub adapter, subscriber loop & heartbeat
|
|-- frontend/                         # Pure vanilla HTML5/CSS3/JavaScript client
|   |-- Dockerfile                    # Nginx unprivileged Alpine static container
|   |-- .dockerignore                 # Frontend build exclusions
|   |-- nginx.conf                    # Frontend static server configuration
|   |-- index.html                    # Accessible chat interface markup (zero inline JS/CSS)
|   `-- assets/                       # Modular browser assets
|       |-- app.js                    # Chat client state machine, WebSocket handler & DOM
|       `-- styles.css                # Responsive, modern CSS with custom properties
|
|-- nginx/                            # Ingress reverse proxy & TLS termination gateway
|   |-- Dockerfile                    # Gateway image build with custom nginx.conf
|   `-- nginx.conf                    # Dynamic upstream resolution, rate limits, security headers
|
|-- redis/                            # Redis configuration & access control lists
|   |-- redis.conf                    # In-memory ephemeral bus tuning (no persistence)
|   `-- users.acl                     # ACL definitions restricting chatapp user
|
|-- tests/                            # Comprehensive multi-tier test suite
|   |-- conftest.py                   # Pytest async fixtures, event loop & mock Redis
|   |-- unit/                         # Fast isolated component checks
|   |   |-- test_protocol.py          # Unicode code point normalization & schema validation
|   |   |-- test_limits.py            # Token bucket math & admission limits
|   |   `-- test_settings.py          # Pydantic configuration parsing & validation
|   |-- contracts/                    # Schema compliance fixtures against JSON schemas
|   |-- integration/                  # Real multi-replica messaging & failure scenarios
|   |   |-- test_messaging.py         # Cross-replica Redis publication & fan-out
|   |   |-- test_lifecycle.py         # Redis outage, reconnect & subscriber recovery
|   |   `-- test_drain.py             # SIGTERM handling, close code 1012 & socket cleanup
|   |-- load/                         # Reproducible load testing scripts (k6 / custom async)
|   `-- chaos/                        # Packet drop & subscriber stalling injection
|
|-- scripts/                          # Deterministic automation & deployment tooling
|   |-- package-release.sh            # Packages release artifacts & generates release.json
|   |-- deploy.sh                     # Host-side atomic symlink deployment & rollback engine
|   `-- verify-release.sh             # Synthetic smoke test verifying live cross-messaging
|
|-- terraform/                        # Infrastructure as Code for AWS
|   |-- main.tf                       # VPC, Subnet, IGW, Security Groups & EC2 instance
|   |-- variables.tf                  # Strictly typed variables with validation blocks
|   |-- outputs.tf                    # Public IP, SSH connection strings, health URLs
|   |-- user_data.sh                  # EC2 cloud-init bootstrap script (Docker & Compose)
|   |-- terraform.tfvars.example      # Sample non-secret input variables
|   `-- .terraform.lock.hcl           # Pinned AWS provider dependency lockfile
|
`-- .github/workflows/                # GitHub Actions automated CI/CD pipelines
    |-- test.yml                      # PR validation: linting, contract & containerized tests
    |-- build.yml                     # Push to main: build, Trivy scan, SBOM, Cosign sign
    `-- deploy.yml                    # Release dispatch: atomic SSH deployment to EC2
```

---

## Python Module Symbol & Responsibility Contracts

### 1. `app.settings` (`settings.py`)
- **Class `AppSettings(BaseSettings)`:**
  - `app_env: Literal["local", "test", "public"]`
  - `release_id: str`
  - `allowed_origins: list[str]`
  - `channel_name: str`
  - `max_connections_per_replica: int` (default: 64)
  - `rate_messages_per_second: float` (default: 2.0)
  - `rate_burst: int` (default: 5)
  - `publish_rate_per_second: float` (default: 20.0)
  - `publish_burst: int` (default: 40)
  - `outbound_queue_events: int` (default: 32)
  - `outbound_queue_bytes: int` (default: 262,144)
  - `shutdown_drain_seconds: float` (default: 10.0)
- **Function `get_settings() -> AppSettings`:** Cached singleton instance.

### 2. `app.protocol` (`protocol.py`)
- **Classes:** `SessionEnvelope`, `ChatBroadcastEnvelope`, `SystemBroadcastEnvelope`.
- **Functions:**
  - `normalize_message_text(raw_text: str) -> str`: Normalizes CRLF to LF, performs boundary whitespace trimming, checks code point length ($\le 2000$), rejects C0 control characters.
  - `validate_username(raw_username: str) -> str`: Enforces regex `^[A-Za-z0-9_-]{1,32}$`.
  - `serialize_envelope(envelope: BaseModel) -> str`: Fast JSON serialization via Pydantic v2.

### 3. `app.limits` (`limits.py`)
- **Class `TokenBucket`:** High-precision monotonic clock token bucket implementation for rate limiting.
- **Class `AdmissionController`:** Thread-safe / async slot reservation tracking active connections against `MAX_CONNECTIONS_PER_REPLICA`.

### 4. `app.manager` (`manager.py`)
- **Class `ClientSession`:** Encapsulates `websocket: WebSocket`, `connection_id: UUID`, `user: str`, `queue: asyncio.Queue`, `writer_task: asyncio.Task`.
- **Class `ConnectionManager`:** Active socket registry (`dict[UUID, ClientSession]`), methods `connect()`, `disconnect()`, `broadcast_local()`, and slow-consumer eviction logic.

### 5. `app.messaging` (`messaging.py`)
- **Class `RedisBusAdapter`:** Manages `redis.asyncio.Redis` publisher pool and dedicated subscriber connection.
- **Coroutines:**
  - `publish_event(envelope: BroadcastEnvelope) -> None`: Publishes serialized JSON to Redis.
  - `subscriber_loop(callback: Callable) -> None`: Consumes Pub/Sub messages, updates heartbeat nonce, and forwards envelopes to `ConnectionManager.broadcast_local()`.

### 6. `app.lifecycle` (`lifecycle.py`)
- **Class `DependencySupervisor`:** Background heartbeat probe executing every 5s; manages `generation_nonce`; evaluates `/health` status.
- **Async Context Manager `lifespan(app: FastAPI)`:** Manages startup initialization, Redis pool connection, supervisor launch, and SIGTERM graceful drain handling.

### 7. `app.observability` (`observability.py`)
- **Prometheus Metrics:** Declares `chat_connections_active`, `chat_messages_published_total`, `chat_deliveries_total`, `chat_outbound_queue_bytes`, etc.
- **Structured Logger:** Redacting formatter outputting JSON with UTC timestamp, log level, event class, and latency attributes.

---

## Related Guides

[Requirements](REQUIREMENTS.md) | [Architecture](ARCHITECTURE.md) | [Implementation Plan](IMPLEMENTATION_PLAN.md) | [Development](DEVELOPMENT.md) | [Testing](TESTING.md)

