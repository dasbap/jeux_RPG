#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export JAVA_HOME="$task_root/.toolchains/jdk"
export ANDROID_HOME="$task_root/.toolchains/android-sdk"
export ANDROID_USER_HOME="$task_root/.data/android-user"
mkdir -p "$ANDROID_USER_HOME"
yes | "$ANDROID_HOME/cmdline-tools/19.0/bin/sdkmanager" --sdk_root="$ANDROID_HOME" --licenses >/dev/null || test "${PIPESTATUS[1]}" -eq 0
packages=("platform-tools" "platforms;android-35" "build-tools;35.0.0")
if [ "${1:-}" = "--with-emulator" ]; then
  packages+=("emulator" "system-images;android-35;google_apis;x86_64")
fi
"$ANDROID_HOME/cmdline-tools/19.0/bin/sdkmanager" --sdk_root="$ANDROID_HOME" "${packages[@]}"
