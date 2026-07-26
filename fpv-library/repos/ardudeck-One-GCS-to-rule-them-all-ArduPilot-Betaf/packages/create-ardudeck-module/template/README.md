# __NAME__

An ArduDeck module.

## Build

```bash
pnpm install
pnpm build
```

Outputs `dist/main.js`, `dist/renderer.js`, `dist/module.json`.

## Package

```bash
pnpm package
```

Builds and produces `__SLUG__-<version>.zip` ready to upload.

## Publish

Drag the zip into the ArduDeck Hangar admin **Review** tab (http://localhost:3001/admin). The server signs, versions, and stores it. Pick a user and generate a license in the same flow.
