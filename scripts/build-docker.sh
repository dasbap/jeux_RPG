#!/usr/bin/env bash
set -euo pipefail
rpg_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$rpg_root"
rpg_target="${1:-all}"
case "$rpg_target" in
  windows|linux) rpg_stage=desktop ;;
  android|all) rpg_stage=android ;;
  *) echo 'Usage: bash scripts/build-docker.sh [windows|linux|android|all]' >&2; exit 2 ;;
esac
docker info >/dev/null
mkdir -p dist
docker build --platform linux/amd64 --target "$rpg_stage" -f deploy/build/Dockerfile -t "jeux-rpg-build:$rpg_stage" .
rpg_mounts=(--mount "type=bind,source=$rpg_root/dist,target=/out")
if [[ "$rpg_stage" == android ]]; then
  mkdir -p .signing
  rpg_mounts+=(--mount "type=bind,source=$rpg_root/.signing,target=/project/.signing")
fi
docker run --rm --platform linux/amd64 "${rpg_mounts[@]}" "jeux-rpg-build:$rpg_stage" "$rpg_target"
