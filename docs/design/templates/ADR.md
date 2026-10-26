# Architecture Decision Record Template

**Template revision 2 · 2026-10-26. This is an unfilled record; no decision, implementation or verification is implied.**

Use one ADR for one consequential architectural decision. Keep detailed experiments and execution steps in the linked proposal; summarize the reasoning and consequences here. Read the [template guide](README.md) for naming, lifecycle and copy/link rules.

## 1. Identity and decision state

| Field | Value to complete |
| --- | --- |
| ADR ID / title | TBD — unused ID checked against the [decision register](../../DECISIONS_AND_RISKS.md) |
| Decision status | Proposed / Accepted / Rejected / Superseded |
| Delivery status | Not started / In progress / Implemented / Verified / Retired |
| Date proposed / decided / last reviewed | TBD |
| Decision owner / reviewers / operational owner | TBD |
| Baseline revision / source commit / environment | TBD |
| Related proposal, requirement and issue | TBD — stable links |
| Supersedes / superseded by | None or linked ADR |
| Review date / revisit trigger | TBD |

Decision status and delivery status answer different questions. Accepted means the design choice is recorded; Verified requires evidence against stated criteria. A rejected option can remain in history without becoming a deployment instruction.

## 2. Decision in one paragraph

**Given** [observed context and constraints], **we choose** [specific option and boundaries] **to achieve** [measurable outcome], **accepting** [main disadvantage or residual risk]. **We will revisit this when** [observable condition].

State the selected behavior, component or contract precisely. Avoid statements such as “use a scalable architecture” without explaining topology, ownership and expected failure behavior.

## 3. Context and decision drivers

Describe the concrete problem and why it needs a decision now. Include user impact, current workload, failure mode, budget, skills/ownership and existing dependencies.

| Driver ID | Required outcome or constraint | Priority / mandatory? | Source and evidence | Implication |
| --- | --- | --- | --- | --- |
| DR-01 | TBD — correctness or user behavior | TBD | TBD | TBD |
| DR-02 | TBD — reliability / capacity | TBD | TBD | TBD |
| DR-03 | TBD — cost / operational effort | TBD | TBD | TBD |

Separate facts from assumptions. Record unknown versions, account eligibility, service access or performance as unresolved; do not promote an estimate into evidence.

| Assumption ID | Statement | Validation / owner / due | Consequence if false |
| --- | --- | --- | --- |
| A-01 | TBD | TBD | TBD |

Identify baseline contracts that cannot change implicitly: protocol, identity semantics, delivery guarantees, resource bounds, privacy and operational access.

## 4. Options and trade-off analysis

Include retaining the current design. Explain why each option is feasible or excluded before ranking it.

| Option | Behavior and architecture | Benefits | Drawbacks / failure points | Cost and operational ownership | Evidence / uncertainty |
| --- | --- | --- | --- | --- | --- |
| Retain baseline | TBD | TBD | TBD | TBD | TBD |
| Selected candidate | TBD | TBD | TBD | TBD | TBD |
| Alternative or N/A | TBD | TBD | TBD | TBD | TBD |

Assess correctness and compatibility before convenience. A cheaper option that fails a mandatory requirement cannot win through weighted scoring.

If weights are useful, list the scale, criteria and weights and show whether reasonable changes alter the outcome. Mark missing evidence as unknown, not zero risk. State which rejected option becomes preferable if assumptions change.

## 5. Decision details and boundaries

| Concern | Selected rule or mechanism | Affected owner / document | Explicit limitation |
| --- | --- | --- | --- |
| Components and deployment | TBD | [HLD](../HLD.md), [Kubernetes](../../KUBERNETES.md) | TBD |
| Internal interfaces and state | TBD | [LLD](../LLD.md) | TBD |
| External protocol / configuration | TBD | [API](../../API_SPECIFICATION.md), [configuration](../../CONFIGURATION.md) | TBD |
| Data and failure semantics | TBD | [Data design](../DATA_AND_PROTOCOL.md) | TBD |
| Security / release / operations | TBD | Relevant guides and owners | TBD |

Describe the normal path and failure behavior. Include an architecture or sequence diagram only if it clarifies the decision; link larger diagrams instead of maintaining divergent copies.

List non-goals and excluded environments. Explain which current defaults remain authoritative and which require a reviewed change. This ADR must not silently claim authentication, replay, host availability or zero cost that the selected design does not provide.

## 6. Consequences and residual risk

| Type | Consequence | Who is affected | Mitigation or accepted boundary | Evidence / follow-up |
| --- | --- | --- | --- | --- |
| Benefit | TBD | TBD | TBD | TBD |
| Cost / complexity | TBD | TBD | TBD | TBD |
| Failure / security / privacy risk | TBD | TBD | TBD | TBD |
| Dependency / lock-in | TBD | TBD | TBD | TBD |
| Deferred work | TBD | TBD | TBD | TBD |

Name remaining single points of failure and operational duties. State whether additional replicas protect the application, node, control plane, ingress and broker separately.

A mitigation is proposed until tested. Explain how a failed mitigation is detected and who responds. Avoid “fully mitigated” or “guaranteed” unless the claim has a precise scope and evidence.

## 7. Capacity, cost and lifecycle implications

Summarize the linked proposal's workload model, measured bottleneck, operating margin and expected resource changes. Distinguish connection limits, requested resources, cgroup limits and observed consumption.

| Item | Current evidence | Expected effect / uncertainty | Owner / review condition |
| --- | --- | --- | --- |
| Throughput, fan-out and connection distribution | TBD | TBD | TBD |
| Node/Pod resources and rollout peak | TBD | TBD | TBD |
| Recurring and migration-overlap cost | TBD | TBD | TBD |
| Retained storage / backups / logs | TBD | TBD | TBD |
| Upgrade, credential rotation and teardown | TBD | TBD | TBD |

Reference dated quotes and account-specific benefits rather than embedding a timeless “free” claim. Record what happens when credits expire, quotas change, dependencies lose support or the operator can no longer sustain the maintenance load.

## 8. Compatibility, adoption and reversal

| Change surface | Compatibility strategy | Adoption checkpoint | Reversal or forward repair |
| --- | --- | --- | --- |
| Client/server or event schema | TBD | TBD | TBD |
| Mixed backend versions / broker behavior | TBD | TBD | TBD |
| Configuration / Kubernetes / Terraform | TBD | TBD | TBD |
| Secrets / identity / permissions | TBD | TBD | TBD |
| Durable data, if introduced | TBD or N/A with reason | TBD | TBD |

Link the executable migration plan once it exists. Define the maximum coexistence period, state writer ownership, session drain and old-resource retirement criteria.

State reversibility explicitly: fully reversible, reversible with interruption, or constrained by data/contract changes. Identify the last safe checkpoint, rollback prerequisites and the point beyond which old binaries are unsafe. Record data-loss and credential-revocation boundaries.

## 9. Verification contract

| Evidence ID | Requirement / success criterion | Experiment and environment | Expected observation | Result and artifact |
| --- | --- | --- | --- | --- |
| V-01 | TBD | Functional / compatibility | TBD | Pending |
| V-02 | TBD | Failure / recovery | TBD | Pending |
| V-03 | TBD | Load / resource margin | TBD | Pending |
| V-04 | TBD | Security / negative access | TBD | Pending |
| V-05 | TBD | Rollback / cleanup / cost | TBD | Pending |

Use applicable [acceptance criteria](../../REQUIREMENTS.md) and the [review checklist](../DESIGN_REVIEW_CHECKLIST.md). Mark irrelevant experiments N/A with reason. Verification must test the decision's important assumptions, not just repeat its desired configuration.

Record exact release/configuration, workload, environment and limitations. Code existing, Pods being Ready and a screenshot of a dashboard are different from proving user-visible behavior.

## 10. Open questions and implementation obligations

| Item ID | Question or obligation | Owner / due | Blocking which milestone? | Resolution / evidence |
| --- | --- | --- | --- | --- |
| O-01 | TBD | TBD | Design / implementation / release / nonblocking | TBD |

Link existing OPEN IDs when applicable. Do not close an open item merely because a candidate was written down.

Record implementation tasks, runbook changes, documentation owners, planned removal of temporary resources and any time-limited exception. Keep the main register current so this record does not become a second inconsistent backlog.

## 11. Review outcome and dissent

| Reviewer / role | Area | Position and rationale | Date / evidence |
| --- | --- | --- | --- |
| TBD | TBD | Pending | TBD |

**Outcome:** TBD. **Accepted scope and conditions:** TBD. **Recorded disagreement:** None or concise rationale. **Unresolved blocker:** TBD or None with evidence.

Document a disagreement fairly and explain why the selected trade-off was accepted. Record actual review outcomes; do not prefill fictitious approvals.

## 12. Follow-up, revisit triggers and supersession

| Trigger | Observable condition | Review owner / date | Likely action |
| --- | --- | --- | --- |
| Workload or reliability changes | TBD | TBD | Re-benchmark or revise topology |
| Assumption or cost changes | TBD | TBD | Reassess option and budget |
| Security or dependency changes | TBD | TBD | Patch, replace or restrict scope |
| Operational burden changes | TBD | TBD | Reassign ownership or simplify |

After implementation, compare expected and observed outcomes and append links to measured evidence. If the decision changes, create a new ADR and mark this one Superseded with a reciprocal link. Preserve its original context, rejected options and consequences; annotate factual corrections rather than rewriting history to match the new choice.

## 13. Record history

| Date | Change | Author | Reason / linked evidence |
| --- | --- | --- | --- |
| TBD | Initial proposal | TBD | TBD |
