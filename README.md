# RSTKCodeWP

Repository for embedded, FPV, and drone open-source projects.

## FPV Library (auto-synced)

**[`fpv-library/`](fpv-library/)** — automated mirror catalog from GitHub search.

- **55 repos** synced from [FPV search page 4](https://github.com/search?q=Fpv&type=repositories&s=updated&o=desc&p=4) + owner expansion
- Daily discover + sync via [GitHub Actions](.github/workflows/fpv-library-sync.yml)
- Manifest: [`fpv-library/catalog.json`](fpv-library/catalog.json)

```bash
# Discover more pages
python3 fpv-library/scripts/discover.py --search Fpv --page 4 --expand-owners

# Pull upstream updates
python3 fpv-library/scripts/sync.py --all
```

See [`fpv-library/README.md`](fpv-library/README.md) for full documentation.

**Themed highlights:** [`fpv-library/THEMED.md`](fpv-library/THEMED.md) — GCS, WFB, OpenIPC, fiber, MAVLink (280+ catalogued).

## Legacy examples (hand-copied)

| Folder | Description |
|--------|-------------|
| [`Steer-iOS-RC-Car-FPV/`](Steer-iOS-RC-Car-FPV/) | iOS app for driving an RC car from an iPhone with IP camera FPV |
| [`SkySweep32-ESP32-Drone-Detector/`](SkySweep32-ESP32-Drone-Detector/) | ESP32 passive drone detector — multi-band RF scanning (900 MHz, 2.4 GHz, 5.8 GHz) |
| [`fly-or-no_fly-RaspberryPi-FPV-Flight-Monitor/`](fly-or-no_fly-RaspberryPi-FPV-Flight-Monitor/) | Raspberry Pi FPV flight go/no-go monitor with e-paper display and weather API |
| [`fpv-inventory-Deno-FPV-Parts-Inventory/`](fpv-inventory-Deno-FPV-Parts-Inventory/) | Deno web app for tracking FPV quads, parts bins, assemblies, and gear history |
| [`wfb-ng-WiFi-FPV-Long-Range-Radio-Link/`](wfb-ng-WiFi-FPV-Long-Range-Radio-Link/) | Long-range digital FPV radio link over raw WiFi (video + mavlink, FEC, encryption) |
| [`fpv-boat-RaspberryPi-Quest-VR-RC-Boat/`](fpv-boat-RaspberryPi-Quest-VR-RC-Boat/) | FPV RC boat — Raspberry Pi WebRTC stream + Meta Quest WebXR piloting with motor/lights control |

## FPVibe federation ([github.com/FPVibe](https://github.com/FPVibe))

| Folder | Source | Description |
|--------|--------|-------------|
| [`docs-FPVibe-Federation-Architecture-Specs/`](docs-FPVibe-Federation-Architecture-Specs/) | [FPVibe/docs](https://github.com/FPVibe/docs) | Federation architecture, API contract, implementation plan |
| [`flowchart-Node-FPV-Training-Tracker-PWA/`](flowchart-Node-FPV-Training-Tracker-PWA/) | [FPVibe/flowchart](https://github.com/FPVibe/flowchart) | Self-hosted PWA for FPV freestyle training, sessions, trick mastery |
| [`fpv-inventory-Deno-FPV-Parts-Inventory/`](fpv-inventory-Deno-FPV-Parts-Inventory/) | [FPVibe/fpv-inventory](https://github.com/FPVibe/fpv-inventory) | Deno parts & gear inventory (see above) |
| [`fpv-tools-Deno-Browser-Betaflight-Utilities/`](fpv-tools-Deno-Browser-Betaflight-Utilities/) | [FPVibe/fpv-tools](https://github.com/FPVibe/fpv-tools) | Browser PWA tools: CLI merge, rate profiles, prop/motor sizer |
| [`fpvibe-github-io-FPVibe-Org-Website/`](fpvibe-github-io-FPVibe-Org-Website/) | [FPVibe/fpvibe.github.io](https://github.com/FPVibe/fpvibe.github.io) | FPVibe GitHub Pages site (placeholder) |
| [`FPVibe-github-Org-Profile-Defaults/`](FPVibe-github-Org-Profile-Defaults/) | [FPVibe/.github](https://github.com/FPVibe/.github) | Org-level GitHub profile and defaults |

## bobberdolle1 — FPV-relevant only ([github.com/bobberdolle1](https://github.com/bobberdolle1))

> Раніше сюди потрапили **всі 20 репо** автора (включно з HolyBot, MailPechkinBot тощо) — це **не** частина `fpv-library`. Зайві Telegram/mail-боти прибрані; у каталозі лишаються лише FPV/дрон-проєкти.

| Folder | Source | Description |
|--------|--------|-------------|
| [`SkySweep32-ESP32-Drone-Detector/`](SkySweep32-ESP32-Drone-Detector/) | [bobberdolle1/SkySweep32](https://github.com/bobberdolle1/SkySweep32) | ESP32 passive drone detector |
| [`GyroChad-Rust-FPV-Drone-AI-Bot/`](GyroChad-Rust-FPV-Drone-AI-Bot/) | [bobberdolle1/GyroChad](https://github.com/bobberdolle1/GyroChad) | FPV drone assistant (RAG, vision, blackbox) |
| [`at32f435-rgt7-manual-AT32-Flight-Controller-Manual/`](at32f435-rgt7-manual-AT32-Flight-Controller-Manual/) | [bobberdolle1/at32f435-rgt7-manual](https://github.com/bobberdolle1/at32f435-rgt7-manual) | AT32F435 RGT7 flight controller manual |
| [`maixcam-servo-control-AI-Ballistic-Servo-MaixCAM/`](maixcam-servo-control-AI-Ballistic-Servo-MaixCAM/) | [bobberdolle1/maixcam-servo-control](https://github.com/bobberdolle1/maixcam-servo-control) | AI ballistic servo drop (MaixCAM, YOLOv8) |
| [`maixcam-wildtrap-AI-Camera-Trap-MaixCAM/`](maixcam-wildtrap-AI-Camera-Trap-MaixCAM/) | [bobberdolle1/maixcam-wildtrap](https://github.com/bobberdolle1/maixcam-wildtrap) | AI camera trap for MaixCAM |
| [`openflash-Rust-NAND-Flash-Programmer/`](openflash-Rust-NAND-Flash-Programmer/) | [bobberdolle1/openflash](https://github.com/bobberdolle1/openflash) | NAND/eMMC flash programmer (Pico, STM32, ESP32) |
| [`Pico-Nand-Flasher-RaspberryPi-Pico-NAND/`](Pico-Nand-Flasher-RaspberryPi-Pico-NAND/) | [bobberdolle1/Pico-Nand-Flasher](https://github.com/bobberdolle1/Pico-Nand-Flasher) | NAND flasher for Raspberry Pi Pico |

## paulnurkkala ([github.com/paulnurkkala](https://github.com/paulnurkkala))

| Folder | Source | Description |
|--------|--------|-------------|
| [`ardufleetcheck-Python-ArduPilot-Fleet-Check-Skills/`](ardufleetcheck-Python-ArduPilot-Fleet-Check-Skills/) | [paulnurkkala/ardufleetcheck](https://github.com/paulnurkkala/ardufleetcheck) | ArduPilot post-build fleet-check pipeline (Claude Code skills) |
| [`hackrf-vtx-elrs-monitor-HackRF-FPV-VTX-ELRS-Monitor/`](hackrf-vtx-elrs-monitor-HackRF-FPV-VTX-ELRS-Monitor/) | [paulnurkkala/hackrf-vtx-elrs-monitor](https://github.com/paulnurkkala/hackrf-vtx-elrs-monitor) | HackRF multi-band FPV VTX + ELRS link monitor |
| [`leoflight-dual-thrustmasters-Jetson-Dual-Thrustmaster-MAVLink/`](leoflight-dual-thrustmasters-Jetson-Dual-Thrustmaster-MAVLink/) | [paulnurkkala/leoflight-dual-thrustmasters](https://github.com/paulnurkkala/leoflight-dual-thrustmasters) | Dual Thrustmaster controllers on Jetson → MAVLink to FC |
| [`RCGroupsScraper-Python-RCGroups-Search-Notifier/`](RCGroupsScraper-Python-RCGroups-Search-Notifier/) | [paulnurkkala/RCGroupsScraper](https://github.com/paulnurkkala/RCGroupsScraper) | Automated RC Groups forum search and notifications |
| [`claude-mgrsosd-Betaflight-OSD-Layout-Claude-Plugin/`](claude-mgrsosd-Betaflight-OSD-Layout-Claude-Plugin/) | [paulnurkkala/claude-mgrsosd](https://github.com/paulnurkkala/claude-mgrsosd) | Claude plugin: push Betaflight OSD layout (.rtf) to FC |
| [`claude-osdfont-Betaflight-OSD-Font-Claude-Plugin/`](claude-osdfont-Betaflight-OSD-Font-Claude-Plugin/) | [paulnurkkala/claude-osdfont](https://github.com/paulnurkkala/claude-osdfont) | Claude plugin: upload OSD .mcm font to Betaflight FC |
| [`claude-rctest-Betaflight-RC-Test-Claude-Plugin/`](claude-rctest-Betaflight-RC-Test-Claude-Plugin/) | [paulnurkkala/claude-rctest](https://github.com/paulnurkkala/claude-rctest) | Claude plugin: verify live RC frames on Betaflight FC |
| [`claude-satest-Betaflight-SmartAudio-Claude-Plugin/`](claude-satest-Betaflight-SmartAudio-Claude-Plugin/) | [paulnurkkala/claude-satest](https://github.com/paulnurkkala/claude-satest) | Claude plugin: SmartAudio sanity test on Betaflight FC |
| [`dronewars2026-HTML-Drone-Wars-2026/`](dronewars2026-HTML-Drone-Wars-2026/) | [paulnurkkala/dronewars2026](https://github.com/paulnurkkala/dronewars2026) | Drone Wars 2026 web project |
| [`MEANduino-MEAN-Server-Arduino-Data/`](MEANduino-MEAN-Server-Arduino-Data/) | [paulnurkkala/MEANduino](https://github.com/paulnurkkala/MEANduino) | MEAN stack server for Arduino sensor data |
| [`comm-slackbot-Slack-COMMGamers-Bot/`](comm-slackbot-Slack-COMMGamers-Bot/) | [paulnurkkala/comm-slackbot](https://github.com/paulnurkkala/comm-slackbot) | Slack bot for COMMGamers.us |
| [`commgamers-us-COMMGamers-Website/`](commgamers-us-COMMGamers-Website/) | [paulnurkkala/commgamers.us](https://github.com/paulnurkkala/commgamers.us) | Official COMMGamers.us website source |
| [`django-password-reset-Django-Password-Reset-Views/`](django-password-reset-Django-Password-Reset-Views/) | [paulnurkkala/django-password-reset](https://github.com/paulnurkkala/django-password-reset) | Class-based Django password reset views |
| [`Django-Pushbullet-Django-Pushbullet-Integration/`](Django-Pushbullet-Django-Pushbullet-Integration/) | [paulnurkkala/Django-Pushbullet](https://github.com/paulnurkkala/Django-Pushbullet) | Django Pushbullet integration |
| [`django-templated-email-Django-Templated-Email/`](django-templated-email-Django-Templated-Email/) | [paulnurkkala/django-templated-email](https://github.com/paulnurkkala/django-templated-email) | Django templated email module |
| [`sedona-trip-planner-Leaflet-Sedona-Trip-Map/`](sedona-trip-planner-Leaflet-Sedona-Trip-Map/) | [paulnurkkala/sedona-trip-planner](https://github.com/paulnurkkala/sedona-trip-planner) | Leaflet satellite map for Sedona trip planning |
| [`stellar-js-Parallax-Scrolling-Library/`](stellar-js-Parallax-Scrolling-Library/) | [paulnurkkala/stellar.js](https://github.com/paulnurkkala/stellar.js) | Stellar.js parallax scrolling library |
| [`TUCapstone12-TU-Orals-Quiz-Web-App/`](TUCapstone12-TU-Orals-Quiz-Web-App/) | [paulnurkkala/TUCapstone12](https://github.com/paulnurkkala/TUCapstone12) | TU orals finals quizzing web application |
| [`uptimerobot-Python-UptimeRobot-API-Wrapper/`](uptimerobot-Python-UptimeRobot-API-Wrapper/) | [paulnurkkala/uptimerobot](https://github.com/paulnurkkala/uptimerobot) | Python wrapper for UptimeRobot API |
| [`wordpress-s3-migration-script-WordPress-S3-Migration/`](wordpress-s3-migration-script-WordPress-S3-Migration/) | [paulnurkkala/wordpress-s3-migration-script](https://github.com/paulnurkkala/wordpress-s3-migration-script) | WordPress to Amazon S3 migration script |
| [`wpcustposttype-WordPress-Custom-Post-Types/`](wpcustposttype-WordPress-Custom-Post-Types/) | [paulnurkkala/wpcustposttype](https://github.com/paulnurkkala/wpcustposttype) | WordPress custom post type helper class |
| [`sausage-Java-Sausage-App/`](sausage-Java-Sausage-App/) | [paulnurkkala/sausage](https://github.com/paulnurkkala/sausage) | Say Sausage (Java) |
| [`zyloweathergetter-JavaScript-Weather-Getter/`](zyloweathergetter-JavaScript-Weather-Getter/) | [paulnurkkala/zyloweathergetter](https://github.com/paulnurkkala/zyloweathergetter) | Weather getter utility |
