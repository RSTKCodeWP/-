/**
 * electron-builder `afterSign` hook: notarize the signed macOS .app with
 * notarytool, RETRYING transient failures.
 *
 * electron-builder's built-in `"notarize": true` makes exactly one notarytool
 * call, so a single flaky TLS/network blip talking to Apple's notary service
 * (e.g. `-1202 "certificate for this server is invalid"` / `-9807`, connection
 * resets, 5xx, timeouts) fails the entire multi-platform release. Apple's notary
 * endpoint is intermittently unreliable; a couple of retries with backoff absorbs
 * essentially all of it. A REAL rejection (bad credentials, an "Invalid" audit
 * result) doesn't match the transient patterns, so it still fails fast.
 *
 * Wired via build.mac.afterSign (with build.mac.notarize set to false so we don't
 * double-notarize). Reads the same APPLE_ID / APPLE_APP_SPECIFIC_PASSWORD /
 * APPLE_TEAM_ID env the built-in path used; absent those (local dev builds) it
 * no-ops so packaging still succeeds unsigned.
 */
const { notarize } = require('@electron/notarize');

const MAX_ATTEMPTS = 4;

/** Network / TLS / service blips that are worth retrying (NOT a real rejection). */
function isTransient(err) {
  const msg = String((err && err.message) || err || '');
  return /-1202|-9807|certificate for this server is invalid|ECONNRESET|ETIMEDOUT|EAI_AGAIN|ENOTFOUND|socket hang up|network|timed out|timeout|Failed with unexpected result|\b(?:429|500|502|503|504)\b/i.test(
    msg,
  );
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

module.exports = async function notarizeHook(context) {
  const { electronPlatformName, appOutDir, packager } = context;
  if (electronPlatformName !== 'darwin') return;

  const { APPLE_ID, APPLE_APP_SPECIFIC_PASSWORD, APPLE_TEAM_ID } = process.env;
  if (!APPLE_ID || !APPLE_APP_SPECIFIC_PASSWORD || !APPLE_TEAM_ID) {
    console.log('[notarize] Apple credentials absent; skipping notarization (unsigned local build).');
    return;
  }

  const appName = packager.appInfo.productFilename;
  const appPath = `${appOutDir}/${appName}.app`;

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    try {
      console.log(`[notarize] attempt ${attempt}/${MAX_ATTEMPTS}: ${appPath}`);
      await notarize({
        tool: 'notarytool',
        appPath,
        appleId: APPLE_ID,
        appleIdPassword: APPLE_APP_SPECIFIC_PASSWORD,
        teamId: APPLE_TEAM_ID,
      });
      console.log('[notarize] success.');
      return;
    } catch (err) {
      if (attempt === MAX_ATTEMPTS || !isTransient(err)) throw err;
      const backoffMs = Math.min(60_000, 5_000 * 2 ** (attempt - 1));
      console.warn(`[notarize] transient failure on attempt ${attempt}: ${(err && err.message) || err}`);
      console.warn(`[notarize] retrying in ${backoffMs / 1000}s ...`);
      await sleep(backoffMs);
    }
  }
};
