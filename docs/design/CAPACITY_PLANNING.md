# Capacity Planning and Scaling Triggers

**Status: design documentation only. Baseline: design revision 5. Updated: 2026-10-26.**

A scaling decision needs measured workload and a diagnosed bottleneck. The values below are planning inputs, not capacity guarantees.

## Baseline experiment

Use the exact NFR workload from [requirements](../REQUIREMENTS.md): 25 clients across two backend Pods, 5 aggregate messages/s, 512-byte payloads, 2-minute warmup and 30-minute steady interval. Record latency percentiles, timely deliveries, duplicates, rejected sends, resource use and recovery behavior.

The 64-per-replica admission ceiling is a safety bound, not proof that 128 clients meet the targets. The 4-GiB node candidate includes OS, K3s and system Pods; application limits alone do not establish usable capacity.

## Workload worksheet

| Symbol | Meaning | Baseline / measurement |
| --- | --- | --- |
| C | Connected active recipients | 25 in initial experiment. |
| M | Accepted published messages per second | Target 5; record actual separately from attempted sends. |
| B | Mean serialized broadcast bytes | Measure envelope plus escaped text; 512-byte payload is not total event size. |
| R | Backend replicas subscribed to the room | 2 initially. |
| Q | Per-session queued-byte bound | 262144 by default. |
| S | Measured session overhead | Measure idle and active sockets including buffers. |

For one global room, approximate delivery work is `M × C` sends/s and serialized application egress is `M × C × B` bytes/s before transport/TLS overhead. Broker fan-out to backend subscribers is approximately `M × R × B`. More backend replicas do not reduce the number of deliveries owed to users.

At the baseline, 5 × 25 = 125 recipient deliveries/s. During 1800 steady seconds, 9000 successful publications would imply 225000 expected deliveries to 25 continuously connected recipients. Use actual publication/connectivity data for final results and account for system events separately.

## Memory model

Plan:

```text
node usage =
  OS + K3s + system Pods
  + singleton gateway/frontend/Redis
  + sum(backend process baseline + sessions + queued/in-flight data)
  + image operations, rollout and temporary diagnostics
  + required headroom
```

A conservative queue exposure estimate per backend is active sessions × Q. At 64 sessions and 262144 bytes, that is 16 MiB of queued delivery accounting, before in-flight events, object overhead, transport buffers and other process memory. Shared immutable events may reduce physical duplication but cannot replace measurements.

Measure steady-state and drain/reconnect peaks. Retain at least the baseline 512-MiB node MemAvailable objective. Avoid placing load generators on the node being measured.

## Signals and actions

These are **review triggers**, not automatic scaling thresholds.

| Observation | Investigation | Candidate action and required proof |
| --- | --- | --- |
| Latency/delivery target fails repeatedly under legitimate expected load | CPU, event-loop lag, broker, network and queue pressure | Optimize identified path; rerun same workload and fault tests. |
| A backend approaches validated admission capacity while node has room | Connection skew and per-Pod pressure | Add backend Pod cautiously; prove new-session distribution and drain. |
| Pods remain unschedulable or node headroom fails | Requests, system overhead and node pressure | Re-size or add workers only after cost and failure-domain design. |
| Redis CPU/network/output buffers dominate | Global fan-out and subscriber behavior | Reassess room routing/broker topology; replicas alone may worsen fan-out. |
| Outage tolerance is below a single-node recovery time | Measured incidents and business impact | Design end-to-end HA, not just more backend Pods. |
| Users need missed messages or receipts | Product requirement | New persistence/protocol design; this is not a resource-sizing change. |

Use a recorded observation window, repeatability criterion, owner and deadline for each trigger. No one has measured a universal “1000 users” threshold for this app.

## Benchmark progression

Establish baseline first. Increase one dimension at a time: connections, message rate, payload size, room distribution if introduced, or reconnect rate. Test skewed connections and hot rooms, not only even distributions.

Record the first breached objective and the saturating component. Re-run failure/recovery and rollout tests at the proposed operating point. Choose an operating margin below measured failure, then document it with exact versions and instance configuration.

## Cost worksheet for every stage

Include node runtime, storage, addresses, egress, control-plane services if selected, ingress/load balancers, broker/database, monitoring, backups and overlap during migration. Quote current regional prices at proposal time using [AWS requirements](../AWS_FREE_TIER_REQUIREMENTS.md); do not reuse an expired credit assumption.

The current $100 planning boundary does not imply that multi-node HA, managed services or continuous hosting fit it. Keep a reserve and schedule teardown. A rejected cost estimate means remaining at the existing stage or revising scope.
