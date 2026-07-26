# Recce - Tethered FPV Drone

A tethered 5-inch FPV quad with wireless control over ESP-NOW, a hot-swap power switching circuit, MAVLink telemetry, and a full Python GCS with a dark avionics GUI.

## How it works

The drone is physically tethered (power delivery), but control and telemetry run wirelessly over ESP-NOW between two ESP32s. A PS5 DualSense connects to the ground station laptop; `bigController.py` reads gamepad input and sends control packets to the transmitter ESP32 over USB serial. The transmitter broadcasts over ESP-NOW to the receiver ESP32 on the drone, which decodes the packet and outputs CRSF directly to the SpeedyBee F405v3 flight controller running iNav. Telemetry flows the other way, the receiver reads MAVLink from the FC and sends structured telemetry back over ESP-NOW to the GCS.

A hot-swap circuit (see schematic) switches between tether power and onboard LiPo mid-flight via GPIO-controlled MOSFETs, triggered from the ground station.

```
PS5 Controller
      │
      ▼
bigController.py  ──USB Serial──►  CRSF_ESP_NowSender (ESP32)
      ▲                                      │ ESP-NOW
      │ telemetry                            ▼
      └──────────────────────  CRSF_ESP_NowReceiver (ESP32)
                                             │ CRSF
                                             ▼
                                    SpeedyBee F405v3 (iNav)
```

## Repo structure

```
recce/
├── CRSF_ESP_NowSender/       # ESP32 firmware - receives serial commands, broadcasts ESP-NOW
├── CRSF_ESP_NowReceiver/     # ESP32 firmware on drone - ESP-NOW → CRSF to FC + MAVLink telemetry
├── VanillaWebserver/         # XIAO ESP32S3-Sense camera stream server
├── bigController.py          # Python GCS -PS5 input, avionics GUI, telemetry display
├── Schematic_Recce-Switching-Circuit.pdf  # Hot-swap tether/battery circuit
└── .gitignore
```

## Components

| Component | Part |
|---|---|
| Frame | 5-inch FPV quad |
| Flight Controller | SpeedyBee F405v3 stack |
| Flight Firmware | iNav |
| Drone-side ESP32 | ESP32 (CRSF receiver + MAVLink) |
| Ground-side ESP32 | ESP32 (serial bridge + ESP-NOW transmitter) |
| Camera | Seeed Studio XIAO ESP32S3 Sense |
| Controller | PS5 DualSense |

## Ground station (`bigController.py`)

- PS5 DualSense input via `pygame`
- Dark avionics GUI -artificial horizon, compass rose, battery gauge, stick visualizers
- MAVLink telemetry parsing (attitude, GPS, battery, arming state, flight mode)
- Heartbeat / keepalive with automatic failsafe on timeout
- GPIO hot-swap trigger -toggles tether/battery from a controller button

## Firmware (`CRSF_ESP_NowReceiver`)

- Receives `ControlPacket` (throttle, roll, pitch, yaw, arm, GPIO toggle) over ESP-NOW
- Outputs CRSF RC channels to FC via UART
- Reads MAVLink from FC on UART2 (GPIO20), parses attitude / GPS / battery / heartbeat
- Sends `MavlinkTelemetry` struct back over ESP-NOW on each heartbeat ACK
- Failsafe: on heartbeat timeout, centers sticks and disarms

## Hot-swap circuit

The switching circuit (see `Schematic_Recce-Switching-Circuit.pdf`) allows mid-flight switching between tether-supplied power and the onboard LiPo. GPIO2/GPIO8 on the receiver ESP32 drive the switching logic; the GCS triggers the toggle over ESP-NOW.

## Setup

### Firmware

1. Install Arduino IDE with ESP32 board support
2. Install libraries: `AlfredoCRSF`, `MAVLink_ardupilotmega`
3. Flash `CRSF_ESP_NowSender` to the ground-side ESP32
4. Flash `CRSF_ESP_NowReceiver` to the drone-side ESP32
5. Update MAC addresses in both sketches if not using broadcast

### Ground station

```bash
pip install pygame pyserial
python bigController.py
```

Connect the ground-side ESP32 via USB before launching. Select the correct COM port when prompted.

## Flight notes

- Arm via right stick down-right on DualSense (mirrored to CH5 high)
- Failsafe kicks in after 2 seconds of lost ESP-NOW heartbeat -throttle cuts, sticks center
- MAVLink stream requested at 10 Hz on connect
- Camera stream available on the XIAO ESP32S3's IP once on the same network
