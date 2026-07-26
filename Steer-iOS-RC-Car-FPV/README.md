# Steer

iOS app for driving a remote controlled car from an iPhone with an IP camera FPV (first-person view) stream.

Originally created by [John Boiles](https://github.com/johnboiles). Source: [johnboiles/Steer](https://github.com/johnboiles/Steer).

## Features

- **FPV video** — RTSP/IP camera stream via FFmpeg/OpenGL ES
- **Dual joystick** — touch-based steering and throttle
- **Accelerometer control** — tilt-to-steer mode
- **UDP car control** — sends commands to the RC car over the network
- **Configuration** — IP address, stream URL, and control settings

## Requirements

- macOS with Xcode (legacy iOS project, circa 2010)
- iOS device or simulator (older SDK; may need project updates for modern Xcode)
- Network-connected RC car with UDP control receiver
- IP camera or RTSP stream for FPV

## Project structure

| Path | Description |
|------|-------------|
| `Classes/` | App logic — joysticks, accelerometer, car control, settings |
| `FFMPEG/` | FFmpeg video player integration (OpenGL ES) |
| `Libraries/ffmpeg/` | Prebuilt FFmpeg static libraries |
| `Resources/` | UI images and icons |
| `Steer.xcodeproj/` | Xcode project |

## Build

1. Open `Steer.xcodeproj` in Xcode on macOS.
2. Select your target device or simulator.
3. Build and run (⌘R).

> **Note:** This project targets legacy iOS APIs (pre-ARC, UIApplicationMain delegate pattern). Building on current Xcode may require SDK and deployment target updates.

## Server test utility

`ServerTest.c` is a small C utility for testing UDP communication with the car receiver.

## License

Original project by John Boiles. FFmpeg components are under LGPL/GPL — see headers in `Libraries/ffmpeg/`.
