# Architecture Change Proposal Template

**Template revision 2 · 2026-10-26. This file is an unfilled template, not an accepted design or implementation.**

Use this proposal to make an architecture change concrete enough to review, implement, measure and reverse. Read the [template guide](README.md) before copying it. Replace TBD values with facts, evidence or an open item with an owner and due date. Mark an inapplicable section `N/A — reason`; never invent results to complete a table.

## 1. Proposal identity and summary

| Field | Value to complete |
| --- | --- |
| Proposal ID and title | TBD — stable ID and specific outcome |
| Design status | Draft / In review / Accepted / Rejected / Superseded |
| Delivery status | Not started / In progress / Implemented / Verified / Retired |
| Author, reviewers and operational owner | TBD — people or responsible roles |
| Created / last updated / review due | TBD — explicit dates and timezone when scheduling |
| Baseline design revision and source commit | TBD — identify the actual comparison point |
| Target environment and milestone | Local / AWS demo / future service; TBD |
| Related issue, ADR and previous proposal | TBD — links or None with reason |
| Change class | Capacity / topology / protocol / data / security / operations; select all affected |
| Decision requested | TBD — one sentence stating the design choice to settle |

**Summary to complete:** Because [observed problem or requested capability], propose [bounded change] for [users/environment]. Success means [measurable outcome]. The main trade-off is [cost, complexity or reliability consequence]. The fallback is [defined recovery path].

Design acceptance selects a technical direction. Record implementation, verification and resource spending separately; none is established by filling this template.

## 2. Problem, baseline and evidence

Describe the user-visible problem, why it matters now, and what happens if no change is made. Distinguish an observed bottleneck from an anticipated workload or product request.

| Evidence ID | Observation or requirement | Environment / date / version | Artifact or source | Confidence / limitation |
| --- | --- | --- | --- | --- |
| E-01 | TBD | TBD | TBD — sanitized logs, benchmark, requirement or official reference | TBD |
| E-02 | TBD | TBD | TBD | TBD |

Record current connections, attempted and accepted message rate, payload distribution, recipient fan-out, Pod/node utilization and incident frequency when relevant. Include raw counts and observation windows; a single percentile without workload context is not a baseline.

If the application is not implemented, say **not measured**. Use an explicit hypothesis and planned experiment instead of a fabricated before/after result.

## 3. Scope, invariants and non-goals

| Concern | Current contract / owner | Proposed change | Preserved invariant or deliberate break |
| --- | --- | --- | --- |
| Product behavior | [Requirements](../../REQUIREMENTS.md) | TBD | TBD |
| Public protocol | [API](../../API_SPECIFICATION.md) | TBD | TBD |
| Configuration and resource bounds | [Configuration](../../CONFIGURATION.md) | TBD | TBD |
| Runtime and networking | [Kubernetes](../../KUBERNETES.md) | TBD | TBD |
| Security and data | [Security](../../SECURITY.md) | TBD | TBD |
| Release and operations | [Deployment](../../DEPLOYMENT.md), [operations](../../OPERATIONS.md) | TBD | TBD |

List explicit non-goals. For this project, address whether anonymous identity, one global room, session-first ordering, ephemeral Pub/Sub and single-node availability remain unchanged. If any changes, identify the new requirement and affected contract.

## 4. Success criteria and guardrails

| Criterion ID | Metric or behavior | Baseline / evidence | Target and window | Measurement / acceptance rule |
| --- | --- | --- | --- | --- |
| SC-01 | TBD — user-visible outcome | TBD | TBD | TBD |
| SC-02 | TBD — recovery or compatibility | TBD | TBD | TBD |
| SC-03 | TBD — resource/cost boundary | TBD | TBD | TBD |

Define numerator, denominator, units, sample size, warmup, steady interval and excluded events for rate/latency targets. Report rejected or ambiguous sends separately so exclusions do not hide failures.

Map targets to existing FR/AC/NFR IDs or propose explicit revisions. Do not silently replace the current targets. Separate healthy-run objectives, fault-run behavior and operational recovery.

## 5. Assumptions, dependencies and blockers

| ID | Assumption or dependency | Why it matters | Validation / owner / due | Fallback if false |
| --- | --- | --- | --- | --- |
| A-01 | TBD — unverified premise | TBD | TBD | TBD |
| D-01 | TBD — version, permission, service or team dependency | TBD | TBD | TBD |

Identify the critical path: version compatibility, account/region access, registry permissions, real hostname/TLS, deployment route, capacity measurement and responsible operator. Check [open decisions](../../DECISIONS_AND_RISKS.md) before treating a previously proposed value as resolved.

## 6. HLD: components, deployment and trust boundaries

Describe both current and target topology. Link or include Mermaid context/deployment diagrams with a legend distinguishing application traffic, administration, provisioning and replication. Label future components as proposed.

| Component | Before → after | State and interface ownership | Placement / failure domain | Scaling and recovery |
| --- | --- | --- | --- | --- |
| Gateway / frontend | TBD | TBD | TBD | TBD |
| Backend workloads | TBD | TBD | TBD | TBD |
| Broker / persistent store, if any | TBD | TBD | TBD | TBD |
| Control plane / infrastructure | TBD | TBD | TBD | TBD |

State how clients reach healthy endpoints after failure, not only how many nodes exist. Name remaining singleton components and shared failure points.

| Source → destination | Protocol / port | Identity or trust mechanism | Network enforcement | Failure behavior |
| --- | --- | --- | --- | --- |
| TBD | TBD | TBD | TBD | TBD |

Include DNS, certificates, private diagnostics, external dependencies and administrative routes. Identify changes to Kubernetes Services, public exposure, network policies, node access and metadata access.

## 7. LLD: interfaces, concurrency and resource ownership

Link the affected [LLD](../LLD.md) modules and proposed source paths. For each changed interface, describe inputs, outputs, errors, timeout, cancellation and owner; do not present invented function names as existing code.

| Module / interface | Input → output | State owner / lifecycle | Bounds and timeout | Failure / cleanup invariant |
| --- | --- | --- | --- | --- |
| TBD | TBD | TBD | TBD | TBD |

Describe the main sequence and at least one failure sequence. For asynchronous work, state who creates/awaits tasks, owns writes, releases reservations and prevents duplicate cleanup. Account for queue entries, encoded bytes, in-flight data and transport buffers separately.

For this chat app, explicitly assess:

- Session-first ordering during connection initialization and replacement.
- Admission races, per-socket and per-replica budgets.
- Subscriber generation, heartbeat freshness and ambiguous publication.
- Slow-client isolation and single-writer ownership.
- Signal handling, Pod termination budget and reconnect storms.
- Stale browser callbacks, preserved drafts and terminal versus retryable errors.

## 8. Data and protocol compatibility

| Combination or scenario | Expected behavior | Contract/version rule | Test and fallback |
| --- | --- | --- | --- |
| Old client → new server | TBD | TBD | TBD |
| New client → old server | TBD | TBD | TBD |
| Old and new backend replicas share broker | TBD | TBD | TBD |
| Reconnect during transition | TBD | TBD | TBD |
| Restored old release reads new data | TBD or N/A with reason | TBD | TBD |

The current strict event schema is authoritative; do not assume extra fields are safe. Identify negotiation, event-size changes, ordering scope, idempotency and acknowledgment semantics.

For persistent data, define authoritative writer, schema constraints, indexes, retention, deletion, backup/restore, cursor/replay behavior and handling of duplicate or out-of-order events. Describe partial failure between storage and publication. If data remains ephemeral, state what can be lost and why a rollback cannot recover it.

## 9. Capacity model and operating envelope

| Quantity | Current measurement | Proposed workload / limit | Model or evidence | Margin / uncertainty |
| --- | --- | --- | --- | --- |
| Concurrent sockets and distribution | TBD | TBD | TBD | TBD |
| Attempted / accepted messages per second | TBD | TBD | TBD | TBD |
| Payload / serialized event bytes | TBD | TBD | TBD | TBD |
| Recipient deliveries and broker fan-out | TBD | TBD | TBD | TBD |
| Per-Pod CPU, memory, queues and descriptors | TBD | TBD | TBD | TBD |
| Node/platform overhead and disk growth | TBD | TBD | TBD | TBD |
| Rollout/reconnect peak | TBD | TBD | TBD | TBD |

Use [capacity planning](../CAPACITY_PLANNING.md) for calculations. For a global room, distinguish client-delivery work from broker-to-replica fan-out. Do not equate an admission ceiling or memory request with demonstrated capacity.

Specify the bottleneck, instrumentation, load progression, saturation signal, operating margin and what would trigger another redesign. If autoscaling is proposed, define metrics ownership, stale/missing-metric behavior, limits, stabilization, node capacity and scale-down effects on existing sockets.

## 10. Reliability and failure analysis

| Failure scenario | Detection and user impact | Containment / retry policy | Data-loss boundary | Recovery objective / evidence |
| --- | --- | --- | --- | --- |
| Backend termination or crash | TBD | TBD | TBD | TBD |
| Redis failure or stalled subscriber | TBD | TBD | TBD | TBD |
| Node / ingress / control-plane loss | TBD | TBD | TBD | TBD |
| Slow receiver or reconnect surge | TBD | TBD | TBD | TBD |
| Invalid config, secret or artifact | TBD | TBD | TBD | TBD |
| Additional change-specific failure | TBD | TBD | TBD | TBD |

For any RTO (recovery time objective), define start/end events and the user-visible verification. For any RPO (recovery point objective), identify the durable data and restore boundary; use N/A with explanation where no durable history exists.

Explain whether added redundancy covers application, control plane, ingress and broker separately. Test partial failures and recovery, not only complete restarts.

## 11. Security, privacy and abuse review

| Asset / boundary | Threat or misuse | Proposed control | Negative test | Residual risk / owner |
| --- | --- | --- | --- | --- |
| Public connection and user content | TBD | TBD | TBD | TBD |
| Internal service and broker access | TBD | TBD | TBD | TBD |
| Secrets / deployment identity | TBD | TBD | TBD | TBD |
| Artifacts / administrator / node | TBD | TBD | TBD | TBD |

Document least privilege, secret issuance/rotation/revocation, public/private paths, unsafe Pod permissions, log redaction and evidence access. Explain how the change affects anonymous abuse controls or future authenticated authorization.

Identify what data is collected, who can read it, how long it lives and how it is deleted. Do not include real credentials, private messages, kubeconfig or raw Terraform state in this proposal.

## 12. Cost, account constraints and teardown

| Resource or activity | Region / quantity / runtime | Quoted rate and date / source | Gross estimate | Owner and removal condition |
| --- | --- | --- | --- | --- |
| Compute / control plane | TBD | TBD | TBD | TBD |
| Storage / snapshots / backups | TBD | TBD | TBD | TBD |
| Address / ingress / transfer | TBD | TBD | TBD | TBD |
| Broker / database / monitoring | TBD | TBD | TBD | TBD |
| Migration overlap / temporary tests | TBD | TBD | TBD | TBD |

Separate one-time migration costs, recurring usage and retained-resource costs. Record estimate range, currency, assumptions and unpriced items.

Record actual eligible credit balance, expiry, shared-account usage, reserve, planned end time and billing owner using [AWS requirements](../../AWS_FREE_TIER_REQUIREMENTS.md). Credits offset eligible charges; they do not change gross usage cost. Do not infer ongoing funding for a future HA design from the initial demo budget.

State alert routing, response, scheduled teardown and inventory/billing checks. An alert alone is not the stop mechanism.

## 13. Observability and operations

| Signal / symptom | Source and bounded dimensions | Detection threshold / window | Action and owner | Evidence retention |
| --- | --- | --- | --- | --- |
| TBD | TBD | TBD | TBD | TBD |

Describe dashboards or diagnostic views, alert delivery tests, runbook changes, secret/certificate renewal, on-call or demo ownership and maintenance windows. Avoid identifiers or message text as unbounded metric labels.

Provide a diagnostic path from user symptom to gateway, backend, broker and node evidence. State how operation continues if telemetry is unavailable.

## 14. Alternatives and recommended design

Compare keeping the current design and at least one feasible alternative. Record assumptions behind projected benefits and distinguish measured values from estimates.

| Option | Meets required behavior? | Capacity / failure behavior | Cost / operating effort | Compatibility / reversibility | Evidence and disposition |
| --- | --- | --- | --- | --- | --- |
| Keep baseline | TBD | TBD | TBD | TBD | TBD |
| Option A | TBD | TBD | TBD | TBD | TBD |
| Option B or N/A | TBD | TBD | TBD | TBD | TBD |

Explain the recommendation in plain language. If using scores, publish criteria, weights and uncertainty; a score must not conceal an unmet mandatory security or correctness requirement.

## 15. Implementation and migration plan

| Step / checkpoint | Action and environment | Owner / dependency | Verification / evidence | Stop or restore action |
| --- | --- | --- | --- | --- |
| Prepare | TBD | TBD | TBD | TBD |
| Rehearse | TBD | TBD | TBD | TBD |
| Introduce compatible changes | TBD | TBD | TBD | TBD |
| Cut over / drain | TBD | TBD | TBD | TBD |
| Observe | TBD | TBD | TBD | TBD |
| Retire old path/resources | TBD | TBD | TBD | TBD |

Use the [migration playbook](../MIGRATION_PLAYBOOK.md). Include credential/bootstrap work, release verification, concurrency control, interrupted-operation recovery and human ownership. Canary or parallel stacks require implemented traffic selection and sufficient temporary capacity.

Define the mixed-version period and what happens to existing WebSockets. Identify every irreversible step and the last safe rollback checkpoint before it.

## 16. Abort conditions, rollback and forward repair

| Trigger | Threshold / observation window | Decision owner | Recovery action | Functional proof after recovery |
| --- | --- | --- | --- | --- |
| Correctness / authorization regression | TBD | TBD | TBD | TBD |
| Availability / latency / resource regression | TBD | TBD | TBD | TBD |
| Cost or migration boundary breached | TBD | TBD | TBD | TBD |

Record prior image/configuration/Secret references and independently verified artifacts. A complete rollback restores compatible resources, not only a Deployment revision. Never restore a revoked credential.

Explain when binary rollback becomes unsafe because data or contracts changed. Provide a forward-repair or restore path with explicit data-loss implications, recovery prerequisites and communication. State how failure of rollback is detected and handled.

## 17. Verification and release evidence

| Test ID | Requirement / AC / NFR | Scenario and environment | Expected outcome | Artifact / owner / result |
| --- | --- | --- | --- | --- |
| V-01 | TBD | Normal functional path | TBD | Pending |
| V-02 | TBD | Boundary / negative / authorization | TBD | Pending |
| V-03 | TBD | Mixed-version or failure recovery | TBD | Pending |
| V-04 | TBD | Load / rollout peak / rollback | TBD | Pending |
| V-05 | TBD | Cleanup / retained resources | TBD | Pending |

Record versions, commit, image digests, configuration hashes, sampling method and limitations. Keep raw evidence sanitized and link a readable summary. A local test does not establish AWS routing, pricing or instance behavior.

Define the acceptance window, required regression coverage, unresolved findings and how time-limited exceptions are owned and revisited. Keep implementation verification separate from design review.

## 18. Review outcome, follow-up and design updates

| Reviewer / role | Area reviewed | Outcome / date | Blocker or condition | Evidence / resolution owner |
| --- | --- | --- | --- | --- |
| TBD | TBD | Pending | TBD | TBD |

**Decision:** TBD. **Accepted scope:** TBD. **Unresolved conditions:** TBD. **Related ADR:** TBD.

| Task / document | Owner | Dependency / due | Completion evidence |
| --- | --- | --- | --- |
| HLD, LLD and sequence/data diagrams | TBD | TBD | TBD |
| Requirements, API, configuration and tests | TBD | TBD | TBD |
| Platform, security, deployment and operations | TBD | TBD | TBD |
| Implementation, rollout and cleanup | TBD | TBD | TBD |

Set a post-change review date and revisit triggers, including failed assumptions, new workload, changed budget, security findings or unacceptable operational effort. Record expected versus observed results after implementation and update the [decision register](../../DECISIONS_AND_RISKS.md).
