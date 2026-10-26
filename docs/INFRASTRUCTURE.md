# AWS Infrastructure Design

**Design revision 5 — 2026-10-26. Status: specification only.** Terraform and bootstrap files do not exist. [Kubernetes](KUBERNETES.md) defines the application platform; [AWS requirements](AWS_FREE_TIER_REQUIREMENTS.md) defines account and cost gates.

## Resource inventory

| Resource | Proposed configuration | Validation |
| --- | --- | --- |
| Region | `ap-south-1` / Mumbai | Confirm account access, quotas and selected instance availability. |
| VPC | `10.0.0.0/16` | Avoid overlap with local/private connectivity. |
| Public subnet | `10.0.1.0/24`, one availability zone | Default IPv4 route through Internet Gateway. |
| EC2 | Ubuntu 24.04 LTS x86_64 candidate; 2 vCPU / 4 GiB | Resolve trusted regional AMI; validate K3s compatibility and capacity. |
| Instance type | `c7i-flex.large` candidate | Confirm allowed by plan, region and estimate; never silently substitute. |
| Root volume | 20 GiB encrypted gp3 starting size | Measure image/cache/log/state usage; explicitly choose deletion-on-termination. |
| Public IPv4 | One address while running | Include address-hours in estimate; reassignment can require DNS updates. |
| Security group | 443 public; 80 only when needed; 22 approved source CIDRs | No public 6443, 8000, 6379 or overlay ports. |
| IMDS | Require IMDSv2 | Minimize instance profile permissions; review Pod access to metadata. |
| Terraform state | Private, encrypted, versioned S3 bucket | Block public access; least-privilege state and lock access. |

No NAT Gateway, AWS load balancer, EKS cluster or managed data service belongs in the baseline plan. ServiceLB is software on the EC2 node.

The candidate type has 2 vCPU and 4 GiB and appears on AWS's newer-account eligibility list. This does not establish launch permission or a free runtime allowance for this account. See [C7i-flex specification](https://aws.amazon.com/ec2/instance-types/c7i/) and [EC2 eligibility](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html).

## Terraform interface to implement

Inputs: account/environment identifiers, region, validated AMI ID, instance type, subnet AZ, administrative CIDRs, hostname, root volume size, resource tags and state configuration. Reject unrestricted SSH, invalid CIDRs, undersized node choices and unresolved placeholders.

Outputs: instance ID, public address, security-group ID and non-secret deployment identifiers. Do not output tokens, private keys, Redis credentials or kubeconfig.

Maintain a separate bootstrap/state lifecycle. Pin Terraform and provider versions, commit the provider lockfile and use native S3 locking with `use_lockfile = true` on Terraform 1.10+. Never put credentials into backend configuration committed to Git. State may contain sensitive values even when outputs are marked sensitive.

Review the saved plan for unexpected recurring services, changes to the account/region, resource destruction and security exposure. Tag resources with project, environment, owner and planned teardown date. Tags aid inventory but do not stop billing.

## Node bootstrap contract

1. Validate OS/architecture, disk, time synchronization and package sources.
2. Install an explicitly selected K3s release through a verified installation process; avoid uncontrolled `latest` upgrades.
3. Configure K3s server with local worker, SQLite, CoreDNS, network policy and ServiceLB; disable Traefik.
4. Enable secrets encryption at initial bootstrap and restrict server-token/kubeconfig permissions.
5. Configure node logging, image cleanup and access policy; avoid exhausting the 20 GiB root disk.
6. Bootstrap namespace and deployment RBAC separately from application releases.
7. Verify node readiness, required DNS, policy enforcement and port ownership before deploying the app.

K3s runs on the host with containerd; Docker Engine is not the AWS application runtime. No application image builds or load generators run on this node. Platform initialization contains no plaintext credentials in cloud-init/user-data.

## Access paths

Prefer restricted SSH followed by node-local kubectl. The deployer uses namespace-scoped permissions rather than the root K3s kubeconfig. Design issuance, expiry and revocation of its credential before automated deployment.

GitHub OIDC provides AWS authentication, not SSH connectivity. A hosted runner with arbitrary outbound addresses will not satisfy a narrow SSH allowlist. Use an approved runner with known egress or a controlled operator workstation. Do not open SSH or the Kubernetes API to the world to make a pipeline pass.

## Network validation

Prove internet → gateway works and internet → backend/Redis/API fails. Prove gateway → frontend/backend and backend → Redis work; prove gateway/frontend → Redis fails. Validate DNS and kubelet probes under policy. Record actual ServiceLB source-address translation before selecting gateway ingress NetworkPolicy rules.

If an instance role is unnecessary, omit it. If present, use minimal privileges and assess IMDS access from Pods; IMDSv2 alone is not a complete Pod isolation boundary.

## Lifecycle and recovery

An EC2 stop does not delete EBS or all related resources. A terminated node loses local cluster state unless retained/recovered; application messages are ephemeral in either case. Rebuild from infrastructure, platform configuration, verified release and separately protected secrets. Define encrypted backup access and test restore before claiming a platform recovery objective.

Teardown destroys the workload infrastructure from its reviewed state, then inventories retained volumes, snapshots, addresses, buckets and other services. Keep the protected state bucket until destruction is verified; its retention and eventual deletion are explicit decisions. Recheck billing after delayed usage records appear.

## Evidence required

Record plan, region, AMI, instance specification, K3s version, network checks, node measurements, release ID, cost estimate, actual runtime, retained resources and teardown owner. No infrastructure acceptance box is complete yet.

