# Two axis thrust vectoring Y6 drone

This project focuses on the development of an experimental FPV Y6 drone with continuous two-axis thrust vectoring.
The platform uses a six-motor configuration (two motors for each propulsion unit; one rear propulsion unit and two front propulsion units), where each propulsion unit can redirect its thrust through a dual-ring gimbal mechanism with full 360° rotational capability. This significantly increases maneuverability, attitude control authority, and fault tolerance compared with conventional multirotor designs.

The control system will be based on a Teensy 4.1 microcontroller programmed in C++, using ICM-42688-P inertial sensors and long-range LoRa communication. Power electronics will be integrated into the fixed main frame, and it will be transferred to moving assemblies through slip rings. Data will be transferred through a local ESP-NOW network formed by eleven ESP32-S3 SuperMini boards. Two of them will be connected to the Teensy 4.1: one dedicated to transmitting the packets containing the gimbal motor angle commands and thrust motor RPM setpoints calculated by the Teensy, and the other dedicated to receiving error reports and telemetry data from the remaining nine ESP32 nodes.
In addition to real-time FPV flight, the platform will include onboard video recording to MicroSD storage and an independent action camera.

A core objective of the project is to develop an aircraft capable of:

- Reconfiguring its geometry on the ground by relocating modules thanks to its modular design.

- Automatically detecting structural changes or deformations.

- Adapting its control system to the current geometry.

- Maintaining stability under partial motor or actuator failures.

- Serving as a test platform for advanced flight-control strategies.

As a future extension, in-flight geometry reconfiguration may also be explored.
A custom transmitter/controller specifically designed for the platform will also be developed.

## Project Status

Currently working on the Gimbal Design 7.1. This includes the CAD design, electronics design and assembly, and programming both the Teensy 4.1 and the ESP32-S3 SuperMini nodes for local sensor and actuator control, as well as real-time ESP-NOW communication.
