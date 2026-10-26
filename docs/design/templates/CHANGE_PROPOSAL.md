# Architecture Change Proposal Template

Copy this document into a descriptively named Markdown file in the design folder when a real change is proposed. Replace every placeholder; an unfilled template is not a decision or approval.

## Metadata

| Field | Value |
| --- | --- |
| Proposal ID / title | TBD |
| Status | Proposed |
| Author / reviewers / operational owner | TBD |
| Date / target milestone | TBD |
| Baseline release and design revision | TBD |
| Related issue, ADR and evidence | TBD |

## Problem and success criteria

Describe the observed bottleneck or requested user behavior. Include measurements, reproduction, workload and affected users. State quantitative success criteria, observation window and non-goals.

## Current and proposed HLD

Describe component, deployment, network, trust-boundary and failure-domain changes. Add current/target Mermaid diagrams. Explain which parts remain singleton and what availability claim the new topology can support.

## LLD and contract impact

List module/interfaces, state ownership, concurrency, cancellation and resource limits. Identify changes to API schemas, configuration defaults, browser behavior, Kubernetes manifests, Terraform, IAM/RBAC and operational procedures.

## Alternatives and decision

Compare at least the current design and one feasible alternative. Record evidence, complexity, expected benefit, failure behavior and cost; explain the selected option and rejected alternatives.

## Capacity and cost

Record expected connections, accepted message rate, payload sizes, fan-out, measured limits and headroom. Quote regional compute/storage/network/platform/monitoring/backup costs, migration overlap and credit expiry. Name the budget and teardown owner.

## Security and data lifecycle

State identity/authorization changes, secret handling, network boundaries, retention, deletion, backup/restore and new abuse cases. If no durable data exists, state that explicitly.

## Migration and compatibility

List ordered checkpoints, mixed-version behavior, old/new data compatibility, traffic cutover, drain and cleanup. Identify irreversible steps and the point beyond which a binary rollback is unsafe.

## Verification and abort conditions

Map checks to existing/new acceptance IDs. Define load/fault/security tests, evidence retention, predeclared abort thresholds and restoration verification.

## Rollback and recovery

Name the owner, last safe checkpoint, artifact/config/secret prerequisites and recovery steps. State known data-loss risks and forward-repair options.

## Implementation tasks and review outcome

List tasks with dependencies, owners and completion evidence. Record review date, accepted scope and unresolved blockers. Update HLD/LLD and authoritative guides together after acceptance; attach measured results after implementation.
