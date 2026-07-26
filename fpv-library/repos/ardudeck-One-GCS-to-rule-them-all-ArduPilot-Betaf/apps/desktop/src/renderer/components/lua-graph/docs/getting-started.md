# Getting Started

The Lua Graph Editor is a visual scripting environment for ArduPilot. Instead of writing Lua code by hand, you connect nodes in a data-flow graph. The editor compiles your graph into a valid ArduPilot Lua script that you can upload to your flight controller's SD card.

## How It Works

1. **Add nodes** from the palette on the left by clicking them
2. **Connect ports** by dragging from an output port to an input port
3. **Configure properties** by selecting a node and editing its properties in the inspector panel on the right
4. **Export Lua** to compile the graph into a `.lua` file

## The Interface

| Area | Purpose |
| --- | --- |
| Toolbar | File operations, undo/redo, export, templates, docs |
| Node Palette | All available nodes grouped by category |
| Canvas | The graph editor where you arrange and connect nodes |
| Inspector | Properties and details for the selected node |
| Lua Preview | Live preview of the compiled Lua output |

## Toolbar Actions

- **New** - Create a blank graph
- **Open** - Load a `.adgraph` file
- **Save** - Save to a `.adgraph` file
- **Templates** - Load a pre-built example graph
- **Export Lua** - Compile and save a `.lua` file
- **Undo / Redo** - Standard undo/redo for all graph changes

## Your First Script

1. Click **Battery** in the Sensors category to add a battery node
2. Click **Compare** in Logic to add a comparison node
3. Connect **Voltage** output to **A** input
4. Add a **Constant** node, set its value to `11.1`
5. Connect the constant's **Value** output to **B** input
6. Set the Compare operator to `<` (less than)
7. Add a **Send GCS Text** node in Actions
8. Connect the Compare **Result** to the GCS text **Trigger**
9. Click **Export Lua** to generate your script

> This script sends a GCS message whenever battery voltage drops below 11.1V.

## Saving & Loading

Graphs are saved as `.adgraph` JSON files. These contain the full node layout, connections, properties, and viewport position. You can share `.adgraph` files with other ArduDeck users.

The **Export Lua** button compiles the graph and saves a standard `.lua` file that runs on ArduPilot. Copy the `.lua` file to your flight controller's `scripts/` directory on the SD card.
