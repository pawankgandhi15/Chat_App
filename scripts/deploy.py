"""Linux operator deployment with verified bundles, serialization and automatic restoration."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from release import verify
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ["bundle", "kubeconfig", "context", "identity", "image-prefix", "state-dir"]:
        parser.add_argument("--" + arg, required=True)
    args = parser.parse_args()
    if os.name != "posix":
        raise SystemExit("Run this deployment entrypoint on the controlled Linux operator/runner.")
    import fcntl
    state = Path(args.state_dir).resolve()
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (state / "deploy.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        source = Path(args.bundle).resolve()
        manifest = verify(source, args.identity, args.image_prefix)
        target = state / manifest["release_id"]
        if target.exists():
            # Do not overwrite an accepted artifact set under the same identifier.
            if (target / "release.json").read_bytes() != (source / "release.json").read_bytes():
                raise ValueError("Release ID already exists with different content")
        else:
            target.mkdir(mode=0o700)
            for filename in ["release.json", "release.sigstore.json", *manifest["files"]]:
                shutil.copyfile(source / filename, target / filename)
        verify(target, args.identity, args.image_prefix)
        kube = ["kubectl", "--kubeconfig", args.kubeconfig, "--context", args.context, "-n", "chat-app"]
        current_file = state / "current.json"
        previous = json.loads(current_file.read_text()) if current_file.exists() else None

        def journal(status):
            (state / "journal.json").write_text(json.dumps({"release_id":manifest["release_id"], "status":status}) + "\n")

        def apply(bundle, spec):
            deadline = time.monotonic() + 240
            subprocess.run(kube + ["apply", "--dry-run=server", "-f", str(bundle / "manifests.yaml")], check=True, timeout=30)
            subprocess.run(kube + ["apply", "-f", str(bundle / "manifests.yaml")], check=True, timeout=30)
            for component in ["redis", "frontend", "backend", "gateway"]:
                remaining = max(1, int(deadline - time.monotonic()))
                subprocess.run(kube + ["rollout", "status", "deployment/" + component, "--timeout=" + str(remaining) + "s"], check=True, timeout=remaining + 5)
            subprocess.run([sys.executable, str(ROOT / "scripts/smoke.py"), "--url", spec["origin"]], check=True, timeout=60)

        journal("started")
        try:
            apply(target, manifest)
            pending = state / "current.pending"
            pending.write_text(json.dumps({"directory":str(target), "release_id":manifest["release_id"]}) + "\n")
            os.replace(pending, current_file)
            journal("accepted")
        except Exception:
            journal("failed")
            if previous:
                prior = Path(previous["directory"])
                prior_spec = verify(prior, args.identity, args.image_prefix)
                apply(prior, prior_spec)
                journal("restored")
            raise


if __name__ == "__main__":
    main()
