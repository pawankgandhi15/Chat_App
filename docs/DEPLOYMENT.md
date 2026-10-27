# Deployment and recovery

The local Kubernetes deployment is working. AWS infrastructure and signed delivery tooling are implemented, but no AWS environment, public certificate, registry release or cloud rollback rehearsal has been created by this implementation. See [implementation status](IMPLEMENTATION_STATUS.md).

## Local deployment

Follow [Development](DEVELOPMENT.md). The local launcher builds/imports images and applies the local Kustomize overlay. It needs no AWS account.

## AWS prerequisites

Before provisioning, supply and review:

- AWS account/region, actual credit eligibility, cost estimate, budget notifications and teardown owner/date.
- A reviewed Ubuntu 24.04 x86_64 AMI for the region, AZ, existing EC2 SSH key and restricted administrator IPv4 CIDRs.
- The SHA-256 checksum for the selected official K3s binary.
- A real DNS hostname and trusted TLS certificate/key, with a renewal procedure.
- A private Terraform state bucket and separate state/workload identities.
- A controlled Linux deployment runner with private API access, pinned kubectl/Cosign and the Python dependencies from the hashed lock.
- Publicly readable GHCR application images, or separately configured node registry authentication. The current manifests do not provision image-pull credentials.

The code uses one K3s node and K3s ServiceLB. There is no EKS control plane, NAT gateway or managed load balancer. AWS services may still incur charges; account credits are not a zero-cost guarantee.

## Terraform

Two independent roots exist:

| Directory | Responsibility |
| --- | --- |
| `infra/bootstrap-state` | Private encrypted/versioned S3 state bucket, TLS-only access, deletion protection |
| `infra/workload` | VPC, public subnet, routes, restricted security group, EC2 and encrypted 20 GiB gp3 root volume |

The state bootstrap has a local state file initially. Keep it in an access-controlled location and protect it separately. The workload uses an S3 backend with native state locking. Never commit state, credentials or filled tfvars.

After creating/reviewing a state bucket, copy and fill the `.example` files in `infra/workload`. These commands prepare a reviewable plan; applying it is a separate operational action:

~~~bash
terraform -chdir=infra/workload init -backend-config=backend.hcl
terraform -chdir=infra/workload fmt -check
terraform -chdir=infra/workload validate
terraform -chdir=infra/workload plan -out=workload.tfplan
~~~

Review the plan, account, region and costs before executing an approved apply. The checksum-verified bootstrap installs K3s with Traefik disabled and Secrets encryption enabled. Public ingress is limited to HTTP/HTTPS and restricted SSH; the Kubernetes API, backend and Redis ports are not publicly exposed.

There is no static Elastic IP in the current configuration. An instance stop/start can change its public IP; update DNS accordingly. Node-level recovery remains a single-host operation.

## Operator bootstrap

Use an explicit administrative kubeconfig/context that reaches the private API, for example through an SSH tunnel. Do not open port 6443 publicly. Apply the platform resources, then create the required Secrets:

~~~bash
kubectl --kubeconfig /secure/admin.yaml --context aws-demo apply -f k8s/platform/namespace.yaml
kubectl --kubeconfig /secure/admin.yaml --context aws-demo apply -f k8s/platform/deployer-rbac.yaml
python scripts/bootstrap_secrets.py --kubeconfig /secure/admin.yaml --context aws-demo \
  --tls-cert /secure/fullchain.pem --tls-key /secure/privkey.pem
~~~

The Secret helper sends values over stdin, preserves an existing Redis pair and refuses a partially missing pair. It updates the TLS Secret. Validate the certificate's hostname, expiry and key correspondence before using it.

Issue a separate deployment identity and bind it to the `chat-deployer` namespace Role. Credential issuance/RoleBinding depends on the operator's identity system and is intentionally separate from application deployment. The deployment identity can apply application resources but cannot directly create Secrets, RBAC or namespaces. Ability to create Pods through Deployments is still sensitive; protect the runner and enforce the restricted Pod Security namespace.

## GitHub Actions

`validate.yml` builds the local environment and runs unit, browser, integration, manifest and network checks on PRs and main pushes.

`release.yml` is manual and restricted to main. It runs validation, publishes four Linux amd64 images to GHCR, generates SPDX inventories, blocks fixable HIGH/CRITICAL vulnerabilities and signs each image plus `release.json` using GitHub OIDC/Cosign. It uploads a release artifact.

`deploy.yml` is manual and runs on a controlled Linux runner labelled `chat-app-deployer`. Configure the protected `aws-demo` environment and these variables:

| Variable | Meaning |
| --- | --- |
| `DEPLOY_KUBECONFIG` | Absolute path to the runner's restricted kubeconfig |
| `DEPLOY_CONTEXT` | Exact intended context name |
| `DEPLOY_STATE_DIR` | Private persistent directory for accepted bundles and deployment journal |
| `IMAGE_PREFIX` | Exact lowercase prefix, e.g. `ghcr.io/pawankgandhi15/chat_app-` |

Use trusted branches and protect the runner; do not run untrusted pull-request code on it. The workflow downloads the selected Release artifact. Signature verification independently checks the main-branch release workflow identity and GitHub OIDC issuer. Repository names and workflow paths must match the trust policy if this project is forked or renamed.

Neither workflow has been executed in GitHub yet. Local checks do not prove registry permissions, OIDC configuration, environment protections or remote deployment success.

## Bundle verification and deployment

The signed manifest binds four digest references, rendered manifests, scan reports and SBOMs. Verification checks file hashes, scan/image association, fixable high/critical findings, resource types/namespaces, Pod hardening and service exposure. The checked-in policy is a useful control, not a substitute for a general admission-policy engine.

To deploy an already downloaded bundle from the controlled runner:

~~~bash
python scripts/deploy.py --bundle /secure/releases/candidate \
  --kubeconfig /secure/deployer.yaml --context aws-demo \
  --state-dir /secure/chat-deploy-state \
  --identity https://github.com/pawankgandhi15/Chat_App/.github/workflows/release.yml@refs/heads/main \
  --image-prefix ghcr.io/pawankgandhi15/chat_app-
~~~

The script acquires a filesystem lock, verifies/copies the immutable bundle, performs a server dry-run, applies it, waits for the four Deployments and runs a public cross-replica smoke test. It updates `current.json` only after success. GitHub concurrency serializes workflow deployments as well.

## Failure and rollback

If a candidate fails and a previous accepted bundle exists, the script re-verifies and reapplies that complete bundle, waits for readiness and repeats smoke checks. The candidate deployment still exits nonzero after a successful restoration so the failed release is visible.

A first-ever failed deployment has no previous accepted bundle to restore. Inspect the namespace and correct the candidate. If rollback itself fails, keep the failed journal and investigate; do not mark the candidate accepted.

Backend updates use maxSurge 0 / maxUnavailable 1; existing connections on a terminating Pod receive 1012 and reconnect. Gateway, frontend and Redis use Recreate, so whole-bundle updates can interrupt service. **Zero downtime and a 10-minute recovery target have not been demonstrated.** Secrets, DNS, TLS and infrastructure are not restored by an application bundle.

Old hashed ConfigMaps are retained for rollback. After the retention period, an operator can remove only unreferenced versions after checking both active Pod references and retained bundles. No broad namespace pruning is automated.

## Acceptance and teardown

Run the full off-node load test plus node-memory monitoring, Redis/subscriber failure tests, node reboot, TLS renewal, failed-release restoration and cloud teardown rehearsals. Record evidence before calling the AWS deployment accepted.

Remove workload resources through the reviewed Terraform workflow when the demo ends. S3 state is deliberately protected against routine destroy. Check remaining volumes, snapshots, addresses and registry/runner resources separately. The application does not automatically shut down AWS spending.
