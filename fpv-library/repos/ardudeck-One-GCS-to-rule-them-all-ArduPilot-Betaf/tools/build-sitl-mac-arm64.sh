#!/usr/bin/env bash
# Build ArduPilot SITL binaries for macOS ARM64 and (optionally) publish them
# to this repo's GitHub Releases. Runs on Apple Silicon Macs only — that's the
# entire point: GHA-hosted macOS runners hang on the Lua-bindings step (see
# git history of .github/workflows/build-sitl.yml), so we build locally on the
# same hardware our users run on.
#
# What ArduDeck consumes:
#   GitHub Releases tag:  sitl-v{X.Y.Z}
#   Asset name format:    {arducopter|arduplane|ardurover|ardusub}-macos-arm64
#   Pinned in code:       apps/desktop/src/main/sitl/ardupilot-sitl-downloader.ts
#                         (constant SITL_RELEASE_TAG)
#
# Typical use after a new ArduPilot stable release lands:
#
#   ./tools/build-sitl-mac-arm64.sh --ref Copter-4.5.8
#       └─ builds locally into ./build-sitl/{ref}/output/, no upload
#
#   ./tools/build-sitl-mac-arm64.sh --ref Copter-4.5.8 --publish
#       └─ builds + creates/updates `sitl-v4.5.8` GH release with the four
#          binaries attached. Asks for confirmation before publishing.
#
# After publish, bump SITL_RELEASE_TAG in the downloader to the new tag.

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────

REF=""
PUBLISH=0
KEEP_CHECKOUT=0
WORKDIR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/build-sitl"

# ── Parse args ───────────────────────────────────────────────────────────────

usage() {
  cat <<EOF
Usage: $(basename "$0") --ref <ardupilot-ref> [--publish] [--keep-checkout]

  --ref <ref>          ArduPilot tag/branch/SHA to build. e.g. Copter-4.5.8
                       (the version watcher issue tells you which to use).
  --publish            Upload to GitHub Releases as sitl-v{version} after build.
                       Asks confirmation before creating the release.
  --keep-checkout      Don't delete the ArduPilot clone after build (handy for
                       debugging). Default: cleaned up.
  -h | --help          This message.

Examples:
  $0 --ref Copter-4.5.8
  $0 --ref Copter-4.5.8 --publish
  $0 --ref master --publish              # bleeding-edge build
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref)            REF="$2"; shift 2 ;;
    --publish)        PUBLISH=1; shift ;;
    --keep-checkout)  KEEP_CHECKOUT=1; shift ;;
    -h|--help)        usage; exit 0 ;;
    *)                echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$REF" ]]; then
  echo "ERROR: --ref is required" >&2
  usage
  exit 1
fi

# ── Sanity checks ────────────────────────────────────────────────────────────

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ERROR: this script only runs on macOS (you're on $(uname -s))" >&2
  exit 1
fi
if [[ "$(uname -m)" != "arm64" ]]; then
  echo "ERROR: this script targets Apple Silicon (arm64), found $(uname -m)" >&2
  exit 1
fi

for cmd in git python3 gh; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not on PATH: $cmd" >&2
    [[ "$cmd" == "gh" ]] && echo "  -> install: brew install gh && gh auth login" >&2
    exit 1
  fi
done

# ── Derive version + paths ───────────────────────────────────────────────────

# Strip vehicle prefix if the user passed e.g. "Copter-4.5.8". Leave generic
# refs (master, branch names) alone but suffix with date so each rebuild gets
# a unique release tag.
if [[ "$REF" =~ ^[A-Za-z]+-([0-9]+\.[0-9]+.*) ]]; then
  VERSION="${BASH_REMATCH[1]}"
else
  VERSION="${REF}-$(date +%Y%m%d)"
fi
RELEASE_TAG="sitl-v${VERSION}"

WORKDIR="${WORKDIR_ROOT}/${REF}"
SRCDIR="${WORKDIR}/ardupilot"
OUTDIR="${WORKDIR}/output"

echo "════════════════════════════════════════════════════════════════"
echo "  ArduPilot ref:  ${REF}"
echo "  Version:        ${VERSION}"
echo "  Release tag:    ${RELEASE_TAG}"
echo "  Build dir:      ${WORKDIR}"
echo "  Publish:        $([[ $PUBLISH -eq 1 ]] && echo yes || echo no)"
echo "════════════════════════════════════════════════════════════════"

# ── Clone (shallow, with submodules) ────────────────────────────────────────

mkdir -p "$WORKDIR"
if [[ -d "$SRCDIR/.git" ]]; then
  echo "▶ Updating existing checkout at $SRCDIR"
  git -C "$SRCDIR" fetch --depth 1 origin "$REF"
  git -C "$SRCDIR" checkout FETCH_HEAD
  git -C "$SRCDIR" submodule update --init --recursive --depth 1
else
  echo "▶ Cloning ArduPilot @ $REF (shallow + shallow submodules)"
  git clone \
    --depth 1 \
    --branch "$REF" \
    --recurse-submodules \
    --shallow-submodules \
    https://github.com/ArduPilot/ardupilot.git \
    "$SRCDIR"
fi

# ── Configure + build ────────────────────────────────────────────────────────

cd "$SRCDIR"

echo "▶ waf configure --board sitl"
./waf configure --board sitl

echo "▶ waf copter plane rover sub"
./waf copter plane rover sub

# ── Sanity-check each binary launches ────────────────────────────────────────
# A binary that crashes on macOS ARM64 with SIGILL on first run is exactly the
# class of bug we're trying to avoid uploading. `--help` exercises the same
# init path that fails when broken, but exits cleanly.

mkdir -p "$OUTDIR"
declare -a BINARIES=(arducopter arduplane ardurover ardusub)

for bin in "${BINARIES[@]}"; do
  src="$SRCDIR/build/sitl/bin/$bin"
  if [[ ! -x "$src" ]]; then
    echo "ERROR: expected binary missing: $src" >&2
    exit 1
  fi
  echo "▶ Smoke-test $bin --help"
  if ! "$src" --help >/dev/null 2>&1; then
    echo "ERROR: $bin --help exited non-zero. Don't ship this build." >&2
    exit 1
  fi
  cp "$src" "$OUTDIR/${bin}-macos-arm64"
done

echo ""
echo "✅ Built and smoke-tested:"
ls -lh "$OUTDIR"

# ── Publish (optional) ───────────────────────────────────────────────────────

if [[ $PUBLISH -eq 1 ]]; then
  echo ""
  echo "▶ Publishing to GitHub Release: $RELEASE_TAG"
  read -rp "  Confirm? [y/N] " ans
  if [[ ! "$ans" =~ ^[Yy]$ ]]; then
    echo "  Aborted publish. Binaries remain in $OUTDIR"
    exit 0
  fi

  # Create release if it doesn't exist; --clobber the assets so re-runs work.
  if gh release view "$RELEASE_TAG" >/dev/null 2>&1; then
    echo "  Release exists — uploading assets with --clobber"
  else
    gh release create "$RELEASE_TAG" \
      --title "ArduPilot SITL $VERSION" \
      --notes "macOS ARM64 SITL binaries built locally from ArduPilot @ $REF." \
      --prerelease
  fi

  for bin in "${BINARIES[@]}"; do
    gh release upload "$RELEASE_TAG" "$OUTDIR/${bin}-macos-arm64" --clobber
  done

  echo ""
  echo "✅ Published $RELEASE_TAG"
  echo ""
  echo "Next: bump SITL_RELEASE_TAG in apps/desktop/src/main/sitl/ardupilot-sitl-downloader.ts"
  echo "  to '$RELEASE_TAG'  (current value lives near the top of the file)"
fi

# ── Cleanup ──────────────────────────────────────────────────────────────────

if [[ $KEEP_CHECKOUT -eq 0 ]]; then
  echo "▶ Cleaning up ArduPilot checkout (re-run with --keep-checkout to preserve)"
  rm -rf "$SRCDIR"
fi

echo "Done."
