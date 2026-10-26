# Release Readiness Checklist

**Design revision 5 — 2026-10-26. Status: every runtime gate is pending.** Documentation is not a deployable release.

## Gate 1 — Contracts and local platform

- [ ] Versioned API schemas, settings and dependency locks reviewed.
- [ ] Pinned k3d/K3s versions and local/AWS overlays render and validate.
- [ ] Four Deployments produce five ready application Pods; static frontend loads (AC-01).
- [ ] Both backend identities observed and cross-replica messaging passes (AC-02).
- [ ] Sender receives one echo, schemas validate, session is first (AC-03, AC-04, AC-12).
- [ ] Input boundaries and browser safe rendering pass (AC-07).

## Gate 2 — Isolation and recovery

- [ ] Redis outage and recovery, subscriber stale/generation tests pass (AC-05, AC-18).
- [ ] Backend replacement, endpoint updates and reconnect behavior pass (AC-06).
- [ ] Slow-client isolation and bounded cleanup pass (AC-13).
- [ ] Private diagnostics and redacted logs verified (AC-14).
- [ ] NetworkPolicy, security group, Redis ACL and RBAC negative tests pass (AC-17).
- [ ] Graceful drain measured inside total Pod grace, including hooks.

## Gate 3 — Supply chain and delivery

- [ ] CI lint/unit/contract/integration/browser/security checks pass (AC-08).
- [ ] Final image digests, SBOM, provenance and trusted signatures verified (AC-15).
- [ ] No secret values in bundles; Secret references and rotation compatibility reviewed.
- [ ] Deployer route/permissions tested; root kubeconfig excluded from CI.
- [ ] Failed/interrupted release and full bundle rollback rehearsed <=10 minutes (AC-09).
- [ ] Current/previous artifacts retained; owned-resource cleanup reviewed.

## Gate 4 — AWS capacity and credit budget

- [ ] Actual plan, credit balance/expiry, regional instance access and price recorded.
- [ ] Gross usage estimate fits available eligible credit after reserve.
- [ ] Teardown time, owner and alert delivery tested.
- [ ] Candidate 2-vCPU/4-GiB node measured, including K3s/system overhead (AC-10).
- [ ] NFR-01 through NFR-08 evaluated with raw data (AC-16).
- [ ] Public hostname, trusted TLS, renewal and private diagnostics verified on AWS.

## Gate 5 — Recovery and teardown

- [ ] Node/platform recovery prerequisites documented and tested to the claimed scope.
- [ ] Infrastructure destruction and retained-resource inventory verified (AC-11).
- [ ] Delayed billing/credit use reviewed; remaining resources explicitly owned.
- [ ] Operational owner and incident/rotation procedures confirmed.

## Release evidence record

| Field | Required entry |
| --- | --- |
| Release/source | Release ID, commit, timestamp, prior accepted release. |
| Environment | Account/region, instance, OS, K3s/Kubernetes, namespace; sanitize shared copy. |
| Artifacts | Signed manifest identity, image digests, config hashes, SBOM/provenance. |
| Validation | AC/NFR result links, raw samples, failures and approved exceptions. |
| Recovery | Rollback timeline, restored image/config identity, functional result. |
| Cost | Estimate, credit eligibility, start/end, observed usage and retained resources. |
| Decision | Accepted / rejected / restored, operator and unresolved limitations. |

A failed mandatory gate blocks acceptance. A waiver must identify the scope, owner, expiry and residual risk; it must not relabel an untested result as passing. See [deployment](DEPLOYMENT.md) and [testing](TESTING.md).

