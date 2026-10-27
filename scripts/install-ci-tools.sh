#!/usr/bin/env bash
set -euo pipefail
mkdir -p .local/bin
curl -fsSL https://github.com/k3d-io/k3d/releases/download/v5.9.0/k3d-linux-amd64 -o .local/bin/k3d
curl -fsSL https://github.com/k3d-io/k3d/releases/download/v5.9.0/checksums.txt -o .local/bin/checksums.txt
(cd .local/bin && grep ' k3d-linux-amd64$' checksums.txt | sed 's/k3d-linux-amd64/k3d/' | sha256sum -c -)
curl -fsSL https://dl.k8s.io/release/v1.37.1/bin/linux/amd64/kubectl -o .local/bin/kubectl
curl -fsSL https://dl.k8s.io/release/v1.37.1/bin/linux/amd64/kubectl.sha256 -o .local/bin/kubectl.sha256
(cd .local/bin && printf '%s  kubectl\n' "$(cat kubectl.sha256)" | sha256sum -c -)
chmod +x .local/bin/k3d .local/bin/kubectl
