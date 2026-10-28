"""Reproducible local k3d environment; never accesses the user's default kube context."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
KUBECONFIG = LOCAL / "kubeconfig"
NAME = "baatchit"


def run(args, *, capture=False, data=None, check=True):
    return subprocess.run([str(x) for x in args], cwd=ROOT, input=data, text=True,
                          capture_output=capture, check=check)


def k3d():
    installed = shutil.which("k3d")
    private = LOCAL / "bin" / ("k3d.exe" if os.name == "nt" else "k3d")
    if installed:
        return installed
    if private.exists():
        return str(private)
    raise SystemExit("Install k3d 5.9.0 and ensure Docker is running. See docs/IMPLEMENTATION_STATUS.md.")


def kubectl(*args, **kwargs):
    return run(["kubectl", "--kubeconfig", KUBECONFIG, "--context", "k3d-baatchit", *args], **kwargs)


def secret(name, data):
    existing = kubectl("-n", NAME, "get", "secret", name, capture=True, check=False)
    if existing.returncode == 0:
        return False
    resource = {"apiVersion": "v1", "kind": "Secret",
                "metadata": {"name": name, "namespace": NAME}, "stringData": data}
    kubectl("apply", "-f", "-", data=json.dumps(resource), capture=True)
    return True


def up():
    LOCAL.mkdir(exist_ok=True)
    run(["docker", "info"], capture=True)
    for component in ["backend", "frontend", "gateway"]:
        run(["docker", "build", "-f", ROOT / component / "Dockerfile",
             "-t", "baatchit-" + component + ":dev", "."])
    clusters = json.loads(run([k3d(), "cluster", "list", "-o", "json"], capture=True).stdout)
    if not any(c["name"] == NAME for c in clusters):
        run([k3d(), "cluster", "create", "--config", "platform/k3d/config.yaml"])
    config = run([k3d(), "kubeconfig", "get", NAME], capture=True).stdout
    KUBECONFIG.write_text(config, encoding="utf-8")
    KUBECONFIG.chmod(0o600)
    run([k3d(), "image", "import", "--cluster", NAME,
         "baatchit-backend:dev", "baatchit-frontend:dev", "baatchit-gateway:dev"])
    kubectl("apply", "-f", "k8s/platform/namespace.yaml")
    # A pair is provisioned together. Do not rotate one half on repeated startup.
    have_url = kubectl("-n", NAME, "get", "secret", "redis-url", capture=True, check=False).returncode == 0
    have_acl = kubectl("-n", NAME, "get", "secret", "redis-auth", capture=True, check=False).returncode == 0
    if have_url != have_acl:
        raise SystemExit("Incomplete Redis secret pair. Restore it or recreate the disposable local cluster.")
    if not have_url:
        password = secrets.token_hex(32)
        digest = hashlib.sha256(password.encode()).hexdigest()
        secret("redis-auth", {"users.acl": "user default off\nuser app on #" + digest
                              + " &global_chat_channel +ping +publish +subscribe +unsubscribe\n"})
        secret("redis-url", {"url": "redis://app:" + password + "@redis:6379/0"})
    have_database = kubectl("-n", NAME, "get", "secret", "database-url", capture=True, check=False).returncode == 0
    have_postgres = kubectl("-n", NAME, "get", "secret", "postgres-auth", capture=True, check=False).returncode == 0
    if have_database != have_postgres:
        raise SystemExit("Incomplete PostgreSQL secret pair. Restore the original credentials; do not rotate them independently.")
    if not have_database:
        password = secrets.token_hex(32)
        secret("postgres-auth", {"password": password})
        secret("database-url", {"url": "postgresql+psycopg://baatchit:" + password + "@postgres:5432/baatchit"})
    kubectl("apply", "-f", "k8s/platform/database.yaml")
    kubectl("-n", NAME, "rollout", "status", "deployment/postgres", "--timeout=240s")
    # A one-shot migration Pod uses the same image and secret as the application.
    migration_name = "accounts-migrate-" + secrets.token_hex(4)
    migration = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": migration_name, "namespace": NAME, "labels": {"app": "database-migration"}},
        "spec": {"restartPolicy": "Never", "automountServiceAccountToken": False,
            "securityContext": {"runAsNonRoot": True, "runAsUser": 10001, "runAsGroup": 10001, "fsGroup": 10001, "seccompProfile": {"type": "RuntimeDefault"}},
            "containers": [{"name": "migrate", "image": "baatchit-backend:dev", "imagePullPolicy": "IfNotPresent",
                "command": ["python", "-m", "app.migrate"],
                "env": [{"name": "REDIS_URL", "value": "redis://redis:6379/0"}, {"name": "DATABASE_URL_FILE", "value": "/etc/database/url"}],
                "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}},
                "resources": {"requests": {"cpu": "50m", "memory": "64Mi"}, "limits": {"cpu": "500m", "memory": "128Mi"}},
                "volumeMounts": [{"name": "database", "mountPath": "/etc/database", "readOnly": True}]}],
            "volumes": [{"name": "database", "secret": {"secretName": "database-url", "defaultMode": 288}}]}}
    # Install policies before the labeled migration Pod is scheduled.
    kubectl("-n", NAME, "apply", "-f", "k8s/base/network-policies.yaml")
    kubectl("apply", "-f", "-", data=json.dumps(migration))
    kubectl("-n", NAME, "wait", "--for=jsonpath={.status.phase}=Succeeded", "pod/" + migration_name, "--timeout=120s")
    kubectl("-n", NAME, "delete", "pod", migration_name)
    kubectl("apply", "-k", "k8s/overlays/local")
    for component in ["redis", "frontend", "backend", "gateway"]:
        if component != "redis":
            kubectl("-n", NAME, "rollout", "restart", "deployment/" + component)
        kubectl("-n", NAME, "rollout", "status", "deployment/" + component, "--timeout=240s")
    print("Baatchit: http://localhost:8080")
    print("Explicit kubeconfig:", KUBECONFIG)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["up", "down", "status"])
    args = parser.parse_args()
    if args.action == "up":
        up()
    elif args.action == "down":
        if input("This deletes the local cluster, including saved accounts and messages. Type DELETE to continue: ") != "DELETE":
            raise SystemExit("Cancelled; local data preserved.")
        run([k3d(), "cluster", "delete", NAME])
        print("Removed only the local baatchit k3d cluster.")
    else:
        kubectl("-n", NAME, "get", "deployments,pods,services")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        # Do not echo input payloads: some commands receive Secret data on stdin.
        print("Local operation failed (exit " + str(exc.returncode) + ").", file=sys.stderr)
        raise SystemExit(1) from None
