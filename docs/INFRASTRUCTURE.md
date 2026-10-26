# Infrastructure and Cost Plan

**Status:** Proposed AWS/Terraform design and cost accounting model. See the [documentation index](../README.md).

**Design Revision 4 (2026-10-25):** Production-grade Terraform HCL specifications, IMDSv2-hardened EC2 instance configuration, automated cloud-init bootstrap blueprints, S3 state locking architecture, and quantitative AWS cost models.

---

## AWS Resource Inventory & Architecture

```
AWS Cloud: Region ap-south-1 (Mumbai)
└── VPC (10.0.0.0/16)
    ├── Internet Gateway (chat-app-igw)
    └── Public Subnet (10.0.1.0/24, AZ ap-south-1a)
        ├── Route Table (0.0.0.0/0 -> IGW)
        ├── Security Group (chat-app-sg)
        │   ├── Ingress: 80, 443 (0.0.0.0/0)
        │   ├── Ingress: 22 (RESTRICTED to operator CIDR)
        │   └── Egress: ALL (0.0.0.0/0)
        └── EC2 Instance (chat-app-host: t3.micro)
            ├── IMDSv2 Enforced (http_tokens = "required")
            ├── Encrypted EBS gp3 (20 GB, kms_key_id = default)
            └── Docker Engine 26.0+ & Compose v2.27+
```

---

## Production Terraform HCL Blueprint (`terraform/main.tf`)

```hcl
terraform {
  required_version = ">= 1.10.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.73.0"
    }
  }

  # Production S3 Backend with Native State Locking (Terraform 1.10+)
  backend "s3" {
    bucket       = "chatapp-tfstate-ap-south-1-prod"
    key          = "prod/terraform.tfstate"
    region       = "ap-south-1"
    encrypt      = true
    use_lockfile = true # Deprecates legacy DynamoDB lock table
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "chat-app"
      Environment = "production"
      ManagedBy   = "terraform"
    }
  }
}

# 1. VPC & Networking
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = "chat-app-vpc" }
}

resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "chat-app-igw" }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "${var.aws_region}a"
  tags                    = { Name = "chat-app-public-subnet" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }
  tags = { Name = "chat-app-public-rt" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# 2. Ingress & Egress Security Group
resource "aws_security_group" "web" {
  name        = "chat-app-sg"
  description = "Ingress for HTTP/HTTPS and restricted operator SSH"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP Ingress"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS Ingress"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Restricted Operator SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_allowed_cidrs # Must be explicit operator IP
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 3. EC2 Instance Hardening
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}

resource "aws_key_pair" "deployer" {
  key_name   = "chat-app-deployer-key"
  public_key = file(pathexpand(var.public_key_path))
}

resource "aws_instance" "app_host" {
  ami                  = data.aws_ami.ubuntu.id
  instance_type        = "t3.micro"
  subnet_id            = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.web.id]
  key_name             = aws_key_pair.deployer.key_name

  # Enforce IMDSv2 (Neutralizes SSRF credential theft)
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  # Encrypted 20GB gp3 Root Volume
  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  credit_specification {
    cpu_credits = "standard" # Avoid unexpected surplus charges
  }

  user_data = file("${path.module}/user_data.sh")
  tags      = { Name = "chat-app-instance" }
}
```

---

## Automated EC2 Cloud-Init Script (`terraform/user_data.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

# Log all output to cloud-init log
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

echo "[+] Starting Chat App Host Initialization..."

# 1. Update OS and install prerequisites
apt-get update -y
apt-get install -y ca-certificates curl gnupg lsb-release ufw

# 2. Add Docker official GPG key and APT repository
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# 3. Install Docker Engine and Compose plugin
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 4. Enable Docker daemon
systemctl enable --now docker
usermod -aG docker ubuntu

# 5. Configure Docker daemon log rotation
cat <<EOF > /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
systemctl restart docker

# 6. Initialize release directories
mkdir -p /home/ubuntu/chat-app/releases
mkdir -p /home/ubuntu/chat-app/secrets
chown -R ubuntu:ubuntu /home/ubuntu/chat-app
chmod 700 /home/ubuntu/chat-app/secrets

echo "[+] Initialization complete successfully."
```

---

## Quantitative AWS Cost Model (`ap-south-1`)

Complete the [AWS Free Tier requirements](AWS_FREE_TIER_REQUIREMENTS.md) before provisioning. Account-specific credits and benefits must be verified; this design does not guarantee zero cost or a fixed monthly bill. AWS distinguishes legacy accounts from newer credit-based offers. See [EC2 Free Tier eligibility](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html).

| Billable Resource | Planned Quantity | Estimation Requirement |
| --- | --- | --- |
| EC2 compute | One `t3.micro` with 2 vCPUs and 1 GiB RAM | Current Mumbai Linux On-Demand rate multiplied by planned runtime; explicitly use Standard CPU credit mode. |
| EBS storage | One encrypted 20 GB `gp3` root volume | Regional storage rate for its full lifetime, including periods when the host is stopped; add snapshots or extra performance if selected. |
| Public IPv4 | One address | Published USD 0.005 per address-hour before applicable account benefits; see [VPC pricing](https://aws.amazon.com/vpc/pricing/). |
| Data transfer | Measured or estimated egress | Check applicable regional rates and remaining account-wide allowances. |
| S3 Terraform state | State, lock objects and retained versions | Include storage and API requests; no assumed free allocation. |
| Optional services | Only explicitly selected resources | Add DNS, monitoring, backup and other service costs to the estimate. |

Use the [AWS Pricing Calculator](https://calculator.aws/) for `ap-south-1`, record the estimate date and assumptions, then apply only credits confirmed for the account. Budget alerts are notifications, not a guaranteed spending cutoff. Record a teardown deadline and inspect usage after billing updates.

---

## Clean Infrastructure Teardown & Verification

To eliminate cloud spending after testing or demonstrations:

```bash
cd terraform/
# Review planned resource deletions
terraform plan -destroy -out=destroy.plan

# Apply destruction cleanly
terraform apply destroy.plan

# Check running project instances; this is only one part of cleanup verification
aws ec2 describe-instances --filters "Name=tag:Project,Values=chat-app" "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].InstanceId"
```

Also inspect stopped instances, retained volumes/snapshots, allocated addresses and optional services in the intended account and regions. The separately managed state bucket requires its own retention/cleanup decision after necessary recovery records are preserved. See the [teardown requirements](AWS_FREE_TIER_REQUIREMENTS.md#9-teardown-requirements).

---

## Related Guides

[AWS Free Tier requirements](AWS_FREE_TIER_REQUIREMENTS.md) | [Configuration](CONFIGURATION.md) | [Security](SECURITY.md) | [Deployment](DEPLOYMENT.md) | [Operations](OPERATIONS.md)

