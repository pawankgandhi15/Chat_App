# Configuration Reference

**Design revision 5 — 2026-10-26. Status: proposed contract.** This replaces the old Compose blueprint. Actual configuration files and manifests remain to be implemented.

## Backend settings


| Variable Name | Consumer | Type | Default | Allowed Values / Pattern | Secret? | Mutability |
| --- | --- | --- | --- | --- | --- | --- |
| `APP_ENV` | Backend / Scripts | String | `local` | `local`, `test`, `public` | No | Startup |
| `RELEASE_ID` | Backend / Observability | String | `development` | String, e.g. `20261025.1-sha.e95405e` | No | Startup |
| `ALLOWED_ORIGINS` | Backend | List[String] | `http://localhost:8080,http://127.0.0.1:8080` | Comma-separated full URIs (scheme + host + port) | No | Startup |
| `CHANNEL_NAME` | Backend | String | `global_chat_channel` | `^[a-z0-9_-]{3,64}$` | No | Startup |
| `REDIS_URL` | Backend (Local only) | AnyUrl | None; explicitly configured for isolated tests | Valid Redis URI (`redis://...`) | Sensitive | Startup |
| `REDIS_URL_FILE` | Backend (Local / Public) | FilePath | `None` | Path to mounted Kubernetes Secret file | File Secret | Startup |
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

Use `REDIS_URL_FILE` in local Kubernetes and AWS. Direct `REDIS_URL` is limited to isolated local/test harnesses; reject both sources being set together. Public mode requires a readable secret file, explicit origins, a verified release ID and non-example credentials. Never print a resolved Redis URI.

Validate settings once at startup. Reject malformed origins, wildcards in public mode, invalid channel names, non-positive limits and heartbeat intervals greater than or equal to the stale threshold. Require shutdown drain below the Pod termination grace. Freeze settings for the process lifetime.

## Kubernetes configuration ownership

| Setting | Owner | Change behavior |
| --- | --- | --- |
| Namespace `chat-app`, app labels, Service selectors | Base manifests | Review policy and service compatibility. |
| Replicas: gateway 1, frontend 1, backend 2, Redis 1 | Base Deployments | Measure changes before accepting higher load. |
| Image digests and release ID | Verified release bundle | Roll out all affected Pod templates. |
| Application settings | Release-specific ConfigMap | Hash/reference in Pod template triggers a rollout. |
| Redis credentials / ACL | Versioned Secret references | Rotate through a tested overlap/recovery procedure. |
| Public TLS certificate/key | Gateway-mounted Secret | Validate certificate and reload or replace gateway. |
| Origin / hostname | Environment overlay | Explicit localhost ports locally; real HTTPS origin on AWS. |
| K3s version, Traefik disable, encryption | Platform bootstrap | Separate platform change; not an application release. |

Do not rely on live ConfigMap edits taking effect automatically. Environment variables do not update in existing containers. Projected-file updates also require application reload behavior; versioned configuration references simplify rollback.

## Gateway and Service configuration

Gateway runs non-root on 8080/8443. Its LoadBalancer Service exposes 80/443 via K3s ServiceLB. Disable Traefik so it does not reserve these ports. Frontend Service port 80 targets 8080; backend uses 8000; Redis uses 6379.

Proxy `/` to `frontend.chat-app.svc.cluster.local:80` and WebSocket routes to `backend.chat-app.svc.cluster.local:8000`. Preserve Upgrade/Connection handling, disable inappropriate buffering and define tested idle/ping timeouts. Use cluster DNS, not Docker's resolver. Preserve stable Services during normal releases; test gateway behavior after Service recreation.

Overwrite forwarding headers; trust only the intended proxy boundary. Public `/live` and `/metrics` are blocked. Keep detailed `/health` cluster-private too; a separate minimal public status response is optional and must not expose replica or dependency details. Public TLS, origin validation and sanitized access logs are mandatory.

## Redis configuration

Use one ephemeral Redis Pod; disable RDB snapshots and AOF for message history. Kubernetes platform state is separate and persists on the EC2 root disk.

Start measurement with a 128Mi Redis container limit and a candidate `maxmemory` of 48 MiB, leaving space for process overhead and Pub/Sub buffers. This does not cap RSS. Configure explicit Pub/Sub output-buffer limits and disconnect slow subscribers; verify recovery. Candidate values must be tested under normal traffic, stalled subscribers and reconnect storms.

Disable the default user. Give the backend identity only the commands needed by its selected client and probes, with an exact Pub/Sub channel rule such as `&global_chat_channel`. Key-pattern rules beginning with `~` do not grant channel access. If heartbeat control traffic uses another channel, specify and grant that channel explicitly. Do not grant administrative commands or all channels. See [Redis ACL documentation](https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/).

Publisher pool size, transport frame buffering, ping intervals and internal heartbeat format remain implementation decisions requiring recorded bounds. Do not inherit unreviewed client defaults.

## Resource and lifecycle values

[Kubernetes](KUBERNETES.md) owns candidate CPU/memory requests and limits. Backend shutdown drain is 10s within 20s termination grace; account for hooks and asynchronous endpoint removal. Readiness uses `/health`; liveness and startup use `/live` with distinct thresholds.

Kubelet/containerd log rotation and image garbage collection replace Compose log-driver settings. Record node disk usage and configure measured retention. No runtime application Pod needs privileged mode, host networking, hostPath, a Docker socket or Kubernetes API access.

## Required validation

Render both overlays; reject unresolved variables, mutable public image tags, missing resource limits, plaintext secrets, invalid selectors and public backend/Redis exposure. Validate application settings in a container using the same release artifact. Test local origins with the actual mapped ports and public origins with the real TLS hostname.

Configuration correctness is a release gate, not evidence supplied by these examples. See [security](SECURITY.md), [testing](TESTING.md) and [deployment](DEPLOYMENT.md).

