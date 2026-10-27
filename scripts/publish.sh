#!/usr/bin/env bash
# Only the explicitly dispatched Release workflow invokes this.
set -euo pipefail
test -n "$GITHUB_REPOSITORY"
test -n "$GITHUB_SHA"
test -n "$PUBLIC_ORIGIN"
mkdir -p artifacts/release
owner=$(printf '%s' "$GITHUB_REPOSITORY" | cut -d / -f 1 | tr '[:upper:]' '[:lower:]')
prefix="ghcr.io/$owner/baatchit-"
docker buildx create --use --driver docker-container --name baatchit-release-builder
for component in backend frontend gateway redis; do
  image="$prefix$component:$GITHUB_SHA"
  docker buildx build --platform linux/amd64 --provenance=true --sbom=true \
    -f "$component/Dockerfile" -t "$image" --push --metadata-file "artifacts/$component.json" .
  digest=$(python -c 'import json,sys;print(json.load(open(sys.argv[1]))["containerimage.digest"])' "artifacts/$component.json")
  ref="$prefix$component@$digest"
  docker run --rm -e TRIVY_USERNAME -e TRIVY_PASSWORD \
    -v "$PWD/artifacts/release:/reports" aquasec/trivy@sha256:790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c image \
    --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 --format json \
    --output "/reports/scan-$component.json" "$ref"
  docker run --rm -e TRIVY_USERNAME -e TRIVY_PASSWORD \
    -v "$PWD/artifacts/release:/reports" aquasec/trivy@sha256:790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c image \
    --format spdx-json --output "/reports/sbom-$component.json" "$ref"
  cosign sign --yes "$ref"
done
python - <<'PY'
import json, os
from pathlib import Path
prefix = "ghcr.io/" + os.environ["GITHUB_REPOSITORY"].split("/")[0].lower() + "/baatchit-"
images = {c: prefix+c+"@"+json.loads(Path("artifacts/"+c+".json").read_text())["containerimage.digest"]
          for c in ["backend","frontend","gateway","redis"]}
Path("artifacts/images.json").write_text(json.dumps(images))
PY
python scripts/release.py render --images artifacts/images.json --output artifacts/release \
  --release-id "$GITHUB_SHA" --commit "$GITHUB_SHA" --origin "$PUBLIC_ORIGIN"
cosign sign-blob --yes --bundle artifacts/release/release.sigstore.json artifacts/release/release.json
