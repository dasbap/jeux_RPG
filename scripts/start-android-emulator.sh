#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "$0")/.." && pwd)"
export JAVA_HOME="$task_root/.toolchains/jdk"
export ANDROID_HOME="$task_root/.toolchains/android-sdk"
export ANDROID_USER_HOME="$task_root/.data/android-user"
export ANDROID_EMULATOR_HOME="$ANDROID_USER_HOME"
export ADB_VENDOR_KEYS="$ANDROID_USER_HOME/adbkey"
export ANDROID_AVD_HOME="$task_root/.data/android-avd"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH"
mkdir -p "$ANDROID_AVD_HOME"
if [ ! -f "$ADB_VENDOR_KEYS" ]; then adb keygen "$ADB_VENDOR_KEYS"; fi
if [ ! -f "$ANDROID_AVD_HOME/JeuxRPGTest.ini" ]; then
  echo no | "$ANDROID_HOME/cmdline-tools/19.0/bin/avdmanager" create avd -n JeuxRPGTest -k 'system-images;android-35;google_apis;x86_64' -p "$ANDROID_AVD_HOME/JeuxRPGTest.avd"
  printf '\nhw.lcd.width=540\nhw.lcd.height=960\nhw.lcd.density=240\n' >> "$ANDROID_AVD_HOME/JeuxRPGTest.avd/config.ini"
fi
exec "$ANDROID_HOME/emulator/emulator" -avd JeuxRPGTest -no-window -no-audio -no-boot-anim -no-snapshot -no-metrics -gpu swiftshader -memory 2048 -cores 2 -accel on
