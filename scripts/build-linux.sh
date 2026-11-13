#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
export PATH="$task_root/.toolchains/node/bin:$PATH"
export ELECTRON_CACHE="$task_root/.toolchains/electron-cache"
export ELECTRON_BUILDER_CACHE="$task_root/.toolchains/electron-builder-cache"
node desktop/build.cjs --linux --skip-prepare
