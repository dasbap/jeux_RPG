#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "$0")/.." && pwd)"
export ANDROID_USER_HOME="$task_root/.data/android-user"
export ADB_VENDOR_KEYS="$ANDROID_USER_HOME/adbkey"
exec "$task_root/.toolchains/android-sdk/platform-tools/adb" "$@"
