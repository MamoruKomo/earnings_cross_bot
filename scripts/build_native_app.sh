#!/bin/zsh
set -euo pipefail
REPO_DIR="${0:A:h:h}"
NATIVE_DIR="$REPO_DIR/native"
APP_DIR="$REPO_DIR/build/EarningsCrossManager.app"
CACHE_DIR="$REPO_DIR/.swift-cache"
mkdir -p "$CACHE_DIR/clang" "$CACHE_DIR/home"
export HOME="$CACHE_DIR/home"
export CLANG_MODULE_CACHE_PATH="$CACHE_DIR/clang"
export SWIFTPM_MODULECACHE_OVERRIDE="$CACHE_DIR/clang"
cd "$NATIVE_DIR"
swift build --disable-sandbox -c release
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"
cp "$NATIVE_DIR/.build/release/EarningsCrossManager" "$APP_DIR/Contents/MacOS/EarningsCrossManager"
cp "$NATIVE_DIR/Info.plist" "$APP_DIR/Contents/Info.plist"
cp "$NATIVE_DIR/Resources/AppIcon.png" "$APP_DIR/Contents/Resources/AppIcon.png"
echo "$APP_DIR"
