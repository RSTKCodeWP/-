# @ardudeck/module-sdk

SDK for building ArduDeck modules.

## Install

From an external repo:

```json
{
  "devDependencies": {
    "@ardudeck/module-sdk": "github:codeforges/ardudeck#master&path:packages/module-sdk"
  }
}
```

Or bootstrap a new module with the generator:

```bash
node packages/create-ardudeck-module/bin/create.mjs my-module
```

## Manifest (`module.json`)

```json
{
  "manifestVersion": 1,
  "slug": "your.vendor.module-name",
  "name": "Your Module",
  "version": "0.1.0",
  "entry": { "main": "main.js", "renderer": "renderer.js" },
  "mountPoints": ["floatingOverlay"],
  "permissions": ["pty"]
}
```

Slug must match `^[a-z][a-z0-9]*(\.[a-z][a-z0-9-]*)+$`. Version must be semver.

## Renderer entry

```tsx
import type { RendererHostApi } from '@ardudeck/module-sdk';

export async function activate(host: RendererHostApi) {
  host.log('info', 'activated');
  host.registerMountPoint('floatingOverlay', () => <MyFloatingComponent host={host} />);
}
```

## Main entry

```ts
import type { MainHostApi } from '@ardudeck/module-sdk';

export async function activate(host: MainHostApi) {
  host.onRendererMessage('doThing', async () => ({ result: 'ok' }));
}
```

## Build with esbuild

```js
import { build } from 'esbuild';
import { ardudeckModulePlugin } from '@ardudeck/module-sdk/esbuild';

await build({
  entryPoints: ['src/renderer/index.tsx'],
  bundle: true,
  platform: 'browser',
  format: 'esm',
  target: 'es2022',
  jsx: 'automatic',
  plugins: [ardudeckModulePlugin()],
  outfile: 'dist/renderer.js',
});
```

The plugin rewrites `react`, `react-dom`, and `react-dom/client` imports to the host's `window.__ardudeckHost.*` globals so your module shares the host's React instance (required for hooks to work).

## Host API

See `src/host-types.ts` for full typings. The renderer host exposes telemetry, connection state, current view, parameters, PTY sessions (if permitted), and a mount-point registration hook.

## Permissions

Declare what your module needs in `module.json`:

- `pty` - Spawn PTY sessions (e.g., for CLI tools like `claude`)
- `filesystem` - Reserved for future use (currently all modules get a scoped data dir)
- `network` - Reserved for future use

Permissions are enforced by the host at runtime.
