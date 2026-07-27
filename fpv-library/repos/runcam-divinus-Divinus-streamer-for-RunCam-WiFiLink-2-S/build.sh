#!/bin/bash
# build.sh — Cross-compile Divinus for RunCam WiFiLink 2 (SSC338Q / star6e)
# Usage: ./build.sh [all|clean|patch|build]
set -e

DIVINUS_REPO="https://github.com/OpenIPC/divinus.git"
DIVINUS_DIR="./divinus-src"
PATCH_DIR="./patches"
OUTPUT_DIR="./sdcard"
TARGET="star6e"

clone() {
    if [ ! -d "$DIVINUS_DIR" ]; then
        echo "[build] Cloning Divinus..."
        git clone "$DIVINUS_REPO" "$DIVINUS_DIR"
    else
        echo "[build] Divinus source already exists, pulling latest..."
        cd "$DIVINUS_DIR" && git pull && cd ..
    fi
}

patch_sources() {
    echo "[build] Applying patches..."
    for p in "$PATCH_DIR"/*.patch; do
        if [ -f "$p" ]; then
            echo "  Applying $(basename $p)..."
            cd "$DIVINUS_DIR"
            git apply "../$p" 2>/dev/null || echo "  (already applied or conflict)"
            cd ..
        fi
    done
}

build() {
    echo "[build] Building for target: $TARGET"
    cd "$DIVINUS_DIR"
    chmod +x build.sh
    bash build.sh "$TARGET"
    cd ..

    echo "[build] Copying binary to $OUTPUT_DIR/"
    cp "$DIVINUS_DIR/divinus" "$OUTPUT_DIR/divinus"
    chmod +x "$OUTPUT_DIR/divinus"
    echo "[build] Done! Binary at $OUTPUT_DIR/divinus"
}

clean() {
    echo "[build] Cleaning..."
    rm -rf "$DIVINUS_DIR"
    rm -f "$OUTPUT_DIR/divinus"
    echo "[build] Clean complete."
}

case "${1:-all}" in
    clone) clone ;;
    patch) clone && patch_sources ;;
    build) build ;;
    clean) clean ;;
    all)   clone && patch_sources && build ;;
    *)     echo "Usage: $0 [all|clone|patch|build|clean]" ;;
 esac
