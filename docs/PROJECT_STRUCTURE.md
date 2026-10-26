# Planned Project Structure

**Design revision 5 — 2026-10-26.** Only root Markdown, documentation and architecture images currently exist. Every source/configuration path below is a proposal, not a runnable file.

## Future layout

```text
Chat_App/
  README.md
  CONTRIBUTING.md
  CHANGELOG.md
  docs/
    design/                 # Existing HLD, LLD, evolution and review handbook
      templates/            # Existing architecture proposal and ADR templates
    images/
  backend/
    app/
      main.py
      settings.py
      protocol.py
      validation.py
      sessions.py
      limits.py
      broker.py
      health.py
      telemetry.py
    requirements.in
    requirements.lock
    Dockerfile
  frontend/
    index.html
    css/
    js/
      app.js
      protocol.js
      connection.js
      state.js
      view.js
    nginx.conf
    Dockerfile
  gateway/
    nginx.conf
    Dockerfile
  schemas/
    events-v1.schema.json
    release.schema.json
  k8s/
    base/
      kustomization.yaml
      gateway/
      frontend/
      backend/
      redis/
      network-policies/
    overlays/
      local/
      aws/
    platform/
      namespace.yaml
      deployer-rbac.yaml
  infra/
    bootstrap-state/
    workload/
  platform/
    k3s/
    k3d/
  scripts/
    verify-release.sh
    deploy.sh
    rollback.sh
    smoke-test.sh
  tests/
    unit/
    property/
    contract/
    integration/
    browser/
    infrastructure/
    load/
  .github/
    workflows/
      validate.yml
      release.yml
      deploy.yml
```

## Responsibility boundaries

Backend modules separate settings, wire schemas, validation, session ownership, limit accounting, Redis supervision, health and telemetry. One writer owns each socket; subscriber code never waits for browser I/O.

Frontend modules separate protocol validation, connection/retry state, view state and safe DOM rendering. Runtime secrets never appear in frontend assets.

Each Kubernetes component directory contains its Deployment, Service and applicable non-secret configuration. NetworkPolicies are reviewed as a set. Base manifests express shared behavior; overlays hold explicit differences such as origins, TLS references, local ports and public release digests.

Platform configuration owns K3s installation/version, encryption, namespace and RBAC. Application releases cannot grant themselves cluster-wide privileges. Secret values are provisioned outside Git; checked-in examples name required keys only.

Terraform state bootstrap has an independent lifecycle from workload infrastructure, so destroying a demo does not accidentally destroy the evidence needed to manage it. Release scripts consume verified bundles rather than executing arbitrary files from a downloaded archive.

## Generated artifacts

Do not commit credentials, kubeconfig, server tokens, private keys, Terraform state/plans, local environment files, raw user-containing logs or build caches. Commit dependency/provider locks and safe schemas. Store signed release manifests, rendered hashes, SBOMs and sanitized test evidence in versioned artifact storage with retention.

## Naming and traceability

Use namespace `chat-app`, stable app labels and release annotations. Avoid Pod-name assumptions because replacement changes identity. All documentation links to future paths must identify them as planned; the README must not advertise nonexistent setup scripts.

See [implementation plan](IMPLEMENTATION_PLAN.md), [configuration](CONFIGURATION.md) and [CI/CD](CICD.md).

