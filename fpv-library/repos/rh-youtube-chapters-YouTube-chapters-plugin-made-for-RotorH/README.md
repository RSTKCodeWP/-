<!-- PROJECT SHIELDS -->
![Project Stage][project-stage-shield]
![Project Maintenance][maintenance-shield]
[![License][license-shield]](LICENSE)

![RHCP Badge][rhcp-shield]
[![RHFest][rhfest-shield]][rhfest-url]

# YouTube Chapters

When you publish a video on YouTube, you have the option to add a [chapters list](https://support.google.com/youtube/answer/9884579) in the description, which divides the video timeline into chapters for easier navigation.

This [RotorHazard](https://github.com/RotorHazard/RotorHazard) plugin will help you to generate a chapters list based on the start time of each heat. Ideal for when you want to publish the VOD of your livestream afterwards and make it easier for viewers to navigate to a specific round / heat of the race.

## Functionality

![alt plugin overview](https://raw.githubusercontent.com/dutchdronesquad/rh-youtube-chapters/main/assets/plugin_overview.png)

- Every time a heat starts it will be logged as a chapter entry.
- Based on the start time, the plugin will generate a list of chapters for YouTube.
- Export a txt file where you can copy/paste the chapters into your YouTube video description.

## Installation

> [!WARNING]
> This plugin is still in development and only works currently with the dev branch of RotorHazard.

### Community Plugins (GUI)

_This method is the easiest way to install the plugin._

The **YouTube Chapters** plugin is available as a [community plugin](https://rotorhazard.github.io/community-plugins/) for RotorHazard. You can install it directly from the RotorHazard web interface.

1. Go to the **Settings** page in RotorHazard.
2. Click on the **Plugins** tab and click on the **Browse Community Plugins (online only)** button.
3. Search for **YouTube Chapters** in the list of available plugins.
4. Click on the **Install** button to install the plugin.
5. After the installation is complete, restart RotorHazard to load the plugin.

### Install script (CLI)

_This method is for more advanced users who are comfortable with the command line._

1. Install the **YouTube Chapters** plugin, by running the following command in your terminal at the device where RotorHazard is installed:
```bash
bash -c "$(curl -fsSL https://short.dutchdronesquad.nl/install-youtube-chapters)"
```

2. You'll be prompted to choose between **stable** or **development**:
    - **stable**: Choose this option if you want to install a stable release.
        - The script will fetch the last 5 stable releases from GitHub.
        - Choose the version you want to install and press enter.
    - **development**: Choose this option if you want to install the latest development version.
        - The script will fetch the main branch from GitHub.
3. If the plugin is already in RotorHazard, you'll be prompted to update it.
    - Choose **y (yes)** to update the plugin.
    - Choose **n (no)** to exit the script.
4. When the installation is finished, restart RotorHazard to load the plugin.

## Getting started

1. Note when you started live streaming (local time).
2. Do the race timing as you are used to, each heat start will be logged automatically.
3. When you are done, fill in the start time and confirm with the `Set Start Time` button.
4. Click on `Export Chapters` to generate a txt file with the chapters.
    - You will see the download link after page refresh under **Exported Chapters List**.
5. Don't forget to reset the logging every time you have a new event.

## Setting up development environment

This Python project relies on [uv] as its dependency manager,
providing comprehensive management and control over project dependencies.

You need the following tools to get started:

- [uv] - A python virtual environment/package manager
- [Python] 3.11 (or higher) - The programming language

### Installation

1. Clone the repository
2. Install all dependencies with UV. This will create a virtual environment and install all dependencies

```bash
uv sync --all-groups
```

### Prek check

As this repository uses the [prek][prek] framework, all changes
are linted and tested with each commit.

To install the prek check, run:

```bash
uv run prek install
```

To run all checks and tests manually, use the following command:

```bash
uv run prek run --all-files
```

To manual run only on the staged files, use the following command:

```bash
uv run prek run
```

## Credits

This plugin has been requested by [Dutch Drone Racing](https://dutchdroneracing.com/) (DDR) and developed by [Dutch Drone Squad](https://dutchdronesquad.nl/) (DDS).

## License

Distributed under the **MIT** License. See [`LICENSE`](LICENSE) for more information.

<!-- LINK -->
[license-shield]: https://img.shields.io/github/license/dutchdronesquad/rh-youtube-chapters.svg
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-yellow.svg
[rhfest-shield]: https://github.com/dutchdronesquad/rh-youtube-chapters/actions/workflows/rhfest.yaml/badge.svg
[rhfest-url]: https://github.com/dutchdronesquad/rh-youtube-chapters/actions/workflows/rhfest.yaml
[rhcp-shield]: https://img.shields.io/badge/RotorHazard-Community_Plugins-orange.svg

[uv]: https://docs.astral.sh/uv/
[Python]: https://www.python.org/
[prek]: https://github.com/j178/prek
