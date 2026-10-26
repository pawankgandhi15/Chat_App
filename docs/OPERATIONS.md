# Operations and Troubleshooting

**Design revision 5 — 2026-10-26. Status: runbook design, not a deployed service.** Assign an operator and billing/teardown owner before AWS launch. No alert destination is configured.

## Routine checks

| Area | Inspect | Action |
| --- | --- | --- |
| Application | Expected five ready application Pods; session-first and cross-replica messaging | Investigate behavior even when readiness is green. |
| Dependencies | Subscriber freshness/generation, publisher failures, Redis memory/buffers | Distinguish subscriber failure from publisher connectivity. |
| Node | MemAvailable, CPU, disk, Pod evictions and K3s service | Stop load growth under pressure; preserve diagnostic evidence. |
| Network | Public TLS, private diagnostics, NetworkPolicy positive/negative checks | Recheck after platform or policy changes. |
| Certificates/secrets | Expiry, references, permissions and rotation status | Rotate early through a rehearsed procedure. |
| Costs | Credit balance, actual/forecast use, resource inventory, planned end time | Shorten or end the exercise before budget exhaustion. |

## Diagnostic commands after implementation

Confirm the intended kubeconfig/context before running commands. Node access is restricted; these commands do not establish authorization for another cluster.

```bash
kubectl config current-context
kubectl -n chat-app get deployments,pods,services,endpointslices
kubectl -n chat-app get events --sort-by=.metadata.creationTimestamp
kubectl -n chat-app describe deployment backend
kubectl -n chat-app logs deployment/backend --all-pods=true --tail=100
kubectl get nodes
```

The `--all-pods` option depends on the selected kubectl version; per-Pod log reads are a fallback. Redact operational output before sharing. On the EC2 node, inspect `systemctl status k3s`, restricted `journalctl -u k3s`, `free -m` and `df -h`. Use `kubectl top` only when the metrics API is installed and working; it is not the source of host MemAvailable.

Avoid dumping Secrets, kubeconfig, environment variables or entire configuration objects into incident reports.

## Telemetry contract

Backend metrics cover active connections, admission outcomes, message validation/publication/delivery outcomes, queue count/bytes, send timeouts, Redis subscriber state, heartbeat age, reconnects and shutdown duration. Freeze exact names/types with API implementation; dashboards and tests must agree.

Use bounded labels such as replica, outcome and failure class. No usernames, session UUIDs, raw request paths or message bodies in labels. Structured logs contain event class, release, replica and timing with sensitive data removed. Metrics and detailed health endpoints remain cluster-private.

Initial alert candidates: no ready backend; subscriber stale >10s; repeated Pod restarts/OOM; node MemAvailable <512 MiB during acceptance; disk use >80%; certificate expiry <14 days; cost above planned thresholds. Tune windows against observed behavior. Alert delivery and ownership need a real test; do not claim an on-call integration exists.

A full Prometheus/Grafana stack is optional and requires additional memory/storage cost accounting. Baseline diagnostics may use an authorized off-node collector and short-lived private inspection.

## Incident procedures

### Redis outage or stalled subscriber

Record heartbeat generation, publisher outcomes, Pod events and resource pressure. Expect backend readiness failure and active sockets closed with 1011. Restore Redis/network/credential access; verify a new subscriber generation and acknowledged heartbeat before readiness returns. Check cross-Pod delivery afterward. Do not promise replay of missed events.

### Backend crash or rollout failure

Inspect termination reason, image ID, rollout status and bounded logs. Confirm the other ready Pod still accepts sessions. If release-related, restore the full previous verified bundle. A forced crash will not reliably send a graceful close code; distinguish it from planned 1012 draining.

### Gateway/TLS failure

Check certificate validity/hostname, Secret reference, configuration validation and ServiceLB port ownership. Ensure Traefik is disabled. Test static HTTP routing and WSS separately. Renew using the agreed certificate process, validate the new material, then reload/replace the gateway and verify browser trust.

### Node memory or disk pressure

Capture usage and events before intervention. Reduce synthetic load; inspect system and application consumption. Delete only known disposable image/log artifacts according to retention policy, preserving current/rollback releases and platform recovery material. Pod limits alone do not guarantee node safety. Re-size only after cost review and measurements.

### Node loss

Rebuild from Terraform and the pinned platform bootstrap; recover required secrets through their protected source and apply the last verified bundle. If restoring K3s state, follow the selected version/datastore procedure and test it separately. Neither Redis nor the browser can reconstruct lost history. Node recovery time remains unmeasured.

### Unexpected spend

Check all relevant regions/services, running/retained resources and shared-account use. End the scheduled exercise through the reviewed teardown procedure. Alerts can lag; verify actual destruction and later billing. Do not infer a $0 balance from an empty Kubernetes namespace.

## Rotation and maintenance

Test Redis credential rotation with an overlap window where possible, revoke the old identity afterward and verify denied access. Preserve compatible Secret references for rollback without restoring revoked secrets. Rotate deployment credentials and encryption keys using supported procedures and confirm old access is revoked.

K3s upgrades are platform maintenance with separate backup, compatibility, rollout and recovery plans. Never assume application rollback can downgrade the cluster.

## Teardown and records

Follow [AWS requirements](AWS_FREE_TIER_REQUIREMENTS.md) and [infrastructure](INFRASTRUCTURE.md). Delete workload infrastructure, inventory retained state/backups/addresses/volumes, revoke temporary access and recheck delayed billing. Record incident timeline, release IDs, impact, lost-message boundary, actions, evidence and follow-up work.

