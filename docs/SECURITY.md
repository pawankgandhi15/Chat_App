# Security Plan and Threat Model

**Status:** Security controls, threat modeling, and container hardening specifications. See the [documentation index](../README.md).

**Design Revision 4 (2026-10-25):** Comprehensive security architecture establishing formal STRIDE threat modeling, strict Content Security Policy Level 3, Linux capability pruning, Redis ACL sandboxing, and OCI cryptographic provenance verification.

---

## STRIDE Threat Modeling & Control Matrix

| STRIDE Category | Threat Scenario | Architectural Mitigation Control | Verification Evidence |
| --- | --- | --- | --- |
| **Spoofing** | Attacker spoofs `X-Forwarded-For` or `Origin` headers to bypass rate limits or CORS. | Gateway strips and overwrites client-supplied forwarding headers using `$remote_addr`. Backend validates `Origin` against strict whitelist before ASGI upgrade. | Spoofed header curl probes; rejected origins return HTTP 403. |
| **Tampering** | Attacker injects HTML/JavaScript into message text to execute XSS in other clients. | DOM updates exclusively use `element.textContent` via `SafeDOM` module; raw HTML tags render as literal strings. Strict CSP blocks inline scripts. | Synthetic XSS payload injection (`<script>`, `<img>`, `svg onload`); zero script execution. |
| **Repudiation** | User claims they did not send a disruptive broadcast. | Server assigns immutable UUIDv4 `event_id` and UTC timestamp at Redis publish time; structured logs capture correlation ID. | Correlation between server log and client broadcast envelope. |
| **Information Disclosure** | Public attacker scrapes internal performance counters or Redis credentials via `/metrics` or `/health`. | Gateway explicitly intercepts and drops `/live` and `/metrics` with HTTP 403. Health responses scrub exception traces and connection strings. | External curl to `http://gateway/metrics` returns 403; internal curl returns OpenMetrics. |
| **Denial of Service** | Malicious client floods 10,000 msgs/s or holds socket write loop open to starve server memory. | Per-socket token bucket (2 msg/s, burst 5), replica publish budget (20 msg/s), and outbound queue caps (32 events / 256 KiB) with 1013 disconnect. | Flood tests trigger close code 1013; memory stays within 192 MiB container ceiling. |
| **Elevation of Privilege** | Attacker exploits an ASGI or Python vulnerability to gain root execution on the EC2 host. | Backend executes as non-root unprivileged user `chatapp` (UID 10001); drops all Linux capabilities (`cap_drop: [ALL]`); read-only container root. | Container escape attempt fails; `id` returns 10001; root filesystem write fails with EROFS. |

---

## Browser Security & Content Security Policy (CSP Level 3)

The Nginx gateway and frontend serve strict HTTP response headers designed to prevent clickjacking, MIME sniffing, and script injection:

```nginx
# Nginx Gateway Security Headers
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "geolocation=(), camera=(), microphone=(), payment=()" always;

# Strict CSP Level 3: Zero inline code, zero eval, same-origin only
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' ws: wss:; img-src 'self' data:; font-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self';" always;

# HSTS: Enforced only on public HTTPS endpoints
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
```

---

## Container Security & Linux Capability Pruning

All application containers in production Compose enforce least-privilege runtime security profiles:

```yaml
# Security Profile Snippet for backend in docker-compose.prod.yml
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
cap_add:
  - NET_BIND_SERVICE  # Only if binding to privileged ports (gateway only)
read_only: true
tmpfs:
  - /tmp:rw,noexec,nosuid,size=16m
user: "10001:10001"
```

### Security Rationale:
1. **`cap_drop: [ALL]`:** Strips all 41 Linux capabilities (including `CAP_SYS_ADMIN`, `CAP_NET_ADMIN`, `CAP_CHOWN`), neutralizing kernel privilege escalation attacks.
2. **`read_only: true`:** Prevents malware persistence by ensuring container root filesystem cannot be modified.
3. **`no-new-privileges:true`:** Prevents setuid binaries inside the container from gaining elevated privileges.

---

## Redis ACL Hardening & Ephemeral Bus Security

The default unauthenticated Redis mode is completely disabled in production. A dedicated, sandboxed application ACL profile is enforced:

```text
# redis/users.acl
user default off
user chatapp on >${REDIS_PASSWORD} ~global_chat_* +ping +publish +subscribe +unsubscribe +client|setname +client|id
```

### Access Control Rules:
- **No Key Storage Access:** Commands such as `SET`, `GET`, `KEYS`, `DEL`, and `SCAN` are blocked.
- **No Administrative Control:** `FLUSHALL`, `CONFIG`, `SHUTDOWN`, and `DEBUG` are blocked and renamed to empty strings.
- **Channel Scoping:** Publication and subscription are strictly locked to the glob pattern `~global_chat_*`.
- **Secret Mounting:** Passwords are never committed to Git or passed as plain environment variables; they are injected via Docker secret files (`REDIS_URL_FILE`).

---

## Supply Chain Integrity & OCI Attestation Pipeline

1. **Digest Immutability:** Mutable tags (`:latest`) are forbidden in production deployments. All services resolve exact OCI SHA-256 digests (`@sha256:...`).
2. **Static Vulnerability Scanning:** Automated Trivy scan runs on every build; blocks releases if any `HIGH` or `CRITICAL` vulnerabilities with an available patch exist.
3. **Software Bill of Materials (SBOM):** Generated in CycloneDX format during CI; attached to release artifacts.
4. **Cosign Keyless Signatures:** Employs Sigstore Cosign via GitHub Actions OpenID Connect (OIDC) identity to cryptographically verify image provenance before deployment.

---

## Secret Rotation Runbook

| Secret Entity | Rotation Procedure | Service Impact |
| --- | --- | --- |
| **Redis Password** | 1. Add secondary user to `users.acl`.<br>2. Update `redis_url.secret` and redeploy backends.<br>3. Remove deprecated user from Redis. | Zero downtime; backend re-establishes connection. |
| **EC2 Deploy SSH Key** | 1. Generate new Ed25519 keypair.<br>2. Append public key to `/home/ubuntu/.ssh/authorized_keys`.<br>3. Update GitHub Actions secret `EC2_SSH_KEY`.<br>4. Remove old public key. | Zero downtime. |
| **Let's Encrypt TLS Key** | Automated via `certbot renew` cron; reloads Nginx via `docker exec gateway nginx -s reload`. | Zero connection drops; in-flight WebSockets persist. |

---

## Related Guides

[Requirements](REQUIREMENTS.md) | [Architecture](ARCHITECTURE.md) | [Configuration](CONFIGURATION.md) | [CI/CD](CICD.md) | [Operations](OPERATIONS.md)

