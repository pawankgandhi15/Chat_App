"""Check both Kustomize overlays without requiring a cluster."""
import json
from pathlib import Path
import subprocess
import yaml
from release import validate_resources

ROOT = Path(__file__).resolve().parents[1]


def check():
    for overlay in ["local", "aws"]:
        result = subprocess.run(["kubectl", "kustomize", str(ROOT / "k8s/overlays" / overlay)],
                                check=True, capture_output=True, text=True)
        objects = list(yaml.safe_load_all(result.stdout))
        assert all(o["metadata"].get("namespace") == "baatchit" for o in objects)
        configs = {o["metadata"]["name"] for o in objects if o["kind"] == "ConfigMap"}
        deployments = [o for o in objects if o["kind"] == "Deployment"]
        assert len(deployments) == 4
        for deployment in deployments:
            pod = deployment["spec"]["template"]["spec"]
            container = pod["containers"][0]
            volumes = {v["name"]: v for v in pod.get("volumes", [])}
            assert any(m["mountPath"] == "/tmp" for m in container["volumeMounts"])
            for mount in container["volumeMounts"]:
                assert mount["name"] in volumes
            for volume in volumes.values():
                if "configMap" in volume:
                    assert volume["configMap"]["name"] in configs
            for source in container.get("envFrom", []):
                assert source["configMapRef"]["name"] in configs
        backend = next(d for d in deployments if d["metadata"]["name"] == "backend")
        assert backend["spec"]["replicas"] == 2
        if overlay == "aws":
            manifest = {"images": {d["metadata"]["name"]: d["spec"]["template"]["spec"]["containers"][0]["image"]
                                   for d in deployments},
                        "release_id": "RELEASE_REQUIRED", "origin": "PUBLIC_ORIGIN_REQUIRED",
                        "secrets_required": ["redis-url", "redis-auth", "gateway-tls", "database-url"]}
            validate_resources(objects, manifest)
        print(overlay + ": topology, namespace, volume/config references and permissions passed")
    print("Both overlays render successfully.")
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    from app.protocol import SessionEvent, BroadcastEvent
    contract = json.loads((ROOT / "schemas/events-v1.schema.json").read_text())
    assert contract["oneOf"] == [SessionEvent.model_json_schema(), BroadcastEvent.model_json_schema()]
    print("Checked-in event schema matches the backend models.")


if __name__ == "__main__":
    check()
