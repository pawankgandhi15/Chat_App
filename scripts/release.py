"""Render and validate immutable AWS releases. Signature verification is mandatory for deploy."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = {"gateway", "frontend", "backend", "redis"}
DIGEST = re.compile(r"^[a-z0-9./:_-]+@sha256:[0-9a-f]{64}$")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def validate_resources(resources, manifest):
    deployments = {}
    services = {}
    allowed = {"Deployment", "Service", "ConfigMap", "NetworkPolicy"}
    identities = set()
    for obj in resources:
        if not isinstance(obj, dict) or obj.get("kind") not in allowed:
            raise ValueError("Unsupported application resource kind")
        meta = obj.get("metadata", {})
        if meta.get("namespace") != "chat-app" or not re.fullmatch(r"[a-z0-9-]+", meta.get("name", "")):
            raise ValueError("Unexpected namespace or resource name")
        key = (obj["kind"], meta["name"])
        if key in identities:
            raise ValueError("Duplicate resource")
        identities.add(key)
        if obj["kind"] == "Deployment":
            name = meta["name"]
            if name not in COMPONENTS:
                raise ValueError("Unexpected Deployment")
            spec = obj["spec"]["template"]["spec"]
            if any(spec.get(k) for k in ("hostNetwork", "hostPID", "hostIPC", "initContainers", "ephemeralContainers")):
                raise ValueError("Unsafe Pod permissions")
            if spec.get("automountServiceAccountToken") is not False:
                raise ValueError("Application API tokens are forbidden")
            security = spec.get("securityContext", {})
            if security.get("runAsNonRoot") is not True or security.get("seccompProfile", {}).get("type") != "RuntimeDefault":
                raise ValueError("Missing Pod hardening")
            containers = spec["containers"]
            if len(containers) != 1 or containers[0]["image"] != manifest["images"][name]:
                raise ValueError("Unexpected application image")
            container = containers[0]
            ctx = container.get("securityContext", {})
            if (ctx.get("privileged", False) or ctx.get("allowPrivilegeEscalation") is not False
                    or ctx.get("readOnlyRootFilesystem") is not True
                    or ctx.get("capabilities", {}).get("drop") != ["ALL"]
                    or ctx.get("capabilities", {}).get("add")):
                raise ValueError("Unsafe container permissions")
            if not all(container.get("resources", {}).get(k, {}).get("memory") for k in ["requests", "limits"]):
                raise ValueError("Missing resource bounds")
            for volume in spec.get("volumes", []):
                if set(volume) - {"name", "emptyDir", "configMap", "secret"}:
                    raise ValueError("Unsupported volume")
                if "secret" in volume and volume["secret"]["secretName"] not in manifest["secrets_required"]:
                    raise ValueError("Unexpected Secret reference")
            if any(p.get("hostPort") for p in container.get("ports", [])):
                raise ValueError("Application host ports are forbidden")
            deployments[name] = obj
        if obj["kind"] == "Service":
            name = meta["name"]
            if name not in COMPONENTS:
                raise ValueError("Unexpected Service")
            if obj["spec"].get("type", "ClusterIP") != ("LoadBalancer" if name == "gateway" else "ClusterIP"):
                raise ValueError("Unexpected service exposure")
            if obj["spec"].get("externalIPs") or obj["spec"].get("externalName"):
                raise ValueError("Unexpected external route")
            services[name] = obj
        if obj["kind"] == "ConfigMap":
            if "REDIS_URL" in obj.get("data", {}):
                raise ValueError("Credentials cannot be included in configuration")
            if "APP_ENV" in obj.get("data", {}):
                data = obj["data"]
                if data.get("APP_ENV") != "public" or data.get("RELEASE_ID") != manifest["release_id"] or data.get("ALLOWED_ORIGINS") != manifest["origin"]:
                    raise ValueError("Release configuration mismatch")
    if set(deployments) != COMPONENTS or set(services) != COMPONENTS:
        raise ValueError("Incomplete release topology")
    if ("NetworkPolicy", "default-deny") not in identities:
        raise ValueError("Missing isolation policy")


def validate_bundle(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "release.json").read_text())
    schema = json.loads((ROOT / "schemas/release.schema.json").read_text())
    jsonschema.validate(manifest, schema)
    origin = urlsplit(manifest["origin"])
    if origin.scheme != "https" or not origin.hostname or origin.path or origin.query or origin.fragment or origin.username or origin.hostname.endswith(".invalid"):
        raise ValueError("Release needs a real HTTPS origin")
    for image in manifest["images"].values():
        if not DIGEST.fullmatch(image):
            raise ValueError("All release images must use immutable digests")
    for filename, digest in manifest["files"].items():
        if not re.fullmatch(r"[a-zA-Z0-9._-]+\.(json|yaml)", filename):
            raise ValueError("Invalid bundle filename")
        if sha256((directory / filename).read_bytes()) != digest:
            raise ValueError("Bundle hash mismatch: " + filename)
    resources = list(yaml.safe_load_all((directory / "manifests.yaml").read_text()))
    validate_resources(resources, manifest)
    for component, image in manifest["images"].items():
        scan = json.loads((directory / ("scan-" + component + ".json")).read_text())
        if scan.get("ArtifactName") != image or scan.get("ArtifactType") != "container_image":
            raise ValueError("Scan does not match the released image")
        for result in scan.get("Results", []):
            for vulnerability in result.get("Vulnerabilities") or []:
                if vulnerability.get("Severity") in {"HIGH", "CRITICAL"} and vulnerability.get("FixedVersion"):
                    raise ValueError("Image has a fixable high/critical vulnerability")
        sbom = json.loads((directory / ("sbom-" + component + ".json")).read_text())
        if not str(sbom.get("spdxVersion", "")).startswith("SPDX-") or not sbom.get("packages"):
            raise ValueError("Missing SPDX software inventory")
    return manifest


def verify(directory, identity, image_prefix):
    directory = Path(directory)
    if not re.fullmatch(r"ghcr\.io/[a-z0-9_.-]+/[a-z0-9_.-]+-", image_prefix):
        raise ValueError("Set the exact trusted GHCR repository prefix ending in a hyphen")
    if not re.fullmatch(r"https://github\.com/[^/]+/[^/]+/\.github/workflows/release\.yml@refs/heads/main", identity):
        raise ValueError("Set the trusted main-branch release workflow identity")
    # Identity and repository policy come from the operator, never the bundle.
    subprocess.run(["cosign", "verify-blob", "--bundle", str(directory / "release.sigstore.json"),
                    "--certificate-identity", identity, "--certificate-oidc-issuer",
                    "https://token.actions.githubusercontent.com", str(directory / "release.json")],
                   check=True, capture_output=True, timeout=60)
    manifest = validate_bundle(directory)
    for image in manifest["images"].values():
        component = next(name for name, ref in manifest["images"].items() if ref == image)
        if image.split("@")[0] != image_prefix + component:
            raise ValueError("Image repository is outside the trusted prefix")
        subprocess.run(["cosign", "verify", "--certificate-identity", identity,
                        "--certificate-oidc-issuer", "https://token.actions.githubusercontent.com", image],
                       check=True, capture_output=True, timeout=60)
    return manifest


def render(args):
    directory = Path(args.output)
    directory.mkdir(parents=True, exist_ok=True)
    images = json.loads(Path(args.images).read_text())
    if set(images) != COMPONENTS:
        raise ValueError("Supply all four component images")
    rendered = subprocess.run(["kubectl", "kustomize", str(ROOT / "k8s/overlays/aws")],
                              check=True, text=True, capture_output=True).stdout
    resources = list(yaml.safe_load_all(rendered))
    rename = {}
    for obj in resources:
        if obj["kind"] == "ConfigMap" and "APP_ENV" in obj.get("data", {}):
            obj["data"].update(APP_ENV="public", RELEASE_ID=args.release_id, ALLOWED_ORIGINS=args.origin)
            old = obj["metadata"]["name"]
            new = "backend-config-" + sha256(json.dumps(obj["data"], sort_keys=True).encode())[:10]
            rename[old] = new
            obj["metadata"]["name"] = new
    for obj in resources:
        if obj["kind"] == "Deployment":
            name = obj["metadata"]["name"]
            template = obj["spec"]["template"]
            template["metadata"].setdefault("annotations", {})["chat-app/release"] = args.release_id
            container = template["spec"]["containers"][0]
            container["image"] = images[name]
            for source in container.get("envFrom", []):
                if "configMapRef" in source:
                    ref = source["configMapRef"]
                    ref["name"] = rename.get(ref["name"], ref["name"])
    body = yaml.safe_dump_all(resources, sort_keys=False).encode()
    (directory / "manifests.yaml").write_bytes(body)
    files = {"manifests.yaml": sha256(body)}
    for path in sorted(directory.glob("*.json")):
        if path.name.startswith(("sbom-", "scan-")):
            files[path.name] = sha256(path.read_bytes())
    for component in COMPONENTS:
        if "sbom-" + component + ".json" not in files or "scan-" + component + ".json" not in files:
            raise ValueError("Include an SBOM and scan report for every image before packaging")
    manifest = {"schema_version":1, "release_id":args.release_id, "source_commit":args.commit,
                "created_at":datetime.now(timezone.utc).isoformat(), "origin":args.origin,
                "target_architecture":"linux/amd64", "images":images, "files":files,
                "secrets_required":["redis-url", "redis-auth", "gateway-tls"]}
    (directory / "release.json").write_text(json.dumps(manifest, indent=2) + "\n")
    validate_bundle(directory)
    print("Rendered release; sign release.json before deployment.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("render")
    for flag in ["output", "images", "release-id", "commit", "origin"]:
        create.add_argument("--" + flag, required=True)
    verify_cmd = sub.add_parser("verify")
    for flag in ["directory", "identity", "image-prefix"]:
        verify_cmd.add_argument("--" + flag, required=True)
    args = parser.parse_args()
    if args.action == "render":
        render(args)
    else:
        verify(args.directory, args.identity, args.image_prefix)
        print("Verified release and images.")
