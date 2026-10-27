#!/bin/sh
# Run inside the pinned Terraform container; no AWS credentials or apply needed.
set -eu
terraform fmt -check -recursive infra
for root in infra/workload infra/bootstrap-state; do
  terraform -chdir="$root" init -backend=false -lockfile=readonly -input=false
  terraform -chdir="$root" validate
done
