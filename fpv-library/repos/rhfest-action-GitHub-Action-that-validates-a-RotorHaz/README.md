# RHFest Action

A reusable GitHub Action that validates `manifest.json` files for RotorHazard plugins. It checks for missing fields, invalid formats, and unsupported values, and logs validation errors directly in GitHub Actions logs using **GitHub-friendly annotations**.

## 🛠️ Features

- ✅ Schema validation for keys in `manifest.json`
- ✅ Plugin repository structure validation
  - 📁 Presence of `custom_plugins` folder
  - 📁 Presence of single plugin domain folder
  - 📄 Presence of `manifest.json` file
  - 🔁 Plugin domain folder matches the `domain` in `manifest.json`
- 🚨 GitHub Action annotations for validation errors
- ⚠️ Warnings for missing required fields
- 🐳 Docker image for local testing (manual or pre-commit)
- 📋 Validates for example:
  - **domain** format (e.g., lowercase letters, numbers, underscores)
  - **version** [semver](https://semver.org) format (e.g., `X.Y.Z`)
  - **dependencies** using the [version specifiers](https://packaging.python.org/en/latest/specifications/version-specifiers/#id5) format (e.g., `==X.Y.Z`)
  - **documentation_uri** URL format

## 🚀 How to Use

Create a file `.github/workflows/validate.yml` in your plugin repository with the following content:

```yaml
name: Validate Plugin Manifest

on:
  push:
  pull_request:

jobs:
  validate:
    name: Run RHFest validation
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Run RHFest validation
        uses: docker://ghcr.io/rotorhazard/rhfest-action:v3
```

## Test plugin locally

_Needs Docker installed_

RHFest is available as a [Docker image](https://github.com/RotorHazard/rhfest-action/pkgs/container/rhfest-action), which makes it easy to test locally without installing any dependencies. To test your RotorHazard plugin repository, you can use the following command:

```bash
docker run --rm -v "$(pwd)":/repo ghcr.io/rotorhazard/rhfest-action:latest
```

## Development

How to setup the development environment.

### Prerequisites

You need the following tools to get started:

- [uv] - A python virtual environment/package manager
- [Python] 3.13 - The programming language

### Installation

1. Clone the repository
2. Install all dependencies with UV. This will create a virtual environment and install all dependencies

```bash
uv sync
```

3. Setup the pre-commit check, you must run this inside the virtual environment

```bash
uv run pre-commit install
```

4. Run the application

```bash
uv run python rhfest/core.py
```

### Run pre-commit checks

As this repository uses the [pre-commit][pre-commit] framework, all changes
are linted and tested with each commit. You can run all checks and tests
manually, using the following command:

```bash
uv run pre-commit run --all-files
```

To manual run only on the staged files, use the following command:

```bash
uv run pre-commit run
```

### Test Docker image

To build the Docker image locally, run the following command:

```bash
docker build -t rhfest-action:latest .
```

To run the Docker image, use the following command:

```bash
docker run --rm -v "$(pwd)":/repo rhfest-action:latest
```

## 🌟 Credits

This project was inspired by:

- Manifest validation in [HACS](https://hacs.xyz/)
- Manifest validation (Hassfest) in [Home Assistant](https://www.home-assistant.io/)

## License

Distributed under the **MIT** License. See [`LICENSE`](LICENSE) for more information.

<!-- LINK -->
[uv]: https://docs.astral.sh/uv/
[Python]: https://www.python.org/
[pre-commit]: https://pre-commit.com/
