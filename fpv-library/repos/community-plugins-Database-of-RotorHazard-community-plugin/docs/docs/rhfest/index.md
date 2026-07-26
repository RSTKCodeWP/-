---
id: rhfest
title: RHFest Action
description: Automated validation for RotorHazard plugins via GitHub Actions
hide:
  - navigation
---

# RHFest Action

**RHFest** is a GitHub Action that automatically validates RotorHazard plugins to ensure they follow official structure and formatting standards. It checks for required files, verifies the contents of the `manifest.json`, confirms that the plugin folder matches the manifest `domain`, and validates version number formatting.

This helps plugin authors maintain consistent quality and catch problems before release. It is also a mandatory part if you want to add a plugin to the database.

## How it works

Once configured, RHFest runs automatically whenever code is pushed or a pull request is opened. It analyzes your repository, performs all validation checks, and reports the results directly in the GitHub Actions logs. If something is missing or invalid, the workflow will fail with clear feedback so issues can be fixed right away.

## Benefits

Using RHFest ensures your plugin remains compliant with RotorHazard requirements:

- Detects issues automatically during development
- Validates pull requests and main branch updates
- Can run on a daily schedule to verify ongoing compliance
- Reduces manual review effort and improves consistency

## Installation

!!! tip "Start from the official template"
    The RHFest workflow is already included by default in the [plugin template repository](https://github.com/RotorHazard/plugin-template). If you are starting from that template, no further setup is required.

For existing repositories, create a new file at `.github/workflows/rhfest.yaml` and add the following content:

```yaml
name: RHFest

on:
  push:
    branches:
      - main
  pull_request:
  schedule:
    - cron: "0 0 * * *" # Every day at midnight

jobs:
  validation:
    name: Validation
    runs-on: ubuntu-latest
    steps:
      - name: ⤵️ Check out code from GitHub
        uses: actions/checkout@v4.2.2

      - name: 🚀 Run RHFest validation
        uses: docker://ghcr.io/rotorhazard/rhfest-action:latest
```

This configuration runs RHFest automatically on pushes to `main`, on pull requests, and once per day. You can modify the triggers in the `on:` section to fit your preferred workflow.

## Results and reporting

When the workflow completes, you can view the results in the Actions tab of your repository.
A green checkmark means validation succeeded. If validation fails, the logs will include clear error messages with guidance on how to fix each issue.

You can add a validation status badge to your README:

```markdown
![RHFest](https://github.com/your-username/your-plugin/actions/workflows/rhfest.yaml/badge.svg)
```

This badge updates automatically to reflect the latest validation result.

## Learn more

- [RHFest GitHub repository](https://github.com/RotorHazard/rhfest-action)
- [RHFest Docker image](https://github.com/RotorHazard/rhfest-action/pkgs/container/rhfest-action)
- [Plugin tutorial](../plugin/tutorial.md) - Learn how to create a plugin
- [Manifest reference](../plugin/index.md#manifestjson) - Details about the manifest.json file
