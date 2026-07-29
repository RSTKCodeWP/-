/**
 * Build the Rust procedural frame generator (crates/ardudeck-frame, `frame_blueprint`
 * bin) and stage a runnable binary at apps/desktop/frame-bin/ so electron-builder
 * bundles it (extraResources: frame-bin -> Resources/frame-blueprint) and the 3D Sim
 * World can render procedural airframes in packaged builds, not just the dev tree.
 *
 * Runs from the `package` script, so the GH release build (which installs Rust before
 * `pnpm package`) always compiles it from source. Requires cargo on PATH.
 *
 * On macOS, copying a freshly built Mach-O invalidates its ad-hoc code signature, so
 * the kernel SIGKILLs it ("Killed: 9") on first run. We ad-hoc re-sign after copying
 * so it is runnable, and so electron-builder can re-sign it cleanly during notarization.
 *
 * We stage ATOMICALLY: write + sign a temp file, then rename it over the target, so a
 * generator process that happens to be executing the old binary is never killed.
 */
import { execFileSync } from 'node:child_process';
import { mkdirSync, copyFileSync, chmodSync, renameSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const desktopRoot = path.resolve(here, '..');
const repoRoot = path.resolve(desktopRoot, '..', '..');
const manifest = path.join(repoRoot, 'crates', 'ardudeck-frame', 'Cargo.toml');
const exe = process.platform === 'win32' ? 'frame_blueprint.exe' : 'frame_blueprint';
const builtPath = path.join(repoRoot, 'crates', 'ardudeck-frame', 'target', 'release', exe);
const binDir = path.join(desktopRoot, 'frame-bin');
const outPath = path.join(binDir, exe);

console.log('[stage-frame] cargo build --release --bin frame_blueprint ...');
execFileSync('cargo', ['build', '--release', '--bin', 'frame_blueprint', '--manifest-path', manifest], { stdio: 'inherit' });

mkdirSync(binDir, { recursive: true });
const tmpPath = `${outPath}.staging-${process.pid}`;
try {
  copyFileSync(builtPath, tmpPath);
  if (process.platform !== 'win32') chmodSync(tmpPath, 0o755);
  if (process.platform === 'darwin') {
    execFileSync('codesign', ['--force', '--sign', '-', tmpPath], { stdio: 'inherit' });
    console.log('[stage-frame] ad-hoc code-signed for macOS.');
  }
  renameSync(tmpPath, outPath); // atomic: a live generator keeps its old inode
} catch (err) {
  try {
    rmSync(tmpPath, { force: true });
  } catch {
    /* best-effort cleanup */
  }
  throw err;
}

console.log(`[stage-frame] staged ${path.relative(desktopRoot, outPath)}`);
