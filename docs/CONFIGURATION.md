# Configuration reference

This reference describes the implemented code as of 2026-10-27. [Settings](../backend/app/settings.py), [Kubernetes defaults](../k8s/base/kustomization.yaml) and the [API specification](API_SPECIFICATION.md) are the relevant implementation contracts. Settings are read once at startup and validated before the server starts.

## Backend settings

| Environment variable | Default | Bounds / behavior |
| --- | --- | --- |
| `APP_ENV` | `local` | `local`, `test` or `public` |
| `RELEASE_ID` | `development` | 1–64 characters; public mode rejects `development` |
| `ALLOWED_ORIGINS` | `http://localhost:8080,http://127.0.0.1:8080` | Comma-separated exact HTTP(S) origins, without paths, wildcards or credentials; public mode requires HTTPS |
| `CHANNEL_NAME` | `global_chat_channel` | Lowercase letters, digits, underscores/hyphens; 3–64 characters; ACL must match |
| `REDIS_URL` | Unset | Local/test convenience; secret value excluded from settings representation |
| `REDIS_URL_FILE` | Unset | UTF-8 file containing the connection URI; required in public mode |
| `MAX_CONNECTIONS_PER_REPLICA` | `64` | 10–256 |
| `RATE_MESSAGES_PER_SECOND` | `2` | 0.5–10 per socket |
| `RATE_BURST` | `5` | 1–20 |
| `PUBLISH_RATE_PER_SECOND` | `20` | 5–100 per replica |
| `PUBLISH_BURST` | `40` | 10–200 |
| `OUTBOUND_QUEUE_EVENTS` | `32` | 8–128 per socket |
| `OUTBOUND_QUEUE_BYTES` | `262144` | 65536–1048576 serialized UTF-8 bytes per socket |
| `SEND_TIMEOUT_SECONDS` | `2` | 0.5–10 |
| `REDIS_COMMAND_TIMEOUT_SECONDS` | `1` | 0.2–5 |
| `SUBSCRIBER_HEARTBEAT_SECONDS` | `5` | 1–15 |
| `SUBSCRIBER_STALE_SECONDS` | `10` | 3–30; must exceed heartbeat interval |
| `SHUTDOWN_DRAIN_SECONDS` | `10` | 2–15; keep below Pod termination grace of 20 seconds |

Set exactly one Redis source. Neither silently overrides the other. The URI must use `redis://` or `rediss://`, database zero, and no query or fragment. Public mode also requires a username and password. Kubernetes mounts `redis-url` at `/etc/secrets/redis/url`. The application does not automatically load a `.env` file.

The settings model ignores unrelated environment variables. Invalid configured values stop startup with a generic error so input values and credentials are not printed.

## Fixed wire and transport rules

- Username: ASCII `[A-Za-z0-9_-]{1,32}`.
- WebSocket subprotocol: `chat.v1`, required at handshake.
- Maximum reassembled frame payload: 16,384 bytes, enforced by the canonical Uvicorn entrypoint.
- Maximum normalized text: 2,000 Unicode code points.
- Convert CRLF/lone CR to LF; trim ASCII space, tab, CR and LF only. No NFC/NFKC conversion.
- C0 controls other than tab/LF and DEL are rejected. Empty normalized text is ignored but consumes the socket rate budget.
- Compression is disabled; transport receive queue is four messages; ping interval/timeout are 20 seconds.
- Publication is never retried after an ambiguous failure. Redis Pub/Sub cannot replay lost messages.

## Secrets and Redis

| Secret | Key | Consumer |
| --- | --- | --- |
| `redis-url` | `url` | Backend |
| `redis-auth` | `users.acl` | Redis |
| `gateway-tls` | `tls.crt`, `tls.key` | AWS gateway |

`scripts/local.py up` generates a random local Redis password and stores only its SHA-256 hash in the ACL. `scripts/bootstrap_secrets.py` provides the separate operator path for a selected AWS cluster.

Redis permits the application user only `PING`, `PUBLISH`, `SUBSCRIBE` and `UNSUBSCRIBE` on `global_chat_channel`. The default user is disabled. The client explicitly uses RESP2 and disables library metadata commands to stay within that ACL.

Redis persistence is off. Its configured `maxmemory` is 48 MiB and its Pub/Sub output buffer hard/soft limits are **4 MiB / 1 MiB for 10 seconds**. These are lower than the earlier design examples to fit the 128 MiB container limit. Pub/Sub output buffers require their own limits; `maxmemory` alone is insufficient.

## Kubernetes and gateway

| Component | Replicas | CPU request / limit | Memory request / limit |
| --- | --- | --- | --- |
| Gateway | 1 | 50m / 250m | 32 / 64 MiB |
| Frontend | 1 | 25m / 100m | 16 / 48 MiB |
| Backend | 2 | 100m / 500m each | 128 / 256 MiB each |
| Redis | 1 | 50m / 250m | 64 / 128 MiB |

Application requests total 368 MiB; limits total 752 MiB. Kubernetes, OS and filesystem cache are additional.

All application containers run as non-root with read-only root filesystems, dropped capabilities, no privilege escalation, RuntimeDefault seccomp and no mounted service-account token. Writable temporary directories use bounded emptyDir volumes. NetworkPolicies default to deny and allow the explicit service paths and cluster DNS.

Local entry is HTTP on loopback port 8080. AWS entry uses ports 80/443 mapped to non-root gateway ports 8080/8443. HTTP redirects to HTTPS except `/ready`. Only the gateway is public. `/health`, `/live` and `/metrics` are blocked at the gateway.

The gateway limits handshakes to 5/second per observed peer IP with a burst of 20. K3s ServiceLB may translate client addresses, so this is a coarse shared protection rather than an authenticated per-user quota.

## Browser behavior

The client waits for the first session event before enabling send. It retains up to 500 events in memory and preserves unsent drafts during reconnects; nothing is persisted in browser storage.

Retries use full jitter with a 500 ms base and a 15-second cap, at most 10 attempts. A stable 30-second session resets the attempt count. Close code 1012 uses a 0–500 ms jitter window. Terminal protocol/policy closures require manual action. The browser never automatically resends submitted messages.

Static HTML uses `Cache-Control: no-store` and assets use `no-cache` because their filenames are not content-hashed. TLS certificates are operator-supplied; renewal is not automated.

## Release configuration

`k8s/overlays/aws` deliberately contains invalid placeholders and must not be applied directly. `scripts/release.py render` injects an actual HTTPS origin, release ID and all four immutable image digests. It hashes configuration and bundle contents. `scripts/deploy.py` verifies the signed bundle and images before applying it.

Changing a Secret does not create a new release automatically. Coordinate Redis URL/ACL rotation and restart consumers; TLS rotation requires a gateway restart. Protect and retain previous release artifacts for rollback.
