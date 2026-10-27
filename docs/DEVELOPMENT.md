# Local development

The application runs in a disposable k3d cluster with four Deployments and five application Pods. No AWS credentials are needed. See [implementation evidence](IMPLEMENTATION_STATUS.md) for the tested scope.

## Prerequisites

- Python 3.12 and Node.js 24.
- Docker with Linux containers running; Docker Desktop works on Windows.
- k3d 5.9.0 and kubectl 1.37.x on PATH. The local launcher also looks for k3d under `.local/bin/`.
- Enough Docker resources for Kubernetes plus five application Pods; allow several GiB of RAM and disk space for images.

Install k3d using its [official instructions](https://k3d.io/stable/#installation). On Linux, `bash scripts/install-ci-tools.sh` downloads the pinned k3d/kubectl versions and checks their published SHA-256 checksums. Add `.local/bin` to PATH afterwards. This helper is intended for Linux amd64, not PowerShell.

## Start on Windows

Run from the repository root:

~~~powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.venv\Scripts\python.exe scripts/local.py up
~~~

Open **http://localhost:8080** in two browser tabs. Each tab receives an anonymous display name. Messages appear in both tabs, including when their connections use different backend Pods.

The launcher builds images, creates the `baatchit` cluster if needed, imports the images, creates a Redis ACL/URL Secret pair, applies the local overlay and waits for readiness. Repeating `up` rebuilds and restarts the application while preserving the local credentials.

## Start on Linux/macOS

Install compatible Docker, k3d and kubectl first:

~~~bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.lock
python scripts/local.py up
~~~

The shell helpers for CI and release publication target Linux amd64. macOS uses the Python launcher and locally installed tools.

## Tests

PowerShell examples; on an activated Linux virtual environment use `python` instead of the explicit Windows path:

~~~powershell
.venv\Scripts\python.exe -m pytest tests/unit -q
node --test tests/frontend/*.test.js
.venv\Scripts\python.exe scripts/check_manifests.py
.venv\Scripts\python.exe scripts/smoke.py
.venv\Scripts\python.exe scripts/check_network.py
.venv\Scripts\python.exe scripts/scan_local.py
.venv\Scripts\python.exe -m pytest tests/integration --integration -q
.venv\Scripts\python.exe -m playwright install chromium
.venv\Scripts\python.exe -m pytest tests/browser --browser-url http://localhost:8080 -q
~~~

Integration tests require the locally built `baatchit-backend:dev` image. They create separate, randomly named Docker containers and remove their own resources afterwards. They stop Redis and signal a backend inside that test environment; they do not stop the Kubernetes workload.

Browser tests save desktop/mobile screenshots in ignored `artifacts/`. On Linux, use `python -m playwright install --with-deps chromium` to install browser dependencies.

A short load check:

~~~powershell
.venv\Scripts\python.exe scripts/load.py --warmup 5 --duration 60 --output artifacts/load-local.json
~~~

The default load command uses 25 clients, 5 aggregate messages/second, 512-byte messages, 120 seconds of warmup and 1,800 seconds of measurement. Run it from a separate machine for AWS acceptance, and collect node memory independently. A short local pass does not establish AWS capacity.

## Inspect and stop

~~~powershell
.venv\Scripts\python.exe scripts/local.py status
kubectl --kubeconfig .local/kubeconfig --context k3d-baatchit -n baatchit get pods
kubectl --kubeconfig .local/kubeconfig --context k3d-baatchit -n baatchit logs deployment/backend --tail=50
.venv\Scripts\python.exe scripts/local.py down
~~~

The scripts always select the local kubeconfig/context explicitly. `down` deletes only the named local cluster; it does not stop Docker Desktop or remove global images. Chat history is ephemeral.

The `.local/kubeconfig` grants access to the disposable cluster. Keep `.local/` and `artifacts/` untracked. Do not copy local credentials into AWS.

## Existing environments after the rename

The local cluster and namespace are now `baatchit`; the context is `k3d-baatchit`. Images use `baatchit-backend:dev`, `baatchit-frontend:dev` and `baatchit-gateway:dev`.

If a pre-rename local cluster is running, stop that specific cluster with `k3d cluster stop <previous-cluster-name>` before `python scripts/local.py up`, because both configurations bind localhost port 8080. The new cluster gets its own credentials and namespace. Keep the stopped cluster until the new environment passes smoke checks, then remove it when it is no longer needed.

For an existing cloud installation, review the new namespace, `baatchit-deployer` runner label/Role, `baatchit-*` registry prefix and Terraform state-key example as a migration. Preserve existing state and explicitly migrate it if changing the backend key; do not point Terraform at empty state for existing infrastructure. Old signed bundles target the old namespace and cannot be used unchanged with the renamed release validator. No cloud resources are changed by the source rename.

## Working on the code

- Backend entrypoint: `python -m app.run` from `backend/` with a configured Redis URL/file. This entrypoint enforces transport limits and early SIGTERM draining; a bare `uvicorn app.main:app` command is not equivalent.
- Frontend modules are served directly; no bundler or npm installation is needed.
- Re-run `scripts/local.py up` after source changes; the cluster uses imported images.
- Update dependency inputs, then regenerate hashed locks using `python -m piptools compile --generate-hashes`. Review the resulting versions and run tests before adopting them.
- Update `schemas/events-v1.schema.json` when intentionally changing the event models, and review protocol compatibility.
- Keep future design proposals in `docs/design/` separate from measured implementation status.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Docker unavailable | Start Docker and select Linux containers |
| Port 8080 busy | Stop the conflicting service or deliberately change the k3d mapping and allowed origins together |
| Gateway stuck mounting | Check ConfigMap names and namespaces; run `check_manifests.py` |
| Backend readiness fails | Redis Pod, paired Secret mounts and private backend logs |
| Browser remains disconnected | Browser console, exact Origin, `chat.v1` and `/ws/` routing |
| Kubernetes permission error | Explicit `.local/kubeconfig`; do not switch to an unrelated admin context |
| Redis credentials partially missing | Restore the pair or recreate the disposable cluster; do not rotate only one half |
