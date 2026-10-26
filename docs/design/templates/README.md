# Architecture Template Guide

**Template pack revision 2 · updated 2026-10-26.** These documents help turn an idea into a reviewable architecture change and preserve the reasoning after a decision.

The project remains at the documentation stage. This pack adds no application implementation, cloud resources or accepted runtime decisions.

## Choose the right document

| Document | Main question | What belongs in it |
| --- | --- | --- |
| [Change proposal](CHANGE_PROPOSAL.md) | What should change, and how will it be implemented and verified? | HLD/LLD, evidence, alternatives, compatibility, capacity/cost, migration and release plan. |
| [ADR](ADR.md) | Why was this architectural option selected? | Context, drivers, decision, trade-offs, consequences, verification and revisit conditions. |

Use a proposal for a cross-component change, a new product contract or a migration with meaningful failure/cost consequences. Use an ADR for a durable decision that future maintainers need to understand. A proposal can produce several ADRs if it contains independent choices; each ADR should link back to the relevant proposal section.

Routine spelling fixes or a small documentation clarification do not need a full architecture proposal. Scale the record to the decision: keep essential reasoning and mark irrelevant sections N/A with a short reason.

## Workflow

1. Read the current [design handbook](../README.md) and [decision register](../../DECISIONS_AND_RISKS.md).
2. Copy the appropriate template into `docs/design/`; keep these master files unfilled.
3. Assign a unique identifier, concrete title, author and baseline revision/commit.
4. Fill observations, assumptions, scope and success criteria before selecting a solution.
5. Compare options, complete affected design sections and record unresolved dependencies.
6. Record actual review outcomes and link accepted decisions to implementation tasks.
7. Append verification evidence after implementation; keep unrun checks Pending.
8. Record cleanup, revisit conditions and supersession when the design changes.

No review status implies that AWS resources were created or that future spending was authorized. Preserve the actual task scope and resource ownership.

## Names and relative links

Suggested copied filenames are `PROPOSAL-<id>-<short-slug>.md` and `ADR-<id>-<short-slug>.md` in `docs/design/`. Check the main register and existing files before allocating an ADR number; ADR-01 through ADR-21 are already used at the time of this revision.

The master templates live one directory deeper than their proposed copies. Repair links as part of copying:

| Destination | Link from template directory | Link from copied file in design directory |
| --- | --- | --- |
| Main requirements | `../../REQUIREMENTS.md` | `../REQUIREMENTS.md` |
| HLD or LLD | `../HLD.md` / `../LLD.md` | `HLD.md` / `LLD.md` |
| This template guide | `README.md` | `templates/README.md` |
| Design review checklist | `../DESIGN_REVIEW_CHECKLIST.md` | `DESIGN_REVIEW_CHECKLIST.md` |

If a record is stored elsewhere, calculate links from its actual directory. Add the new record to the appropriate index/register. Do not replace the master with a filled decision.

## Status and evidence conventions

| Label | Meaning |
| --- | --- |
| Fact | Observed behavior or established contract, with source/environment/date. |
| Assumption | Unverified premise with validation, owner and consequence if false. |
| Estimate | Modeled value with units, inputs, range and uncertainty. |
| Target | Desired acceptance condition; not a measurement. |
| Pending / not measured | Work or evidence does not exist yet. |
| N/A — reason | A reviewer can see why a topic does not apply. |

Keep design status separate from delivery status. Proposed or In review means the choice is unresolved. Accepted selects a design. Implemented means the change exists; Verified means the stated checks passed with linked evidence. Superseded preserves the old reasoning and points to its replacement.

TBD is acceptable in a draft when the missing value is explicit. Before a decision or release milestone, resolve blocking TBDs or record their disposition, owner and constraint. Do not use empty checkboxes or a completed table as proof of execution.

## Scope the detail to the change

| Change type | Sections that need particular attention |
| --- | --- |
| More backend replicas or revised limits | Workload model, connection skew, per-replica budgets, broker fan-out, rollout pressure and recovery. |
| More nodes or different control plane | Failure domains, reachable ingress, network enforcement, placement, operational ownership and cost. |
| Protocol or browser change | Strict schema, mixed versions, session ordering, close/retry behavior, drafts and accessibility. |
| Identity, rooms or durable history | Authorization, data ownership, retention, ordering, replay, idempotency, backup and irreversible migration boundaries. |
| Delivery or security change | Trusted artifact identity, RBAC, secrets/revocation, interrupted operations, full rollback and negative tests. |

Use the authoritative guides linked from the handbook for current defaults. Reference the baseline revision; if a value changes, update its owner instead of creating a competing default in a copied template.

## Worked framing example — illustrative only

**Candidate problem:** A future benchmark shows legitimate connections reaching the admission limit while node resources remain available.

**Hypothesis:** Additional backend replicas might improve admission without breaching latency, memory or broker limits.

**Evidence still needed:** Actual workload, connection distribution, queue/CPU/RSS data, Redis fan-out cost, rollout peak and recovery measurements. None is supplied by this example.

**Options to compare:** Keep the baseline and reduce client load; optimize the identified bottleneck; change bounded admission if safe; add replicas if measured capacity permits.

**Decision boundary:** Select an option only after tests establish the bottleneck and its trade-offs. More replicas on one node do not change the host failure domain. Any proposed numerical target must come from the relevant requirement or a reviewed revision.

This example demonstrates reasoning structure. It does not select a new replica count, approve a budget or claim a successful test.

## Evidence quality and safe records

For a benchmark, record versions, commit/digests, configuration, environment, workload, warmup/window, raw samples and calculation method. For a security test, capture expected and denied paths plus effective identity. For a cost estimate, record quantities, regional rate sources, quote date, credits separately and retained resources.

Use sanitized artifacts. Keep passwords, tokens, kubeconfig, private chat transcripts and Terraform state out of records. Link controlled evidence where appropriate and explain any access limitation without copying sensitive content.

## Completion checklist

- [ ] The problem, baseline and decision requested are clear.
- [ ] Proposed values are distinguished from measured results.
- [ ] Alternatives and meaningful drawbacks are recorded.
- [ ] HLD, LLD, protocol/data, security and operational impacts are addressed.
- [ ] Capacity, costs, migration overlap and teardown are accounted for.
- [ ] Failure behavior, compatibility, rollback limits and forward repair are explicit.
- [ ] Success/abort criteria and evidence ownership are testable.
- [ ] Links work from the copied record's actual location.
- [ ] Related specifications, index/register and changelog are updated as needed.
- [ ] Review and implementation status match what actually happened.

Use the [design review checklist](../DESIGN_REVIEW_CHECKLIST.md) and [release checklist](../../RELEASE_CHECKLIST.md) for their respective milestones.
