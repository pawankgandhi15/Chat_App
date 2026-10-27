# Capacity Planning & Mathematical Workload Modeling

**Status: Production Architecture Specification. Baseline: Design Revision 5. Updated: 2026-10-26.**

This document provides the formal mathematical workload formulations, resource allocation equations, kernel network tuning specifications, and empirical sizing benchmarks for Baatchit.

---

## 1. Formal Mathematical Capacity Models

### 1.1 Total Node Memory Allocation Formulation
To prevent Out-Of-Memory (OOM) kills and guarantee the mandatory **NFR-06** floor ($\ge 512\text{ MiB}$ free `MemAvailable`), node memory consumption is modeled as:

$$M_{\text{node}} = M_{\text{OS+K8s}} + M_{\text{infra}} + \sum_{i=1}^R \left(M_{\text{base}} + N_i \times \left(S_{\text{tcp}} + S_{\text{ssl}} + S_{\text{asgi}} + S_{\text{session}} + \bar{Q}_{\text{bytes}}\right)\right) + M_{\text{headroom}}$$

Where:
* $M_{\text{OS+K8s}}$: Linux kernel, systemd, containerd runtime, K3s control plane, Flannel CNI, and CoreDNS ($\approx 1,200\text{ MiB}$).
* $M_{\text{infra}}$: Singleton supporting Pods (Nginx Gateway: $32\text{ MiB}$, Static Frontend: $16\text{ MiB}$, Redis: $64\text{ MiB}$) ($\approx 112\text{ MiB}$).
* $R$: Number of backend FastAPI replicas ($R = 2$ in baseline).
* $M_{\text{base}}$: Base memory footprint of single FastAPI/Uvicorn process ($100\text{ MiB}$ per Pod).
* $N_i$: Number of concurrent active WebSocket connections on replica $i$ ($N_i \le 64$).
* $S_{\text{tcp}}$: Linux kernel TCP send and receive socket buffer overhead ($\approx 16\text{ KiB}$ per socket).
* $S_{\text{ssl}}$: TLS connection context and session buffer overhead terminated at gateway ($\approx 24\text{ KiB}$ per socket).
* $S_{\text{asgi}}$: Python AsyncIO WebSocket protocol wrapper and event loop task metadata ($\approx 12\text{ KiB}$ per socket).
* $S_{\text{session}}$: Session tracking object, TokenBucket state, and monotonic timestamps ($\approx 4\text{ KiB}$ per socket).
* $\bar{Q}_{\text{bytes}}$: Mean queued message bytes in outbound `DeliveryQueue` ($0\text{ KiB}$ steady-state; up to $256\text{ KiB}$ maximum during network stall).
* $M_{\text{headroom}}$: Mandatory unallocated safety reserve floor ($\ge 512\text{ MiB}$).

#### Sizing Verification for Baseline (64 sockets/replica, 128 sockets total)
$$\text{Socket Overhead per Connection} = 16 + 24 + 12 + 4 = 56\text{ KiB}$$
$$\text{Per-Backend Active Memory} = 100\text{ MiB} + (64 \times 56\text{ KiB}) = 103.5\text{ MiB}$$
$$\text{Aggregate Backend Memory (2 Replicas)} = 2 \times 103.5\text{ MiB} = 207\text{ MiB}$$
$$\text{Worst-Case Queue Saturation (all 128 queues full at 256 KiB)} = 128 \times 256\text{ KiB} = 32\text{ MiB}$$
$$\text{Total System Memory Required} = 1,200\text{ MiB} + 112\text{ MiB} + 207\text{ MiB} + 32\text{ MiB} + 512\text{ MiB} = 2,063\text{ MiB} \approx 2.01\text{ GiB}$$

**Conclusion:** A 4-GiB instance candidate provides ample capacity ($\sim 2.0\text{ GiB}$ spare margin) for container image pulls, rolling deployment peaks, and OS page cache.

---

### 1.2 Throughput, Fan-Out & Network Egress Formulation

Let:
* $C$: Total connected concurrent recipients across all replicas.
* $\lambda_{\text{msg}}$: Accepted inbound chat messages per second across all users.
* $\bar{B}_{\text{payload}}$: Average inbound message payload size ($512\text{ bytes}$ baseline).
* $\bar{B}_{\text{event}}$: Serialized outbound JSON broadcast envelope size ($\approx 720\text{ bytes}$).
* $R$: Number of subscribed backend replicas ($R = 2$).

The traffic dynamics are governed by three linear equations:

$$\text{Total Outbound Delivery Rate} = \lambda_{\text{msg}} \times C \quad \text{deliveries/sec}$$
$$\text{Application Egress Bandwidth} = \lambda_{\text{msg}} \times C \times \bar{B}_{\text{event}} \quad \text{bytes/sec}$$
$$\text{Broker Fan-Out Ingress Bandwidth} = \lambda_{\text{msg}} \times R \times \bar{B}_{\text{event}} \quad \text{bytes/sec}$$

---

## 2. Multi-Tier Workload Sizing & Scaling Projections

| Metric / Parameter | Tier 1: NFR Baseline | Tier 2: Single-Node Peak | Tier 3: Multi-Node Medium | Tier 4: Enterprise Scale |
| :--- | :--- | :--- | :--- | :--- |
| **Concurrent Active Clients ($C$)** | 25 | 128 (Admission Cap) | 1,000 | 10,000 |
| **Message Ingress Rate ($\lambda_{\text{msg}}$)**| 5.0 msg/s | 20.0 msg/s | 100.0 msg/s | 500.0 msg/s |
| **Backend Replicas ($R$)** | 2 Pods | 2 Pods | 8 Pods (4 Nodes) | 40 Pods (Multi-AZ) |
| **Outbound Frame Rate** | **125 frames/s** | **2,560 frames/s** | **100,000 frames/s** | **5,000,000 frames/s** |
| **Application Egress Throughput** | $90.0\text{ KiB/s}$ ($0.72\text{ Mbps}$) | $1.84\text{ MiB/s}$ ($15.4\text{ Mbps}$) | $72.0\text{ MiB/s}$ ($604\text{ Mbps}$) | $3.60\text{ GiB/s}$ ($30.2\text{ Gbps}$) |
| **Broker Fan-Out Rate** | 10 events/s | 40 events/s | 800 events/s | 20,000 events/s |
| **Aggregate Delivery Queue Cap** | $6.4\text{ MiB}$ | $32.8\text{ MiB}$ | $256.0\text{ MiB}$ | $2.56\text{ GiB}$ |
| **Recommended Infrastructure** | 1x EC2 `c7i-flex.large` | 1x EC2 `c7i-flex.large` | 3x EC2 `c7i-flex.large` + ALB | EKS Multi-AZ + ElastiCache |
| **P95 Latency Expectation** | $< 130\text{ ms}$ | $< 180\text{ ms}$ | $< 150\text{ ms}$ | $< 120\text{ ms}$ |

---

## 3. High-Performance Linux Kernel & Network Tuning

To support high-density WebSocket connections without dropping TCP SYN packets or encountering socket descriptor exhaustion, the following kernel tuning parameters are enforced on the host EC2 instance via `/etc/sysctl.d/99-baatchit.conf`:

```ini
# Maximum open file descriptors across the system
fs.file-max = 2097152

# Socket listen backlog queue depth
net.core.somaxconn = 4096

# Maximum number of unacknowledged SYN connection requests
net.ipv4.tcp_max_syn_backlog = 4096

# Ephemeral local port range for outbound connections
net.ipv4.ip_local_port_range = 1024 65535

# Fast recycling of TCP sockets in TIME_WAIT state
net.ipv4.tcp_tw_reuse = 1

# Time to wait for FIN before closing socket (seconds)
net.ipv4.tcp_fin_timeout = 15

# TCP Keepalive parameters for persistent WebSocket detection
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_intvl = 15
net.ipv4.tcp_keepalive_probes = 5

# TCP Window Autotuning (min, default, max bytes)
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# Increase network interface packet receive queue depth
net.core.netdev_max_backlog = 10000

# Enable BBR TCP Congestion Control
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
```

### Process Limits (`/etc/security/limits.d/99-nofile.conf`)
```text
*    soft nofile 65536
*    hard nofile 65536
root soft nofile 65536
root hard nofile 65536
```

---

## 4. AWS EC2 Instance Sizing & Pricing Evaluation

The following AWS candidate instances in region `ap-south-1` (Mumbai) were evaluated against the 2-vCPU / 4-GiB baseline constraint:

| Instance Type | vCPU Architecture | RAM (GiB) | Baseline Network / Burst | EBS Bandwidth | Free Tier Status | On-Demand Hourly (ap-south-1) | Est. Monthly Cost (Gross) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`c7i-flex.large` (Selected Candidate)** | 2 vCPU (Intel Xeon 4th Gen) | 4.0 | Up to 12.5 Gbps | Up to 10 Gbps | Eligible (New Accounts) | \$0.0476 | \$34.27 |
| **`t4g.medium` (Arm Alternative)** | 2 vCPU (AWS Graviton2) | 4.0 | Up to 5.0 Gbps | Up to 2,780 Mbps | Eligible (Free Trial) | \$0.0336 | \$24.19 |
| **`t3.medium` (Legacy x86)** | 2 vCPU (Intel Xeon Skylake) | 4.0 | Up to 5.0 Gbps | Up to 2,085 Mbps | Ineligible | \$0.0416 | \$29.95 |
| **`c6i.large` (Compute Optimized)** | 2 vCPU (Intel Ice Lake) | 4.0 | Up to 12.5 Gbps | Up to 10 Gbps | Ineligible | \$0.0850 | \$61.20 |

### Storage & Peripheral Infrastructure Cost (Monthly)
* **Root EBS Volume:** $20\text{ GiB}$ gp3 General Purpose SSD ($3,000\text{ IOPS}$, $125\text{ MB/s}$ throughput baseline) $\times \$0.096/\text{GB-month} = \$1.92$.
* **Public IPv4 Address:** $1\text{ In-use Public IPv4 address} \times \$0.005/\text{hour} \times 720\text{ hours} = \$3.60$.
* **Data Transfer Egress:** First $100\text{ GB/month}$ free; baseline demo egress ($< 5\text{ GB}$) incurs $\$0.00$.
* **Total Baseline Monthly Estimate:** **\$39.79 Gross** (Fully offset by $\$100$ credit allocation; leaves $\$60.21$ reserve).
