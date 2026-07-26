---
title: Publishing & Updates
description: Questions about publishing and updating plugins
---

# Publishing & Updates

## How do I add my plugin to the community database?

Follow these steps:

1. Ensure your plugin meets all [requirements](../docs/plugin/index.md#requirements)
2. Add [RHFest validation](../docs/rhfest/index.md) to your repository
3. Publish at least one GitHub release
4. Fork the [community-plugins](https://github.com/RotorHazard/community-plugins) repository
5. Add your repository to `plugins.json` and `categories.json` using the **exact repository name** (including correct capitalization, e.g., `"JohnDoe/my-plugin"`)
6. Submit a pull request

Detailed instructions are in the [Include repository guide](../docs/plugin/include.md).

## How long does it take for my plugin to appear in the database?

After your pull request is merged, the metadata is updated automatically every 2 hours. Your plugin will be available to users after the next update cycle.

## How do I update my plugin?

1. Make your code changes
2. Update the `version` field in `manifest.json`
3. Create a new GitHub release with a tag matching the version
4. Users will automatically see the update in RotorHazard

## Do I need to create a PR every time I update my plugin?

No! Once your plugin is in the database, updates are detected automatically through GitHub releases. You only need to:

- Update the version in `manifest.json`
- Create a new GitHub release

## My release tag doesn't match the manifest version. What happens?

If there's a mismatch, your plugin will be temporarily skipped during metadata updates and users won't see your plugin anymore. Make sure the SemVer part of your release tag matches the `version` field in `manifest.json`.

## Why is my plugin showing as "uncategorized" on the website?

This can happen if the repository name in `categories.json` doesn't match the exact casing of your GitHub repository. For example, if your GitHub repository is `JohnDoe/my-plugin` but `categories.json` has `johndoe/my-plugin`, the category won't be matched properly.

To fix this:

1. Check your exact repository name on GitHub (including capitalization)
2. Update both `plugins.json` and `categories.json` to use the exact name
3. Submit a pull request with the correction

The CI checks now validate this automatically for new plugins to prevent this issue.
