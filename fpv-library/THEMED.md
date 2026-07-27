# FPV Library — themed highlights

Curated index after multi-query discovery (GCS, datalink, fiber, IP control, OpenIPC, WFB, DroneBridge, OpenHD, ELRS, DJI mods).

**Catalog:** 386+ repos tracked · **Synced:** see `fpv-library/repos/`

## Radio link & video (WiFi / WFB)

| Source | Notes |
|--------|-------|
| [DroneBridge/DroneBridge](https://github.com/DroneBridge/DroneBridge) | Bi-directional WiFi drone comms (MAVLink, RC, telemetry) |
| [DroneBridge/ESP32](https://github.com/DroneBridge/ESP32) | ESP32 telemetry link + WiFi |
| [svpcom/wfb-ng](https://github.com/svpcom/wfb-ng) | Long-range raw WiFi FPV (legacy mirror at repo root) |
| [svpcom/wfb-ng-osd](https://github.com/svpcom/wfb-ng-osd) | MAVLink OSD + video player for wfb-ng |
| [OpenHD/OpenHD](https://github.com/OpenHD/OpenHD) | Open-source HD FPV air/ground system |
| [OpenHD/QOpenHD](https://github.com/OpenHD/QOpenHD) | QOpenHD ground viewer app |
| [KenLagoni/OpenHD-LTE](https://github.com/KenLagoni/OpenHD-LTE) | MAVLink + HD video over LTE (4G), multi-client |
| [KenLagoni/MavlinkGPRS](https://github.com/KenLagoni/MavlinkGPRS) | MAVLink telemetry via GPRS (SIM800L) |
| [rodizio1/EZ-WifiBroadcast](https://github.com/rodizio1/EZ-WifiBroadcast) | Affordable digital HD video over WiFiBroadcast |
| [Consti10/LiveVideo10ms](https://github.com/Consti10/LiveVideo10ms) | Real-time video decode on Android |
| [Consti10/RubyFPV](https://github.com/Consti10/RubyFPV) | RubyFPV long-range link stack |
| [ejowerks/wfb-stabilizer](https://github.com/ejowerks/wfb-stabilizer) | WFB video stabilizer |
| [lian/wfb-go](https://github.com/lian/wfb-go) | WFB in Go |
| [flyspark015/NexusLink](https://github.com/flyspark015/NexusLink) | Multi-band adaptive FHSS link (H.265 + CRSF/MAVLink) |

## OpenIPC ecosystem (IP camera FPV)

| Source | Notes |
|--------|-------|
| [OpenIPC/fpv](https://github.com/OpenIPC/fpv) | FPV-focused OpenIPC builds |
| [OpenIPC/aviateur](https://github.com/OpenIPC/aviateur) | Cross-platform OpenIPC FPV ground station (Lin/Win/Mac) |
| [OpenIPC/msposd](https://github.com/OpenIPC/msposd) | MSP DisplayPort OSD |
| [OpenIPC/smolrtsp](https://github.com/OpenIPC/smolrtsp) | Lightweight RTSP streaming library |
| [OpenIPC/divinus](https://github.com/OpenIPC/divinus) | Multi-platform open source streamer |
| [OpenIPC/waybeam_venc](https://github.com/OpenIPC/waybeam_venc) | Standalone video encoder & streamer for FPV |
| [OpenIPC/configurator](https://github.com/OpenIPC/configurator) | Configurator for OpenIPC FPV / URLLC devices |
| [OpenIPC/fpv4win](https://github.com/OpenIPC/fpv4win) | WFB client for Windows |
| [OpenIPC/PixelPilot](https://github.com/OpenIPC/PixelPilot) | Android H.265 WFB viewer |
| [OpenIPC/sbc-groundstations](https://github.com/OpenIPC/sbc-groundstations) | SBC ground station configs |
| [OpenIPC/steam-groundstations](https://github.com/OpenIPC/steam-groundstations) | Steam Deck GCS setups |
| [OpenIPC/adaptive-link](https://github.com/OpenIPC/adaptive-link) | Adaptive RF link |
| [OpenIPC/mavfwd](https://github.com/OpenIPC/mavfwd) | MAVLink serial → UDP forwarder (C) |
| [Lupinixx/OpenIPC-FPV-Groundstation-scripts](https://github.com/Lupinixx/OpenIPC-FPV-Groundstation-scripts) | Ground station scripts |

**Fiber over OpenIPC:** camera Ethernet (Majestic RTSP) + BiDi SFP media converters — community config, not stock firmware. Docs: [openfpv.com.ua fiber guide](https://openfpv.com.ua/en/software/fiber-optic).

## Ground control stations (GCS)

| Source | Notes |
|--------|-------|
| [ExperimentalDesignBureau-1571/fpv-ground-control-station](https://github.com/ExperimentalDesignBureau-1571/fpv-ground-control-station) | НСК «ГАЛІТ» modular GCS (UA) |
| [ExperimentalDesignBureau-1571/FPV-control-and-video-repeater](https://github.com/ExperimentalDesignBureau-1571/FPV-control-and-video-repeater) | FPV control + video repeater |
| [rubenCodeforges/ardudeck](https://github.com/rubenCodeforges/ardudeck) | ArduPilot + Betaflight + iNav in one GCS |
| [mavlink/qgroundcontrol](https://github.com/mavlink/qgroundcontrol) | QGroundControl |
| [MishkaRogachev/JAGCS](https://github.com/MishkaRogachev/JAGCS) | Cross-platform GCS (Qt) |
| [asv-soft/asv-drones](https://github.com/asv-soft/asv-drones) | .NET/Avalonia GCS for ArduPilot |
| [iBz-04/Cevheri](https://github.com/iBz-04/Cevheri) | Modern PWA GCS — Next.js + FastAPI + MAVSDK |
| [altnautica/ADOSMissionControl](https://github.com/altnautica/ADOSMissionControl) | Web GCS for autonomous drones |
| [altnautica/ADOSDroneAgent](https://github.com/altnautica/ADOSDroneAgent) | Software-defined drone network agent |
| [altnautica/ADOSAndroidGCS](https://github.com/altnautica/ADOSAndroidGCS) | Native Kotlin Android GCS |
| [skybrush-io/live](https://github.com/skybrush-io/live) | Drone show / swarm GCS frontend |
| [skybrush-io/skybrush-server](https://github.com/skybrush-io/skybrush-server) | Skybrush server (light shows) |
| [rmeadomavic/steam-deck-gcs](https://github.com/rmeadomavic/steam-deck-gcs) | Steam Deck portable GCS |
| [rmeadomavic/ax12-tac-tools](https://github.com/rmeadomavic/ax12-tac-tools) | RadioMaster AX12 → field GCS / CoT bridge |
| [rmeadomavic/ardupilot-mcp](https://github.com/rmeadomavic/ardupilot-mcp) | MCP server for ArduPilot over MAVLink |
| [ajain189/HADES](https://github.com/ajain189/HADES) | SAR desktop GCS with FPV + AI |

## Fiber / specialty / non-RF links

| Source | Notes |
|--------|-------|
| [mervinnguyen/photonflight-fiber-optic-drone](https://github.com/mervinnguyen/photonflight-fiber-optic-drone) | Fiber-tethered quadcopter + ArduPilot |
| [zenos01/ASRS-Specter](https://github.com/zenos01/ASRS-Specter) | Open source fiber optic FPV system |
| [jusstinn/Katena](https://github.com/jusstinn/Katena) | C-UAV solution for fiber optic drones |
| [flyspark015/N-Spine](https://github.com/flyspark015/N-Spine) | HV tether + single-mode fiber link (ground-to-air) |
| [flyspark015/NexusLink](https://github.com/flyspark015/NexusLink) | Long-range multi-band link (see radio section) |

## RC link / ELRS / joystick bridges

| Source | Notes |
|--------|-------|
| [ExpressLRS/ExpressLRS](https://github.com/ExpressLRS/ExpressLRS) | High-performance open RC link |
| [ExpressLRS/ExpressLRS-Configurator](https://github.com/ExpressLRS/ExpressLRS-Configurator) | Build & flash tool |
| [kaack/elrs-joystick-control](https://github.com/kaack/elrs-joystick-control) | USB joystick → drone/airplane via ELRS |
| [juricabi/ELRS-Crossfire-WiFi-Joystick-Windows](https://github.com/juricabi/ELRS-Crossfire-WiFi-Joystick-Windows) | ELRS/Crossfire WiFi → vJoy |
| [AkitaEngineering/Meshtastic-Integration-for-DroneBridge32-Swarm](https://github.com/AkitaEngineering/Meshtastic-Integration-for-DroneBridge32-Swarm) | Meshtastic + DroneBridge ESP32 swarm |

## MAVLink / IP control / OSD

| Source | Notes |
|--------|-------|
| [fpv-wtf/msp-osd](https://github.com/fpv-wtf/msp-osd) | MSP DisplayPort OSD (DJI WTFOS) |
| [coroiu/mavlink-node-fpv-server](https://github.com/coroiu/mavlink-node-fpv-server) | Node.js MAVLink FPV server |
| [coroiu/mavlink-node-fpv-drone](https://github.com/coroiu/mavlink-node-fpv-drone) | Drone-side Node FPV |
| [coroiu/mavlink-node-fpv-client](https://github.com/coroiu/mavlink-node-fpv-client) | Client for Node FPV stack |
| [alexbezu/goosd](https://github.com/alexbezu/goosd) | Go OSD over MAVLink |
| [wkumik/Digital-FPV-OSD-Tool](https://github.com/wkumik/Digital-FPV-OSD-Tool) | MSP-OSD overlay on DVR video |
| [AtiqAakash/Mavlink-OSD](https://github.com/AtiqAakash/Mavlink-OSD) | FPV-style transparent MAVLink overlay |

## Caddx Ascent / HD VRX (official)

| Source | Notes |
|--------|-------|
| [CaddxFPV-Tech/Caddx_vrx_udp_protocol](https://github.com/CaddxFPV-Tech/Caddx_vrx_udp_protocol) | Ascent VRX UART binary protocol + Python UDP client |
| [JerryLamMV/caddx_vrx_udp_protocol](https://github.com/JerryLamMV/caddx_vrx_udp_protocol) | Community mirror of VRX UDP protocol docs + client (≈ same as official) |
| [JerryLamMV/CaddxPCTool_Release](https://github.com/JerryLamMV/CaddxPCTool_Release) | Caddx PC Tool release download links (Windows) |
| [CaddxFPV-Tech/Caddx-Ascent-Firmware_Release](https://github.com/CaddxFPV-Tech/Caddx-Ascent-Firmware_Release) | Ascent firmware releases — see [V17.5.15](https://github.com/CaddxFPV-Tech/Caddx-Ascent-Firmware_Release/releases/tag/V17.5.15) |
| [CaddxFPV-Tech/Caddx-PC-Tool-Release](https://github.com/CaddxFPV-Tech/Caddx-PC-Tool-Release) | Caddx PC configuration tool |
| [CaddxFPV-Tech/Caddx_Ground_Configuration_Release](https://github.com/CaddxFPV-Tech/Caddx_Ground_Configuration_Release) | Ascent ground-station config app (Windows) — see [v0.3.3](https://github.com/CaddxFPV-Tech/Caddx_Ground_Configuration_Release/releases/tag/v0.3.3) |
| [umeow0716/Walksnail-Ascent-FPV-VRX-Rooting-Exploit](https://github.com/umeow0716/Walksnail-Ascent-FPV-VRX-Rooting-Exploit) | PoC: USB upgrade service RCE → root shell on Ascent VRX |
| [umeow0716/extract-ascent-otra](https://github.com/umeow0716/extract-ascent-otra) | Extract Ascent OTRA firmware (companion to rooting exploit) |

### Firmware release V17.5.15 (2026-07-17)

| Device | Role | Chip | Image | Size |
|--------|------|------|-------|------|
| Ascent_G_Gnd | ground (VRX) | cx485 | `Ascent_G_Gnd_17_5_15.img` | ~47 MB |
| Ascent_G_Sky | air | cx486 | `Ascent_G_Sky_17_5_15.img` | ~15 MB |
| Ascent_H_Sky | air | cx482 | `Ascent_H_Sky_17_5_15.img` | ~14 MB |
| Ascent_L_Gnd | ground | cx401 | `Ascent_L_Gnd_17_5_15.img` | ~46 MB |

Manifest with SHA256: `fpv-library/repos/Caddx-Ascent-Firmware_Release-.../manifest.json`

```bash
# Download official .img (not mirrored — too large)
python3 fpv-library/scripts/download_caddx_firmware.py Ascent_G_Gnd

# Unpack OTRA container
uv run python fpv-library/repos/extract-ascent-otra/extract_ascent_otra.py \
  fpv-library/firmware-images/Ascent_G_Gnd_17_5_15.img -o extracted/
```

### Ground Configuration releases

| Tag | Date | Notes |
|-----|------|-------|
| [v0.3.3](https://github.com/CaddxFPV-Tech/Caddx_Ground_Configuration_Release/releases/tag/v0.3.3) | 2026-07-24 | Fix RC stick travel for some 10-byte reportLength controllers (maxValue=255) |
| [v0.3.1](https://github.com/CaddxFPV-Tech/Caddx_Ground_Configuration_Release/releases/tag/v0.3.1) | 2026-07-22 | Test build |

| Asset (v0.3.3) | Kind | Size |
|----------------|------|------|
| `CaddxGroundConfiguration-win-Setup.exe` | Windows installer (Squirrel) | ~54 MB |
| `CaddxGroundConfiguration-win-Portable.zip` | Portable zip | ~50 MB |
| `CaddxGroundConfiguration-0.3.3-full.nupkg` | Squirrel full package | ~50 MB |
| `CaddxGroundConfiguration-0.3.3-delta.nupkg` | Squirrel delta update | ~145 KB |

Manifest with SHA256: `fpv-library/manifests/Caddx_Ground_Configuration_Release.json`

```bash
# Refresh manifest from GitHub + download all release assets
python3 fpv-library/scripts/sync_caddx_ground_config.py --download

# List / download single asset
python3 fpv-library/scripts/download_caddx_ground_config.py
python3 fpv-library/scripts/download_caddx_ground_config.py setup
python3 fpv-library/scripts/download_caddx_ground_config.py portable --tag v0.3.3
```

Update watch status: `fpv-library/manifests/Caddx_Ground_Configuration_Release.status.json` (CI checks daily).

## DJI FPV mods (fpv-wtf ecosystem)

| Source | Notes |
|--------|-------|
| [fpv-wtf/wtfos](https://github.com/fpv-wtf/wtfos) | Firmware mod framework for DJI Goggles / Air Unit (O3/O4 era) |
| [fpv-wtf/wtfos-configurator](https://github.com/fpv-wtf/wtfos-configurator) | WTFOS configurator + margerine |
| [fpv-wtf/msp-osd](https://github.com/fpv-wtf/msp-osd) | MSP DisplayPort OSD on DJI goggles |
| [fpv-wtf/voc-poc](https://github.com/fpv-wtf/voc-poc) | USB video out from DJI FPV Goggles |
| [fpv-wtf/voc-web](https://github.com/fpv-wtf/voc-web) | Web-based DJI Goggles video out |
| [fpv-wtf/fpv_viewer_android](https://github.com/fpv-wtf/fpv_viewer_android) | Android FPV viewer for DJI devices |
| [fpv-wtf/margerine](https://github.com/fpv-wtf/margerine) | Root exploit chain for DJI HD system |
| [fpv-wtf/ar-firmware-tools](https://github.com/fpv-wtf/ar-firmware-tools) | OTRA firmware format tools (Artosyn / Walksnail family) |
| [fpv-wtf/dji-moonlight-shim](https://github.com/fpv-wtf/dji-moonlight-shim) | Stream games to DJI goggles via Moonlight |
| [fpv-wtf/dji-moonlight-gui](https://github.com/fpv-wtf/dji-moonlight-gui) | Moonlight streaming GUI for DJI |
| [fpv-wtf/wtfos-tweaks](https://github.com/fpv-wtf/wtfos-tweaks) | OS behavior tweaks on DJI FPV devices |
| [fpv-wtf/opkg-repo](https://github.com/fpv-wtf/opkg-repo) | Official WTFOS package repository |
| [fpv-wtf/driver-installer](https://github.com/fpv-wtf/driver-installer) | USB driver installer for FPV devices |
| [JoshG20/DJI-MIPI-Switch](https://github.com/JoshG20/DJI-MIPI-Switch) | DJI Vista MIPI switch hardware/firmware |

## Walksnail Avatar / HD digital (community)

| Source | Notes |
|--------|-------|
| [avsaase/walksnail-osd-tool](https://github.com/avsaase/walksnail-osd-tool) | Walksnail OSD font/tooling |
| [alejopdl/walksnail-goggles-web](https://github.com/alejopdl/walksnail-goggles-web) | Web UI for Walksnail goggles |
| [shellixyz/hd_fpv_video_tool](https://github.com/shellixyz/hd_fpv_video_tool) | HD FPV video processing tool |
| [shellixyz/hd_fpv_osd_font_tool](https://github.com/shellixyz/hd_fpv_osd_font_tool) | HD FPV OSD font editor |
| [egorsiniaev/walksnail-osd-export](https://github.com/egorsiniaev/walksnail-osd-export) | Export Walksnail OSD assets |

## RubyFPV digital link

| Source | Notes |
|--------|-------|
| [Consti10/RubyFPV](https://github.com/Consti10/RubyFPV) | Ruby long-range digital FPV stack |
| [RubyFPV/RubyFPV](https://github.com/RubyFPV/RubyFPV) | RubyFPV org mirror / releases |
| [wkumik/RubyFPV](https://github.com/wkumik/RubyFPV) | Community RubyFPV fork |

## Emax

| Source | Notes |
|--------|-------|
| [EmaxModel/fpv-presets](https://github.com/EmaxModel/fpv-presets) | Official Emax Betaflight/iNav presets |
| [EmaxModel/betaflight](https://github.com/EmaxModel/betaflight) | Emax Betaflight fork |
| [EmaxModel/OpenVTx](https://github.com/EmaxModel/OpenVTx) | OpenVTx for Emax hardware |

## OpenCV / vision FPV

| Source | Notes |
|--------|-------|
| [Orandus/fpv-opencv](https://github.com/Orandus/fpv-opencv) | OpenCV FPV experiments |
| [DreamChase29/fpv-yolo-drone-detection](https://github.com/DreamChase29/fpv-yolo-drone-detection) | YOLO drone detection on FPV stream |
| [Jadit19/FPV-Drone-Racing](https://github.com/Jadit19/FPV-Drone-Racing) | FPV racing + computer vision |

## Runcam

| Source | Notes |
|--------|-------|
| [RastaDevX/runcam-divinus](https://github.com/RastaDevX/runcam-divinus) | Runcam Divinus / WiFi-link related tooling |

## DJI O3 / O4 (community)

| Source | Notes |
|--------|-------|
| [matyxcz44/Mat-j-FPV-Drone-](https://github.com/matyxcz44/Mat-j-FPV-Drone-) | DJI O3-based FPV drone project |
| [MegaAnda123/o3_auto_encode](https://github.com/MegaAnda123/o3_auto_encode) | O3 auto-encode utilities (watch) |

## Owner ecosystems (repos as parts of larger projects)

| Owner | Project / focus | Key repos |
|-------|-----------------|-----------|
| [OpenIPC](https://github.com/OpenIPC) | IP-camera FPV platform | fpv, aviateur, msposd, smolrtsp, PixelPilot, adaptive-link |
| [svpcom](https://github.com/svpcom) | WiFiBroadcast / wfb-ng stack | wfb-ng, wfb-ng-osd, rtl8812au drivers |
| [DroneBridge](https://github.com/DroneBridge) | WiFi MAVLink bridge | DroneBridge, ESP32, Desktop, Docs |
| [OpenHD](https://github.com/OpenHD) | HD FPV system | OpenHD, QOpenHD, ImageBuilder |
| [fpv-wtf](https://github.com/fpv-wtf) | DJI FPV hacking (WTFOS, VOC, MSP-OSD, OTRA tools) | wtfos, voc-web, msp-osd, ar-firmware-tools |
| [CaddxFPV-Tech](https://github.com/CaddxFPV-Tech) | Caddx Ascent / Walksnail HD | vrx_udp_protocol, firmware, PC tool, ground config |
| [ExperimentalDesignBureau-1571](https://github.com/ExperimentalDesignBureau-1571) | НСК «ГАЛІТ» (UA) | fpv-ground-control-station, FPV-control-and-video-repeater |
| [altnautica](https://github.com/altnautica) | ADOS drone platform | ADOSMissionControl, ADOSDroneAgent, ADOSAndroidGCS |
| [skybrush-io](https://github.com/skybrush-io) | Drone light shows | live, skybrush-server, studio-blender |
| [flyspark015](https://github.com/flyspark015) | N-Defender / RF defense | NexusLink, N-Spine, N-Defender-Drone-Detection-System |
| [rmeadomavic](https://github.com/rmeadomavic) | Field GCS research | steam-deck-gcs, ax12-research, ax12-tac-tools, ardupilot-mcp |
| [paulnurkkala](https://github.com/paulnurkkala) | Betaflight AI tools | hackrf-vtx-elrs-monitor, ardufleetcheck |
| [ExpressLRS](https://github.com/ExpressLRS) | RC link ecosystem | ExpressLRS, Configurator, Backpack, Hardware |
| [KenLagoni](https://github.com/KenLagoni) | Cellular MAVLink/video | OpenHD-LTE, MavlinkGPRS |
| [mervinnguyen](https://github.com/mervinnguyen) | PhotonFlight fiber drone | photonflight-fiber-optic-drone (+ embedded coursework repos) |
| [Dexon-Drones](https://github.com/Dexon-Drones) | DIY parts compatibility | openfpv |

Run discovery: `python3 fpv-library/scripts/discover_themes.py --pages 1-2`
