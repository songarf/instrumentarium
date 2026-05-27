#!/bin/bash
# Generate macOS .icns from icon.png (512x512)
# Requires macOS + iconutil
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ICON_PNG="$SCRIPT_DIR/icon.png"
ICONSET="$SCRIPT_DIR/icon.iconset"
ICONS_ICNS="$SCRIPT_DIR/icon.icns"

rm -rf "$ICONSET" "$ICONS_ICNS"
mkdir -p "$ICONSET"

# Generate all required sizes
sips -z 16 16     "$ICON_PNG" --out "$ICONSET/icon_16x16.png" >/dev/null
sips -z 32 32     "$ICON_PNG" --out "$ICONSET/icon_16x16@2x.png" >/dev/null
sips -z 32 32     "$ICON_PNG" --out "$ICONSET/icon_32x32.png" >/dev/null
sips -z 64 64     "$ICON_PNG" --out "$ICONSET/icon_32x32@2x.png" >/dev/null
sips -z 128 128   "$ICON_PNG" --out "$ICONSET/icon_128x128.png" >/dev/null
sips -z 256 256   "$ICON_PNG" --out "$ICONSET/icon_128x128@2x.png" >/dev/null
sips -z 256 256   "$ICON_PNG" --out "$ICONSET/icon_256x256.png" >/dev/null
sips -z 512 512   "$ICON_PNG" --out "$ICONSET/icon_256x256@2x.png" >/dev/null
sips -z 512 512   "$ICON_PNG" --out "$ICONSET/icon_512x512.png" >/dev/null
cp "$ICON_PNG" "$ICONSET/icon_512x512@2x.png"

# Compile .icns
iconutil -c icns "$ICONSET" -o "$ICONS_ICNS"
rm -rf "$ICONSET"
echo "✅ icon.icns generated"
