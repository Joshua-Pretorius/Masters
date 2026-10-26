#!/usr/bin/env bash
set -euo pipefail
job_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$job_dir/../.." && pwd)"
cd "$repo_dir"
test -f compose.yml
test -f /mnt/storage/bolelang_mount/Joshua/server.env
python3 "$job_dir/validate_inputs.py"
sudo env JOB_DIR="$job_dir" JOB_MANIFEST=/job/job.yaml docker compose --env-file /mnt/storage/bolelang_mount/Joshua/server.env run --rm pipeline
