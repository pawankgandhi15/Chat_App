# Architecture Migration Playbook

**Status: design documentation only. Baseline: design revision 5. Updated: 2026-10-26.**

Use this process for adding replicas/nodes, changing broker/platform, introducing durable storage or versioning the protocol. It is a design and review procedure, not an executable migration script.

## Required change record

Capture current and proposed topology, measured problem, user impact, affected contracts, data ownership, required access, recurring/temporary cost, operator, rollback owner, decision deadline and evidence links. Use the [proposal template](templates/CHANGE_PROPOSAL.md).

Classify the change: resource-only, topology, protocol, security/identity or persistent-data migration. A resource-only change still needs capacity and recovery evidence; a data migration needs stronger compatibility and restore planning.

## Ordered gates

| Gate | Work | Stop condition |
| --- | --- | --- |
| 1. Baseline | Record current release/config, symptoms, measurements and accepted objectives | Problem or baseline cannot be reproduced. |
| 2. Design | Update HLD/LLD, contracts, threat model, alternatives and cost | Unresolved correctness/security or budget blocker. |
| 3. Rehearse | Run new design locally or in disposable staging with faults and mixed versions | Missing functional, compatibility or recovery evidence. |
| 4. Prepare | Verify artifacts, backups where relevant, restore drill, access and maintenance notice | No viable recovery path or unclear ownership. |
| 5. Introduce | Apply bounded changes with observable checkpoints | Metrics/behavior exceed documented abort thresholds. |
| 6. Cut over | Verify new connections, existing session drain, data behavior and operator visibility | Unexpected loss, authorization failure or capacity pressure. |
| 7. Stabilize | Observe for a declared window, compare to baseline, exercise recovery | Evidence insufficient for acceptance. |
| 8. Retire | Remove old paths/resources only after rollback window closes | Old clients, data or dependencies still need the path. |

## WebSocket-specific cutover

Existing sockets may stay on old replicas while new sessions use the new path. Define whether they drain or coexist, how old/new versions exchange events and the maximum coexistence period. Avoid forcing all clients to reconnect simultaneously.

A canary is useful only if traffic selection and mixed-version compatibility are implemented. On a small node, overlapping old/new stacks can exceed memory; estimate overlap or choose an announced interruption. Do not assume blue/green fits the original budget.

## Protocol and data compatibility

For protocol changes, negotiate explicit supported versions and test old-client/new-server plus new-client/old-server behavior. The current strict schema means added fields can break clients.

For persistence, prefer an expand → migrate/backfill → verify → switch readers/writers → retire sequence when applicable. Define duplicate handling and authoritative writer ownership; uncontrolled dual writes can diverge. Backups require restore tests, retention and protected access.

Separate application rollback from data rollback. Once the new path accepts data the old code cannot represent, blindly restoring an old binary can corrupt or discard information. Define a compatible old reader, forward repair or controlled restore with an explicit data-loss boundary.

## Abort and recovery record

Set thresholds before execution: error/latency/delivery regressions, readiness loss, memory pressure, missing authorization, replication lag if relevant and spending above the agreed estimate. Thresholds are change-specific; do not invent a universal safe percentage.

Record the last safe checkpoint, compatible prior artifact/config/secret references and exact restoration verification. If secrets were revoked, never restore them solely for compatibility. If rollback is no longer safe, stop automatic changes and use the reviewed forward-repair path.

## Acceptance and cleanup

Require behavioral evidence through the public path, network/security negative tests, resource measurements, relevant fault drills and complete resource inventory. Link results to AC/NFR IDs or explicitly revised targets.

Remove obsolete images, old infrastructure, temporary credentials and duplicate monitoring only after the recovery window. Update cost records, ownership, README status and diagrams. A successful rollout without cleanup is an unfinished migration.
