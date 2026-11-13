#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$task_root"
export RPG_DESKTOP_EXECUTABLE="$task_root/dist/linux/linux-unpacked/jeux-rpg"
"$task_root/.toolchains/node/bin/node" scripts/verify_desktop.cjs --packaged
