#!/usr/bin/env bash
set -euo pipefail
MODE="${1:-run}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
APP_NAME="CompanionMac"
APP="$ROOT/dist/$APP_NAME.app"
if [[ "$MODE" != "--build" ]]; then pkill -x "$APP_NAME" >/dev/null 2>&1 || true; fi
cd "$ROOT"
swift build
export OPUS_LIB_DIR="${OPUS_LIB_DIR:-$(brew --prefix opus)/lib}"
cargo build --release --locked --manifest-path "$REPO/packages/macos-audio/Cargo.toml"
BIN="$(swift build --show-bin-path)"
mkdir -p "$APP/Contents/MacOS"
cp "$BIN/$APP_NAME" "$APP/Contents/MacOS/$APP_NAME"
cp "$BIN/companion-mcp" "$APP/Contents/MacOS/companion-mcp"
TARGET="${CARGO_TARGET_DIR:-$REPO/packages/macos-audio/target}"
cp "$TARGET/release/companion-mac-audio" "$APP/Contents/MacOS/companion-mac-audio"
cat >"$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>CompanionMac</string>
<key>CFBundleIdentifier</key><string>com.denzic.companion.mac</string>
<key>CFBundleName</key><string>Companion</string>
<key>CFBundleShortVersionString</key><string>0.1.0</string>
<key>CFBundleVersion</key><string>1</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>LSMinimumSystemVersion</key><string>14.0</string>
<key>NSPrincipalClass</key><string>NSApplication</string>
<key>NSBluetoothAlwaysUsageDescription</key><string>连接你的 Companion 录音卡，接收按住说话录音和重点标记。</string>
</dict></plist>
PLIST
codesign --force --sign - "$APP/Contents/MacOS/companion-mac-audio"
codesign --force --sign - "$APP/Contents/MacOS/companion-mcp"
codesign --force --sign - "$APP"
case "$MODE" in
  --build) printf '%s\n' "$APP" ;;
  --debug) lldb -- "$APP/Contents/MacOS/$APP_NAME" ;;
  --logs|--telemetry) open -n "$APP"; /usr/bin/log stream --info --style compact --predicate 'process == "CompanionMac"' ;;
  --verify) open -n "$APP"; sleep 1; pgrep -x "$APP_NAME" >/dev/null ;;
  run) open -n "$APP" ;;
  *) printf 'usage: %s [run|--build|--debug|--logs|--telemetry|--verify]\n' "$0" >&2; exit 2 ;;
esac
