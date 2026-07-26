/**
 * electron-builder afterPack hook that copies the portable Python and git
 * from dependencies/darwin_<arch>/ (fetched by
 * dependencies/download-mac-dependencies.sh) into the macOS app bundle.
 *
 * This cannot be done with extraFiles because the universal ("fat binary")
 * build merges an x64 and an arm64 app with @electron/universal, which
 * requires both apps to contain identical non Mach-O files. The intermediate
 * apps are therefore packed without the arch specific dependencies and the
 * universal app receives both dependency trees after the merge; at runtime
 * main.ts picks the directory matching process.arch.
 */
const fs = require('fs');
const path = require('path');

// builder-util Arch enum values
const ARCH_NAMES = { 0: 'ia32', 1: 'x64', 2: 'armv7l', 3: 'arm64', 4: 'universal' };

exports.default = async function copyMacDependencies(context) {
  const { electronPlatformName, appOutDir, arch, packager } = context;
  if (electronPlatformName !== 'darwin') {
    return;
  }

  // the intermediate x64/arm64 packs of the universal target are built into
  // "<outDir>/mac-universal-<arch>-temp" and must stay identical for the
  // merge; electron-builder emits a dedicated afterPack call for the merged
  // app with arch === universal
  if (/-(x64|arm64)-temp$/.test(appOutDir)) {
    return;
  }

  const archName = ARCH_NAMES[arch];
  if (!archName) {
    throw new Error(`Unknown electron-builder arch value: ${JSON.stringify(arch)}`);
  }
  const archesToBundle = archName === 'universal' ? ['x64', 'arm64'] : [archName];

  const appFile = `${packager.appInfo.productFilename}.app`;
  const bundleDependenciesDir = path.join(
    appOutDir,
    appFile,
    'Contents',
    'dependencies',
  );

  for (const dependencyArch of archesToBundle) {
    const source = path.join(
      packager.projectDir,
      'dependencies',
      `darwin_${dependencyArch}`,
    );
    if (!fs.existsSync(source)) {
      throw new Error(
        `${source} is missing, run ./dependencies/download-mac-dependencies.sh ${dependencyArch} first`,
      );
    }
    const destination = path.join(bundleDependenciesDir, `darwin_${dependencyArch}`);
    fs.rmSync(destination, { recursive: true, force: true });
    fs.mkdirSync(bundleDependenciesDir, { recursive: true });
    fs.cpSync(source, destination, { recursive: true, verbatimSymlinks: true });
    console.log(`  • bundled dependencies/darwin_${dependencyArch} into ${appFile}`);
  }
};
