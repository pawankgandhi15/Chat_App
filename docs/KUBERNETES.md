# Kubernetes Deployment Design

**Design revision 5 — 2026-10-26. Status: planned, not implemented.** Kubernetes is the primary deployment target. This replaces the earlier optional-Kubernetes / Docker Compose proposal. No cluster or application manifests exist yet.

## Deployment environments

| Environment | Platform | Purpose |
| --- | --- | --- |
| Local development and integration CI | k3d: K3s nodes in Docker | Validate the same application manifests, networking and failure behavior without AWS charges. |
| AWS demonstration | One K3s server/worker on EC2 in `ap-south-1` | Demonstrate Kubernetes with a measured, time-limited credit budget. |
| Future managed cluster | EKS, separately designed and costed | Outside the current implementation scope. |

Docker builds application images and hosts local k3d nodes. On EC2, K3s runs as a host service and uses containerd for Pods. Local tests do not prove AWS security-group, public routing, instance performance or billing behavior. See [k3d](https://k3d.io/stable/) and [K3s architecture](https://docs.k3s.io/).

## Cluster and workload contract

Use one server with its embedded SQLite datastore and local worker. Enable CoreDNS, Flannel and the packaged network-policy controller. Disable packaged Traefik; retain ServiceLB for the gateway. This is one failure domain, with no control-plane or host redundancy.

Namespace: `chat-app`. Four Deployments produce **five steady-state application Pods**, each with one application container. K3s system Pods, deployment transients and test Jobs are additional.

| Deployment | Replicas | Service and port | Pod port | Responsibility |
| --- | --- | --- | --- | --- |
| gateway | 1 | LoadBalancer: 80, 443 | 8080, 8443 | HTTP redirect and HTTPS/WSS termination; route static and WebSocket traffic. |
| frontend | 1 | ClusterIP: 80 | 8080 | Serve HTML, CSS and native JavaScript. |
| backend | 2 | ClusterIP: 8000 | 8000 | One Uvicorn worker per Pod; local sessions and Redis fan-out. |
| redis | 1 | ClusterIP: 6379 | 6379 | Authenticated, ephemeral Pub/Sub; no message-history volume. |

The K3s ServiceLB implementation exposes the gateway on node ports 80/443 using host ports. It is **not an AWS ALB or NLB**. Do not install an AWS load-balancer controller for this design. Confirm public address behavior, source NAT and port ownership in the chosen K3s version. See [K3s networking services](https://docs.k3s.io/networking/networking-services).

Use Service DNS names such as `backend.chat-app.svc.cluster.local`. Readiness controls backend Service endpoints; a WebSocket stays attached to its selected Pod for its lifetime. Replica distribution is measured, not guaranteed to be even. Clients reconnect when their Pod disappears.

## Manifests to implement

Use Kustomize with `k8s/base/`, `k8s/overlays/local/` and `k8s/overlays/aws/`. Keep platform/bootstrap resources separate from namespace-scoped application releases.

- Deployments, Services, explicit resource requests/limits and security contexts.
- Non-secret ConfigMaps; mounted Secrets for Redis, TLS and registry access where required.
- Default-deny ingress and egress NetworkPolicies plus explicit allowed flows.
- Backend startup, readiness and liveness probes.
- ServiceAccounts without automatic API-token mounts for application Pods.
- Release annotations and immutable image digests for every application image.
- Separate platform RBAC, namespace creation, K3s configuration and secret bootstrap instructions.

Local port mappings use localhost 8080/8443 to cluster 80/443, with local origins configured accordingly. Local certificates are development credentials; AWS requires a real hostname and trusted certificate. A local HTTP-only overlay is permitted, but the AWS overlay must fail validation without TLS configuration.

## Resource planning

K3s documents a server minimum of 2 cores and 2 GB RAM **excluding application workload**. The old 1 GiB `t3.micro` proposal is unsuitable. Plan a **2-vCPU, 4-GiB candidate**, then measure OS, K3s, system Pods and application usage. [K3s requirements](https://docs.k3s.io/installation/requirements).

AWS lists `c7i-flex.large` among newer-account Free Tier eligible types; its specification is 2 vCPU and 4 GiB. It is a candidate, subject to account access, regional availability, price and measured capacity. Eligibility is not unlimited free usage. See [EC2 eligibility](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html) and [C7i-flex specifications](https://aws.amazon.com/ec2/instance-types/c7i/).

Proposed starting values below are **test inputs**, not validated sizing:

| Pod | CPU request / limit | Memory request / limit |
| --- | --- | --- |
| gateway | 50m / 250m | 32Mi / 64Mi |
| frontend | 25m / 100m | 16Mi / 48Mi |
| backend, each of two | 100m / 500m | 128Mi / 256Mi |
| redis | 50m / 250m | 64Mi / 128Mi |

Application memory requests total 368Mi; limits total 752Mi. Neither figure includes K3s, node services, kernel memory, container image operations or test Jobs. Require at least 512 MiB node `MemAvailable` under the acceptance workload, no OOMs and no pressure-related evictions. Tune from evidence before release.

## Security and networking

Allow gateway → frontend/backend, backend → Redis and required DNS. Deny gateway/frontend → Redis. Test both directions and Service/Pod IP paths. Public gateway ingress requires a policy compatible with actual ServiceLB/SNAT behavior; a label-only allow rule for browsers is insufficient. NetworkPolicies require an enforcing network implementation and do not replace node firewall rules. [Kubernetes NetworkPolicies](https://kubernetes.io/docs/concepts/services-networking/network-policies/).

Keep 8000/6379 and overlay networking off the public security group. Prefer kubectl on the node over approved SSH access; keep 6443 closed publicly. Any remote API access requires a separately reviewed restricted route and trusted certificate.

Enable K3s secrets encryption at bootstrap. Store secrets in mounted files, restrict RBAC and keep root kubeconfig out of CI. Secret base64 encoding alone is not encryption. [K3s secrets encryption](https://docs.k3s.io/security/secrets-encryption).

## Probes, rollout and rollback

Map backend `/health` to readiness and `/live` to liveness. Startup probes check process startup without making Redis availability a liveness dependency. Proposed readiness: every 2s, timeout 1s, failure threshold 1; liveness: every 10s, timeout 1s, threshold 3. Verify behavior under load and dependency failure.

Use two backend replicas with `maxSurge: 0`, `maxUnavailable: 1`. Use Recreate for singleton gateway/frontend/Redis until a tested overlapping strategy exists. This permits interruptions; it is not zero-downtime deployment. Terminating backend Pods get 20s grace including hooks, with a 10s application drain. Kubernetes endpoint removal is asynchronous: test retry behavior and application admission during termination.

Rollback reapplies the preceding verified release bundle, including configuration and compatible Secret references. `kubectl rollout undo` alone does not restore all release resources. See [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) and [deployment guide](DEPLOYMENT.md).

## AWS credit boundary

K3s removes the EKS cluster fee, but EC2, EBS, IPv4, transfer and state still cost money. Use at most the actual eligible credit balance, capped at $100 for this exercise, with a proposed $20 reserve. No AWS account has been inspected and no $0 bill is guaranteed. Follow the [AWS requirements and cost worksheet](AWS_FREE_TIER_REQUIREMENTS.md) before provisioning.

## Completion evidence

All gates remain open: local manifests validate; five application Pods become ready; cross-replica messaging passes; forbidden network paths fail; Redis recovery and rolling replacement pass; resource targets pass; previous bundle restores within 10 minutes; AWS eligibility/estimate are recorded; teardown and residual billing are checked.
