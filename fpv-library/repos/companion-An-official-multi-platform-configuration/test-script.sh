#!/bin/bash

# Define the project paths and app bundle location
desktop_project="OpenIPC/OpenIPC_Config.Desktop"
output_dir="./build"
app_bundle="$output_dir/OpenIPC_Config.app"
binary_source="$output_dir/osx-arm64/OpenIPC_Config.Desktop"

# Clean and prepare the output directory
echo "Cleaning previous builds..."
rm -rf "$output_dir"
mkdir -p "$output_dir/osx-arm64"

# Build for macOS
echo "Building $desktop_project for macOS (osx-arm64)..."
dotnet publish "$desktop_project" -c Release -r osx-arm64 --output "$output_dir/osx-arm64" --self-contained -v normal

# Verify that the binary is for macOS
file_type=$(file "$binary_source" | grep -o 'Mach-O 64-bit executable arm64')
if [ -z "$file_type" ]; then
    echo "Error: macOS build did not produce a valid macOS executable."
    exit 1
fi
echo "macOS binary built successfully."

# Create the .app bundle structure
echo "Packaging the .app bundle..."
mkdir -p "$app_bundle/Contents/MacOS"
mkdir -p "$app_bundle/Contents/Resources"

# Copy and rename the macOS binary to remove .dll extension
cp "$binary_source" "$app_bundle/Contents/MacOS/OpenIPC_Config"

# Add Info.plist for macOS app metadata
cat > "$app_bundle/Contents/Info.plist" <<EOL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>OpenIPC_Config</string>
    <key>CFBundleDisplayName</key>
    <string>OpenIPC Config</string>
    <key>CFBundleIdentifier</key>
    <string>com.openipc.config</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>OpenIPC_Config</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.12</string>
</dict>
</plist>
EOL

# Set executable permissions
chmod +x "$app_bundle/Contents/MacOS/OpenIPC_Config"

echo ".app bundle created at $app_bundle"
