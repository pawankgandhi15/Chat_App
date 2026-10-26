# ADR Template

Copy this template into a descriptively named design document for a real decision. Assign an ID consistent with the main [decision register](../../DECISIONS_AND_RISKS.md); do not reuse an existing ID for an unrelated decision.

## Metadata

| Field | Value |
| --- | --- |
| ADR ID / title | TBD |
| Status | Proposed / Accepted / Superseded |
| Date / decision owner / reviewers | TBD |
| Related proposal and evidence | TBD |
| Supersedes / superseded by | None or linked ADR |

## Context

Describe the concrete requirement, constraints, workload, current failure mode and uncertainty. Separate observations from assumptions.

## Decision

State the chosen design and scope precisely. Identify affected components, contracts and environment. Acceptance of this record selects a design; it does not claim implementation.

## Alternatives

Compare options by correctness, complexity, cost, operational ownership and reversibility. Include keeping the current design where reasonable.

## Consequences

Record benefits, disadvantages, new failure modes, dependencies, security/data implications and recurring costs. State remaining single points of failure and what the decision does not guarantee.

## Verification

List acceptance criteria, experiments and required evidence. Reference the authoritative requirements, API and configuration documents instead of duplicating their defaults.

## Migration and reversal

Link the migration/rollback plan. State compatibility constraints, irreversible changes, credential/data recovery needs and conditions for revisiting the decision.

## Follow-up and evidence

List implementation tasks, owners, unresolved questions and dates. Add verified results later; retain this record when superseded so the decision history stays understandable.
