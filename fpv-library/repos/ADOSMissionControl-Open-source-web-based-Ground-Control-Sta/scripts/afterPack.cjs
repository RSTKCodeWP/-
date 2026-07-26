const path = require('path');
const fs = require('fs');

module.exports = async function afterPack(context) {
  const { appOutDir, electronPlatformName, packager } = context;

  // Determine Resources path per platform
  let resourcesDir;
  if (electronPlatformName === 'darwin') {
    const productName = packager.appInfo.productFilename;
    resourcesDir = path.join(appOutDir, `${productName}.app`, 'Contents', 'Resources');
  } else {
    resourcesDir = path.join(appOutDir, 'resources');
  }

  const source = path.join(__dirname, '..', '.next', 'standalone', 'node_modules');
  const target = path.join(resourcesDir, 'standalone', 'node_modules');

  console.log(`[afterPack] Copying standalone node_modules → ${target}`);
  fs.cpSync(source, target, { recursive: true });
  console.log(`[afterPack] Done (${electronPlatformName} ${context.arch})`);
};
