# Deployment and Rollback

**Design revision 5 — 2026-10-26. Status: proposed procedure.** No manifests, release bundles or deployment scripts exist. Examples become usable only after implementation and validation.

## Release contents and trust

A release is a signed manifest plus rendered Kubernetes configuration and exact image digests. Record source commit, release ID, target platform, K3s compatibility, image references, configuration hashes, SBOM/provenance references and required Secret names/versions. Do not include secret values.

Verify signatures against the expected repository, workflow identity and issuer, then verify hashes before applying any artifact. A valid signature alone does not authorize arbitrary RBAC, hostPath or privileged resources. Restrict application bundles to reviewed namespace-scoped kinds and reject namespace overrides, cluster roles and unsafe Pod specifications.

Keep at least current and previous verified bundles and their compatible secret/configuration references. Define retention before enabling image garbage collection.

## First deployment gates

1. Complete local integration, policy and failure tests in [testing](TESTING.md).
2. Confirm the actual AWS credit balance, instance permission, regional estimate and destruction time.
3. Review Terraform plan; provision the selected node only when implementation is authorized.
4. Bootstrap the pinned K3s platform, namespace, RBAC and encryption; verify DNS and ServiceLB.
5. Install generated Redis credentials, trusted TLS material and registry pull access through the restricted bootstrap path.
6. Verify deployer permissions and network route; keep root kubeconfig out of CI.
7. Verify and apply the first release; collect functional and resource evidence.

The primary AWS type remains a measured 2-vCPU/4-GiB candidate. No EKS, managed load balancer or NAT resource should appear in this plan.

## Application update transaction

Use CI environment concurrency and a single deployment entry point. A node-local advisory lock may serialize that entry point, but it does not prevent another administrator from running kubectl. Restrict bypass paths and record all changes.

| Stage | Required action | Failure handling |
| --- | --- | --- |
| Preflight | Confirm context, node, namespace, current release, budget window and available disk/memory. | Stop before mutation if identity or capacity is uncertain. |
| Verify | Check signed bundle, image identity/digests, hashes and permitted resource kinds. | Reject invalid input; do not execute scripts from the bundle. |
| Preview | Render overlay, validate schemas/policies and review server-side diff/dry-run. | Record and resolve drift or permission failures. |
| Apply | Reconcile configuration and workload resources in dependency order. | Record partial progress; Kubernetes apply is not atomic. |
| Rollout | Wait for expected ready replicas and exact image/config revisions with bounded timeouts. | Capture events/logs, then restore prior bundle. |
| Verify behavior | Frontend/TLS, session-first, two-Pod messaging, private diagnostics, network boundaries. | Roll back even if Pods report Ready. |
| Accept | Record release ID, artifacts, evidence and previous release pointer. | Do not mark accepted before functional checks finish. |

A release journal should record started, applied, verified, failed or restored state. After interruption, inspect live image IDs, configuration references and journal before resuming. Do not infer success from the last shell exit alone.

## Rollout behavior

Backend Deployment: two replicas, zero surge, maximum one unavailable. Each terminating backend rejects new admissions and drains sockets with 1012 within 10s; total Pod grace is 20s including hooks. Verify temporary endpoint races and browser retries.

Gateway, frontend and Redis are singletons with Recreate in the initial design. Their updates can interrupt service; Redis replacement loses ephemeral messages and briefly makes both backends unready. No zero-downtime claim is made.

Normal updates preserve Service identities and ClusterIPs. If Service recreation is unavoidable, verify DNS resolution and reload gateway configuration as needed. NetworkPolicy changes must be tested before removing the previous allowed path.

## Rollback procedure

1. Select the last accepted compatible bundle and verify its signatures/hashes again.
2. Check that its referenced credentials and TLS material remain valid. Never restore a revoked or compromised secret just to match an old release.
3. Reapply its ConfigMaps, workload specs, Services and policies using the controlled entry point.
4. Reconcile resources introduced by the failed release using an explicit owned-resource inventory; avoid broad pruning that can remove bootstrap Secrets or unrelated resources.
5. Wait for ready replicas and verify actual image IDs/configuration hashes.
6. Run session-first and cross-replica messaging checks, diagnostics denial and critical policy checks.
7. Record elapsed recovery, failure cause and restored release. Target <=10 minutes; measure it.

`kubectl rollout undo` alone is insufficient: it does not restore a complete multi-resource release. Rollback cannot recover messages lost during disconnection. If restoration fails, keep the incident open and use the node/platform recovery procedure.

## Secret and platform changes

Separate credential rotation, TLS renewal, K3s upgrade and application releases where possible. Define a compatibility window for old/new credentials before rollout. K3s upgrades require supported-version review, protected state backup/restore instructions and an explicit maintenance window; application rollback is not a Kubernetes downgrade procedure.

## Required deployment evidence

Capture sanitized manifest identity, context/account/region, prior/current release, rendered hashes, Pod image IDs, readiness/events, functional results, resource peaks, rollback elapsed time and any retained resources. See [CI/CD](CICD.md), [release checklist](RELEASE_CHECKLIST.md) and [operations](OPERATIONS.md).

