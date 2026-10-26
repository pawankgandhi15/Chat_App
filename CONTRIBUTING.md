# Contribution Guide

**Current phase:** Documentation and design only. This guide describes how to maintain the plans and how future implementation contributions should be reviewed. See the [documentation index](README.md).

## Start Here

Read the [requirements](docs/REQUIREMENTS.md), [architecture](docs/ARCHITECTURE.md), [API specification](docs/API_SPECIFICATION.md) and [implementation plan](docs/IMPLEMENTATION_PLAN.md). Check [open decisions](docs/DECISIONS_AND_RISKS.md) before selecting a default that affects other components.

The original planning document is historical context. Its snippets are not verified source code. Describe an implementation correction in the current guides rather than rewriting the historical discussion.

## Documentation Contributions Now

1. Identify the missing detail or contradiction and the affected guides.
2. Make a focused change that preserves the containerized Kubernetes application runtime (k3d locally, K3s on AWS) and initial feature scope.
3. Distinguish an existing design choice from a proposed default or unresolved decision.
4. Keep local links relative and add a README index entry for a new guide.
5. Check links, tables, fenced examples and status statements.
6. Record material documentation changes in the changelog.

Do not mark an implementation milestone or acceptance criterion complete without corresponding evidence. Keep commands labeled as future examples until their prerequisites exist.

## Future Implementation Contributions

After implementation work is requested:

1. Use a focused branch and identify the requirement or acceptance criterion being addressed.
2. Follow the implementation phases, including the early containerized test setup.
3. Add meaningful checks for behavior, failures and cleanup rather than tests that only repeat implementation details.
4. Run the checks relevant to the change and record their actual results.
5. Update the API, configuration and operational guides when behavior changes.
6. Prepare a pull request that another contributor can review without the chat history.

Keep unrelated refactoring and new features outside a focused change. Accounts, history and extra rooms require an explicit scope change before implementation.

## Change-to-Documentation Map

| Change | Review or update |
| --- | --- |
| Route, event field or close behavior | API specification, browser behavior and testing plan. |
| Environment variable or validation limit | Configuration reference, API policy and relevant tests. |
| Service topology or Redis lifecycle | Architecture, failure scenarios and operations. |
| Image build or dependency versions | Technology overview, selected-version decision and CI checks. |
| Cloud resources or deployment access | Infrastructure, security, configuration and teardown procedures. |
| Release or rollback behavior | CI/CD, deployment guide and release checklist. |
| Evidence or capability claims | Changelog, demo guide and the corresponding acceptance criteria. |

## Pull Request Description

Explain the concrete problem and resulting behavior. Include the scope, affected requirement IDs, validation results and material limitations. For documentation changes, identify what was clarified; do not imply that a described feature was implemented.

Suggested review checklist:

- [ ] The change matches the requested scope.
- [ ] The docs distinguish proposed behavior from verified behavior.
- [ ] Relevant local links and examples are consistent.
- [ ] Meaningful validation is recorded, or clearly marked not run.
- [ ] No secrets, private chat content, Terraform state or saved plans are included.
- [ ] Related guides and the changelog are updated when needed.

## Reporting Problems

Include the affected guide or future release identifier, expected result, observed result and sanitized reproduction details. Record the environment and time when reporting a runtime issue. Do not publish private keys, credentials, raw environment output or sensitive chat transcripts.

For credential exposure, follow the rotation guidance in the [security plan](docs/SECURITY.md); deleting the visible value is not sufficient recovery.

## Related Guides

[Development](docs/DEVELOPMENT.md), [testing](docs/TESTING.md), [decisions and risks](docs/DECISIONS_AND_RISKS.md), [changelog](CHANGELOG.md).
