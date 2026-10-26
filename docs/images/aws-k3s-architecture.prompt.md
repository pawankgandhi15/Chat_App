# AWS K3s Architecture Image — Generation Record

Created 2026-10-26 with the built-in image generation tool in reference-image edit mode. Opaque background; no external API key or CLI. Final asset: [aws-k3s-architecture.png](aws-k3s-architecture.png).

The initial reference was [the previous Compose diagram](aws-single-host-architecture-v2.png), retained for historical context. The first K3s draft was revised to correct ServiceLB host-port labels, gateway Service type, EC2 address ownership and Pub/Sub arrows. This is a conceptual design illustration, not evidence of running infrastructure. [Kubernetes documentation](../KUBERNETES.md) owns the exact resource and networking contract; the ServiceLB platform implementation is shown inline with traffic for readability.

## Initial prompt

Recreate the attached architecture diagram as a polished, highly legible professional technical infographic, landscape, large resolution, white background, navy typography, restrained AWS orange/green and Kubernetes blue. This is an updated DESIGN ONLY architecture for Chat App. Completely replace the old Docker Compose architecture with the following exact K3s Kubernetes design. Prioritize correct readable labels and uncluttered arrows over decorative icons. Title: "Chat App | AWS + Kubernetes". Subtitle: "Planned single-node K3s deployment · Mumbai (ap-south-1)". Badge: "DESIGN ONLY".

Nested boundaries: AWS region > VPC 10.0.0.0/16 > Public subnet 10.0.1.0/24 > EC2 node running K3s server + worker and containerd. Node label: "2 vCPU / 4 GiB candidate · verify eligibility and sizing". A small attached EBS card: "20 GiB gp3 · encrypted root". Do NOT call it t3.micro or Docker Compose.

Main application route, left to right: Browser users → Internet Gateway / public IPv4 (arrow HTTPS/WSS :443) → K3s ServiceLB (node ports 80/443) → gateway Service → Nginx gateway Pod (TLS termination). Inside namespace chat-app, gateway branches upward to frontend ClusterIP Service → Static frontend Pod (HTML · CSS · JavaScript), and downward to backend ClusterIP Service :8000 → two clearly distinct FastAPI backend Pods (1 Uvicorn worker each). Both backend Pods exchange Pub/Sub with redis ClusterIP Service :6379 → one Redis Pod (ACL-authenticated · ephemeral). Fit services as small labels/pills and Pods as larger cards. Exactly five APPLICATION Pods: gateway, frontend, backend 1, backend 2, Redis. Show separate small platform strip: "K3s platform: CoreDNS · Flannel · NetworkPolicy · ServiceLB". Caption: "4 Deployments · 5 application Pods + system Pods". Do not draw a managed AWS load balancer. Note "Traefik disabled".

Security sidebar: "443 public HTTPS/WSS", "80 redirect if enabled", "22 approved admin CIDRs", "6443 / 8000 / 6379 not public". App isolation note: "Default-deny NetworkPolicies; gateway → frontend/backend; backend → Redis". Place administration as a separate dashed route, not part of message traffic: operator / CI → restricted SSH + namespace-scoped kubectl → EC2. Terraform operator / CI separately dotted arrows → AWS APIs and → private versioned encrypted S3 state + lockfile, outside the VPC message path. S3 is NOT chat history.

Bottom three concise notes: "Single node: no host high availability" / "Local testing: k3d" / "AWS usage consumes eligible credits; no EKS cluster fee". Legend solid blue = application traffic, dashed purple = administration / provisioning. Preserve generous whitespace and clear arrow direction. All labels accurate and spelled correctly. Avoid excessive visual clutter and unrelated services. This image supersedes the previous Compose diagram; all current imagery must show Kubernetes.

## Correction prompt

Edit this diagram while preserving its professional layout, styling and all other accurate content. Make these precise technical corrections:
1. In the K3s ServiceLB card, replace "(node ports)" with "(host ports)". Remove the invented "80 → 30080" and "443 → 30443". Replace those two lines with "HTTP :80" and "HTTPS :443". No 30080 or 30443 anywhere.
2. The gateway Service card currently says "ClusterIP". Replace that with "LoadBalancer". This Service is implemented by K3s ServiceLB, not an AWS load balancer. Other Services remain ClusterIP.
3. Under the Internet Gateway, remove "(public IPv4)". Add a small "One public IPv4" note to the EC2 instance header area, since the address belongs to EC2, not the Internet Gateway.
4. The Redis traffic arrows must visibly represent bidirectional Pub/Sub between both backend Pods and the Redis Service/Pod, without crossing other paths.
5. Add one small legible note within the namespace boundary where space permits: "NetworkPolicies: gateway → frontend/backend; backend → Redis". This must not overlap cards or arrows.
Keep exact title, single-node and DESIGN ONLY labels, EBS 20GiB, K3s platform, admin/provisioning separation, credit caveat, and 4 Deployments / 5 application Pods + system Pods. Do not introduce any new services or invented numeric ports.
