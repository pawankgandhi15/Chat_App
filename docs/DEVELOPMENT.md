# Local Development and Contribution Guide

**Status:** Developer setup and debugging runbooks for implementation. See the [documentation index](../README.md).

**Design Revision 4 (2026-10-25):** Comprehensive local developer environment specification, containerized testing execution, interactive CLI debugging recipes (`websocat`, `redis-cli`), and cross-platform (Windows WSL2, Linux, macOS) guidelines.

---

## Prerequisites & Tooling

To ensure zero host system contamination, the application and backend tests run exclusively within Docker containers.
- **Docker Engine:** Version 26.0+ or Docker Desktop 4.30+ with Docker Compose v2 (v2.27+).
- **Git:** Configured with `core.autocrlf = input` (on Linux/macOS) or `core.autocrlf = true` with `.gitattributes` enforcing LF on shell scripts.
- **Web Browser:** Modern Chromium or Firefox with DevTools Network WebSocket frame inspection.
- **Optional Host Utilities:** `websocat` (for headless WebSocket CLI testing), `curl`, `jq`.

---

## Rapid Local Setup (Interactive Stack)

1. **Clone repository:**
   ```bash
   git clone https://github.com/your-org/chat_app.git
   cd chat_app/repo
   ```

2. **Configure local environment:**
   Create `.env` from template:
   ```bash
   cp .env.example .env
   ```
   Verify local defaults: `APP_ENV=local`, `ALLOWED_ORIGINS=http://localhost,http://127.0.0.1`.

3. **Build and launch the five-container cluster:**
   ```bash
   docker compose up --build -d --scale backend=2 --wait
   ```

4. **Verify container cluster health:**
   ```bash
   docker compose ps
   # Output should confirm:
   # - gateway (port 80 published)
   # - frontend (unexposed)
   # - backend-1 (healthy)
   # - backend-2 (healthy)
   # - redis (healthy)
   ```

5. **Access Application:**
   Open `http://localhost` in two independent browser windows or incognito sessions.

---

## Containerized Test Suite Execution

All unit, contract, and integration tests execute inside the containerized test harness, guaranteeing identical results across Windows, macOS, and Linux CI runners.

```bash
# 1. Execute Unit & Contract Tests (Fast, in-memory)
docker compose -f docker-compose.test.yml run --rm test-runner pytest tests/unit tests/contracts -v

# 2. Execute Multi-Replica Integration Tests (Real Redis & dual backends)
docker compose -f docker-compose.test.yml run --rm test-runner pytest tests/integration -v

# 3. Generate Coverage Report
docker compose -f docker-compose.test.yml run --rm test-runner pytest --cov=app --cov-report=term-missing tests/
```

---

## Interactive CLI Debugging & Inspection Runbooks

### 1. Headless WebSocket Testing with `websocat`
Simulate a client joining the chat room directly from the command line:

```bash
# Connect with subprotocol chat.v1 and explicit origin
websocat --protocol chat.v1 --header "Origin: http://localhost" ws://localhost/ws/CLI_User_1
```
*Expected sequence upon connection:*
1. Receives session JSON envelope:
   ```json
   {"schema_version":1,"type":"session","connection_id":"...","container_id":"backend-1","user":"CLI_User_1","sent_at":"..."}
   ```
2. Type plain text and hit Enter: `Hello from CLI!`
3. Receives broadcast JSON envelope with `event_id` and `container_id`.

### 2. Live Redis Pub/Sub Inspection
Inspect the raw messages traversing the internal Redis event bus:

```bash
docker compose exec redis redis-cli SUBSCRIBE global_chat_channel
```
*Output displays real-time JSON publication envelopes as sent by backend replicas.*

### 3. Simulating a Slow Consumer (Backpressure Eviction Test)
Using `websocat` with artificial input stalls to trigger close code `1013`:

```bash
# Flood server from client 1 while client 2 pauses read loop
websocat --protocol chat.v1 --header "Origin: http://localhost" ws://localhost/ws/Reader_Stalled
# Suspend terminal process via Ctrl+Z; send 50 messages from another tab; resume process.
# Observe socket closed with code 1013 (Try Again Later).
```

### 4. Inspecting Dynamic Nginx Upstream Resolution
Verify that the Nginx gateway is dynamically resolving both backend replicas:

```bash
docker compose exec gateway nginx -T | grep -A 5 "upstream backend_cluster"
docker compose exec gateway cat /var/log/nginx/access.log | tail -n 20
```

---

## Windows & WSL2 Development Guidelines

1. **Line Endings:** Enforce LF line endings for all `.sh`, `.py`, and `.conf` files. Windows CRLF will cause Docker container entrypoints to crash with `\r: command not found`.
   ```bash
   git config core.autocrlf false
   git checkout -- .
   ```
2. **File Permissions:** Ensure executable scripts maintain chmod +x:
   ```bash
   chmod +x scripts/*.sh terraform/*.sh
   ```
3. **Docker Engine Backend:** In Docker Desktop settings, enable the WSL 2 based engine and assign at least 2 GiB RAM and 2 CPU cores to Docker.

---

## Code Quality & Pre-Commit Standards

Prior to opening a Pull Request, ensure all linters pass:
```bash
# Python linting and type checking (via test container)
docker compose -f docker-compose.test.yml run --rm test-runner ruff check app/ tests/
docker compose -f docker-compose.test.yml run --rm test-runner mypy app/

# Schema validation
docker compose -f docker-compose.test.yml run --rm test-runner check-jsonschema --schemafile schemas/events-v1.schema.json tests/fixtures/events/*.json
```

---

## Related Guides

[Project Structure](PROJECT_STRUCTURE.md) | [Testing](TESTING.md) | [Configuration](CONFIGURATION.md) | [Contributing](../CONTRIBUTING.md)

