---
id: tutorial
title: Build Your First Plugin
description: Step-by-step guide to creating your first RotorHazard plugin
---

# Plugin Development Tutorial

This tutorial will guide you through creating a simple RotorHazard plugin from scratch. We'll build a "Race Counter" plugin that displays the total number of races completed.

## Prerequisites

Before starting, make sure you have:

- Basic [Python](https://www.python.org/) knowledge
- A GitHub account
- Git installed on your computer
- A RotorHazard instance for testing

## Step 1: Create Your Repository

1. Go to the [plugin template repository](https://github.com/RotorHazard/plugin-template)
2. Click **"Use this template"** → **"Create a new repository"**
3. Name your repository (e.g., `rh-race-counter`)
4. Set it to **Public**
5. Click **"Create repository"**

## Step 2: Clone Your Repository

```bash
git clone https://github.com/YOUR_USERNAME/rh-race-counter.git
cd rh-race-counter
```

## Step 3: Set Up the Plugin Structure

The template provides a basic structure with a folder named `rh_template`. First, rename this folder to match your plugin domain:

```bash
cd custom_plugins
mv rh_template race_counter
cd race_counter
```

You should now see:
```
custom_plugins/
└── race_counter/
    ├── __init__.py
    └── manifest.json
```

## Step 4: Update the Manifest

Edit `manifest.json` with your plugin details:

```json
{
  "domain": "race_counter",
  "name": "Race Counter",
  "description": "Displays the total number of races completed",
  "version": "1.0.0",
  "required_rhapi_version": "1.0.0",
  "author": "Your Name",
  "author_uri": "https://github.com/YOUR_USERNAME",
  "documentation_uri": "https://github.com/YOUR_USERNAME/rh-race-counter",
  "license": "MIT",
  "license_uri": "https://github.com/YOUR_USERNAME/rh-race-counter/blob/main/LICENSE"
}
```

!!! important "Domain naming"
    The `domain` field must match your directory name exactly and use only lowercase letters, numbers, and underscores.

## Step 5: Create the Plugin Code

Edit `__init__.py` to implement your plugin:

```python
"""Race Counter Plugin - Displays the total number of races completed."""

from eventmanager import Evt


def initialize(rhapi):
    """Called when the plugin is loaded."""
    # Initialize race counter
    rhapi.db.option_set("race_counter_total", 0)

    # Register event handlers
    rhapi.events.on(Evt.RACE_FINISH, on_race_finish)

    # Add UI panel
    rhapi.ui.register_panel(
        "race_counter",
        "Race Counter",
        "stats",
        order=0,
    )

    # Add UI field to display count
    rhapi.ui.register_quickbutton(
        "race_counter",
        "race_counter_display",
        "Total Races",
        get_race_count,
        [],
    )


def on_race_finish(args):
    """Called when a race finishes - Increments the race counter."""
    rhapi = args["rhapi"]

    # Get current count
    current_count = int(rhapi.db.option("race_counter_total", 0))

    # Increment
    new_count = current_count + 1

    # Save
    rhapi.db.option_set("race_counter_total", new_count)

    # Log
    rhapi.ui.message_notify(f"Race #{new_count} completed!")


def get_race_count(rhapi):
    """Return the current race count."""
    count = rhapi.db.option("race_counter_total", 0)
    return f"{count} races completed"
```

## Step 6: Understanding the Code

Let's break down what each part does:

### The `initialize()` Function

```python
def initialize(rhapi):
    """Called when the plugin is loaded"""
```

This is the entry point of your plugin. It's called when RotorHazard loads your plugin.

### Event Handlers

```python
rhapi.events.on(Evt.RACE_FINISH, on_race_finish)
```

This registers a function to be called when a race finishes. Available events include:

- `Evt.RACE_START` - Race has started
- `Evt.RACE_FINISH` - Race has finished
- `Evt.LAPS_SAVE` - Laps have been saved
- `Evt.LAPS_CLEAR` - Laps have been cleared
- `Evt.DATABASE_INIT` - Database initialized

### Database Options

```python
rhapi.db.option_set("race_counter_total", 0)
count = rhapi.db.option("race_counter_total", 0)
```

Store persistent data that survives restarts.

### UI Elements

```python
rhapi.ui.register_panel('race_counter', 'Race Counter', 'stats')
```

Creates a panel in the RotorHazard interface where your plugin's UI elements will appear.

## Step 7: Test Your Plugin Locally

1. Create a symbolic link to your plugin in the RotorHazard data directory:

    ```bash
    ln -s /full/path/to/your/repo/custom_plugins/race_counter /path/to/rh-data/plugins/race_counter
    ```

    !!! tip "Why use a symbolic link?"
        Using a symbolic link instead of copying allows you to:

        - Edit your plugin files directly in your repository
        - See changes immediately after restarting RotorHazard
        - Keep your development workflow clean with git
        - Avoid syncing issues between copies

    !!! tip "Finding your rh-data folder"
        The `rh-data` folder is typically located outside your RotorHazard installation directory. Common locations:

        - Linux: `~/rh-data/plugins/`
        - Custom installs: Check your RotorHazard configuration for the data directory path

2. Restart RotorHazard to load your plugin:

    ```bash
    cd /path/to/RotorHazard/src/server
    python server.py
    ```

    !!! note "Restart required"
        RotorHazard loads plugins at startup, so you need to restart the server whenever you make changes to your plugin code.

3. Verify your plugin is loaded:

    - Open the RotorHazard web interface in your browser
    - Navigate to **Settings** → **Plugins**
    - Your "Race Counter" plugin should be listed
    - Check that it shows the correct version and description

4. Test the functionality:

    - Go to the race interface
    - Start and complete a test race
    - You should see a notification: "Race #1 completed!"
    - Check the Stats panel for the race counter display
    - Run another race and verify the counter increments to 2

5. Development workflow:

    During development, follow this cycle:

    - Edit your plugin files in the repository
    - Restart RotorHazard (`Ctrl+C` then restart `python server.py`)
    - Test your changes in the web interface
    - Check the server logs for any errors
    - When satisfied, commit your changes with git to GitHub

## Step 8: Verify RHFest Validation

The template repository already includes RHFest validation in `.github/workflows/rhfest.yml`. This automatically validates your plugin structure and manifest.

After you push your changes to GitHub, check that the validation passes:

1. Go to your repository on GitHub
2. Click the **Actions** tab
3. You should see the RHFest workflow running
4. Wait for it to complete and verify it shows a green checkmark

If the validation fails, check the error messages and fix any issues with your `manifest.json` or plugin structure.

## Step 9: Create Your First Release

1. Update `manifest.json` if needed (version should be `1.0.0`)

2. Commit your changes:
   ```bash
   git add .
   git commit -m "Initial release: Race Counter v1.0.0"
   git push
   ```

3. Create a release on GitHub:
   - Go to your repository → **Releases** → **Create a new release**
   - Tag version: `v1.0.0`
   - Release title: `v1.0.0`
   - Click **Generate release notes** to automatically create a description from your commits
   - Click **Publish release**

## Step 10: Add to Community Database

Follow the [Include repository guide](include.md) to submit your plugin to the community database.

## Enhancements

Once you have the basics working, try adding these features:

### Add a Reset Button

```python
def reset_counter(rhapi, args):  # noqa: ARG001
    """Reset the race counter."""
    rhapi.db.option_set("race_counter_total", 0)
    rhapi.ui.message_notify("Race counter reset!")


# In initialize():
rhapi.ui.register_quickbutton(
    "race_counter",
    "race_counter_reset",
    "Reset Counter",
    reset_counter,
    [],
)
```

### Display Statistics

```python
def get_race_stats(rhapi):
    """Calculate race statistics."""
    total_races = int(rhapi.db.option("race_counter_total", 0))

    # Get all saved races from database
    races = rhapi.db.races

    if races:
        avg_pilots = sum(len(race.pilots) for race in races) / len(races)
        return f"{total_races} races, avg {avg_pilots:.1f} pilots per race"

    return f"{total_races} races completed"
```

### Add Configuration Options

```python
from RHUI import UIField, UIFieldType

# In initialize():
rhapi.ui.register_option(
    rhapi.ui.UIField(
        name="race_counter_show_notifications",
        label="Show Notifications",
        field_type=UIFieldType.CHECKBOX,
        value=True,
    ),
    "race_counter",
)

# In on_race_finish():
show_notifications = rhapi.db.option("race_counter_show_notifications", True)
if show_notifications:
    rhapi.ui.message_notify(f"Race #{new_count} completed!")
```

## Common Issues

### Plugin Doesn't Load

- Check that `domain` in `manifest.json` matches the folder name
- Verify `required_rhapi_version` is compatible with your RotorHazard version
- Check RotorHazard logs for error messages

### Events Not Firing

- Ensure you're using the correct event name (e.g., `Evt.RACE_FINISH`, not `RACE_FINISH`)
- Verify the event handler is registered in `initialize()`
- Check that the event you're using exists in your RotorHazard version

### Database Values Not Persisting

- Use `rhapi.db.option_set()` to save values
- Don't use regular Python variables for persistence
- Values are stored as strings, convert when needed

## Next Steps

- Explore the [RotorHazard API documentation](https://github.com/RotorHazard/RotorHazard/blob/main/doc/RHAPI.md)
- Study existing plugins in the [community database](../../database.md)
- Join the [Discord community](https://discord.gg/ANKd2pzBKH) for help and ideas
- Read the [FAQ](../../faq/index.md) for common questions

## Resources

- [RotorHazard API Reference](https://github.com/RotorHazard/RotorHazard/blob/main/doc/RHAPI.md)
- [Plugin Template](https://github.com/RotorHazard/plugin-template)
- [RHFest Validation](../rhfest/index.md)
- [Community Plugins Database](../../database.md)

Happy coding!
