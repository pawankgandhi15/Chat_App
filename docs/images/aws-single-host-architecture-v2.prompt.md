# AWS Architecture Image — Generation Prompt

**Asset:** [Professional architecture diagram](aws-single-host-architecture-v2.png)

**Reference:** [Original diagram](aws-single-host-architecture.png)

**Generation method:** Built-in `image_gen` tool with the original diagram as a reference image. The image depicts a planned architecture, not a deployed system.

The main view shows application hosting; the lower view shows separate Terraform management connections. Application traffic never passes through the S3 state bucket.

## Final Prompt

```text
Use case: infographic-diagram.
Asset type: Detailed professional AWS architecture illustration for a GitHub README and technical presentation.
Input image 1: reference and redesign target. Recreate it with a much more polished layout, clearer technical detail, and corrected connections. Preserve the project topology, not the old composition.

PRIMARY DESIGN
Create one high-resolution landscape image, approximately 16:10, with a white background, crisp vector-like geometry, consistent flat AWS architecture service icons, generous gutters and readable sans-serif typography. Use dark navy text, light gray frames, AWS orange for compute, purple for networking, green for storage, and subdued blue/red for application components. No heavy gradients, fuzzy glows, 3D effects, ornamental clouds, overlapping text or crossing arrows. A precisely aligned technical blueprint suitable for an engineering portfolio. Use short legible labels, not dense prose.

TITLE: "Baatchit | AWS Architecture"
SUBTITLE: "Planned single-host deployment • ap-south-1 (Mumbai)"
Small top-right status label: "DESIGN ONLY"

MAIN DIAGRAM: ABOUT 75% OF CANVAS
Show nested boundaries accurately:
AWS Region: ap-south-1 (Mumbai)
  VPC: 10.0.0.0/16
    Public subnet: 10.0.1.0/24
      Security group boundary enclosing ONE EC2 host
      Encrypted root EBS disk attached to EC2, inside the subnet
Internet Gateway is attached at the VPC boundary, outside the subnet. A small subnet routing annotation says "Default route: 0.0.0.0/0 → Internet Gateway". It is an annotation, not a second network traffic path.
Browser users are outside AWS at far left. Draw one solid blue request/response connection through the Internet Gateway to the Nginx gateway inside EC2 labeled "HTTPS / WSS :443". Security group is a boundary enforcing traffic policy, not an extra proxy server.

EC2 HEADER:
"Amazon EC2 • t3.micro"
"Ubuntu 24.04 LTS • 2 vCPU / 1 GiB RAM"
small tags: "IMDSv2" and "One public IPv4"
Inside the EC2 host, one "Docker Compose • 5 containers / 4 services" grouping containing EXACTLY FIVE service cards with distinct readable names:
1. "Nginx gateway" / "TLS termination + reverse proxy" / network tag "edge"
2. "Static frontend" / "HTML • CSS • JavaScript" / network tag "edge"
3. "FastAPI replica 1" / "Uvicorn • 1 worker" / network tag "edge + data"
4. "FastAPI replica 2" / "Uvicorn • 1 worker" / network tag "edge + data"
5. "Redis Pub/Sub" / "ACL-authenticated • ephemeral" / network tag "data only"
Arrange gateway left, frontend above middle, backend replicas stacked in middle, Redis on right. Draw gateway → frontend labeled "HTTP • static assets". Draw gateway → each backend labeled "WS :8000". Draw each backend ↔ Redis labeled "Pub/Sub :6379". All service cards are within EC2.
Use network membership tags INSTEAD OF ambiguous overlapping network boxes. A small note within the Docker grouping says "edge = proxy network   •   data = internal Docker network". Frontend and gateway have no Redis connection. Only gateway publishes application ports to the EC2 host.
Beside EC2, a real storage icon and short card: "Amazon EBS" / "20 GiB gp3 • encrypted" / "Root volume", with a simple attachment line to EC2.

A compact security rules callout INSIDE the security-group boundary but not obstructing arrows:
"INBOUND"
"443 — public HTTPS/WSS"
"80 — redirect / ACME, if enabled"
"22 — approved operator CIDRs"
A separate note: "8000 / 6379: container-only"

BOTTOM MANAGEMENT ROW: ABOUT 18% OF CANVAS, BELOW VPC
Separate this area visually with a subtle horizontal divider and the heading "Provisioning & state".
Place a workstation icon labeled "Terraform operator / CI" on the left, an "AWS APIs" small neutral endpoint badge near the region border above it, and a green AWS S3 bucket card on the right INSIDE THE AWS REGION BUT OUTSIDE THE VPC:
"Amazon S3"
"Terraform remote state + lockfile"
"Private • encrypted • versioned"
Draw TWO INDEPENDENT dashed connections FROM TERRAFORM:
A) Terraform → AWS APIs at the region boundary labeled "Provision infrastructure".
B) Terraform ↔ S3 labeled "Read/write state + locking".
CRITICAL: NO LINE from S3 to EC2, VPC, or AWS APIs. S3 does not provision resources and is not part of chat runtime traffic. Route the provisioning arrow independently of the state connection.

BOTTOM FOOTER:
A compact legend: blue solid = application traffic; purple dashed = provisioning/state; small pill = Docker network membership.
Three concise notes: "Readiness: /health" | "Private diagnostics: /live, /metrics" | "One host • no durable message history"

INVARIANTS:
One EC2, one VPC, one public subnet, one EBS root volume, one S3 state bucket, five app containers. No CloudFront, ALB, NAT gateway, ECS, EKS, managed database, extra hosts, or multi-AZ claims. Internal gateway-to-backend arrows say WS, not WSS, because TLS terminates at gateway. Backends attach to edge + data; Redis data only. Keep every arrow readable and correct. Do not let region boundaries contain the external browser or Terraform workstation. No text on top of connector lines. Render all labels accurately.
```
