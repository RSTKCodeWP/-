#!/bin/bash
# TerraForge Studio - Build Script for Linux/macOS
# Скрипт сборки TerraForge Studio для Linux/macOS

set -e

TARGET="release"
SKIP_FRONTEND=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --debug)
            TARGET="debug"
            shift
            ;;
        --skip-frontend)
            SKIP_FRONTEND=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "🌍 TerraForge Studio - Build Script"
echo "====================================="
echo ""

# Check Node.js
echo "📦 Checking Node.js..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "✅ Node.js version: $NODE_VERSION"
else
    echo "❌ Node.js not found. Please install Node.js 18+"
    exit 1
fi

# Check Rust
echo "🦀 Checking Rust..."
if command -v rustc &> /dev/null; then
    RUST_VERSION=$(rustc --version)
    echo "✅ Rust version: $RUST_VERSION"
else
    echo "❌ Rust not found. Please install Rust from https://rustup.rs"
    exit 1
fi

# Check OS-specific dependencies
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "🐧 Checking Linux dependencies..."
    
    MISSING_DEPS=()
    
    if ! dpkg -l | grep -q libgtk-3-dev; then
        MISSING_DEPS+=("libgtk-3-dev")
    fi
    if ! dpkg -l | grep -q libwebkit2gtk-4.0-dev; then
        MISSING_DEPS+=("libwebkit2gtk-4.0-dev")
    fi
    if ! dpkg -l | grep -q libappindicator3-dev; then
        MISSING_DEPS+=("libappindicator3-dev")
    fi
    
    if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
        echo "⚠️  Missing dependencies: ${MISSING_DEPS[*]}"
        echo "Install with: sudo apt-get install ${MISSING_DEPS[*]}"
        read -p "Install now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo apt-get update
            sudo apt-get install -y "${MISSING_DEPS[@]}"
        else
            exit 1
        fi
    fi
fi

# Build Frontend
if [ "$SKIP_FRONTEND" = false ]; then
    echo ""
    echo "🔨 Building Frontend..."
    
    cd frontend-new
    
    echo "Installing dependencies..."
    npm install
    
    echo "Building frontend..."
    npm run build
    
    echo "✅ Frontend built successfully"
    
    cd ..
else
    echo "⏭️  Skipping frontend build"
fi

# Build Tauri
echo ""
echo "🚀 Building Tauri application..."

cd frontend-new

if [ "$TARGET" = "release" ]; then
    echo "Building RELEASE version..."
    npm run tauri build
else
    echo "Building DEBUG version..."
    npm run tauri build -- --debug
fi

cd ..

echo ""
echo "✅ Build completed successfully!"
echo ""
echo "📦 Output files:"

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "   DEB package: frontend-new/src-tauri/target/release/bundle/deb/"
    echo "   AppImage: frontend-new/src-tauri/target/release/bundle/appimage/"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "   DMG: frontend-new/src-tauri/target/release/bundle/dmg/"
    echo "   App: frontend-new/src-tauri/target/release/bundle/macos/"
fi

echo ""
