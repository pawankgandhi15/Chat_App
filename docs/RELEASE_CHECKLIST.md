# Release Readiness & Verification Checklist

**Design Revision 5 — 2026-10-26. Status: Production Release Governance Specification.** This document defines the mandatory pre-release gates, automated verification scripts, artifact evidence requirements, and sign-off governance for deploying Chat App.

---

## 1. Five-Gate Release Verification Checklist

Every candidate release must pass all 25 criteria across five release gates before promotion to production:

### Gate 1: Contracts, Schemas & Local Integration
- [ ] **Dependency Immutability:** Python `requirements.lock` and container base images pinned with SHA-256 hashes.
- [ ] **Schema Compliance:** `schemas/events-v1.schema.json` rejects unexpected properties (`additionalProperties: false`).
- [ ] **Topology Spin-Up (AC-01):** Local k3d deployment produces four Deployments and five application Pods in `1/1 Ready` state.
- [ ] **Cross-Replica Fan-Out (AC-02):** Client on Pod 1 exchanges messages with Client on Pod 2 with verified `container_id` separation.
- [ ] **Single-Writer & Session-First (AC-03, AC-12):** Initial message is a unicast `session` envelope; sender receives exactly one echo via Redis.
- [ ] **Input Sanitization (AC-07):** Reassembled frames capped at 16 KiB; Unicode NFC normalized; C0/DEL controls rejected; XSS rendered as inert text.

### Gate 2: Network Isolation & Fault Resilience
- [ ] **Broker Recovery (AC-05, AC-18):** Terminating Redis triggers backend readiness failure (503); restarting Redis restores readiness in $\le 15\text{s}$.
- [ ] **Rolling Replacement (AC-06):** Rolling update drains connections with close code `1012`; surviving replica continues serving.
- [ ] **Backpressure & Slow Client (AC-13):** Simulated slow reader queue overflows ($> 32$ items or $> 256\text{ KiB}$) and evicts with code `1013` without impacting peers.
- [ ] **Zero-Trust NetworkPolicies (AC-14, AC-17):** Gateway and frontend cannot reach Redis port 6379; public access to `/metrics` returns HTTP 403.
- [ ] **Pod Termination Budget (NFR-07):** Paced connection drain completes within 10s; container process exits cleanly within 20s grace.

### Gate 3: Supply Chain Integrity & Automated Rollback
- [ ] **Quality Pipeline (AC-08):** GitHub Actions static linting, unit tests, and property tests pass 100%.
- [ ] **Vulnerability Clearance:** Trivy container scans report 0 `CRITICAL` and 0 `HIGH` unresolved CVEs.
- [ ] **SBOM & Signatures (AC-15):** Syft SBOM generated; Cosign cryptographically signs all image digests.
- [ ] **Image Digest Immutability:** Kubernetes manifests reference immutable `@sha256:...` digests; mutable tags rejected.
- [ ] **Automated Rollback (AC-09, NFR-08):** `scripts/rollback.sh` restores prior stable release in $\le 10\text{ minutes}$.

### Gate 4: AWS Budget Governance & Performance Sizing
- [ ] **Credit Ceiling Compliance (NFR-08):** Total gross cloud spend modeled at $\$39.79/\text{month}$, maintaining $\ge \$20$ buffer within $\$100$ credit allocation.
- [ ] **AWS Budgets Alarms:** Automated budget alerts configured at 50%, 75%, and 90% spending thresholds.
- [ ] **Host Headroom (NFR-06):** Linux `MemAvailable` on EC2 host remains $\ge 512\text{ MiB}$ during peak steady-state load.
- [ ] **Latency SLA Compliance (NFR-01, NFR-03):** 30-minute benchmark verifies p95 latency $< 250\text{ ms}$ and p99 $< 1,000\text{ ms}$ with zero data corruption.
- [ ] **IMDSv2 Enforced:** EC2 instance metadata requires session tokens (`http_tokens = "required"`).

### Gate 5: Operational Governance & Teardown Verification
- [ ] **Structured Logging:** JSON logs capture lifecycle events with message text, usernames, and secrets redacted.
- [ ] **Clean Infrastructure Teardown (AC-11):** `terraform destroy` successfully destroys all billable EC2, EBS, and Elastic IP assets.
- [ ] **Disaster Recovery Tested:** Platform rebuild from Terraform and cloud-init verified.
- [ ] **Audit Trail Updated:** Version changelog, git tags, and release manifests recorded in documentation.

---

## 2. Automated Release Pre-Flight Verification Script (`scripts/verify-release.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo "CHAT APP RELEASE PRE-FLIGHT VERIFIER"
echo "=========================================================="

MANIFEST_FILE="${1:-schemas/release.schema.json}"

# 1. Validate Release Manifest Schema
echo "[1/4] Validating release manifest against schema..."
check-jsonschema --schemafile "${MANIFEST_FILE}" release.json

# 2. Verify Cosign Cryptographic Signatures
echo "[2/4] Verifying OCI image signatures via Cosign..."
for IMAGE in $(jq -r '.images | to_entries[].value' release.json); do
  echo "Checking signature for: ${IMAGE}"
  cosign verify --key env://COSIGN_PUBLIC_KEY "${IMAGE}" > /dev/null
done

# 3. Verify Kustomize Manifest Overlays
echo "[3/4] Validating Kubernetes overlays..."
kubectl kustomize k8s/overlays/aws/ | kubeconform -strict -summary

# 4. Check Cluster Headroom
echo "[4/4] Verifying node memory headroom..."
AVAILABLE_MEM=$(kubectl get nodes -o jsonpath='{.items[0].status.allocatable.memory}' | sed 's/Ki//')
if [[ "${AVAILABLE_MEM}" -lt 524288 ]]; then
  echo "ERROR: Node memory headroom is below 512 MiB!"
  exit 1
fi

echo "SUCCESS: All pre-flight verification gates passed."
```

---

## 3. Formal Release Sign-Off Governance Record

```markdown
### Official Release Verification Record

* **Release Identifier:** `YYYYMMDD.1-sha.XXXXXXX`
* **Target Environment:** AWS K3s Production (`ap-south-1`)
* **Source Commit SHA:** `[40-character git commit hash]`
* **Verification Date:** `YYYY-MM-DD HH:MM UTC`

#### Formal Engineering Sign-Offs:
* **Technical Lead:** `APPROVED` — [Signature / Name] (`YYYY-MM-DD`)
* **Security Architecture:** `APPROVED` — [Signature / Name] (`YYYY-MM-DD`)
* **Cloud Infrastructure Owner:** `APPROVED` — [Signature / Name] (`YYYY-MM-DD`)

#### Mandatory Evidence Attachments:
1. Trivy Vulnerability Scan Report (`trivy-report.json`)
2. Cosign Signature Verification Log (`cosign-verify.log`)
3. k6 30-Minute Load & Latency Benchmark Summary (`k6-benchmark-summary.json`)
4. Post-Rollback Automated Verification Log (`rollback-test.log`)
```
