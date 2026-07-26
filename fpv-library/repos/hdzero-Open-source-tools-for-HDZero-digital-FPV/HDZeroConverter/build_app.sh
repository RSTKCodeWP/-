#!/bin/bash
# Builds HDZeroConverter, embeds a self-contained ffmpeg/ffprobe (with all dylibs),
# packages a macOS .app bundle, then Developer ID-signs + notarizes it so it opens
# cleanly on any Mac with no xattr/quarantine workaround.
set -e
cd "$(dirname "$0")"

APP_NAME="HDZero Converter"
BUNDLE_ID="co.arkana.hdzeroconverter"
VERSION="${VERSION:-1.3}"

# ---- Signing / notarization configuration ----------------------------------
# Override via env if needed, e.g. SIGN_IDENTITY="<SHA-1>" NOTARY_PROFILE="..." ./build_app.sh
# This keychain has TWO "Developer ID Application" certs with the SAME name, so passing the name to
# codesign is ambiguous ("matches ... and ..."). Resolve to the first matching SHA-1 hash instead
# (survives cert rotation — re-reads the keychain each run).
if [ -z "${SIGN_IDENTITY:-}" ]; then
    SIGN_IDENTITY="$(security find-identity -v -p codesigning | awk '/Developer ID Application/{print $2; exit}')"
    [ -z "$SIGN_IDENTITY" ] && { echo "✗ No 'Developer ID Application' identity in keychain"; exit 1; }
fi
NOTARY_PROFILE="${NOTARY_PROFILE:-ArkanaNotary}"
ENTITLEMENTS="HDZeroConverter.entitlements"

# Notarization auth. CI (GitHub Actions) passes the App Store Connect API key directly
# (NOTARY_KEY=<.p8 path> + NOTARY_KEY_ID + NOTARY_ISSUER); locally we fall back to the stored
# keychain profile created once via `xcrun notarytool store-credentials "ArkanaNotary"`.
if [ -n "${NOTARY_KEY:-}" ]; then
    NOTARY_ARGS=(--key "$NOTARY_KEY" --key-id "$NOTARY_KEY_ID" --issuer "$NOTARY_ISSUER")
else
    NOTARY_ARGS=(--keychain-profile "$NOTARY_PROFILE")
fi

SRC_FFMPEG="$(command -v ffmpeg)"
SRC_FFPROBE="$(command -v ffprobe)"

echo "▶︎ Compiling (release)…"
swift build -c release

BIN_PATH="$(swift build -c release --show-bin-path)/HDZeroConverter"
APP_DIR="$APP_NAME.app"

echo "▶︎ Assembling $APP_DIR …"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources/ffmpeg/libs"

cp "$BIN_PATH" "$APP_DIR/Contents/MacOS/HDZeroConverter"
chmod +x "$APP_DIR/Contents/MacOS/HDZeroConverter"

# ---- Embed ffmpeg + ffprobe and bundle every non-system dylib --------------
FF_DIR="$APP_DIR/Contents/Resources/ffmpeg"
echo "▶︎ Embedding ffmpeg from $SRC_FFMPEG"
cp "$SRC_FFMPEG"  "$FF_DIR/ffmpeg"
cp "$SRC_FFPROBE" "$FF_DIR/ffprobe"
chmod +x "$FF_DIR/ffmpeg" "$FF_DIR/ffprobe"

echo "▶︎ Bundling dynamic libraries (dylibbundler)…"
dylibbundler -of -b \
    -x "$FF_DIR/ffmpeg" \
    -x "$FF_DIR/ffprobe" \
    -d "$FF_DIR/libs" \
    -p "@executable_path/libs/" >/dev/null

# ---- Info.plist ------------------------------------------------------------
cat > "$APP_DIR/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>            <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>     <string>$APP_NAME</string>
    <key>CFBundleExecutable</key>      <string>HDZeroConverter</string>
    <key>CFBundleIdentifier</key>      <string>$BUNDLE_ID</string>
    <key>CFBundleVersion</key>         <string>$VERSION</string>
    <key>CFBundleShortVersionString</key><string>$VERSION</string>
    <key>CFBundlePackageType</key>     <string>APPL</string>
    <key>CFBundleIconFile</key>        <string>AppIcon</string>
    <key>LSMinimumSystemVersion</key>  <string>13.0</string>
    <key>NSHighResolutionCapable</key> <true/>
    <key>NSPrincipalClass</key>        <string>NSApplication</string>
    <key>LSApplicationCategoryType</key><string>public.app-category.video</string>
</dict>
</plist>
PLIST

if [ -f "AppIcon.icns" ]; then
    cp "AppIcon.icns" "$APP_DIR/Contents/Resources/AppIcon.icns"
fi

# ---- Codesign with Developer ID (hardened runtime, inside-out) --------------
# Order matters: sign the nested dylibs and helper executables BEFORE the app
# wrapper, otherwise the outer signature is invalidated. --options runtime
# (hardened runtime) and --timestamp (secure timestamp) are mandatory for
# notarization.
echo "▶︎ Codesigning with: $SIGN_IDENTITY"
SIGN_FLAGS=(--force --options runtime --timestamp -s "$SIGN_IDENTITY")

# 1. All bundled dylibs.
find "$FF_DIR/libs" -name "*.dylib" -print0 | while IFS= read -r -d '' lib; do
    codesign "${SIGN_FLAGS[@]}" "$lib"
done

# 2. Helper executables (ffmpeg/ffprobe) — give them the entitlements too so the
#    hardened runtime lets them load our relinked dylibs.
codesign "${SIGN_FLAGS[@]}" --entitlements "$ENTITLEMENTS" "$FF_DIR/ffmpeg"
codesign "${SIGN_FLAGS[@]}" --entitlements "$ENTITLEMENTS" "$FF_DIR/ffprobe"

# 3. The main executable.
codesign "${SIGN_FLAGS[@]}" --entitlements "$ENTITLEMENTS" "$APP_DIR/Contents/MacOS/HDZeroConverter"

# 4. Finally the .app wrapper.
codesign "${SIGN_FLAGS[@]}" --entitlements "$ENTITLEMENTS" "$APP_DIR"

echo "▶︎ Verifying signature…"
codesign --verify --deep --strict --verbose=2 "$APP_DIR"
spctl -a -vvv --type execute "$APP_DIR" 2>&1 | head -3 || true

echo "▶︎ Verifying embedded ffmpeg is self-contained…"
if "$FF_DIR/ffmpeg" -hide_banner -version >/dev/null 2>&1; then
    LIBS=$(ls "$FF_DIR/libs" | wc -l | tr -d ' ')
    echo "✓ Embedded ffmpeg works ($LIBS bundled libraries)"
else
    echo "✗ Embedded ffmpeg failed to run — check dylibbundler output"
fi

# ---- Notarize the .app, then staple the ticket into the bundle -------------
# We notarize a zip of the .app and staple the ticket directly into the bundle,
# so the installed app passes Gatekeeper even offline.
echo "▶︎ Submitting to Apple notary service…"
NOTARY_ZIP="$(mktemp -d)/HDZeroConverter.zip"
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

SIZE=$(du -sh "$APP_DIR" | cut -f1)
echo "✓ Built: $(pwd)/$APP_DIR  ($SIZE)"
echo "  Fully portable + notarized — opens with a normal double-click, no Homebrew/ffmpeg needed."

# ---- Package as a distributable .dmg ---------------------------------------
# The app inside is already signed + notarized + stapled, so no README/xattr
# workaround is needed. Just drag-to-Applications.
echo "▶︎ Packaging .dmg …"
DMG_NAME="$APP_NAME ${VERSION}.dmg"
STAGE_DIR="$(mktemp -d)/dmg"
mkdir -p "$STAGE_DIR"

cp -R "$APP_DIR" "$STAGE_DIR/"
ln -s /Applications "$STAGE_DIR/Applications"

cat > "$STAGE_DIR/BACA SAYA — README.txt" <<README
HDZero Converter $VERSION
==========================

CARA PASANG / HOW TO INSTALL
1. Seret "$APP_NAME" ke folder Applications.
   Drag "$APP_NAME" into the Applications folder.

2. Buka aplikasi seperti biasa (klik dua kali). Selesai.
   Launch the app normally (double-click). Done.

Aplikasi sudah ditandatangani & ter-notarisasi Apple — tidak perlu langkah
xattr/Terminal apa pun. (Signed & notarized — no workaround needed.)

Persyaratan / Requirements: macOS 13 (Ventura) atau lebih baru.
README

rm -f "$DMG_NAME"
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$STAGE_DIR" \
    -ov -format UDZO \
    "$DMG_NAME" >/dev/null

# Sign the dmg with Developer ID so its container is trusted too.
codesign --force --timestamp -s "$SIGN_IDENTITY" "$DMG_NAME" 2>/dev/null || true

# Notarize + staple the .dmg itself as well. The .app inside is already notarized, but a freshly
# DOWNLOADED dmg gets a com.apple.quarantine xattr — on modern macOS a signed-but-not-notarized dmg
# is "rejected: Unnotarized Developer ID" when opened. Notarizing the container fixes that.
echo "▶︎ Notarizing the .dmg…"
if xcrun notarytool submit "$DMG_NAME" "${NOTARY_ARGS[@]}" --wait; then
    xcrun stapler staple "$DMG_NAME" && echo "✓ DMG notarized + stapled"
else
    echo "✗ DMG notarization failed (the app inside is still notarized; only the container isn't)"
fi

rm -rf "$STAGE_DIR"
DMG_SIZE=$(du -sh "$DMG_NAME" | cut -f1)
echo "✓ Built: $(pwd)/$DMG_NAME  ($DMG_SIZE)"
echo "  Share this .dmg — recipients just drag to Applications and double-click."
