/**
 * ardudeck-wfb-rx - headless wfb-ng receiver for ArduDeck.
 *
 * Claims an RTL8812AU-family WiFi adapter over libusb (userspace, no kernel
 * driver), receives an OpenIPC / RunCam WiFiLink wfb-ng broadcast, decodes it
 * (libsodium decrypt + zfex FEC) and emits the video as RTP over UDP -
 * where ArduDeck's media engine ingests it.
 *
 * Radio stack: vendored from OpenIPC Aviateur (GPL; see LICENSE and README).
 *
 * Usage:
 *   ardudeck-wfb-rx --key <gs.key> --channel <n> --bandwidth <20|40>
 *                   --output udp://127.0.0.1:5600 [--device vid:pid] [--list]
 */

#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>

#include "gui_interface.h"
#include "wifi/wfbng_link.h"

namespace {

WfbngLink *g_link = nullptr;

void handleSignal(int) {
    if (g_link) g_link->stop();
    std::_Exit(0);
}

int fail(const char *msg) {
    std::fprintf(stderr, "[error] %s\n", msg);
    return 1;
}

} // namespace

int main(int argc, char **argv) {
    std::string keyPath;
    std::string output;
    std::string deviceFilter;
    int channel = 161;
    int bandwidth = 20;
    bool list = false;

    for (int i = 1; i < argc; i++) {
        const std::string arg = argv[i];
        auto next = [&]() -> const char * { return i + 1 < argc ? argv[++i] : nullptr; };
        if (arg == "--key") { const char *v = next(); if (v) keyPath = v; }
        else if (arg == "--channel") { const char *v = next(); if (v) channel = std::atoi(v); }
        else if (arg == "--bandwidth") { const char *v = next(); if (v) bandwidth = std::atoi(v); }
        else if (arg == "--output") { const char *v = next(); if (v) output = v; }
        else if (arg == "--host") { const char *v = next(); if (v) GuiInterface::Instance().forwardHost = v; }
        else if (arg == "--device") { const char *v = next(); if (v) deviceFilter = v; }
        else if (arg == "--list") { list = true; }
        else if (arg == "--verbose") { GuiInterface::Instance().verbose = true; }
        else if (arg == "--version") { std::printf("ardudeck-wfb-rx 0.1.0\n"); return 0; }
        else if (arg == "--help") {
            std::printf("Usage: ardudeck-wfb-rx --key gs.key --channel 161 --bandwidth 20 --output udp://127.0.0.1:5600\n");
            std::printf("         [--host <ip>]   forward video to another machine (default 127.0.0.1)\n");
            std::printf("         [--device vid:pid] [--list] [--verbose]\n");
            return 0;
        }
    }

    const auto devices = WfbngLink::get_device_list();
    if (list) {
        for (const auto &d : devices) {
            std::printf("%04x:%04x bus %u port %u %s\n", d.vendor_id, d.product_id, d.bus_num, d.port_num, d.display_name.c_str());
        }
        return 0;
    }

    if (devices.empty()) return fail("no supported WiFi adapter found (RTL8812AU family)");
    if (keyPath.empty()) return fail("--key <gs.key> is required");

    // Output url -> port (the radio stack always sends to 127.0.0.1).
    int port = 5600;
    if (const auto colon = output.rfind(':'); colon != std::string::npos) {
        const int parsed = std::atoi(output.c_str() + colon + 1);
        if (parsed > 0 && parsed <= 65535) port = parsed;
    }
    GuiInterface::Instance().playerPort = port;

    const DeviceId *picked = &devices.front();
    if (!deviceFilter.empty()) {
        char wantVid[8] = {0}, wantPid[8] = {0};
        if (std::sscanf(deviceFilter.c_str(), "%4[0-9a-fA-F]:%4[0-9a-fA-F]", wantVid, wantPid) == 2) {
            const auto vid = static_cast<uint16_t>(std::strtol(wantVid, nullptr, 16));
            const auto pid = static_cast<uint16_t>(std::strtol(wantPid, nullptr, 16));
            for (const auto &d : devices) {
                if (d.vendor_id == vid && d.product_id == pid) { picked = &d; break; }
            }
        }
    }

    const int widthMode = bandwidth == 40 ? 1 : 0; // index into 20/40 MHz modes
    std::fprintf(stderr, "[info] adapter %04x:%04x, channel %d, %d MHz, rtp -> udp://127.0.0.1:%d\n",
                 picked->vendor_id, picked->product_id, channel, bandwidth, port);

    std::signal(SIGINT, handleSignal);
    std::signal(SIGTERM, handleSignal);

    WfbngLink link;
    g_link = &link;
    if (!link.start(*picked, static_cast<uint8_t>(channel), widthMode, keyPath)) {
        return fail("failed to start the receiver (is the adapter in use by another program?)");
    }

    while (!GuiInterface::Instance().wifiStopped) {
        std::this_thread::sleep_for(std::chrono::milliseconds(250));
    }
    link.stop();
    return 2; // receive loop died - supervisor may restart us
}
