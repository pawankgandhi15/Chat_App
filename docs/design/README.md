# System Design Handbook

**Status: design documentation only. Baseline: design revision 5. Updated: 2026-10-26.**

This folder is the starting point for understanding, implementing and evolving Chat App. **HLD (high-level design)** explains components, boundaries and deployment. **LLD (low-level design)** explains internal responsibilities, state, interfaces and failure handling.

The selected baseline remains local k3d and one AWS EC2 K3s node. Future architectures here are proposals, not deployed systems or approved spending.

## Read in this order

| Document | Use it for |
| --- | --- |
| [HLD](HLD.md) | Product scope, system context, component topology, trust boundaries and trade-offs. |
| [LLD](LLD.md) | Backend/browser modules, conceptual interfaces, task ownership and lifecycle invariants. |
| [Sequence diagrams](SEQUENCE_DIAGRAMS.md) | Connect, publish, failure recovery and deployment flows. |
| [Data and protocol design](DATA_AND_PROTOCOL.md) | Current ephemeral state and requirements for future identity/history. |
| [Capacity planning](CAPACITY_PLANNING.md) | Workload calculations, bottleneck measurements and scaling triggers. |
| [Architecture evolution](ARCHITECTURE_EVOLUTION.md) | Staged HLD upgrades, HA, autoscaling and optional product extensions. |
| [Migration playbook](MIGRATION_PLAYBOOK.md) | Compatibility, staged rollout, rollback, cutover and budget controls. |
| [Design review checklist](DESIGN_REVIEW_CHECKLIST.md) | Review gates, acceptance mapping and unresolved decisions. |
| [Change proposal template](templates/CHANGE_PROPOSAL.md) | Describe a proposed architecture or feature upgrade before implementation. |
| [ADR template](templates/ADR.md) | Record a decision, alternatives, consequences and supersession. |

## Which document owns a rule?

This handbook connects existing specifications; it does not create competing defaults.

| Concern | Authoritative project guide |
| --- | --- |
| Scope, FR/AC IDs and quantitative targets | [Requirements](../REQUIREMENTS.md) |
| Wire schema, normalization and close codes | [API specification](../API_SPECIFICATION.md) |
| Environment variables and default bounds | [Configuration](../CONFIGURATION.md) |
| Kubernetes resources and platform choices | [Kubernetes](../KUBERNETES.md) |
| Detailed frontend and backend implementation requirements | [Frontend](../FRONTEND.md), [backend](../BACKEND.md) |
| Current system architecture and technology selection | [Architecture](../ARCHITECTURE.md), [technologies](../TECHNOLOGIES.md) |
| AWS eligibility, spending and Terraform | [AWS requirements](../AWS_FREE_TIER_REQUIREMENTS.md), [infrastructure](../INFRASTRUCTURE.md) |
| Release and operational procedures | [CI/CD](../CICD.md), [deployment](../DEPLOYMENT.md), [operations](../OPERATIONS.md) |
| Verification and implementation order | [Testing](../TESTING.md), [release checklist](../RELEASE_CHECKLIST.md), [implementation plan](../IMPLEMENTATION_PLAN.md) |
| Security and decision history | [Security](../SECURITY.md), [decisions and risks](../DECISIONS_AND_RISKS.md) |
| Planned source paths | [Project structure](../PROJECT_STRUCTURE.md) |

If a proposed upgrade changes an authoritative rule, update that owner and its tests in the same reviewed change. A future-stage diagram alone does not change the baseline.

## How to maintain this folder

1. Record a measured problem or new product requirement using the change proposal template.
2. Select the smallest evolution stage that addresses it; calculate the full operating cost.
3. Update affected HLD, LLD, data/sequence diagrams and authoritative contracts.
4. Record the decision and identify implementation tasks, compatibility tests and rollback conditions.
5. After implementation, attach evidence and update status to verified only for the scope tested.

Use Git history for previous design versions; avoid multiple conflicting files called “final HLD.” Retain historical diagrams with clear labels and link current documentation to the accepted design. No application source, manifests or cloud resources are created by this handbook.
