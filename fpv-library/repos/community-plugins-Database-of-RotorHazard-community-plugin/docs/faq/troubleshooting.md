---
title: Troubleshooting
description: Common issues and solutions
---

# Troubleshooting

## My plugin isn't showing up in the database

Check the following:

1. **PR merged?** Ensure your pull request was approved and merged
2. **RHFest passing?** All validation checks must pass
3. **Release published?** You need at least one GitHub release
4. **Version mismatch?** Release tag must match `manifest.json` version
5. **Wait time:** Updates happen every 2 hours

## The RHFest validation is failing

Common issues:

- **Folder structure:** Ensure your plugin is in `custom_plugins/DOMAIN/`
- **Manifest keys:** All required fields must be present
- **Domain format:** Use only lowercase letters, numbers, and underscores
- **Version format:** Must follow semantic versioning

Check the [RHFest Action](../docs/rhfest/index.md) documentation for details.

## My plugin causes RotorHazard to crash

Debug steps:

1. Check the RotorHazard logs for error messages
2. Verify all dependencies are installed correctly
3. Test with minimal functionality first
4. Ensure compatibility with the required RotorHazard API version
5. Ask for help in the [Discord community](https://discord.gg/ANKd2pzBKH)

## How do I handle plugin dependencies?

List Python dependencies in the `dependencies` field of `manifest.json`:

```json
"dependencies": [
  "numpy>=1.21",
  "flask==2.2.3"
]
```

RotorHazard will attempt to install these automatically. Use standard PyPI package names and version specifiers. See also the [Getting Started guide](../docs/plugin/index.md#manifestjson).
