---
title: Plugin Development
description: Questions about developing RotorHazard plugins
---

# Plugin Development

## How do I create my own plugin?

Check out our [Getting Started guide](../docs/plugin/index.md) and use the [plugin template](https://github.com/RotorHazard/plugin-template) as a starting point. The template includes:

- Proper folder structure
- Example `manifest.json`
- GitHub Actions for validation
- README template

We also have a comprehensive [step-by-step tutorial](../docs/plugin/tutorial.md) that walks you through creating your first plugin.

## What programming language are plugins written in?

RotorHazard plugins are written in **Python**, as RotorHazard itself is a [Python](https://www.python.org/) application.

## Do I need to know Python to create a plugin?

Basic Python knowledge is required. However, the plugin template and [RotorHazard API documentation](https://github.com/RotorHazard/RotorHazard/blob/main/doc/RHAPI.md) provide good examples to get started.

## What is the manifest.json file?

The `manifest.json` file contains metadata about your plugin:

- Plugin name and description
- Version number
- Minimal required RotorHazard API version
- Dependencies (optional)
- Author information
- License

See the [Getting Started guide](../docs/plugin/index.md#manifestjson) for detailed information about required fields.

## What is semantic versioning (SemVer)?

Semantic Versioning follows the format `MAJOR.MINOR.PATCH` (e.g., `1.2.3`):

- **MAJOR**: Breaking changes that require user action
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

You can also add pre-release identifiers like `-beta` or `-rc.1`.

Learn more at [semver.org](https://semver.org/).
