# ardudeck-wfb-rx

Headless wfb-ng receiver sidecar for ArduDeck's "plug the dongle into this
computer" camera path (OpenIPC / RunCam WiFiLink).

Claims an RTL8812AU-family adapter over libusb in userspace (no kernel
driver on any OS), receives the wfb-ng broadcast, decrypts (gs.key,
libsodium), FEC-decodes (zfex) and emits the video as RTP on UDP - where
ArduDeck's media engine (`wfbng` camera source, dongle mode) ingests it.

```
ardudeck-wfb-rx --key gs.key --channel 161 --bandwidth 20 \
                --output udp://127.0.0.1:5600 [--host <ip>] [--device vid:pid] [--list]
```

`--host <ip>` forwards the decoded video to another machine instead of
localhost - e.g. run the receiver on a PC that can power the dongle and
point `--host` at a Mac running ArduDeck (feed set to Network mode). Both
machines must share a network.

ArduDeck spawns and supervises this binary via
`apps/desktop/src/main/media/wfbng-receiver.ts`; the CLI contract lives in
`wfbng-dongle.ts`.

## Provenance and license

`src/wifi/` and `3rd/devourer/` are vendored unmodified from
[OpenIPC Aviateur](https://github.com/OpenIPC/aviateur)
(commit `2a5a4f241a2f3f13ab170876547f340a3a3d4e50`); `src/gui_interface.h`
is ArduDeck's headless shim replacing Aviateur's GUI singleton, and
`src/main.cpp` is the CLI entry point. This tool is therefore distributed
under the GPL (see LICENSE) as a separate executable; ArduDeck itself
launches it as an independent process and does not link against it.
