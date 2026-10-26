# Continuous Integration and Delivery

**Design revision 5 — 2026-10-26. Status: workflow specification only.** GitHub Actions files, images and release tooling remain to be implemented.

## Pipeline stages

| Stage | Checks and outputs | Credentials |
| --- | --- | --- |
| Pull request | Docs/links, lint, unit/property tests, schema tests, overlay render, security-policy checks | Read-only repository permissions; no AWS or deployment secrets. |
| Local-cluster integration | Pinned k3d/K3s; application images; browser and cross-replica tests; network/fault checks | Ephemeral test-only credentials. |
| Release build | Build once, test final images, scan, generate SBOM and provenance | Minimal GHCR write access for trusted release workflow. |
| Sign and package | Record immutable digests and rendered config hashes; sign image/bundle evidence | Scoped GitHub OIDC identity, no long-lived signing key by default. |
| Deploy | Verify bundle, preflight, apply, wait, functional checks, restore on failure | Restricted deployment identity and approved network route. |
| Record | Publish sanitized evidence and accepted/failed/restored status | Limited artifact permissions. |

Never expose privileged release/deployment credentials to untrusted pull-request code. Pin third-party Actions by reviewed commit. Separate PR checks, image publication, infrastructure changes and application deployment.

## Quality gates

Lint Python/JavaScript and manifests. Run API-contract and lifecycle tests against the real ASGI/Redis transport, not only mocks. Validate both Kustomize overlays against the selected Kubernetes version. Reject plaintext secrets, mutable AWS image tags, missing limits, public backend/Redis exposure and privileged app Pods.

Scan dependencies and final images. Fixed High/Critical findings block release unless an explicit, time-limited exception records owner, justification and mitigation. Signing establishes artifact identity; it does not establish absence of vulnerabilities.

Run the full 30-minute load experiment on the selected AWS candidate before a capacity claim. A shared CI runner's result is not a cloud performance measurement.

## Release manifest fields

| Field | Required meaning |
| --- | --- |
| schema_version / release_id / source_commit | Versioned manifest and immutable source identity. |
| created_at / target_architecture | Build timestamp and supported target, initially linux/amd64. |
| images | Gateway, frontend, backend and Redis repository@sha256 references. |
| configuration | Hashes of rendered manifests and non-secret configuration. |
| secrets_required | Secret names and compatibility versions; no values. |
| platform_compatibility | Tested K3s/Kubernetes version and required features. |
| attestations | SBOM, provenance and expected signature-verification policy. |
| evidence | Links to quality, integration, policy and rollback results. |

Use deterministic serialization and explicit schema validation. A manifest cannot establish its own trust by embedding an arbitrary signer; the verifier's trusted policy is configured separately.

## Registry and deployment access

GHCR is the selected registry. Use ephemeral build credentials where supported. Public pullable images may avoid node registry credentials; private packages require a minimally scoped, rotatable imagePullSecret. Validate organization permissions and available storage/usage allowance before choosing visibility.

AWS OIDC authenticates a workflow to AWS APIs. It does not open an SSH route or grant Kubernetes RBAC. For the initial AWS design, deployment runs through a controlled operator workstation or approved runner with known egress to restricted SSH, then namespace-scoped kubectl on the node. Credential issuance/rotation must be implemented and tested; do not copy the root K3s kubeconfig into GitHub secrets.

## Concurrency and failure

Allow only one deployment per environment through the supported entry point. Keep deployment journal and last accepted bundle. A timeout, canceled job or Ready Pod count alone must not mark a release successful. Reconcile actual live state after interruption and invoke the complete bundle rollback from [deployment](DEPLOYMENT.md).

Infrastructure jobs use separate permissions and state locking. Never destroy the environment from a generic application-test cleanup job.

## Evidence and retention

Retain logs without payloads/secrets, test summaries, raw load samples, digests, signatures, manifests, SBOMs and rollback timings. Set artifact/registry retention to preserve the current and rollback release without unbounded growth. Report pending checks as pending; no CI execution has occurred in this repository.

