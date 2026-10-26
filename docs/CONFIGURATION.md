# Configuration Reference

**Status:** Proposed configuration contract and production blueprints. See the [documentation index](../README.md).

**Design Revision 4 (2026-10-25):** Exhaustive specification of environment variables, Pydantic type validations, hardened container security profiles, and production configuration blueprints for Nginx, Redis, and Docker Compose.

---

## Environment Variable Master Matrix

| Variable Name | Consumer | Type | Default | Allowed Values / Pattern | Secret? | Mutability |
| --- | --- | --- | --- | --- | --- | --- |
| `APP_ENV` | Backend / Scripts | String | `local` | `local`, `test`, `public` | No | Startup |
| `RELEASE_ID` | Backend / Observability | String | `development` | String, e.g. `20261025.1-sha.e95405e` | No | Startup |
| `ALLOWED_ORIGINS` | Backend | List[String] | `http://localhost,http://127.0.0.1` | Comma-separated full URIs (scheme + host + port) | No | Startup |
| `CHANNEL_NAME` | Backend | String | `global_chat_channel` | `^[a-z0-9_-]{3,64}$` | No | Startup |
| `REDIS_URL` | Backend (Local only) | AnyUrl | `redis://redis:6379/0` | Valid Redis URI (`redis://...`) | Sensitive | Startup |
| `REDIS_URL_FILE` | Backend (Public only) | FilePath | `None` | Path to mounted Docker secret file | File Secret | Startup |
| `MAX_CONNECTIONS_PER_REPLICA` | Backend | Integer | `64` | `10` to `256` | No | Startup |
| `RATE_MESSAGES_PER_SECOND` | Backend | Float | `2.0` | `0.5` to `10.0` (Token bucket refill rate) | No | Startup |
| `RATE_BURST` | Backend | Integer | `5` | `1` to `20` (Token bucket burst capacity) | No | Startup |
| `PUBLISH_RATE_PER_SECOND` | Backend | Float | `20.0` | `5.0` to `100.0` (Replica shared budget) | No | Startup |
| `PUBLISH_BURST` | Backend | Integer | `40` | `10` to `200` (Replica burst capacity) | No | Startup |
| `OUTBOUND_QUEUE_EVENTS` | Backend | Integer | `32` | `8` to `128` (Per-socket queued events) | No | Startup |
| `OUTBOUND_QUEUE_BYTES` | Backend | Integer | `262144` | `65536` to `1048576` (256 KiB default) | No | Startup |
| `SEND_TIMEOUT_SECONDS` | Backend | Float | `2.0` | `0.5` to `10.0` | No | Startup |
| `REDIS_COMMAND_TIMEOUT_SECONDS`| Backend | Float | `1.0` | `0.2` to `5.0` | No | Startup |
| `SUBSCRIBER_HEARTBEAT_SECONDS` | Backend | Float | `5.0` | `1.0` to `15.0` | No | Startup |
| `SUBSCRIBER_STALE_SECONDS` | Backend | Float | `10.0` | `3.0` to `30.0` | No | Startup |
| `SHUTDOWN_DRAIN_SECONDS` | Backend | Float | `10.0` | `2.0` to `15.0` (Must be < stop grace) | No | Startup |
| `COMPOSE_PROJECT_NAME` | Docker Compose | String | `chat-app` | Stable project namespace | No | Deployment |

---

## Production Docker Compose Blueprint (`docker-compose.prod.yml`)

The production Compose configuration enforces strict container resource constraints, unprivileged security contexts, and dual-network segmentation:

```yaml
version: "3.8"

networks:
  edge_network:
    name: chat_app_edge
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/24
  data_network:
    name: chat_app_data
    driver: bridge
    internal: true
    ipam:
      config:
        - subnet: 172.28.1.0/24

secrets:
  redis_url:
    file: /etc/chat-app/secrets/redis_url.secret

services:
  gateway:
    image: ${GATEWAY_IMAGE}  # Pin by @sha256 digest
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    networks:
      - edge_network
    deploy:
      resources:
        limits:
          cpus: "0.25"
          memory: 48M
    security_opt:
      - no-new-privileges:true
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  frontend:
    image: ${FRONTEND_IMAGE}  # Pin by @sha256 digest
    restart: unless-stopped
    networks:
      - edge_network
    deploy:
      resources:
        limits:
          cpus: "0.10"
          memory: 32M
    security_opt:
      - no-new-privileges:true
    read_only: true
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  backend:
    image: ${BACKEND_IMAGE}  # Pin by @sha256 digest
    restart: unless-stopped
    stop_grace_period: 20s
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: "0.35"
          memory: 192M
    secrets:
      - redis_url
    environment:
      APP_ENV: public
      RELEASE_ID: ${RELEASE_ID}
      REDIS_URL_FILE: /run/secrets/redis_url
      ALLOWED_ORIGINS: ${ALLOWED_ORIGINS}
      CHANNEL_NAME: global_chat_channel
    networks:
      - edge_network
      - data_network
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=16m
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  redis:
    image: ${REDIS_IMAGE}  # Pin by @sha256 digest
    restart: unless-stopped
    volumes:
      - ./redis/redis.conf:/usr/local/etc/redis/redis.conf:ro
      - ./redis/users.acl:/usr/local/etc/redis/users.acl:ro
    command: ["redis-server", "/usr/local/etc/redis/redis.conf"]
    networks:
      - data_network
    deploy:
      resources:
        limits:
          cpus: "0.20"
          memory: 64M
    security_opt:
      - no-new-privileges:true
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

---

## Hardened Redis Configuration (`redis.conf` & ACLs)

To guarantee zero persistence overhead, strict memory capping, and command isolation on `t3.micro`:

```ini
# /usr/local/etc/redis/redis.conf
port 6379
bind 0.0.0.0
protected-mode yes

# Zero persistence (ephemeral message bus)
save ""
appendonly no

# Memory limits & evictions
maxmemory 64mb
maxmemory-policy noeviction

# Subscriber client buffer limits (hard: 8MB, soft: 4MB for 10s)
client-output-buffer-limit pubsub 8mb 4mb 10
maxclients 64

# Security: Disable legacy dangerous commands
rename-command FLUSHALL ""
rename-command FLUSHDB ""
rename-command CONFIG ""
rename-command KEYS ""
rename-command SHUTDOWN ""

# ACL Authentication
aclfile /usr/local/etc/redis/users.acl
```

### Redis ACL Specification (`users.acl`)
```text
# Disable default unauthenticated user
user default off

# Dedicated application user with minimal Pub/Sub and health-check privileges
user chatapp on >SecureRandomPass123! ~global_chat_* +ping +publish +subscribe +unsubscribe +client|setname +client|id
```

---

## Hardened Nginx Gateway Configuration (`nginx.conf`)

```nginx
events {
    worker_connections 256;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Dynamic DNS resolver for Compose internal network
    resolver 127.0.0.11 valid=5s ipv6=off;

    # Rate limiting & connection limiting zones
    limit_req_zone $binary_remote_addr zone=ws_limit:10m rate=5r/s;
    limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

    # Upstream clusters with dynamic resolution
    upstream backend_cluster {
        zone backend_zone 64k;
        server backend:8000 resolve;
        keepalive 16;
    }

    upstream frontend_cluster {
        zone frontend_zone 64k;
        server frontend:80 resolve;
    }

    map $http_upgrade $connection_upgrade {
        default upgrade;
        '' close;
    }

    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name _;

        ssl_certificate /etc/letsencrypt/live/chat.example.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/chat.example.com/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # Security Headers
        add_header X-Frame-Options "DENY" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
        add_header Content-Security-Policy "default-src 'self'; connect-src 'self' wss:; script-src 'self'; style-src 'self';" always;

        # Deny private internal diagnostics endpoints from public internet
        location ~ ^/(live|metrics) {
            return 403;
        }

        # WebSocket chat endpoint
        location /ws/ {
            limit_req zone=ws_limit burst=10 nodelay;
            limit_conn conn_limit 32;

            proxy_pass http://backend_cluster;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            proxy_read_timeout 75s;
            proxy_send_timeout 75s;
            proxy_next_upstream error timeout http_502 http_503;
        }

        # Health endpoint
        location = /health {
            proxy_pass http://backend_cluster;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_read_timeout 5s;
        }

        # Frontend static assets
        location / {
            proxy_pass http://frontend_cluster;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
        }
    }
}
```

---

## Related Guides

[Requirements](REQUIREMENTS.md) | [Architecture](ARCHITECTURE.md) | [Security](SECURITY.md) | [Deployment](DEPLOYMENT.md) | [Operations](OPERATIONS.md)

