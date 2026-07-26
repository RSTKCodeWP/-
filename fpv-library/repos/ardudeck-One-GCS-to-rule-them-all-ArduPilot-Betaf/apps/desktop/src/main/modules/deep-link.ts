/**
 * ardudeck:// deep-link handling.
 *
 * Two actions are handled:
 *   ardudeck://install?slug=<slug>&name=<name>&key=<license-key>
 *     - validate the key's signature offline, then hand to the renderer to
 *       confirm with the user before installing.
 *   ardudeck://open?view=<viewId>
 *     - navigate the renderer to a built-in view (no validation needed; the
 *       renderer rejects unknown/unavailable views).
 *   ardudeck://open?tool=area-editor
 *     - open a standalone tool that lives in its own window (not a renderer
 *       view), e.g. the Area Editor. Handled entirely in main.
 */

import { app, BrowserWindow } from 'electron';
import { verifyLicenseKey } from './license-validator.js';
import { openAreaEditorWindow } from '../area-editor-window.js';
import { IPC_CHANNELS } from '../../shared/ipc-channels.js';

const PROTOCOL = 'ardudeck';

let getWindow: (() => BrowserWindow | null) | null = null;
// A deep link can arrive before the window/renderer is ready (cold start via
// the link). Hold the most recent one and flush it once the renderer loads.
let pending: { channel: string; payload: unknown } | null = null;

/**
 * Register the protocol and OS-level entry points. Call once, before the app
 * is ready. `resolveWindow` returns the main window (may be null early).
 */
export function setupDeepLinks(resolveWindow: () => BrowserWindow | null): void {
  getWindow = resolveWindow;

  // In dev (unpackaged), the OS must launch electron with the app path as an
  // argument for the protocol to resolve to this project.
  if (process.defaultApp && process.argv.length >= 2) {
    app.setAsDefaultProtocolClient(PROTOCOL, process.execPath, [process.argv[1]!]);
  } else {
    app.setAsDefaultProtocolClient(PROTOCOL);
  }

  // macOS delivers the URL via this event (both cold and warm start).
  app.on('open-url', (event, url) => {
    event.preventDefault();
    handleDeepLink(url);
  });

  // Windows/Linux deliver the URL as an argv entry to a second instance.
  app.on('second-instance', (_event, argv) => {
    const win = getWindow?.();
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
    const url = argv.find((a) => a.startsWith(`${PROTOCOL}://`));
    if (url) handleDeepLink(url);
  });
}

/** Handle a deep link present in the launch argv (Windows/Linux cold start). */
export function handleStartupArgs(argv: string[]): void {
  const url = argv.find((a) => a.startsWith(`${PROTOCOL}://`));
  if (url) handleDeepLink(url);
}

/**
 * Route a deep-link URL as if the OS had delivered it. Used in dev (via the
 * ARDUDECK_DEEPLINK env var) to test the handler without OS scheme registration,
 * which is unavailable for an unpackaged macOS build.
 */
export function deliverDeepLinkUrl(url: string): void {
  handleDeepLink(url);
}

/** Flush any deep link captured before the renderer was ready. */
export function flushPendingDeepLink(): void {
  if (pending) {
    const p = pending;
    pending = null;
    deliver(p.channel, p.payload);
  }
}

function handleDeepLink(url: string): void {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    console.warn('[DeepLink] Unparseable URL:', url);
    return;
  }

  switch (parsed.host) {
    case 'install':
      handleInstall(parsed);
      return;
    case 'open':
      handleOpen(parsed);
      return;
    default:
      console.warn('[DeepLink] Unknown action:', parsed.host);
  }
}

function handleInstall(parsed: URL): void {
  const slug = parsed.searchParams.get('slug') ?? '';
  const name = parsed.searchParams.get('name') ?? slug;
  const key = parsed.searchParams.get('key') ?? '';

  if (!slug || !key) {
    console.warn('[DeepLink] Missing slug or key');
    return;
  }

  // Validate the license signature offline before surfacing anything.
  const verification = verifyLicenseKey(key);
  if (!verification.valid) {
    console.warn('[DeepLink] Rejected key:', verification.error);
    return;
  }

  deliver(IPC_CHANNELS.MODULE_DEEP_LINK_INSTALL, { slug, name, key });
}

function handleOpen(parsed: URL): void {
  // Standalone tools open their own window from main, independent of the
  // renderer's view router.
  const tool = parsed.searchParams.get('tool');
  if (tool === 'area-editor') {
    // A cold-start link can arrive before the app is ready; defer until then
    // since opening a window requires it.
    if (app.isReady()) openAreaEditorWindow();
    else app.whenReady().then(() => openAreaEditorWindow());
    return;
  }
  if (tool) {
    console.warn('[DeepLink] open: unknown tool:', tool);
    return;
  }

  const view = parsed.searchParams.get('view') ?? '';
  if (!view) {
    console.warn('[DeepLink] open: missing view or tool');
    return;
  }
  // No validation here - the renderer validates against its known view ids
  // (and capability gating) before navigating.
  deliver(IPC_CHANNELS.NAV_DEEP_LINK_OPEN, { view });
}

function deliver(channel: string, payload: unknown): void {
  const win = getWindow?.();
  if (!win || win.webContents.isLoading()) {
    pending = { channel, payload };
    return;
  }
  if (win.isMinimized()) win.restore();
  win.focus();
  win.webContents.send(channel, payload);
}
