# Configuration Reference & Environment Contract

**Design Revision 5 — 2026-10-26. Status: Production Architecture Specification.** This document defines the configuration contracts, environment variables, secret mounts, and runtime validation rules for all Chat App components.

---

## 1. Backend Application Settings Contract

Configuration is managed via Pydantic V2 `BaseSettings`, validated strictly during application initialization. If any configuration variable fails regex validation, bounds checking, or file existence validation, **the application process terminates immediately with exit code 1**.

```python
# Conceptual Pydantic V2 Settings Model
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AnyUrl, FilePath, field_validator
from typing import List, Optional

class Settings(BaseSettings):
    app_env: str = Field(default="local", pattern=r"^(local|test|public)$")
    release_id: str = Field(default="development", min_length=1, max_length=64)
    allowed_origins: List[str] = Field(default=["http://localhost:8080", "http://127.0.0.1:8080"])
    channel_name: str = Field(default="global_chat_channel", pattern=r"^[a-z0-9_-]{3,64}$")
    redis_url: Optional[AnyUrl] = None
    redis_url_file: Optional[FilePath] = None
    max_connections_per_replica: int = Field(default=64, ge=10, le=256)
    rate_messages_per_second: float = Field(default=2.0, ge=0.5, le=10.0)
    rate_burst: int = Field(default=5, ge=1, le=20)
    publish_rate_per_second: float = Field(default=20.0, ge=5.0, le=100.0)
    publish_burst: int = Field(default=40, ge=10, le=200)
    outbound_queue_events: int = Field(default=32, ge=8, le=128)
    outbound_queue_bytes: int = Field(default=262144, ge=65536, le=1048576)
    send_timeout_seconds: float = Field(default=2.0, ge=0.5, le=10.0)
    redis_command_timeout_seconds: float = Field(default=1.0, ge=0.2, le=5.0)
    subscriber_heartbeat_seconds: float = Field(default=5.0, ge=1.0, le=15.0)
    subscriber_stale_seconds: float = Field(default=10.0, ge=3.0, le=30.0)
    shutdown_drain_seconds: float = Field(default=10.0, ge=2.0, le=15.0)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="forbid")
```

### Comprehensive Settings Reference

| Variable Name | Consumer | Type | Default | Allowed Range / Pattern | Secret? | Mutability |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `APP_ENV` | Backend / Scripts | String | `local` | `local`, `test`, `public` | No | Startup |
| `RELEASE_ID` | Backend / Telemetry | String | `development` | Alphanumeric commit/date string | No | Startup |
| `ALLOWED_ORIGINS` | Backend Handshake | List[String] | `http://localhost:8080` | Comma-separated full URIs (scheme+host+port) | No | Startup |
| `CHANNEL_NAME` | Backend / Broker | String | `global_chat_channel` | `^[a-z0-9_-]{3,64}$` | No | Startup |
| `REDIS_URL` | Backend (Local dev) | AnyUrl | `None` | Valid Redis URI (`redis://user:pass@host:port/0`) | Sensitive | Startup |
| `REDIS_URL_FILE` | Backend (Kubernetes) | FilePath | `None` | Path to mounted secret file (`/etc/secrets/redis/url`) | File Secret | Startup |
| `MAX_CONNECTIONS_PER_REPLICA` | Backend Admission | Integer | `64` | `10` to `256` | No | Startup |
| `RATE_MESSAGES_PER_SECOND` | Socket Limiter | Float | `2.0` | `0.5` to `10.0` (Token bucket refill rate) | No | Startup |
| `RATE_BURST` | Socket Limiter | Integer | `5` | `1` to `20` (Token bucket burst capacity) | No | Startup |
| `PUBLISH_RATE_PER_SECOND` | Replica Limiter | Float | `20.0` | `5.0` to `100.0` (Replica shared budget) | No | Startup |
| `PUBLISH_BURST` | Replica Limiter | Integer | `40` | `10` to `200` (Replica burst capacity) | No | Startup |
| `OUTBOUND_QUEUE_EVENTS` | Session Queue | Integer | `32` | `8` to `128` (Per-socket queued events) | No | Startup |
| `OUTBOUND_QUEUE_BYTES` | Session Queue | Integer | `262144` | `65536` to `1048576` (256 KiB default) | No | Startup |
| `SEND_TIMEOUT_SECONDS` | Writer Task | Float | `2.0` | `0.5` to `10.0` | No | Startup |
| `REDIS_COMMAND_TIMEOUT_SECONDS`| Broker Pool | Float | `1.0` | `0.2` to `5.0` | No | Startup |
| `SUBSCRIBER_HEARTBEAT_SECONDS` | Broker Watchdog | Float | `5.0` | `1.0` to `15.0` | No | Startup |
| `SUBSCRIBER_STALE_SECONDS` | Broker Watchdog | Float | `10.0` | `3.0` to `30.0` (Must be > heartbeat interval) | No | Startup |
| `SHUTDOWN_DRAIN_SECONDS` | Lifecycle Manager | Float | `10.0` | `2.0` to `15.0` (Must be < Pod termination grace) | No | Startup |

---

## 2. Dual Secret Resolution Mechanics

To adhere to enterprise security guidelines, **credentials must never appear in environment variables or process table listings** (`/proc/$PID/environ`).

```mermaid
flowchart TD
    Start["Application Startup: Resolve Credentials"] --> CheckEnv{"Is REDIS_URL_FILE defined?"}
    
    CheckEnv -->|Yes: Production Mode| ReadFile["Read Secret File from Mounted Volume<br/>(e.g., /etc/secrets/redis/url)"]
    ReadFile --> ValidateFile{"File exists, readable, non-empty,<br/>and contains valid redis:// URI?"}
    ValidateFile -->|Yes| ParseSecret["Parse Redis Credentials into Memory"]
    ValidateFile -->|No| FatalFile["Fatal Error: Corrupt or missing Secret File<br/>Exit Code 1"]

    CheckEnv -->|No| CheckLocal{"Is APP_ENV == 'local' AND<br/>REDIS_URL defined?"}
    CheckLocal -->|Yes: Dev Bypass| ParseEnv["Parse Local Dev URI"]
    CheckLocal -->|No| FatalNoAuth["Fatal Error: No Secret File configured in non-local environment<br/>Exit Code 1"]

    ParseSecret --> Scrub["Scrub temporary buffers; never log URI"]
    ParseEnv --> Scrub
    Scrub --> Success["Proceed to Broker Handshake"]

    classDef pass fill:#064e3b,stroke:#059669,stroke-width:2px,color:#ffffff;
    classDef fail fill:#7f1d1d,stroke:#dc2626,stroke-width:2px,color:#ffffff;
    class CheckEnv,ReadFile,ValidateFile,CheckLocal,ParseSecret,ParseEnv,Scrub,Success pass;
    class FatalFile,FatalNoAuth fail;
```

---

## 3. Kubernetes Manifest Configuration & Injection

Configuration is decoupled into **Base ConfigMaps** (non-sensitive properties) and **Encrypted Secrets** (credentials), managed via Kustomize:

```mermaid
flowchart LR
    subgraph ConfigSources["Configuration Sources"]
        CM["ConfigMap: backend-config<br/><i>(APP_ENV, LIMITS, CHANNELS)</i>"]
        SEC["Secret: redis-credentials<br/><i>(Encrypted at rest via K3s)</i>"]
        TLS["Secret: gateway-tls<br/><i>(TLS Cert & Private Key)</i>"]
    end

    subgraph Pods["Target Kubernetes Pods"]
        BE["FastAPI Backend Pods<br/><i>(Mounts Secret at /etc/secrets/redis)</i>"]
        GW["Nginx Gateway Pod<br/><i>(Mounts Secret at /etc/ssl/certs)</i>"]
    end

    CM -->|Injected via envFrom| BE
    SEC -->|Mounted as volume file| BE
    TLS -->|Mounted as volume file| GW
```

---

## 4. Nginx Gateway Reverse Proxy Configuration Blueprint

The Nginx gateway (`gateway/nginx.conf`) runs as an unprivileged container, proxying static assets and WebSocket streams:

```nginx
worker_processes auto;
pid /tmp/nginx.pid;
error_log /var/log/nginx/error.log warn;

events {
    worker_connections 2048;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    # Hide Nginx version banner
    server_tokens off;

    # Performance optimizations
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;

    # Upstream clusters using Kubernetes ClusterIP DNS
    upstream backend_cluster {
        server backend.chat-app.svc.cluster.local:8000;
        keepalive 32;
    }

    upstream frontend_cluster {
        server frontend.chat-app.svc.cluster.local:80;
        keepalive 16;
    }

    # Port 80: HTTP Redirect to HTTPS
    server {
        listen 8080 default_server;
        server_name _;
        return 301 https://$host$request_uri;
    }

    # Port 443: HTTPS & WSS Termination
    server {
        listen 8443 ssl default_server;
        server_name _;

        ssl_certificate /etc/ssl/certs/tls.crt;
        ssl_certificate_key /etc/ssl/certs/tls.key;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
        ssl_prefer_server_ciphers on;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 1d;

        # Static Frontend Assets
        location / {
            proxy_pass http://frontend_cluster;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # WebSocket Upgrade Route
        location /ws/ {
            proxy_pass http://backend_cluster;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "Upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
            proxy_buffering off;
        }

        # Security Blockade: Private Internal Endpoints Denied
        location ~ ^/(metrics|live|health) {
            deny all;
            return 403;
        }
    }
}
```

---

## 5. Redis Broker Configuration Blueprint

Redis (`redis/redis.conf`) runs as an isolated, in-memory ephemeral broker:

```ini
# Network Binding
bind 0.0.0.0
port 6379
protected-mode yes

# Disable Persistence (Ephemeral Chat)
save ""
appendonly no

# Memory Bounds & Eviction Policy
maxmemory 48mb
maxmemory-policy noeviction

# Pub/Sub Output Buffer Protection (Hard: 32MB, Soft: 8MB for 60s)
client-output-buffer-limit pubsub 32mb 8mb 60

# Logging & Daemonization
loglevel notice
daemonize no

# TCP Keepalive & Backlog
tcp-keepalive 300
tcp-backlog 511
```
