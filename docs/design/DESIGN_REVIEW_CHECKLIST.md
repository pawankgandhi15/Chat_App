# Design Review and Traceability

**Status: review checklist for future implementation; all runtime evidence remains pending. Updated 2026-10-26.**

## Review questions

- [ ] HLD distinguishes selected baseline, future options and deployed reality.
- [ ] Scope and workload are explicit; no unmeasured capacity or availability claims.
- [ ] Every component has an owner, interface, trust boundary and failure behavior.
- [ ] LLD defines state ownership, concurrency, cancellation, cleanup and resource bounds.
- [ ] Public protocol and configuration remain consistent with their authoritative guides.
- [ ] Browser reconnect, draft handling, accessibility and safe rendering are covered.
- [ ] Changes to data durability/identity have retention, authorization and migration designs.
- [ ] Kubernetes placement, probes, network policies, resources and rollout are testable.
- [ ] Secrets, RBAC, artifact trust and administrative routes are reviewed.
- [ ] Cost includes steady state, migration overlap, monitoring, backup and teardown.
- [ ] Abort criteria, rollback limits, operator and evidence location are recorded.
- [ ] New technical assumptions are checked against official documentation for selected versions.

## Acceptance traceability

| Design concern | Existing acceptance IDs | Required evidence |
| --- | --- | --- |
| Topology and fan-out | AC-01, AC-02, AC-03 | Ready application topology plus cross-Pod behavioral delivery. |
| Protocol and validation | AC-04, AC-07, AC-12 | Real transport, schema, input boundaries and session-first checks. |
| Dependency and Pod recovery | AC-05, AC-06, AC-18 | Failure timelines, endpoint behavior and current-generation heartbeat. |
| Resource isolation and capacity | AC-10, AC-13, AC-16 | Slow-reader isolation, raw load samples, node and Pod measurements. |
| Private network and diagnostics | AC-14, AC-17 | Positive/negative access paths, ACLs and redacted logs. |
| Artifact and release safety | AC-08, AC-09, AC-15 | CI checks, rejected tampered artifacts and full verified rollback. |
| Infrastructure lifecycle | AC-11 | Destruction inventory, retained-resource ownership and billing review. |

Use NFR-01 through NFR-08 for quantitative baseline evidence. New product behavior needs new or revised criteria; passing the old demo tests cannot prove private-room authorization or durable replay.

## Open items carried from the project

| Item | Owner to assign | Required resolution |
| --- | --- | --- |
| Version/transport compatibility | Backend/platform implementer | Exact locks and real handshake/termination tests. |
| Redis bounds and heartbeat format | Backend implementer | Pool/buffer choices, internal format and minimal ACL. |
| AWS entitlement, region and duration | Infrastructure/billing owner | Account evidence and current quote. |
| Hostname/TLS and deployer access | Platform/security owner | Renewal, least privilege and restricted route tests. |
| Validated operating capacity | Test owner | Reproducible benchmark and failure/rollout peaks. |
| Alert delivery and teardown | Operations owner | Named recipient, rehearsal and final inventory. |

No owner has been assigned by this document. Maintain the main [decision register](../DECISIONS_AND_RISKS.md) as the authoritative open-item list.

## Review outcome record

Record date, reviewer, proposal/ADR ID, accepted scope, blockers, implementation tasks and evidence links. Use statuses Proposed, Accepted design, Implemented, Verified or Superseded. Accepted design is not Verified.

Before merging documentation, check relative links, diagrams, numerical consistency and that source-code examples are labeled planned. Before accepting a release, complete the separate [release checklist](../RELEASE_CHECKLIST.md).
