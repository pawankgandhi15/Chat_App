# Local Development

**Design revision 5 — 2026-10-26. Status: future workflow.** There is no runnable application yet. Do not run commands referring to planned files until those files exist.

## Tooling and environment

Use Git, Docker with Linux containers, kubectl, k3d and Kustomize support. On Windows, validate Docker Desktop/WSL2 integration and local port availability. Pin compatible versions; local K3s should match the AWS K3s release. Allow memory for the local node, Docker/WSL and development tools; 4 GiB allocated to the cluster is only a starting candidate.

Develop application images off the AWS host. Unit/property tests can run in an isolated test image; integration and browser tests use k3d to exercise actual Services, probes and NetworkPolicies. Test credentials are generated locally and never committed.

## Planned workflow

1. Implement contracts and dependency locks from [backend](BACKEND.md), [frontend](FRONTEND.md) and [API](API_SPECIFICATION.md).
2. Build gateway, frontend and backend images; select a pinned Redis image.
3. Create one local k3d server with Traefik disabled and ServiceLB enabled.
4. Map localhost 8080/8443 to cluster 80/443; configure matching origins and local certificates.
5. Load images into k3d or use a tested local registry. Ensure tags/digests and imagePullPolicy match the chosen workflow.
6. Bootstrap test Secrets and namespace, render/apply `k8s/overlays/local`, then wait for all application Deployments.
7. Run functional, policy and failure checks; capture logs/events before removing the test cluster.

Actual scripts and k3d configuration must make cluster name, ports, version and cleanup explicit. Never run cleanup against an inferred current production context.

## Feedback loop

Use unit tests for normalization, schemas, rate limits and queue accounting. Rebuild/import only affected images, update the local image reference and wait for rollout. ConfigMap changes need a Pod-template revision or an explicit tested reload path.

Use browser tools to inspect subprotocol negotiation, first session envelope, reconnect state and inert rendering. To demonstrate cross-replica delivery, verify different `container_id` values; two browser tabs may land on the same Pod.

Use namespace-scoped logs and events for debugging. Keep detailed health and metrics private; authorized localhost port-forwarding can inspect them. Do not expose Redis or backend ports publicly for convenience.

## Required local scenarios

- Normal chat across both backend Pods, sender echo once and session first.
- Redis restart and subscriber stall/recovery without a process restart.
- Backend rolling replacement and forced crash, with honest disconnected UI.
- Default-deny policies: expected paths succeed, forbidden paths fail.
- Oversize/binary/control-character inputs, duplicate display names and slow readers.
- Public-path diagnostics denial, explicit origins and local TLS where enabled.
- Complete release rollback and deterministic cleanup.

## Parity boundaries

Local Docker networking and k3d's load-balancer container differ from EC2 public networking. Verify AWS ServiceLB/SNAT, security groups, certificates, instance limits and costs independently. Never label a local test as an AWS deployment result.

[Configuration](CONFIGURATION.md), [Kubernetes](KUBERNETES.md), [testing](TESTING.md) and [implementation plan](IMPLEMENTATION_PLAN.md) define the remaining details.

