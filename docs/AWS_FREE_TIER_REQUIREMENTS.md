# AWS Free Tier Requirements

**Status:** Deployment prerequisites and cost review only. No AWS account has been inspected and no resources have been provisioned.

**Official AWS guidance checked:** 2026-10-26. Recheck account eligibility and regional prices before provisioning.

This guide applies to the project's planned single EC2 host running five application containers: an Nginx gateway, a static frontend, two FastAPI backends and Redis. It supplements the [infrastructure plan](INFRASTRUCTURE.md). Free Tier eligibility does not establish that this workload will cost zero or meet its performance targets.

## 1. Account Eligibility

| Account situation | Requirement before deployment |
| --- | --- |
| New customer using the current Free plan | Confirm the plan is active, the required services are available, and enough credits and time remain for the experiment. |
| Paid plan with promotional credits | Check eligible charges, remaining credits and their expiry. Usage outside credit coverage can be billed. |
| Older account | Check actual benefits in the console; do not assume a fresh introductory allowance. |
| Organization-managed account | Have the account owner confirm account restrictions, billing visibility and applicable benefits. |

AWS currently advertises $100 in sign-up credits plus up to $100 earned through eligible activities. The Free plan lasts up to six months or until credits are exhausted. Additional credits are conditional, not an assumed $200 starting balance. AWS changed its sign-up experience in October 2026; record the expiry shown for the specific account in the Settings Portal or Billing Credits page. Plan expiry can suspend access, so schedule teardown and preserve needed records before that date. See the [AWS Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/).

AWS distinguishes accounts created before July 15, 2025 from newer accounts. The older EC2 introductory offer lasted 12 months; those introductory periods have elapsed as of this guide's verification date. The familiar legacy 750-hour allowance must not be used as a current entitlement for this project. `t3.micro` and `gp3` appear in AWS's eligible resource lists, but account benefits, AMI eligibility and available credits still require verification. See [EC2 Free Tier eligibility](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html).

## 2. Required AWS Resources

These are project design choices, not a list of resources automatically supplied free by AWS.

| Resource | Planned requirement | Verification |
| --- | --- | --- |
| Region | `ap-south-1` (Mumbai) | Account access, instance availability, quotas and regional prices. |
| EC2 instance | One Linux `t3.micro`, shared tenancy, On-Demand | 2 vCPUs, 1 GiB RAM; confirm eligibility and capacity in the selected Availability Zone. |
| Operating system | Canonical Ubuntu Server 24.04 LTS, `amd64` | Verify publisher, region-specific AMI ID, architecture and software charges; record the exact selected AMI. |
| CPU credit mode | Explicit `standard` | Confirm the launch configuration instead of relying on the account default. |
| Root disk | One encrypted 20 GB `gp3` EBS volume | Baseline IOPS/throughput; deletion on termination; no extra disks by default. |
| Network | One VPC, public subnet, internet gateway and associated route table | Planned CIDRs `10.0.0.0/16` and `10.0.1.0/24`; internet route `0.0.0.0/0`. |
| Public address | One auto-assigned public IPv4 address | Include its usage in the estimate; an Elastic IP is not required by the base design. |
| Security group | HTTP/HTTPS and restricted administrative SSH | Use the port requirements below. |
| SSH key pair | Existing public key imported for the operator/deployer | Keep the private key outside the repository and Terraform inputs/state. |
| Terraform state | Private, encrypted, versioned S3 bucket and lock objects | Required by the current remote-state blueprint; bootstrap separately, choose a unique bucket name and include storage/request costs. |

The instance specification is documented on the [AWS T3 page](https://aws.amazon.com/ec2/instance-types/t3/). Do not substitute an ARM-based instance without also reviewing the AMI and every container image's architecture.

The base application does not require EKS, a NAT gateway, a managed load balancer, RDS, ElastiCache or ECR. Redis runs inside Docker on EC2. Adding managed services requires a revised architecture and cost estimate.

## 3. Account, Access and Local Tools

- Complete AWS account verification and any payment/identity steps required for the selected sign-up path.
- Protect the root user with MFA. Use a separate operator identity with temporary credentials where supported and permissions limited to the intended work. Follow [AWS IAM best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html).
- Give the operator permission to inspect and manage the planned EC2/VPC resources and tags, import the public key, and access the selected state bucket and lock objects. Grant IAM role-management permissions only if that work is part of the approved deployment design.
- Ensure someone responsible for the project can inspect billing, credits and budgets. Provisioning permission alone is insufficient for cost review.
- Prepare Git, AWS CLI, a compatible Terraform release, an SSH client, Docker Engine or Docker Desktop, and Compose v2. The S3 lockfile design requires Terraform 1.10 or later; validate the eventual tool and provider locks together before use. See the [Terraform 1.10 release notes](https://github.com/hashicorp/terraform/releases/tag/v1.10.0) and [S3 backend prerequisites](https://developer.hashicorp.com/terraform/language/backend/s3).
- Keep AWS credentials in the normal credential/profile chain. Never place access keys, private keys or tokens in Markdown, Git, Terraform variable files or cloud-init scripts.
- Prepare the chosen GitHub repository and container registry access separately. Their quotas and plans are independent of AWS Free Tier.

The current design describes GitHub OIDC plus SSH deployment. OIDC authenticates AWS API access; it does not provide network access to port 22. Before implementation, identify a runner with permitted outbound IP addresses or revise the deployment access design. Do not open SSH to the entire internet to accommodate an unknown runner address.

## 4. Network and HTTPS Requirements

| Port | Intended exposure | Requirement |
| --- | --- | --- |
| TCP 443 | Public application access | HTTPS/WSS termination at the Nginx gateway. |
| TCP 80 | Public redirect and certificate validation, if used | Keep its purpose explicit in the gateway configuration. |
| TCP 22 | Approved administrator/deployment source CIDRs only | Use the actual source address, for example an operator's public IPv4 `/32`. |
| TCP 8000 | Container network only | No public security-group rule or backend host-port publishing. |
| TCP 6379 | Internal container data network only | No public security-group rule or Redis host-port publishing. |

For the planned hostname-based TLS flow, supply a real hostname under the operator's control and a certificate issuance/renewal method. `chat.example.com` in other guides is a placeholder. Domain registration and DNS hosting must be budgeted separately; Route 53 is not mandatory. Allow the outbound connectivity needed for package installation, image pulls, DNS and certificate renewal.

## 5. Cost Controls and Estimate

Create an estimate for **Mumbai**, the selected Linux instance and the intended experiment duration. Use the [AWS Pricing Calculator](https://calculator.aws/) and retain the assumptions with the release record. Do not copy prices from another region or equate an eligible-resource label with an unlimited allowance.

| Cost category | Include in the estimate | Control |
| --- | --- | --- |
| EC2 | Instance running time, including idle periods | Run one host and record a teardown time. |
| EBS | Provisioned storage while the volume exists; extra performance or snapshots if added | Keep 20 GB baseline `gp3`, rotate logs, review retained volumes/snapshots. |
| Public IPv4 | Every allocated address-hour | Use one required public address and account for any retained Elastic IPs. |
| CPU surplus credits | Possible when using Unlimited mode | Keep the planned `standard` mode and measure throttling effects. |
| Network | Internet egress and any cross-region or cross-AZ transfers | Estimate chat fan-out, downloads and test traffic; inspect account-wide allowances. |
| S3 state | Storage, old object versions and API requests | Keep state protected and include its separate lifecycle in teardown planning. |
| Optional services | DNS, domain registration, logs, alarms, backups or additional security services | Review each service before adding it. |

AWS lists public IPv4 at **USD 0.005 per address-hour** for both in-use and idle addresses. One address for 24 hours therefore represents **USD 0.12 before applicable credits or benefits**, excluding every other resource. See [VPC pricing](https://aws.amazon.com/vpc/pricing/).

EBS charges depend on provisioned capacity and performance, not just the space occupied by application files. Retained storage continues to incur usage after the instance is stopped. See [EBS pricing](https://aws.amazon.com/ebs/pricing/).

T3 normally launches in Unlimited mode unless its default is changed; sustained CPU above baseline can incur surplus-credit charges. Explicit Standard mode avoids that charging mechanism, but exhausted credits reduce available CPU toward baseline. Standard mode does not eliminate compute, storage or networking costs. See [Unlimited mode](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances-unlimited-mode.html) and [Standard mode](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances-standard-mode.html).

Set an owner-approved budget with actual and forecast alerts, and verify delivery. Inspect gross service usage as well as credit-adjusted cost: a zero balance due can still mean credits are being consumed. Budget data updates periodically, so alerts are not a real-time spending cutoff. See [AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html).

For review, record `compute + EBS + IPv4 + transfer + state + optional services` before subtracting only benefits confirmed for this account. Record currency and applicable taxes separately. A paid-plan estimate must include the cost after credits expire.

## 6. Capacity and Deployment Readiness

The 1 GiB host is a constrained demonstration target. Container limits, connection counts and latency objectives in other guides remain unverified until implementation and load testing. CPU credits, image extraction, OS processes, logs and deployment overlap affect capacity.

Build and scan images in CI, then deploy the selected images to the host. Measure host available memory, disk space, CPU credit balance and application behavior during representative traffic and rollback. If the target does not fit, reduce the workload or review a larger instance and its cost before changing the deployment plan. See the [testing plan](TESTING.md).

## 7. Account-Specific Readiness Record

Fill this record before provisioning. Store account identifiers and billing evidence privately; never add credentials here.

| Item | Value to record |
| --- | --- |
| Account creation date and active plan | Not yet verified. |
| Credit balance, eligible charges and expiry | Not yet verified; use the account's console. |
| Other workloads consuming shared benefits | Not yet reviewed. |
| Region and Availability Zone | Planned `ap-south-1`; actual zone and capacity to verify. |
| Instance, AMI ID and credit mode | Planned `t3.micro`, Ubuntu 24.04 `amd64`, Standard; exact AMI to select. |
| AWS operator profile and access owner | To be assigned; profile name only, no credentials. |
| SSH source CIDRs and deployment runner | To be verified. |
| State bucket, access and recovery owner | To be assigned; example names are not provisioned buckets. |
| Real hostname and certificate method | To be supplied before public TLS deployment. |
| Estimated usage, spending limit and alert recipient | To be agreed and recorded by the account owner. |
| Experiment start, teardown time and teardown owner | To be scheduled before provisioning. |

## 8. Pre-Provisioning Checklist

- [ ] Account plan, credits, expiry and service access verified.
- [ ] Regional instance/AMI eligibility, capacity and quotas checked.
- [ ] Whole-stack estimate reviewed, including IPv4, EBS, state and post-credit costs.
- [ ] MFA, operator credentials, billing access and tested budget notifications ready.
- [ ] Actual SSH source CIDRs and deployment access path documented.
- [ ] Exact AMI, Standard credit mode and root-volume lifecycle selected.
- [ ] State backend and locking prerequisites validated before Terraform initialization.
- [ ] Public hostname/TLS prerequisites ready for a public release.
- [ ] Future Terraform plan reviewed for unexpected resources or replacements.
- [ ] Teardown owner and deadline recorded before credit or plan expiry.

These unchecked items describe future work; they are not evidence that implementation or provisioning has occurred.

## 9. Teardown Requirements

Stopping containers leaves the EC2 host running. Stopping EC2 is also not complete cleanup: retained EBS storage and other resources must be reviewed. An automatically assigned public IPv4 address can change after stop/start, so update deployment targets and DNS when applicable. See [EC2 stop/start behavior](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html).

Once infrastructure is implemented, review a destroy plan against the intended account, region and Terraform state. After applying that reviewed plan, check running **and stopped** instances, volumes, snapshots, allocated addresses, state-bucket versions, and any optional logging/DNS resources. A query showing no running instances alone does not prove cleanup. Preserve necessary state and evidence before separately retiring the state backend.

Recheck Billing after usage reports update. Cleanup prevents future usage from the removed resources; it does not reverse accrued charges or restore consumed credits. See [operations](OPERATIONS.md) for the broader recovery and teardown workflow.

## Related Guides

[Infrastructure](INFRASTRUCTURE.md) | [Configuration](CONFIGURATION.md) | [Security](SECURITY.md) | [Deployment](DEPLOYMENT.md) | [Release checklist](RELEASE_CHECKLIST.md)
