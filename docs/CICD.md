# CI/CD Design and Pipeline Specification

**Status:** Pipeline architecture, workflow specifications, and supply chain security controls. See the [documentation index](../README.md).

**Design Revision 4 (2026-10-25):** Production-grade GitHub Actions pipeline architecture, Trivy container security gates, CycloneDX SBOM generation, Cosign keyless provenance signing, and cryptographically verified release manifests.

---

## Pipeline Architecture & Trust Boundaries

```
[Pull Request Event]
  └── test.yml: Lint (Ruff), Type Check (Mypy), Contract & Unit Tests (Docker)
      └── Zero access to production secrets / credentials

[Push to main Event]
  └── build.yml: Buildx (linux/amd64) -> Trivy Scan -> CycloneDX SBOM -> Cosign Sign -> Push Registry
      └── Emits immutable release artifacts (@sha256 digest) & release.json

[Manual / Release Dispatch Event]
  └── deploy.yml (Target: Production Environment Gate)
      └── SSH to EC2 -> Host Lock (flock) -> Pull Digests -> Atomic Symlink Swap -> Verify Health
```

---

## Production GitHub Actions Workflows

### 1. Pull Request Validation Workflow (`.github/workflows/test.yml`)

```yaml
name: "PR Validation & Test"

on:
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  validate:
    runs-on: ubuntu-24.04
    steps:
      - name: Checkout Source
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Validate Compose Configurations
        run: |
          docker compose -f docker-compose.yml config --quiet
          docker compose -f docker-compose.prod.yml config --quiet

      - name: Run Unit & Contract Tests in Container
        run: |
          docker compose -f docker-compose.test.yml build test-runner
          docker compose -f docker-compose.test.yml run --rm test-runner pytest tests/unit tests/contracts -v
```

---

### 2. Trusted Build, Scan & Provenance Workflow (`.github/workflows/build.yml`)

```yaml
name: "Build, Scan & Publish Release"

on:
  push:
    branches: [main]

permissions:
  contents: read
  packages: write
  id-token: write # Required for Cosign keyless signing via OIDC

jobs:
  build-and-publish:
    runs-on: ubuntu-24.04
    steps:
      - name: Checkout Source
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Install Cosign & Trivy
        uses: sigstore/cosign-installer@v3.7.0

      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      - name: Build Backend Image
        id: build-backend
        uses: docker/build-push-action@v6
        with:
          context: ./backend
          platforms: linux/amd64
          push: true
          tags: ${{ secrets.DOCKER_USERNAME }}/chatapp-backend:${{ github.sha }}
          outputs: type=image,name=target,annotation-index.org.opencontainers.image.description=ChatApp Backend

      - name: Scan Backend with Trivy (Fail on High/Critical CVEs)
        uses: aquasecurity/trivy-action@0.28.0
        with:
          image-ref: ${{ secrets.DOCKER_USERNAME }}/chatapp-backend:${{ github.sha }}
          format: 'table'
          exit-code: '1'
          ignore-unfixed: true
          severity: 'CRITICAL,HIGH'

      - name: Generate CycloneDX SBOM
        uses: aquasecurity/trivy-action@0.28.0
        with:
          image-ref: ${{ secrets.DOCKER_USERNAME }}/chatapp-backend:${{ github.sha }}
          format: 'cyclonedx'
          output: 'backend-sbom.json'

      - name: Sign Container Image with Cosign (Keyless)
        run: |
          cosign sign --yes ${{ secrets.DOCKER_USERNAME }}/chatapp-backend@${{ steps.build-backend.outputs.digest }}

      - name: Generate and Upload Release Manifest (release.json)
        run: |
          bash scripts/package-release.sh \
            --backend-digest "${{ steps.build-backend.outputs.digest }}" \
            --commit "${{ github.sha }}" \
            --output "release.json"
```

---

## Cryptographic Release Manifest Contract (`release.json`)

The release manifest guarantees immutable traceability between git commit, OCI container image digests, configuration checksums, and SBOM artifacts:

```json
{
  "$schema": "https://chatapp.internal/schemas/release-v1.schema.json",
  "manifest_version": 1,
  "release_id": "20261025.1-sha.e95405e",
  "source_commit": "e95405e4b7b30f0a82b95c6c21e645167015a812",
  "build_timestamp": "2026-10-25T14:45:00Z",
  "platform": "linux/amd64",
  "images": {
    "backend": "index.docker.io/myorg/chatapp-backend@sha256:7f3b4a2e8c1d5f6a9b0c2e4d8f1a3b5c7e9d0f2a4b6c8e0d2f4a6b8c0e2d4f6a",
    "frontend": "index.docker.io/myorg/chatapp-frontend@sha256:1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b",
    "gateway": "index.docker.io/library/nginx@sha256:0d17b565c37bcbd895e3d92318a05974013321437716f29d973a61a3fae9b082",
    "redis": "index.docker.io/library/redis@sha256:c2b189ff4c2c77d46c75fd9dd10c2847a96d29944a1eb4051a3b7d14c2b992f0"
  },
  "config_checksums": {
    "docker_compose": "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    "nginx_conf": "sha256:5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
    "redis_conf": "sha256:4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a"
  },
  "security_evidence": {
    "trivy_scan_passed": true,
    "cosign_signed": true,
    "sbom_sha256": "sha256:2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae"
  }
}
```

---

## Security Scan & Failure Gate Policies

1. **Vulnerability Thresholds:** Any `CRITICAL` or `HIGH` Common Vulnerabilities and Exposures (CVE) with an available vendor patch terminates the CI build immediately.
2. **Indeterminate Scans:** If the vulnerability database cannot be downloaded or the scanner process crashes, the pipeline fails closed; deployment is prohibited.
3. **Vulnerability Exceptions Policy:** If an unfixable upstream base-image vulnerability is detected, an explicit exception record must be added to `.trivyignore` containing:
   - CVE Identifier (e.g. `CVE-2024-XXXXX`).
   - Rationale / Justification explaining why the vulnerability is not exploitable in this architecture.
   - Expiration date ($\le 30\text{ days}$).
   - Assigned engineer owner.

---

## Pipeline Failure Classification & Recovery

| Failure Class | Root Cause Example | Pipeline Action | Operator Remediation |
| --- | --- | --- | --- |
| **Lint / Unit Test Failure** | Syntax error, broken normalization rule, assertion failure. | Workflow exits 1; cancels build. | Fix code on local branch; push new commit. |
| **Vulnerability Gate Failure** | High CVE discovered in base image. | Workflow exits 1; suppresses registry push. | Bump base image digest or update pinned package version. |
| **Signing / Attestation Error** | OIDC token failure or Sigstore network timeout. | Bounded retry (3 attempts); exits if unresolved. | Check GitHub Actions permissions (`id-token: write`). |
| **Host SSH Connection Drop** | EC2 security group block or network disruption. | Deployment script aborts; host lock remains held. | Inspect host journal (`/home/ubuntu/chat-app/deploy.log`); clear lock if safe. |

---

## Related Guides

[Configuration](CONFIGURATION.md) | [Security](SECURITY.md) | [Deployment](DEPLOYMENT.md) | [Release Checklist](RELEASE_CHECKLIST.md)

