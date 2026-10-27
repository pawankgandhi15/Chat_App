import copy
import json
import logging
from types import SimpleNamespace

import pytest
import yaml

from app.run import TransportLogFilter
from scripts.release import render, validate_bundle, verify, sha256, ROOT


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    objects = list(yaml.safe_load_all((ROOT / "k8s/base/workloads.yaml").read_text()))
    objects += list(yaml.safe_load_all((ROOT / "k8s/base/services.yaml").read_text()))
    objects += list(yaml.safe_load_all((ROOT / "k8s/base/network-policies.yaml").read_text()))
    objects.append({"apiVersion":"v1", "kind":"ConfigMap", "metadata":{"name":"backend-config"},
                    "data":{"APP_ENV":"public"}})
    for obj in objects:
        obj["metadata"]["namespace"] = "baatchit"
    monkeypatch.setattr("scripts.release.subprocess.run", lambda *a, **kw: SimpleNamespace(stdout=yaml.safe_dump_all(objects)))
    images = {c: "ghcr.io/test/baatchit-" + c + "@sha256:" + "a"*64 for c in ["backend", "frontend", "gateway", "redis"]}
    imagefile = tmp_path / "images.json"
    imagefile.write_text(json.dumps(images))
    output = tmp_path / "release"
    output.mkdir()
    for c, image in images.items():
        (output / ("scan-" + c + ".json")).write_text(json.dumps(
            {"ArtifactName":image, "ArtifactType":"container_image", "Results":[]}))
        (output / ("sbom-" + c + ".json")).write_text(json.dumps({"spdxVersion":"SPDX-2.3", "packages":[{"name":c}]}))
    render(SimpleNamespace(output=output, images=imagefile, release_id="release-1",
                           commit="a"*40, origin="https://chat.example.com"))
    return output


def rehash(bundle, filename):
    path = bundle / "release.json"
    manifest = json.loads(path.read_text())
    manifest["files"][filename] = sha256((bundle / filename).read_bytes())
    path.write_text(json.dumps(manifest))


def test_valid_release_and_tampered_config(bundle):
    assert validate_bundle(bundle)["release_id"] == "release-1"
    path = bundle / "manifests.yaml"
    path.write_text(path.read_text() + "\n# modified")
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_bundle(bundle)


def test_rejects_privileged_pod_even_with_updated_hash(bundle):
    path = bundle / "manifests.yaml"
    objects = list(yaml.safe_load_all(path.read_text()))
    objects[0]["spec"]["template"]["spec"]["containers"][0]["securityContext"]["privileged"] = True
    path.write_text(yaml.safe_dump_all(objects))
    rehash(bundle, path.name)
    with pytest.raises(ValueError, match="Unsafe container"):
        validate_bundle(bundle)


def test_rejects_wrong_scan_and_fixable_vulnerability(bundle):
    path = bundle / "scan-backend.json"
    original = json.loads(path.read_text())
    data = copy.deepcopy(original)
    data["ArtifactName"] = "different-image"
    path.write_text(json.dumps(data))
    rehash(bundle, path.name)
    with pytest.raises(ValueError, match="Scan does not match"):
        validate_bundle(bundle)
    original["Results"] = [{"Vulnerabilities":[{"Severity":"HIGH", "FixedVersion":"2.0"}]}]
    path.write_text(json.dumps(original))
    rehash(bundle, path.name)
    with pytest.raises(ValueError, match="fixable"):
        validate_bundle(bundle)


def test_empty_trust_policy_fails_before_invoking_cosign(tmp_path):
    with pytest.raises(ValueError, match="trusted GHCR"):
        verify(tmp_path, "", "")


def test_transport_logs_do_not_expose_names_or_exception_values():
    filter_ = TransportLogFilter()
    handshake = logging.LogRecord("uvicorn.error", 20, "", 1, '%s - "WebSocket %s" [accepted]',
                                   ("127.0.0.1", "/ws/Alice"), None)
    assert not filter_.filter(handshake)
    error = logging.LogRecord("uvicorn.error", 40, "", 1, "ASGI error", (),
                              (RuntimeError, RuntimeError("secret-url"), None))
    assert filter_.filter(error)
    assert error.getMessage() == "transport_error: RuntimeError"
    assert error.exc_info is None
