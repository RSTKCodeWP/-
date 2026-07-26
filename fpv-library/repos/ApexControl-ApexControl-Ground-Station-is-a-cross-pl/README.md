# ApexControl Ground Station

ApexControl Ground Station is a cross-platform ground control application built with **.NET MAUI** for monitoring and controlling MAVLink-compatible drones and autopilots.

The project focuses on receiving real-time telemetry, displaying vehicle health, GPS status, flight state, command acknowledgements, and providing basic vehicle commands such as arm, disarm, mode switching, and takeoff.

## Features

- Cross-platform UI using .NET MAUI
- Separate mobile and desktop layouts
- MAVLink telemetry listener over UDP
- Heartbeat monitoring
- Link health detection
- GPS status and freshness monitoring
- Position telemetry display
- VFR HUD telemetry support
- Battery telemetry display
- MAVLink command sending
- Command acknowledgement tracking
- Pre-arm and status text display
- Telemetry counters and diagnostics

## Supported Telemetry

The application currently handles and displays telemetry such as:

- Heartbeat
- Global position
- GPS raw data
- VFR HUD
- System status
- Status text
- Command ACK

## Vehicle Commands

The application includes basic command controls:

- Connect
- Disconnect
- Arm
- Disarm
- Set GUIDED mode
- Set LOITER mode
- Set STABILIZE mode
- Takeoff with configurable altitude

Command buttons are enabled only when the application has a healthy MAVLink connection.

## Project Structure
```text
ApexControl/
├── ApexControl.App/
│   ├── MainPage.xaml
│   ├── MainPage.xaml.cs
│   └── ViewModels/
│       └── MainViewModel.cs
│
├── ApexControl.Core/
│   ├── Models/
│   │   └── DroneTelemetry.cs
│   └── Services/
│       └── MavlinkTelemetryService.cs
│
└── README.md

## Architecture

The project is separated into two main layers:

### ApexControl.Core

Contains the core telemetry and MAVLink logic.

Responsibilities:

- Receiving MAVLink UDP packets
- Parsing MAVLink frames
- Updating telemetry models
- Managing command sending
- Tracking command acknowledgements
- Detecting stale telemetry data

### ApexControl.App

Contains the .NET MAUI user interface.

Responsibilities:

- Displaying telemetry data
- Managing mobile and desktop layouts
- Binding UI state to telemetry state
- Exposing user commands through the ViewModel

## UI Layout

The application uses two different layouts:

### Mobile Layout

Designed for phones with a vertical, scrollable layout.

The mobile UI prioritizes:

- Compact cards
- Single-column telemetry display
- Readable labels
- Touch-friendly controls

### Desktop Layout

Designed for Windows and larger screens.

The desktop UI prioritizes:

- Multi-column dashboard layout
- Wider telemetry cards
- Faster scanning of vehicle state
- Separate control toolbar

## Connection Behavior

The application listens for MAVLink telemetry over UDP.

Default port:

text
14550

Typical simulator configuration:

text
udp:127.0.0.1:14550

For ArduPilot SITL, an example connection can be:

bash
sim_vehicle.py -v ArduCopter --console --map

Then configure MAVProxy or the simulator output to send telemetry to UDP port `14550`.

Example MAVProxy output:

bash
output add 127.0.0.1:14550

## Button State Logic

The control buttons follow this behavior:

| State | Connect | Disconnect | Commands |
|---|---:|---:|---:|
| Disconnected | Enabled | Disabled | Disabled |
| Connecting | Disabled | Disabled | Disabled |
| Connected but unhealthy | Disabled | Enabled | Disabled |
| Connected and healthy | Disabled | Enabled | Enabled |
| Disconnecting | Disabled | Disabled | Disabled |

Commands are only enabled when:

- The application is connected
- The MAVLink heartbeat is fresh
- The link is considered healthy

## Telemetry Freshness

A telemetry watchdog checks whether important data streams are fresh.

Tracked freshness indicators include:

- Heartbeat freshness
- GPS freshness
- Position freshness
- HUD freshness

This helps identify when the vehicle is connected but some telemetry streams are stale or missing.

## Requirements

- .NET 8 SDK or newer
- .NET MAUI workload
- Visual Studio 2022 or newer, or JetBrains Rider with MAUI support
- Windows for desktop target
- Android/iOS tooling for mobile targets

Install MAUI workload:

bash
dotnet workload install maui

## Build

From the repository root:

bash
dotnet build

For Windows:

bash
dotnet build ApexControl.App -f net8.0-windows10.0.19041.0

For Android:

bash
dotnet build ApexControl.App -f net8.0-android

## Run

For Windows:

bash
dotnet build ApexControl.App -t:Run -f net8.0-windows10.0.19041.0

For Android, use Visual Studio or Rider to deploy to an emulator or physical device.

## Development Notes

Recommended development flow:

1. Start the drone simulator or autopilot.
2. Ensure MAVLink telemetry is being sent to UDP port `14550`.
3. Run ApexControl Ground Station.
4. Press `Connect`.
5. Wait for heartbeat and link health to become active.
6. Use command buttons only after the link is healthy.

## Safety Notice

This software is under active development and should be used carefully.

Before sending commands to a real vehicle:

- Test with SITL first
- Verify failsafe behavior
- Confirm mode mappings
- Confirm arming checks
- Use a safe test environment
- Keep manual override available

Do not rely on this application as the only safety mechanism for operating a vehicle.

## Roadmap

Planned improvements:

- Mission planning
- Map view
- Parameter management
- MAVLink v2 signing support
- Multiple vehicle support
- Joystick input
- Log recording
- Telemetry replay
- Better command result visualization
- Theme customization
- Advanced connection settings

## Technologies

- C#
- .NET MAUI
- CommunityToolkit.Mvvm
- MAVLink
- UDP networking

## License

No license has been specified yet.

If this project is intended to be open source, add a license such as MIT, Apache-2.0, or GPL depending on your distribution goals.

## Author

ApexControl Ground Station  
Developed as a cross-platform MAVLink ground station application.

