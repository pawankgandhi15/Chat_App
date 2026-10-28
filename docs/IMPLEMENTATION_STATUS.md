# Implementation status and evidence

## Accounts and persistent conversations — 2026-10-28

- Added stable password accounts, revocable cookie sessions, searchable usernames, persistent direct conversations and saved message history. Guest v1/v2 remains separate.
- PostgreSQL is the deployment database; local tests use file-backed SQLite through the same SQLAlchemy Core model. Writes are authorized, sequenced and deduplicated within transactions. Redis publishes member-only invalidation hints after commit; periodic refresh repairs lost hints.
- Added a PostgreSQL platform Deployment/PVC/Service, schema initialization before local rollout, database network policy and release-secret requirements. App rollback leaves the database platform intact; local cluster deletion now requires explicit confirmation.
- Local persistence/security/concurrency and real-browser checks passed, including lost-response retries, returning recipients, history pagination and non-member rejection. The React build, existing client/guest-browser tests and rendered Kubernetes checks also passed. Browser account tests use real HTTP/WebSockets/SQLite and stubbed Redis; the cross-replica test uses the RESP Pub/Sub double.
- Recorded local suite results: **34 Python backend/integration tests, 10 JavaScript client tests and 6 Chromium browser tests passed** (50 total). One PostgreSQL test was skipped locally because no isolated PostgreSQL instance was available. The browser fixture uses the same WebSocket transport/drain path as the production entrypoint. These results are separate from the original 42-test/load benchmark below.
- A real PostgreSQL concurrency/persistence test and fresh PostgreSQL CI service are included. Docker is stopped, so the new PostgreSQL container, migrations under Kubernetes, persistent-volume recovery, AWS deployment, backup restore and updated load capacity have **not** been verified locally. The historical measurements below do not establish performance or reliability for saved chat.
- See [Accounts and history](ACCOUNTS_AND_HISTORY.md) for the complete current contract and limitations. There is no password recovery, E2EE, durable read receipt or verified real-world identity.

**Recorded: 2026-10-27.** The project now has a runnable application and local Kubernetes deployment. Historical design guides describe broader acceptance goals; this file records what has actually been implemented and checked.

## Direct messaging — 2026-10-28

- Added `chat.v2` with session discovery and one-to-one messages, while preserving the `chat.v1` public-room protocol. Direct events are published through Redis and delivered only to the addressed sender/recipient sessions.
- Added per-conversation drafts, unread indicators, offline state, and client-side validation. A private draft is held until the sender's own event appears; this is not a recipient acknowledgment.
- Browser, client and two-replica ASGI checks cover direct routing and observer isolation. The ASGI check uses a local RESP Pub/Sub test double; a real Redis container test has been added but was not run for this change. Existing Kubernetes, AWS, scan and performance evidence below predates this feature.
- Names remain unverified and sessions change on reconnect. Messages are ephemeral, are visible to the service/Redis, and are not end-to-end encrypted. See [Direct messaging](DIRECT_MESSAGING.md).

## React frontend migration — 2026-10-28

- Replaced the native DOM renderer with React 19 components and a Vite 8 build. Kept the existing wire parser, connection state machine and bounded memory store.
- Added lifecycle cleanup, React text rendering, controlled forms and scroll anchoring when older messages are evicted. The native DOM renderer and entrypoint were removed.
- Added an exact-version npm lockfile, loopback-only dev/preview commands, a digest-pinned Node build stage and CI install/build steps. Nginx continues serving the generated static bundle.
- Six existing JavaScript tests and three new Chromium tests with intercepted WebSockets passed locally. These cover session gating, malformed events, inert message content, keyboard/IME input, drafts across reconnect/rename, the 500-message cap, reading-position preservation and mobile layout.
- The production bundle was built and checked separately under the gateway CSP. These mocked browser checks do not establish real Redis/backend delivery. Full Docker/Kubernetes, image scans and load checks have not been rerun for the React migration; the dated baseline below remains historical evidence.

## Delivered

- Responsive anonymous chat UI with safe text rendering, exact `chat.v1` event validation, session-gated sending, bounded history, retry limits and preserved unsent drafts.
- FastAPI backend with real WebSocket transport limits, exact normalization, per-socket/replica rate budgets, bounded asynchronous fanout, Redis ACL authentication, heartbeat-based readiness and signal draining.
- Nginx static serving/gateway, container builds and digest-pinned base images.
- Local k3d and AWS K3s manifests: four Deployments, five application Pods, probes, resource limits, restricted containers and default-deny network isolation.
- Hashed Python dependency locks, Node/browser/integration tests, public smoke checks and a client-observed load harness.
- Terraform state/workload roots; manually triggered GitHub release/deploy workflows; image scans, SBOMs, signature verification, release hashes and restoration of the previous accepted bundle.
- Explicit operator Secret bootstrap and deployment RBAC.

## Local verification

| Check | Result |
| --- | --- |
| Python unit tests | 26 passed |
| JavaScript tests | 6 passed |
| Real Docker/Redis integration tests | 9 passed |
| Chromium desktop/mobile browser flow | 1 passed; screenshots saved locally |
| Public gateway smoke | Passed; first session, private diagnostics, required subprotocol and cross-replica chat |
| Kubernetes network isolation | Passed; allowed service paths and denied gateway/frontend access to Redis by Service and Pod IP |
| Kustomize | Both overlays render; namespace, references and security checks pass |
| Terraform | Both roots initialized without backend access and validated; AWS provider locked to 6.70.0 |
| Local rollout | Gateway, frontend, two backend Pods and Redis ready |
| Vulnerability scans | All four runtime images pass the fixable HIGH/CRITICAL gate with Trivy 0.76.1; reports in `artifacts/security/` |

The integration suite checks fragmented oversized messages, binary/control/overlength rejection, forbidden handshakes, identical cross-replica events, Redis outage/recovery without backend restart, SIGTERM close code 1012 and forbidden Redis commands/channels.

Browser evidence covers literal HTML-like text, two-tab messaging, disabled send before connection, draft retention across manual reconnect, no automatic resending and a 390-pixel layout without horizontal overflow. This is not a full accessibility audit or cross-browser certification.

The Baatchit rename was checked again with all 42 automated tests, both Kustomize overlays, event-schema consistency, public smoke and network-isolation checks. The app ran in the new `baatchit` namespace using `baatchit-*` local images, and the browser check verified the new title and wordmark. The load measurements and image scans below/above remain evidence from the initial implementation baseline; they were not repeated for the name-only changes.

## Short local load measurement

The 60-second steady-state run used 25 WebSocket clients split 13/12 across replicas, 5 aggregate messages/second and 512-byte payloads after a 5-second warmup:

| Metric | Observed |
| --- | --- |
| Published test messages | 300 |
| Expected / observed fanout deliveries | 7,500 / 7,500 |
| Delivered within 2 seconds | 100% |
| Client-observed p95 / p99 | Approximately 16 / 16 ms |
| Duplicates / reader errors | 0 / 0 |

Raw evidence: ignored `artifacts/load-local.json`. This uses the Windows host's monotonic clock and a local Docker/Kubernetes network. It does **not** establish internet latency, EC2 capacity, sustained 30-minute behavior or the 512 MiB available-node-memory target.

Reproduce with `python scripts/load.py --warmup 5 --duration 60 --output artifacts/load-local.json`. The default command runs the longer specified workload, but cloud acceptance also needs independent resource and cost measurements.

## Remaining environment-dependent acceptance

- AWS plan/apply, actual account eligibility, credit balance and budget alerts.
- Real DNS/TLS, certificate renewal and credential lifecycle.
- GitHub Actions execution, registry access, OIDC signing and signed remote deployment.
- Successful and intentionally failed signed-release/rollback rehearsals.
- Full 2-minute warmup + 30-minute off-node AWS load run, node memory/headroom, recovery timing and reboot testing.
- Broader browser/accessibility testing, internet abuse handling and operational alert routing.

The repository contains implementation for these workflows, but an implementation is not evidence that an external environment is configured correctly. No AWS resources have been provisioned. The initial implementation was pushed as commit `09cca07`; Baatchit branding is a subsequent change.

## Decisions reconciled during implementation

- No NFC/NFKC normalization; the API's exact newline/ASCII-trim contract is followed.
- `ALLOWED_ORIGINS` is comma-separated text; no automatic .env loader.
- Browser retries use the frontend specification's 500 ms base / 15-second cap.
- Redis output buffers use 4 MiB hard / 1 MiB soft for 10 seconds to fit the container budget.
- React/Vite now emits content-hashed assets. Nginx retains conservative `no-cache` asset revalidation and `no-store` HTML; the original stable filenames are no longer used.
- Gateway/frontend/Redis use Recreate; the project does not claim zero-downtime full releases.
- Metrics are private per-process Prometheus series. A persistent metrics server/dashboard and cloud alert delivery are not bundled.
- Single-node Kubernetes demonstrates replica messaging but cannot tolerate loss of the host.
- The Nginx base required explicit Alpine brotli/curl library upgrades to remove two reported CVEs. Fixed package versions are pinned in both Dockerfiles and were rescanned successfully. This gate excludes unfixed and lower-severity findings; it is not a claim of no vulnerabilities.
