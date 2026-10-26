# Security Design

**Design revision 5 — 2026-10-26. Status: controls to implement and test.** This is an anonymous chat demonstration, not a verified secure production service.

## Threat model

| Threat | Required controls | Residual boundary |
| --- | --- | --- |
| Browser script injection | textContent, reviewed CSP, no unsafe HTML rendering | Browser/dependency defects still require review. |
| Unwanted WebSocket origins | Exact origin allowlist, TLS, handshake validation | Origin is not authentication for non-browser clients. |
| Resource exhaustion | Admission/rate limits, bounded frames/queues, timeouts, Pod limits | One EC2 node remains a shared bottleneck. |
| Gateway compromise reaching Redis | Default-deny policies, explicit app paths, Redis ACL | Node/kernel compromise can cross Pod boundaries. |
| Credential theft | Mounted Secrets, RBAC, encryption at rest, redacted logs | A compromised authorized process can read its own secrets. |
| Malicious release | Trusted signature identity, digest/hash verification, permitted-kind policy | Signed code can still contain vulnerabilities. |
| Administrative compromise | MFA, least privilege, restricted SSH/API, credential revocation | The node administrator controls the cluster. |
| Impersonation/privacy loss | Explicit anonymous labels and no durable history claim | No verified identity or end-to-end encryption. |

## Network boundaries

Expose only gateway 443 publicly, with 80 enabled only for the chosen redirect/challenge flow. Restrict 22 to approved sources. Keep 6443, backend 8000, Redis 6379 and overlay ports out of public ingress.

Within `chat-app`, default-deny ingress and egress. Allow gateway → frontend/backend; backend → Redis; necessary DNS; public gateway ingress through the actual ServiceLB path; and narrowly authorized diagnostics. Account for node-origin probes and source NAT. Test Pod IP as well as Service IP access, including forbidden gateway/frontend → Redis.

A NetworkPolicy object is useful only when an enforcing controller implements it. Keep the K3s controller enabled and prove denial behavior. See [NetworkPolicy semantics](https://kubernetes.io/docs/concepts/services-networking/network-policies/).

## Pod and identity hardening

Application Pods use non-root users, no privilege escalation, dropped Linux capabilities, RuntimeDefault seccomp and read-only root filesystems where supported. Declare bounded writable emptyDir volumes for Nginx/runtime needs. Listen on unprivileged Pod ports; Services expose public 80/443.

No privileged application containers, host networking, hostPath or container-runtime sockets. Application ServiceAccounts do not automatically mount API tokens. Node/system components have different privileges and need separate review; do not apply an app security profile blindly to K3s system namespaces.

Namespace deployer RBAC permits only the reviewed application operations. Namespace creation, RBAC, Secrets bootstrap and platform administration stay separate. Keep root kubeconfig and server tokens out of CI. Verify effective permissions and prevent deployer creation of workloads that bypass policy.

## Secret handling

Bootstrap K3s with secrets encryption, protect encryption keys and datastore material, and use encrypted EBS. Kubernetes Secret encoding alone is not encryption. [K3s encryption](https://docs.k3s.io/security/secrets-encryption).

Mount Redis URI/ACL and gateway TLS keys as files with restricted access. Keep values out of Git, Terraform user-data, build arguments, release manifests and logs. Private registry access uses a scoped imagePullSecret if required. Document credential issuance, rotation, expiry, recovery and revocation.

Redis has no public endpoint and its default user is disabled. Limit the app ACL to approved commands and exact channels; use channel permissions, not key-pattern permissions. Validate the chosen client handshake commands and heartbeat channel before freezing the ACL.

## Browser and proxy policy

Public traffic uses a valid trusted certificate and WSS. Enforce a reviewed CSP with same-origin scripts/styles and deliberate WebSocket connect destinations. Set content-type, anti-framing and referrer protections; enable HSTS only after the actual HTTPS/domain arrangement is ready.

Gateway overwrites forwarding headers and backend trusts only the expected proxy boundary. Deny public detailed health, liveness and metrics. Sanitize username-bearing access paths and disable payload logging.

Validate raw UTF-8, username syntax, text policy and transport size at the appropriate layers. Apply only the API's newline normalization and boundary trimming; no NFKC transformation. Reject prohibited controls while safely rendering permitted text.

## Supply chain and infrastructure

Pin dependencies with hashes and release images by digest. Scan final artifacts and verify signatures against independently configured trusted identities. Do not execute arbitrary release scripts or grant cluster privileges from an application bundle.

Require IMDSv2, minimal instance role permissions and reviewed Pod access to metadata. Keep Terraform state private/versioned with least-privilege locking access. Never assume `sensitive` outputs remove secrets from state.

## Security acceptance

Prove denied public/internal paths, denied Redis commands/channels, origin enforcement, session-first behavior, safe rendering, finite buffers, secret redaction, signature rejection and RBAC restrictions. Review failures before deployment. Findings and time-limited exceptions require an owner and evidence; no control is marked effective solely because this document describes it.

