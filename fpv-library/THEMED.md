# FPV Library — themed highlights

Curated index after multi-query discovery (GCS, datalink, fiber, IP control, OpenIPC, WFB, DroneBridge, OpenHD).

## Radio link & video (WiFi / WFB)

| Source | Score | Notes |
|--------|-------|-------|
| [DroneBridge/DroneBridge](https://github.com/DroneBridge/DroneBridge) | 20.4 | Bi-directional WiFi drone comms (MAVLink, RC, telemetry) |
| [svpcom/wfb-ng](https://github.com/svpcom/wfb-ng) | — | Long-range raw WiFi FPV (legacy mirror at repo root) |
| [svpcom/wfb-ng-osd](https://github.com/svpcom/wfb-ng-osd) | 9.8 | OSD companion for wfb-ng |
| [OpenHD/OpenHD](https://github.com/OpenHD/OpenHD) | 8.5 | Open-source HD FPV air/ground system |
| [ejowerks/wfb-stabilizer](https://github.com/ejowerks/wfb-stabilizer) | 7.5 | WFB video stabilizer |
| [SamuelBrucksch/wifibroadcast_osd](https://github.com/SamuelBrucksch/wifibroadcast_osd) | 7.8 | WiFiBroadcast OSD |
| [lian/wfb-go](https://github.com/lian/wfb-go) | 5.0 | WFB in Go |
| [roman-koshchei/5ghz_wifibroadcast_hat](https://github.com/roman-koshchei/5ghz_wifibroadcast_hat) | 7.0 | 5 GHz WFB HAT |

## OpenIPC ecosystem (IP camera FPV)

| Source | Notes |
|--------|-------|
| [OpenIPC/fpv](https://github.com/OpenIPC/fpv) | FPV-focused OpenIPC builds |
| [OpenIPC/msposd](https://github.com/OpenIPC/msposd) | MSP DisplayPort OSD |
| [OpenIPC/sbc-groundstations](https://github.com/OpenIPC/sbc-groundstations) | SBC ground station configs |
| [OpenIPC/steam-groundstations](https://github.com/OpenIPC/steam-groundstations) | Steam Deck GCS setups |
| [OpenIPC/adaptive-link](https://github.com/OpenIPC/adaptive-link) | Adaptive RF link |
| [OpenIPC/PixelPilot](https://github.com/OpenIPC/PixelPilot) | Android H.265 WFB viewer |
| [Lupinixx/OpenIPC-FPV-Groundstation-scripts](https://github.com/Lupinixx/OpenIPC-FPV-Groundstation-scripts) | Ground station scripts |

## Ground control stations (GCS)

| Source | Notes |
|--------|-------|
| [ExperimentalDesignBureau-1571/fpv-ground-control-station](https://github.com/ExperimentalDesignBureau-1571/fpv-ground-control-station) | НСК «ГАЛІТ» modular GCS (UA) |
| [rubenCodeforges/ardudeck](https://github.com/rubenCodeforges/ardudeck) | ArduPilot + Betaflight + iNav GCS |
| [mavlink/qgroundcontrol](https://github.com/mavlink/qgroundcontrol) | QGroundControl |
| [altnautica/ADOSMissionControl](https://github.com/altnautica/ADOSMissionControl) | Mission control |
| [rmeadomavic/steam-deck-gcs](https://github.com/rmeadomavic/steam-deck-gcs) | Steam Deck GCS |
| [ajain189/HADES](https://github.com/ajain189/HADES) | SAR desktop GCS with FPV + AI |

## Fiber / specialty links

| Source | Notes |
|--------|-------|
| [mervinnguyen/photonflight-fiber-optic-drone](https://github.com/mervinnguyen/photonflight-fiber-optic-drone) | Fiber-optic drone project |
| [flyspark015/NexusLink](https://github.com/flyspark015/NexusLink) | Nexus link project |

## MAVLink / IP control / OSD

| Source | Notes |
|--------|-------|
| [fpv-wtf/msp-osd](https://github.com/fpv-wtf/msp-osd) | MSP OSD tooling |
| [coroiu/mavlink-node-fpv-*](https://github.com/coroiu) | Node.js MAVLink FPV stack (server/drone/client) |
| [alexbezu/goosd](https://github.com/alexbezu/goosd) | Go OSD |
| [wkumik/Digital-FPV-OSD-Tool](https://github.com/wkumik/Digital-FPV-OSD-Tool) | Digital FPV OSD tool |
| [juricabi/ELRS-Crossfire-WiFi-Joystick-Windows](https://github.com/juricabi/ELRS-Crossfire-WiFi-Joystick-Windows) | ELRS/Crossfire WiFi joystick |

## Owner ecosystems worth watching

| Owner | Why |
|-------|-----|
| [OpenIPC](https://github.com/OpenIPC) | IP camera FPV, OSD, ground stations |
| [svpcom](https://github.com/svpcom) | wfb-ng, drivers, stabilizer |
| [DroneBridge](https://github.com/DroneBridge) | WiFi drone bridge |
| [OpenHD](https://github.com/OpenHD) | HD FPV system |
| [ExperimentalDesignBureau-1571](https://github.com/ExperimentalDesignBureau-1571) | HALIT GCS + repeater |
| [paulnurkkala](https://github.com/paulnurkkala) | Betaflight Claude tools, HackRF monitor |
| [rmeadomavic](https://github.com/rmeadomavic) | Steam Deck / AX12 GCS research |

Run discovery: `python3 fpv-library/scripts/discover_themes.py --pages 1-2`
