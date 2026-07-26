---
id: start
title: Getting Started
description: "How to get started with the community plugins"
---

RotorHazard encouraged community-driven plugin development, making it easy to extend the platform with new features. By adding your plugin to the community plugins database, it becomes available to all users and can be easily installed through the UI.

## Requirements

For your repository to be added, several criteria need to be met. This guide will help you prepare your repository and add it to the community plugins database.

### General requirements

1. The repository must be public.
2. The source code of the plugin must be available in the repository.
3. A plugin is always free to use for all types of events.
4. Add [RHFest](https://github.com/RotorHazard/rhfest-action) validation action to your repository and make sure it passes.
5. Publish at least 1 [release](#github-releases), this is required for the CI checks.

!!! info "Clarification on point 2"
    The source code of the plugin must be available and not compiled in a way that prevents users from viewing the code. This is to ensure transparency and allow users to review the code for security and functionality. However, in specific cases limited exceptions may be made on an individually-reviewed basis.

    If you have a valid reason to keep part of the code private, please contact us to discuss your situation. We will evaluate your request and determine if an exception can be granted.

### Repository structure

The plugin repository must follow a specific structure to be valid.

- The plugin code must have a `manifest.json` file.
- All files required for the plugin to run must be located inside the directory: `ROOT_OF_REPO/custom_plugins/PLUGIN_DOMAIN/`.
- There must only be one plugin per repository, i.e. there can only be one subdirectory to: `ROOT_OF_REPO/custom_plugins/`.

!!! note "RHFest validation"

    [RHFest](https://github.com/RotorHazard/rhfest-action) will take care of most of the validation checks for you. Make sure to add it to your repository and ensure it passes before submitting your plugin.

#### OK example:

```
custom_plugins/domain/__init__.py
custom_plugins/domain/manifest.json
README.md
```

#### Not OK example (1):

```
domain/__init__.py
domain/manifest.json
README.md
```

#### Not OK example (2):

```
__init__.py
manifest.json
README.md
```

### Manifest.json

In your plugin directory, you must have a `manifest.json` file that contains at least the required keys from the table below. See also the validation examples for specific fields.

| Key                      |  Type     | Required | Description                                                            |
| ------------------------ | :-------: | :------: | :--------------------------------------------------------------------- |
| `domain`                 | string    | Yes      | Unique identifier for the plugin                                       |
| `name`                   | string    | Yes      | Name of the plugin                                                     |
| `description`            | string    | Yes      | Short description of the plugin                                        |
| `required_rhapi_version` | string    | Yes      | The minimum version of the RotorHazard API that the plugin requires    |
| `version`                | string    | Yes      | The version of the plugin (e.g., `1.2.3`, `1.2.3-beta`)                |
| `documentation_uri`      | string    | No       | URL to the documentation                                               |
| `dependencies`           | list[str] | No       | List of additional PyPI dependencies required for this plugin          |
| `zip_filename`           | string    | No       | The filename of the ZIP file containing the plugin code (e.g., `plugin.zip`) |
| `license`                | string    | No       | License under which the plugin is distributed (e.g., `MIT`, `GPL-3.0`) |
| `license_uri`            | string    | No       | URL to the license file                                                |


!!! note "Validation examples for specific fields"

    - **`domain`** must be a unique identifier for the plugin, using only lowercase letters, numbers, and underscores.
        - ✅ Example: `myplugin`, `my_plugin`
        - ❌ Invalid: `MyPlugin`, `my-plugin`, `my_plugin!`
    - **`version`** must follow [Semantic Versioning (SemVer)](https://semver.org/), including:
        - **Basic format:** `major.minor.patch`
            - ✅ Example: `1.2.3`
        - **Pre-release identifiers (optional):** `-alpha`, `-beta`, `-rc`
            - ✅ Example: `1.2.3-beta`, `1.2.3-beta.1`, `1.2.3-rc.2`
    - **`dependencies`** must be valid PyPI package names and can include optional version constraints:
        - **Basic format:**
            - ✅ Example: `package`
        - **Version constraints (optional):**
            - ✅ Examples:
                - Exact version: `flask==2.2.3`
                - Minimum version: `numpy>=1.21`
                - Compatible release: `pandas~=1.3.0`
                - Version exclusion: `scipy!=1.5.2`
        - **Git repositories (optional):**
            - ✅ Example: `git+https://github.com/owner/repo.git`
        - ❌ Invalid: `package_name`, `mypackage!!`, `package==`

### GitHub releases

RotorHazard relies on versioned releases to check for updates and ensure users can install the latest (stable or pre-release) available version.

- Bump the `version` field in `manifest.json` to the upcoming version.
- Use [GitHub Releases][github-releases] to create a release.
- The SemVer part of the release tag must match the `version` field in `manifest.json`.
- You can also add a ZIP file with plugin code to the release assets (optional).
    - If the ZIP asset is named `{plugin_domain}.zip`, you do not need to set `zip_filename`.
    - Otherwise, set `zip_filename` to the exact filename of the ZIP asset that RotorHazard should install from the GitHub release.
    - If your release contains other ZIP assets that are unrelated to plugin installation, you do not need to add `zip_filename` for those files.

By following this approach, users will automatically be noticed when a new version of your plugin is available for installation.

!!! note "Mismatch between release tag and version"

    Please note that if there is a mismatch between the release tag (SemVer part) and the `version` field in `manifest.json`, the plugin will be temporarily skipped in the metadata upload until it is fixed.

    So don't forget to update the `version` field in `manifest.json` before publishing a new release 😉

### Template example

There is a dedicated [template plugin](https://github.com/RotorHazard/plugin-template) repository that demonstrates the structure of a community RotorHazard plugin. You can use it as a reference or fork it as a GitHub template to quickly start developing your own plugin.

<!-- LINKS -->
[github-releases]: https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository
