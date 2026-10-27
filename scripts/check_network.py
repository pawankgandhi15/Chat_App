"""Exercise allowed and denied paths in the disposable local Kubernetes cluster."""
import json
import subprocess
from local import kubectl


def probe(source, host, port, allowed):
    # Use a real socket timeout. Exit 42 means a connection was refused/timed out;
    # missing executables or other setup failures must fail the test, not pass it.
    if source == "backend":
        command = ["python", "-c",
                   "import socket,sys\ntry:\n s=socket.create_connection((sys.argv[1],int(sys.argv[2])),2);s.close()\nexcept OSError: sys.exit(42)",
                   host, str(port)]
    else:
        command = ["sh", "-c", 'command -v nc >/dev/null || exit 127; nc -z -w 2 "$1" "$2" || exit 42',
                   "probe", host, str(port)]
    result = kubectl("-n", "baatchit", "exec", "deployment/" + source, "--", *command,
                     capture=True, check=False)
    expected = 0 if allowed else 42
    if result.returncode != expected:
        raise RuntimeError(f"{source} -> {host}:{port}: expected {expected}, got {result.returncode}: {result.stderr}")
    print(f"{source} -> {host}:{port}: " + ("allowed" if allowed else "denied"))


if __name__ == "__main__":
    probe("gateway", "frontend", 80, True)
    probe("gateway", "backend", 8000, True)
    probe("backend", "redis", 6379, True)
    # DNS must work for the negative test to mean anything.
    for source in ["gateway", "frontend"]:
        kubectl("-n", "baatchit", "exec", "deployment/" + source, "--", "nslookup", "redis.baatchit.svc.cluster.local", capture=True)
        probe(source, "redis", 6379, False)
    pod = json.loads(kubectl("-n", "baatchit", "get", "pods", "-l", "app=redis",
                             "-o", "json", capture=True).stdout)["items"][0]
    probe("gateway", pod["status"]["podIP"], 6379, False)
    probe("frontend", pod["status"]["podIP"], 6379, False)
    print("NetworkPolicy checks passed for Service and direct Pod addresses.")
