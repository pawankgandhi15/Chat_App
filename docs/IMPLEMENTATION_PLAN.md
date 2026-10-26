# Implementation Plan

**Design revision 5 — 2026-10-26. Status: all implementation milestones pending.** Kubernetes is the primary target; there is no prerequisite Compose implementation.

## Milestones and dependencies

| Phase | Work | Exit evidence |
| --- | --- | --- |
| 0. Resolve foundations | Pin supported versions; finalize Redis pool/heartbeat format, ASGI denial behavior, manifests and secret policy. | Reviewed contracts and explicit remaining blockers. |
| 1. Backend core | Settings, validation, schemas, rate/queue accounting, Redis supervision, session-first writer, health and drain. | Unit/property and real-transport contract checks. |
| 2. Frontend | Accessible layout, connection state, protocol validation, safe rendering, bounded history and drafts. | Browser/keyboard/accessibility checks. |
| 3. Local Kubernetes | Images, k3d config, base/local overlay, Services, probes, policies and test Secrets. | Five application Pods; cross-replica, policy and fault checks. |
| 4. Release automation | GHCR publication, scanning/signing, manifest schema, verification and controlled apply/rollback. | Invalid artifact rejection and failed-release recovery. |
| 5. AWS platform | Actual account/credit review, regional quote, Terraform state/workload, K3s bootstrap, TLS and access. | Reviewed plan, measured node, public/private network checks. |
| 6. Acceptance and handoff | Load, drain/recovery, rollback, operational records, demo and teardown. | AC-01–18 and NFR evidence; residual resources/cost recorded. |

## Implementation rules

Preserve `chat.v1` while changing orchestration. Keep Kubernetes details out of the browser's product interface except a deliberately enabled diagnostic panel. Design source modules around ownership of sessions, queues and Redis tasks, not around Pod names.

Local and AWS overlays share application behavior; only environment concerns differ. Do not add EKS, managed load balancers, NAT, persistence, user authentication or autoscaling without new requirements and cost review.

Measure resource requests/limits and startup/termination behavior. A 4-GiB node is a candidate, not an acceptance result. Keep builders and load generators off the AWS node.

## Open prerequisites

- Supported dependency/image/platform versions and hashes.
- Actual AWS plan, credit expiry, allowed instance, regional quote and duration.
- Real hostname/TLS issuance and renewal process.
- Controlled deployer route, least-privilege credential issuance and registry access.
- Redis connection/buffer/heartbeat protocol bounds and tested ACL.
- Node backup/recovery procedure and operational ownership.

## Effort planning

Estimate work after phase 0 identifies implementation experience, available hours and chosen automation depth. The repository currently has no application or manifests, so Kubernetes adoption is not merely adding one YAML file. Track each phase with a reviewable output and evidence; calendar duration depends on staffing and unresolved access requirements.

## Completion definition

Implementation is complete only when the documented behavior runs, mandatory tests pass, the AWS exercise stays within its verified budget, rollback and teardown are demonstrated, and README status reflects actual evidence. This documentation update does not satisfy those runtime gates.

