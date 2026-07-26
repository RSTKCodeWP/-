# create-ardudeck-module

Scaffolds a new ArduDeck module project.

## Usage

From a clone of this repo:

```bash
node packages/create-ardudeck-module/bin/create.mjs ../my-module
```

Prompts for slug, name, version, and whether PTY access is needed, then copies the template and substitutes tokens.

## Template

The generated project:

- Uses `@ardudeck/module-sdk` (pulled via git subdirectory dep)
- Builds with esbuild using the host-externals plugin
- Includes a minimal floating-overlay component

See `packages/module-sdk/README.md` for module authoring documentation.
