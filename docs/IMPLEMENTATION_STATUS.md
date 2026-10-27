# Implementation status and evidence

**Recorded: 2026-10-27.** The project now has a runnable application and local Kubernetes deployment. Historical design guides describe broader acceptance goals; this file records what has actually been implemented and checked.

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

The repository contains implementation for these workflows, but an implementation is not evidence that an external environment is configured correctly. No AWS resources have been provisioned and no changes have been pushed by this implementation task.

## Decisions reconciled during implementation

- No NFC/NFKC normalization; the API's exact newline/ASCII-trim contract is followed.
- `ALLOWED_ORIGINS` is comma-separated text; no automatic .env loader.
- Browser retries use the frontend specification's 500 ms base / 15-second cap.
- Redis output buffers use 4 MiB hard / 1 MiB soft for 10 seconds to fit the container budget.
- Asset names are stable, so assets revalidate instead of using immutable long-lived caching.
- Gateway/frontend/Redis use Recreate; the project does not claim zero-downtime full releases.
- Metrics are private per-process Prometheus series. A persistent metrics server/dashboard and cloud alert delivery are not bundled.
- Single-node Kubernetes demonstrates replica messaging but cannot tolerate loss of the host.
- The Nginx base required explicit Alpine brotli/curl library upgrades to remove two reported CVEs. Fixed package versions are pinned in both Dockerfiles and were rescanned successfully. This gate excludes unfixed and lower-severity findings; it is not a claim of no vulnerabilities.
