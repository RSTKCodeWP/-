# Tips & Limitations

## Tips

### Use Comment Nodes

Add **Comment** nodes to document sections of your graph. They have no effect on the compiled code but make graphs much easier to understand when you revisit them later.

### Start with Templates

The **Templates** button provides pre-built graphs for common tasks. Load one, study how it works, then modify it for your needs.

### Check the Lua Preview

The Lua Preview panel on the right shows the compiled output in real-time. Use it to verify that your graph compiles correctly before exporting.

### Use Debounce for Alerts

Without debounce, a condition that rapidly toggles between true/false will spam GCS messages every update cycle. Always add a **Debounce** or **Rising Edge** node before action nodes that send messages.

### Name Your Variables

When using **Get Variable** and **Set Variable** nodes, use descriptive names like `lowBatteryTriggered` instead of `x`. The names appear in the generated code and help with debugging.

### Organize Left to Right

Arrange your graph with sensor inputs on the left, logic/math in the middle, and actions on the right. This matches the natural data flow direction and is easiest to read.

## Limitations

### ArduPilot Scripting Constraints

- **Memory limit** - Scripts are limited to approximately 50KB of Lua heap memory
- **Instruction limit** - Each `update()` call has a maximum number of bytecode instructions before ArduPilot terminates it
- **No infinite loops** - Scripts that run too long are killed. Always use the callback pattern (`return update, interval`)
- **File I/O** - Writing to SD card is slow. Don't log faster than every 1-2 seconds
- **No network** - Lua scripts cannot open TCP/UDP sockets

### Graph Editor Limits

- Maximum approximately **100 nodes** per graph for reasonable performance
- Very complex graphs with many connections may compile slowly
- The editor does not support sub-graphs or nested graphs (yet)

### Debugging

- Use **Send GCS Text** nodes liberally during development to trace values
- Set severity to **Debug (7)** for development messages
- Use the **Log to File** node to record data for post-flight analysis
- Check `/scripts/` on the SD card for error logs if a script fails to start
- Common issues: nil values (sensor not available), division by zero, exceeding memory limits

### Script File Location

- ArduPilot loads scripts from the `/scripts/` directory on the SD card
- Script file names must end in `.lua`
- Scripts are loaded at boot - reboot the FC after adding/changing scripts
- Only one script runs at a time on most boards (limited by memory)
