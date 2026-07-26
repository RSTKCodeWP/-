#!/bin/bash
# Builds HDZeroProgrammer, embeds a self-contained flashrom (+ its dylibs),
# packages a macOS .app bundle, then Developer ID-signs + notarizes it.
# Mirrors the proven HDZeroConverter pipeline.
set -e
cd "$(dirname "$0")"

APP_NAME="HDZero Programmer"
BUNDLE_ID="co.arkana.hdzeroprogrammer"
VERSION="${VERSION:-1.2}"

# ---- Signing / notarization configuration ----------------------------------
# Two "Developer ID Application" certs share the same name in this keychain, so
# passing the name to codesign is ambiguous. Resolve to the first SHA-1 instead.
if [ -z "${SIGN_IDENTITY:-}" ]; then
    SIGN_IDENTITY="$(security find-identity -v -p codesigning | awk '/Developer ID Application/{print $2; exit}')"
    [ -z "$SIGN_IDENTITY" ] && { echo "✗ No 'Developer ID Application' identity in keychain"; exit 1; }
fi
NOTARY_PROFILE="${NOTARY_PROFILE:-ArkanaNotary}"
ENTITLEMENTS="HDZeroProgrammer.entitlements"
DO_NOTARIZE="${DO_NOTARIZE:-1}"   # set DO_NOTARIZE=0 for a quick local (ad-hoc-ish) build

# Notarization auth. CI (GitHub Actions) passes the ASC API key directly
# (NOTARY_KEY=<.p8 path> + NOTARY_KEY_ID + NOTARY_ISSUER); locally we use the stored
# keychain profile created via `xcrun notarytool store-credentials "ArkanaNotary"`.
if [ -n "${NOTARY_KEY:-}" ]; then
    NOTARY_ARGS=(--key "$NOTARY_KEY" --key-id "$NOTARY_KEY_ID" --issuer "$NOTARY_ISSUER")
else
    NOTARY_ARGS=(--keychain-profile "$NOTARY_PROFILE")
fi

SRC_FLASHROM="$(command -v flashrom || echo /opt/homebrew/sbin/flashrom)"

echo "▶︎ Compiling (release)…"
swift build -c release

BIN_PATH="$(swift build -c release --show-bin-path)/HDZeroProgrammer"
APP_DIR="$APP_NAME.app"

echo "▶︎ Assembling $APP_DIR …"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources/flashrom/libs"

cp "$BIN_PATH" "$APP_DIR/Contents/MacOS/HDZeroProgrammer"
chmod +x "$APP_DIR/Contents/MacOS/HDZeroProgrammer"

# ---- Embed flashrom and bundle every non-system dylib ----------------------
FR_DIR="$APP_DIR/Contents/Resources/flashrom"
echo "▶︎ Embedding flashrom from $SRC_FLASHROM"
cp "$SRC_FLASHROM" "$FR_DIR/flashrom"
chmod +x "$FR_DIR/flashrom"

echo "▶︎ Bundling dynamic libraries (dylibbundler)…"
dylibbundler -of -b \
    -x "$FR_DIR/flashrom" \
    -d "$FR_DIR/libs" \
    -p "@executable_path/libs/" >/dev/null

# Some Homebrew dylibs (e.g. libftdi) already carry an @executable_path/libs/
# LC_RPATH; dylibbundler adds a second identical one, and dyld aborts with
# "duplicate LC_RPATH". Collapse duplicates down to a single entry.
echo "▶︎ De-duplicating LC_RPATH entries…"
for f in "$FR_DIR/flashrom" "$FR_DIR"/libs/*.dylib; do
    while [ "$(otool -l "$f" | grep -c 'LC_RPATH')" -gt 1 ]; do
        install_name_tool -delete_rpath "@executable_path/libs/" "$f" 2>/dev/null || break
    done
done

# ---- Embed esptool (the Radio ELRS path shells out to it, like the official
#      HDZero tool) — a self-contained PyInstaller binary, cached between builds.
ESPTOOL_VER="${ESPTOOL_VER:-5.3.0}"
ESP_DIR="$APP_DIR/Contents/Resources/esptool"
ESP_CACHE="$HOME/.cache/hdzero-build/esptool-$ESPTOOL_VER"
mkdir -p "$ESP_DIR" "$ESP_CACHE"
if [ ! -f "$ESP_CACHE/esptool" ]; then
    echo "▶︎ Downloading esptool $ESPTOOL_VER (arm64)…"
    curl -fsSL "https://github.com/espressif/esptool/releases/download/v${ESPTOOL_VER}/esptool-v${ESPTOOL_VER}-macos-arm64.tar.gz" \
        -o "$ESP_CACHE/esptool.tar.gz"
    tar -xzf "$ESP_CACHE/esptool.tar.gz" -C "$ESP_CACHE"
    cp "$ESP_CACHE/esptool-macos-arm64/esptool" "$ESP_CACHE/esptool"
fi
echo "▶︎ Embedding esptool from cache"
cp "$ESP_CACHE/esptool" "$ESP_DIR/esptool"
chmod +x "$ESP_DIR/esptool"

# ---- Info.plist ------------------------------------------------------------
cat > "$APP_DIR/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>            <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>     <string>$APP_NAME</string>
    <key>CFBundleExecutable</key>      <string>HDZeroProgrammer</string>
    <key>CFBundleIdentifier</key>      <string>$BUNDLE_ID</string>
    <key>CFBundleVersion</key>         <string>$VERSION</string>
    <key>CFBundleShortVersionString</key><string>$VERSION</string>
    <key>CFBundlePackageType</key>     <string>APPL</string>
    <key>CFBundleIconFile</key>        <string>AppIcon</string>
    <key>LSMinimumSystemVersion</key>  <string>13.0</string>
    <key>NSHighResolutionCapable</key> <true/>
    <key>NSPrincipalClass</key>        <string>NSApplication</string>
    <key>LSApplicationCategoryType</key><string>public.app-category.utilities</string>
</dict>
</plist>
PLIST

if [ -f "AppIcon.icns" ]; then
    cp "AppIcon.icns" "$APP_DIR/Contents/Resources/AppIcon.icns"
fi

# ---- Codesign with Developer ID (hardened runtime, inside-out) --------------
echo "▶︎ Codesigning with: $SIGN_IDENTITY"
SIGN_FLAGS=(--force --options runtime --timestamp -s "$SIGN_IDENTITY")

find "$FR_DIR/libs" -name "*.dylib" -print0 | while IFS= read -r -d '' lib; do
    codesign "${SIGN_FLAGS[@]}" "$lib"
done
codesign "${SIGN_FLAGS[@]}" --entitlements "$ENTITLEMENTS" "$FR_DIR/flashrom"
# Re-sign the bundled esptool with our Developer ID + hardened runtime. It MUST get
# `disable-library-validation` (in $ENTITLEMENTS): esptool is a PyInstaller onefile
# that extracts Espressif's Python.framework (a DIFFERENT Team ID) at runtime and
# dlopens it — without this entitlement the team-ID mismatch makes it fail to launch.
codesign "${SIGN_FLAGS[@]}" --entitlements "$ENTITLEMENTS" "$ESP_DIR/esptool"
codesign "${SIGN_FLAGS[@]}" --entitlements "$ENTITLEMENTS" "$APP_DIR/Contents/MacOS/HDZeroProgrammer"
codesign "${SIGN_FLAGS[@]}" --entitlements "$ENTITLEMENTS" "$APP_DIR"

echo "▶︎ Verifying signature…"
codesign --verify --deep --strict --verbose=2 "$APP_DIR"

echo "▶︎ Verifying embedded flashrom runs…"
if "$FR_DIR/flashrom" --version >/dev/null 2>&1; then
    LIBS=$(ls "$FR_DIR/libs" | wc -l | tr -d ' ')
    echo "✓ Embedded flashrom works ($LIBS bundled libraries)"
else
    echo "✗ Embedded flashrom failed to run — check dylibbundler output"
fi

echo "▶︎ Verifying embedded esptool runs…"
if "$ESP_DIR/esptool" version >/dev/null 2>&1; then
    echo "✓ Embedded esptool works"
else
    echo "✗ Embedded esptool failed to run (re-sign may have broken it)"
fi

if [ "$DO_NOTARIZE" != "1" ]; then
    SIZE=$(du -sh "$APP_DIR" | cut -f1)
    echo "✓ Local build (not notarized): $(pwd)/$APP_DIR  ($SIZE)"
    exit 0
fi

# ---- Notarize the .app, then staple ----------------------------------------
echo "▶︎ Submitting to Apple notary service…"
NOTARY_ZIP="$(mktemp -d)/HDZeroProgrammer.zip"
ditto -c -k --keepParent "$APP_DIR" "$NOTARY_ZIP"

if xcrun notarytool submit "$NOTARY_ZIP" "${NOTARY_ARGS[@]}" --wait; then
    echo "▶︎ Stapling ticket…"
    xcrun stapler staple "$APP_DIR"
    xcrun stapler validate "$APP_DIR" && echo "✓ Notarized + stapled"
else
    echo "✗ Notarization failed. Inspect with: xcrun notarytool history ${NOTARY_ARGS[*]}"
    exit 1
fi
rm -f "$NOTARY_ZIP"

# ---- Package .dmg ----------------------------------------------------------
echo "▶︎ Packaging .dmg …"
DMG_NAME="$APP_NAME ${VERSION}.dmg"
STAGE_DIR="$(mktemp -d)/dmg"
mkdir -p "$STAGE_DIR"
cp -R "$APP_DIR" "$STAGE_DIR/"
ln -s /Applications "$STAGE_DIR/Applications"

cat > "$STAGE_DIR/BACA SAYA — README.txt" <<README
HDZero Programmer $VERSION
==========================

1. Seret "$APP_NAME" ke folder Applications. / Drag into Applications.
2. Buka aplikasi (klik dua kali). / Launch normally.

Saat flashing VTX, macOS akan meminta password admin sekali (flashrom butuh
akses USB root). Itu normal. / It asks for your admin password once per flash —
flashrom needs root USB access. Signed & notarized, no xattr workaround needed.

Hardware: programmer CH341A diklip ke chip flash VTX, VTX dinyalakan.
Requirements: macOS 13+.
README

rm -f "$DMG_NAME"
hdiutil create -volname "$APP_NAME" -srcfolder "$STAGE_DIR" -ov -format UDZO "$DMG_NAME" >/dev/null
codesign --force --timestamp -s "$SIGN_IDENTITY" "$DMG_NAME" 2>/dev/null || true

# Notarize + staple the .dmg too — a freshly downloaded dmg gets a quarantine xattr and a
# signed-but-not-notarized container is "rejected" on modern macOS even though the .app inside is fine.
echo "▶︎ Notarizing the .dmg…"
if xcrun notarytool submit "$DMG_NAME" "${NOTARY_ARGS[@]}" --wait; then
    xcrun stapler staple "$DMG_NAME" && echo "✓ DMG notarized + stapled"
else
    echo "✗ DMG notarization failed (the app inside is still notarized; only the container isn't)"
fi

rm -rf "$STAGE_DIR"
echo "✓ Built: $(pwd)/$DMG_NAME"
