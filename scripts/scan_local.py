"""Scan local images using a pinned Trivy image; retains JSON reports in artifacts."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TRIVY = "aquasec/trivy@sha256:790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c"
IMAGES = {"backend":"baatchit-backend:dev", "frontend":"baatchit-frontend:dev", "gateway":"baatchit-gateway:dev",
          "redis":"redis@sha256:47b08295737773de3b711fb86f13ae802f5074e96a9a2d29f5f80164ac08c046"}

if __name__ == "__main__":
    output = ROOT / "artifacts" / "security"
    output.mkdir(parents=True, exist_ok=True)
    failures = []
    for component, image in IMAGES.items():
        result = subprocess.run(["docker", "run", "--rm",
            "-v", "/var/run/docker.sock:/var/run/docker.sock",
            "-v", "baatchit-trivy-cache:/root/.cache/",
            "-v", str(output) + ":/reports", TRIVY, "image",
            "--quiet", "--scanners", "vuln", "--severity", "HIGH,CRITICAL", "--ignore-unfixed",
            "--exit-code", "1", "--format", "json", "--output", "/reports/scan-" + component + ".json", image])
        print(component + ": " + ("passed" if result.returncode == 0 else "failed"), flush=True)
        if result.returncode:
            failures.append(component)
    raise SystemExit(1 if failures else 0)
