#!/bin/bash
# =============================================================================
#  Fix HDZero Converter  —  perbaiki "failed to launch ffmpeg" / "tidak dapat
#  dibuka" di Mac tujuan (app belum ter-notarisasi Apple).
#
#  Cara pakai (di Mac tujuan):
#    1. Buka Terminal  (Spotlight: Cmd+Space → ketik "Terminal")
#    2. Ketik:  bash    lalu spasi
#    3. Seret file ini ke jendela Terminal, tekan Enter.
#       (Menjalankan lewat `bash <file>` melewati blokir Gatekeeper, jadi
#        script ini tetap jalan walau ikut ter-quarantine.)
# =============================================================================
set -uo pipefail

APP_NAME="HDZero Converter"

echo ""
echo "════════════════════════════════════════════════════════"
echo "  Fix HDZero Converter"
echo "════════════════════════════════════════════════════════"
echo ""

# ---- 1. Cari lokasi app -----------------------------------------------------
CANDIDATES=(
    "/Applications/$APP_NAME.app"
    "$HOME/Applications/$APP_NAME.app"
    "$HOME/Downloads/$APP_NAME.app"
    "$HOME/Desktop/$APP_NAME.app"
)

APP=""
for c in "${CANDIDATES[@]}"; do
    if [ -d "$c" ]; then APP="$c"; break; fi
done

# Belum ketemu di lokasi umum? Cari di seluruh folder rumah (maks beberapa detik).
if [ -z "$APP" ]; then
    echo "▶︎ Mencari \"$APP_NAME.app\" di folder rumah…"
    APP="$(find "$HOME" -maxdepth 5 -name "$APP_NAME.app" -type d 2>/dev/null | head -1)"
fi

if [ -z "$APP" ]; then
    echo "✗ Tidak menemukan \"$APP_NAME.app\"."
    echo "  Pastikan kamu sudah menyeret app dari DMG ke folder Applications,"
    echo "  lalu jalankan script ini lagi."
    echo ""
    read -n 1 -s -r -p "Tekan tombol apa saja untuk menutup…"
    echo ""
    exit 1
fi

# Tolak menjalankan langsung dari DMG yang read-only.
case "$APP" in
    /Volumes/*)
        echo "✗ App masih berada di dalam DMG ($APP)."
        echo "  Seret dulu \"$APP_NAME\" ke folder Applications, baru jalankan script ini."
        echo ""
        read -n 1 -s -r -p "Tekan tombol apa saja untuk menutup…"
        echo ""
        exit 1
        ;;
esac

echo "✓ Ditemukan: $APP"
echo ""

# ---- 2. Bersihkan atribut quarantine (rekursif, termasuk ffmpeg) ------------
echo "▶︎ Menghapus karantina Gatekeeper (seluruh isi bundle)…"
xattr -cr "$APP" 2>/dev/null
# Hapus quarantine secara eksplisit juga (jaga-jaga).
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
echo "✓ Karantina dibersihkan."
echo ""

# ---- 3. Re-sign ad-hoc di mesin ini ----------------------------------------
echo "▶︎ Menandatangani ulang (ad-hoc) di Mac ini…"
FF="$APP/Contents/Resources/ffmpeg"
find "$FF/libs" -name "*.dylib" -exec codesign --force -s - {} \; 2>/dev/null || true
codesign --force -s - "$FF/ffmpeg"  2>/dev/null || true
codesign --force -s - "$FF/ffprobe" 2>/dev/null || true
codesign --force --deep -s - "$APP" 2>/dev/null || true
echo "✓ Selesai ditandatangani."
echo ""

# ---- 4. Verifikasi ffmpeg embedded benar-benar bisa jalan -------------------
echo "▶︎ Mengetes ffmpeg bawaan…"
if "$FF/ffmpeg" -hide_banner -version >/dev/null 2>&1; then
    VER="$("$FF/ffmpeg" -hide_banner -version 2>/dev/null | head -1)"
    echo "✓ ffmpeg jalan: $VER"
    echo ""
    echo "════════════════════════════════════════════════════════"
    echo "  BERHASIL ✓  — buka \"$APP_NAME\" seperti biasa,"
    echo "  konversi video sekarang sudah bisa jalan."
    echo "════════════════════════════════════════════════════════"
else
    echo "✗ ffmpeg masih gagal dijalankan. Pesan error mentah:"
    echo "---------------------------------------------------------"
    "$FF/ffmpeg" -hide_banner -version 2>&1 | head -5
    echo "---------------------------------------------------------"
    echo "  Kirim pesan error di atas ke pembuat app untuk dianalisis."
fi

echo ""
read -n 1 -s -r -p "Tekan tombol apa saja untuk menutup…"
echo ""
