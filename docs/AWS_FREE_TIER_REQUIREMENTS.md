# AWS Free Tier and $100 Credit Requirements

**Checked 2026-10-26. Status: planning only; this project's AWS account has not been inspected.** The deployment design is K3s on one EC2 instance, with local k3d development first.

## What the credit can cover

AWS's newer Free Tier experience offers eligible new customers $100 in initial credits and opportunities to earn up to another $100. The Free plan is time-limited and subject to available credits and service restrictions. Account creation date, plan, promotion terms and the balance/expiry shown in the account determine the actual entitlement. Do not assume old 12-month EC2 allowances or count unearned credits. [AWS Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/).

K3s has no EKS control-plane charge. It still consumes billed EC2, EBS, networking and other resources. Zero out-of-pocket spending is conditional on eligible charges remaining covered. A Paid plan can generate charges after credits are exhausted or expire.

AWS lists EKS among services accessible in the new Free plan, but standard-support EKS costs $0.10 per cluster-hour before workers and other resources. That is $72 for a 30-day continuous cluster, or $4.80 for 48 hours. EKS is outside this project's baseline. [Supported services](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html), [EKS pricing](https://aws.amazon.com/eks/pricing/).

## Required account evidence before provisioning

| Requirement | Record before launch |
| --- | --- |
| Account entitlement | Creation date, Free/Paid plan, applicable promotion terms and allowed services. |
| Actual available credit | Eligible remaining balance and expiry; subtract other project usage. |
| Region | Mumbai `ap-south-1`; selected instance availability and quota. |
| Compute permission | Exact allowed instance type and AMI, architecture and hourly price. |
| Security | MFA for administrative identity; least-privilege operator/CI roles, no root access keys. |
| Access | Approved source CIDR, deployer identity and tested route to host. |
| Public endpoint | Actual hostname, DNS control and trusted TLS certificate arrangement. |
| Cost ownership | Alert recipient, planned start/end, teardown owner and billing review date. |

All values are currently unverified. No account upgrade, purchase or resource creation is implied by this document.

## Minimum proposed resource set

| Resource | Candidate | Cost or eligibility consideration |
| --- | --- | --- |
| EC2 | One 2-vCPU / 4-GiB node; evaluate `c7i-flex.large` | Check real account and regional availability; use quoted hourly price. |
| EBS | 20 GiB encrypted gp3 root | Storage persists when compute is stopped; snapshots are additional. |
| Public IPv4 | One | Published price $0.005/address-hour; 24 hours = $0.12 before any applicable benefit. |
| VPC networking | One public subnet and Internet Gateway | Include transfer usage; exclude NAT and managed load balancers. |
| S3 | Small private versioned Terraform state bucket | Storage, requests and retained versions still need an estimate. |
| Optional services | DNS, logging, backups only if selected | Itemize them; do not assume free hosted zones, domains or unlimited logs. |

[K3s requires](https://docs.k3s.io/installation/requirements) at least 2 cores and 2 GB for the server baseline, excluding app workload. The earlier 1 GiB node design is unsuitable. AWS lists `c7i-flex.large` as eligible for newer accounts; its specification is 2 vCPU/4 GiB. This is a measurement candidate, not a guarantee of capacity or free usage. [EC2 eligibility](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html), [instance specification](https://aws.amazon.com/ec2/instance-types/c7i/), [public IPv4 pricing](https://aws.amazon.com/vpc/pricing/).

Do not apply T3 CPU-credit settings to C7i-flex. If a different family is chosen, review its performance and charging model, update the estimate and rerun sizing tests.

## Credit worksheet

Let `B = min(actual eligible remaining credits, $100)`. Reserve a proposed $20 for billing delay and unexpected usage. Planned gross usage must fit `max(0, B - $20)`; if that is zero, stay local.

For a time-limited run:

```text
gross estimate =
  EC2 hourly price × running hours
  + public IPv4 price × address-hours
  + prorated EBS storage and any provisioned extras
  + estimated data transfer
  + S3 storage/requests/versions
  + explicitly selected DNS, logs, snapshots and other services
```

Use the [AWS Pricing Calculator](https://calculator.aws/) for the selected region and record each rate, quantity and quote date. Then separately verify credit coverage. A monthly estimate cannot determine remaining hours without the actual balance and other resource usage.

| Worksheet item | Value to fill |
| --- | --- |
| Eligible balance / expiry / plan | Pending account review |
| Compute hourly quote | Pending regional quote |
| Total non-compute usage estimate | Pending inventory |
| Planned running hours / destruction time | Pending schedule |
| Gross estimate / reserve / available budget | Pending calculation |
| Alert recipient / teardown owner | Pending assignment |

No exact duration or monthly $0 claim can be made from the supplied information.

## Controls during the experiment

Create actual and forecast cost alerts at suitable fractions of the planned budget. Inspect credits, resource inventory and cost reports daily during AWS use. Alerts can lag spending and are **not a hard spending cap**. Record a fixed teardown time and inspect the outcome rather than trusting a scheduled command alone. [AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html).

Develop, build and run load generators outside AWS wherever practical. Do not leave a demonstration node running between exercises without including those hours in the estimate. Avoid allocating an unused Elastic IP or adding managed services incidentally.

## Teardown checklist

- [ ] Capture sanitized release/test evidence before shutdown.
- [ ] Review and execute the correct infrastructure destruction plan.
- [ ] Inspect EC2 instances, EBS volumes, snapshots, addresses and any accidentally introduced load balancers/NAT resources in the relevant regions.
- [ ] Review retained S3 state versions and intentional backups; keep state until teardown is verified.
- [ ] Revoke temporary deployment credentials and remove obsolete DNS records.
- [ ] Check delayed billing/credit usage and record remaining resources and final gross cost.

No resources have been created by this documentation update. See [infrastructure](INFRASTRUCTURE.md), [Kubernetes](KUBERNETES.md) and [operations](OPERATIONS.md).
