# Production Operations, Observability & Incident Runbooks

**Design Revision 5 — 2026-10-26. Status: Production Operational Specification.** This document provides the day-to-day operational procedures, Prometheus alert definitions, troubleshooting runbooks, and disaster recovery protocols for Chat App.

---

## 1. Routine Operations & Inspection Matrix

Operators maintain system reliability by executing the following routine checks across the cluster:

| Inspection Area | Monitoring Target / Command | Healthy Baseline Threshold | Action on Degradation |
| :--- | :--- | :--- | :--- |
| **Application Mesh** | `kubectl get pods -n chat-app` | Exactly 5 Pods in `1/1 Ready` state. | Inspect logs and describe Pods experiencing restarts. |
| **Broker Supervision** | Backend `/health` subscriber state | Generational heartbeat echoed within 5.0s. | Check Redis connectivity and subscriber coroutine health. |
| **Host Node Memory** | `free -m` on EC2 host | `MemAvailable` $\ge 512\text{ MiB}$ (NFR-06). | Stop test traffic; audit container memory usage via cgroups. |
| **Network Ingress** | Public TLS probe (`curl -Iv https://...`) | HTTP 200 via HTTPS; valid SSL handshake. | Verify Let's Encrypt certificate renewal and ServiceLB host ports. |
| **Cloud Billing** | AWS Billing / Budgets Console | Total accumulated charges $\le \$100.00$. | Verify spending rate; schedule emergency teardown if $> \$90.00$. |

---

## 2. Standard Diagnostic & Inspection Runbook

Execute the following commands to assess cluster health:

```bash
# 1. Verify Active Context and Cluster Node Status
kubectl config current-context
kubectl get nodes -o wide

# 2. Inspect Application Pods and Services
kubectl -n chat-app get deployments,pods,services,endpointslices -o wide

# 3. Stream Tail Logs from Backend Replicas
kubectl -n chat-app logs deployment/backend --all-pods=true --tail=100 -f

# 4. Inspect Recent Warning Events in Namespace
kubectl -n chat-app get events --sort-by=.metadata.creationTimestamp \
  --field-selector type=Warning

# 5. Host Memory and Disk Inspection (on EC2 node)
free -m
df -h /
systemctl status k3s --no-pager
```

---

## 3. Incident Troubleshooting Runbooks

### 3.1 Incident Runbook 1: Redis Outage or Stalled Subscriber Loop
* **Symptom:** Backend readiness probe fails (HTTP 503); clients disconnected with close code `1011`; K3s removes backend Pods from ServiceLB endpoints.
* **Root Causes:** Redis Pod crash, memory exhaustion, network partition, or hung subscriber coroutine.
* **Remediation Procedure:**
  ```bash
  # 1. Inspect Redis Pod status and logs
  kubectl describe pod -n chat-app -l app=redis
  kubectl logs -n chat-app -l app=redis --tail=100

  # 2. If Redis is crashed or OOMKilled, restart the Deployment
  kubectl rollout restart deployment/redis -n chat-app

  # 3. Observe backend automatic generational reconnection
  kubectl logs -n chat-app -l app=backend --tail=50 -f
  # Look for: "Generational probe echoed. Transitioning to READY (Generation: X)"

  # 4. Verify readiness restored
  kubectl get pods -n chat-app -l app=backend
  ```

---

### 3.2 Incident Runbook 2: Backend Pod CrashLoopBackOff or OOMKilled
* **Symptom:** Backend Pod restarts repeatedly; Kubelet reports `OOMKilled` (Exit Code 137).
* **Root Causes:** Memory leak in session queue, client payload buffer overflow, or undersized cgroup limit ($256\text{ MiB}$).
* **Remediation Procedure:**
  ```bash
  # 1. Identify terminating Pod and exit code
  kubectl get pods -n chat-app -l app=backend -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[0].lastState.terminated.reason}{"\tExit:"}{.status.containerStatuses[0].lastState.terminated.exitCode}{"\n"}{end}'

  # 2. Extract crash logs prior to restart
  kubectl logs -n chat-app -l app=backend --previous --tail=200 > /tmp/backend-crash.log

  # 3. If OOM occurred under legitimate load, evaluate cgroup limits in KUBERNETES.md
  # 4. If triggered by an unstable release, execute immediate rollback:
  bash scripts/rollback.sh
  ```

---

### 3.3 Incident Runbook 3: Node Memory Pressure & Headroom Floor Breach
* **Symptom:** Host node `MemAvailable` drops below the mandatory $512\text{ MiB}$ threshold (**NFR-06**).
* **Root Causes:** Container image churn, runaway containerd log files, or unthrottled load generator.
* **Remediation Procedure:**
  ```bash
  # 1. Inspect top memory-consuming processes on host
  ps aux --sort=-%mem | head -n 15

  # 2. Purge unused container images and build caches
  sudo crictl rmi --prune

  # 3. Inspect containerd journal disk usage
  sudo journalctl --vacuum-size=200M

  # 4. If memory remains below 512 MiB, scale down load generator immediately
  ```

---

### 3.4 Incident Runbook 4: Runaway Cloud Spend or Budget Alarm
* **Symptom:** AWS Budget Alert email received indicating gross spend $> \$75.00$ or $> \$90.00$.
* **Root Causes:** Forgotten demonstration instance, orphaned Elastic IP, unattached EBS snapshots.
* **Remediation Procedure:**
  ```bash
  # 1. Immediately initiate infrastructure destruction
  cd /opt/chat-app/infra/workload
  terraform destroy -auto-approve

  # 2. Verify all regional EC2 instances are terminated
  aws ec2 describe-instances --region ap-south-1 \
    --filters "Name=instance-state-name,Values=running" \
    --query "Reservations[].Instances[].InstanceId"

  # 3. Confirm 0 residual unattached EBS volumes
  aws ec2 describe-volumes --region ap-south-1 \
    --filters "Name=status,Values=available" \
    --query "Volumes[].VolumeId"
  ```

---

## 4. Production Prometheus Alerting Rules

```yaml
groups:
- name: chatapp-alerts
  rules:
  # 1. Alert: No Ready Backends
  - alert: ChatAppNoReadyBackends
    expr: sum(kube_deployment_status_replicas_ready{deployment="backend",namespace="chat-app"}) == 0
    for: 15s
    labels:
      severity: critical
    annotations:
      summary: "All ChatApp backend replicas are unavailable"

  # 2. Alert: Stale Redis Subscriber
  - alert: ChatAppStaleRedisSubscriber
    expr: chat_subscriber_heartbeat_age_seconds > 10.0
    for: 15s
    labels:
      severity: critical
    annotations:
      summary: "Redis subscriber heartbeat is stale (> 10s)"

  # 3. Alert: Node Memory Headroom Floor Breached (NFR-06)
  - alert: ChatAppNodeMemoryHeadroomLow
    expr: node_memory_MemAvailable_bytes < 536870912
    for: 30s
    labels:
      severity: warning
    annotations:
      summary: "Node MemAvailable has breached the 512 MiB minimum floor"

  # 4. Alert: High Handshake Denial Rate
  - alert: ChatAppHighHandshakeRejections
    expr: sum(rate(websocket_handshake_rejections_total[2m])) / sum(rate(websocket_handshake_attempts_total[2m])) > 0.05
    for: 1m
    labels:
      severity: warning
    annotations:
      summary: "Over 5% of WebSocket handshakes are being rejected"
```
