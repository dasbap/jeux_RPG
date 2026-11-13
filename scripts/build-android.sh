#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$task_root"
export JAVA_HOME="$task_root/.toolchains/jdk"
export ANDROID_HOME="$task_root/.toolchains/android-sdk"
export ANDROID_USER_HOME="$task_root/.data/android-user"
# Gradle's atomic directory renames are unreliable on WSL's Windows mounts.
export GRADLE_USER_HOME="${RPG_GRADLE_CACHE:-/tmp/jeux-rpg-gradle-$UID}"
export PATH="$JAVA_HOME/bin:$PATH"
yes | "$ANDROID_HOME/cmdline-tools/19.0/bin/sdkmanager" --sdk_root="$ANDROID_HOME" --licenses >/dev/null || test "${PIPESTATUS[1]}" -eq 0
if [ ! -f .signing/android/jeux-rpg.jks ]; then
  export RPG_SIGNING_PASSWORD="$(sed -n 's/^storePassword=//p' .signing/android/signing.properties | tr -d '\r')"
  keytool -genkeypair -keystore .signing/android/jeux-rpg.jks -alias jeux-rpg -keyalg RSA -keysize 3072 -validity 10000 -storepass:env RPG_SIGNING_PASSWORD -keypass:env RPG_SIGNING_PASSWORD -dname "CN=Jeux RPG, O=Jeux RPG, C=FR"
  unset RPG_SIGNING_PASSWORD
fi
"$task_root/.toolchains/gradle-8.11.1/bin/gradle" -p android assembleRelease assembleDebug --no-daemon
mkdir -p dist/mobile
cp android/app/build/outputs/apk/release/app-release.apk dist/mobile/Jeux-RPG-Android.apk
"$ANDROID_HOME/build-tools/35.0.0/apksigner" verify --verbose dist/mobile/Jeux-RPG-Android.apk
