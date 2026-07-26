/**
 * Headless GuiInterface shim for ardudeck-wfb-rx.
 *
 * The vendored src/wifi sources (from OpenIPC Aviateur) report logs, counters
 * and stream events through a GuiInterface singleton. This shim provides that
 * exact surface with terminal output instead of GUI signals, so the radio
 * stack compiles unmodified. Everything the wifi sources touch is here;
 * nothing else.
 */

#pragma once

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <format>
#include <string>
#include <string_view>

enum class LogLevel {
    Info,
    Debug,
    Warn,
    Error,
};

/** Aviateur's localization macro - headless build passes tags through. */
#ifndef FTR
    #define FTR(TAG) std::string(TAG)
#endif

class GuiInterface {
public:
    static GuiInterface &Instance() {
        static GuiInterface instance;
        return instance;
    }

    // ── state the wifi stack reads/writes ──────────────────────────────────
    long long wifiFrameCount_ = 0;
    long long wfbngFrameCount_ = 0;
    long long rtpPktCount_ = 0;
    int drone_fec_level_ = 0;
    int playerPort = 5600;
    std::string playerCodec;
    // Destination the decoded RTP is forwarded to. Default localhost (ArduDeck
    // on the same machine); set to a LAN IP via --host so a PC receiver can
    // forward video to ArduDeck running on another machine (e.g. a Mac that
    // can't power the dongle).
    std::string forwardHost = "127.0.0.1";

    /** Set by EmitWifiStopped; the main loop exits non-zero so the supervisor
        (ArduDeck's media engine) can notice and restart. */
    std::atomic<bool> wifiStopped{false};

    bool verbose = false;

    template <typename... Args>
    void PutLog(LogLevel level, const std::string_view message, Args... format_items) {
        if (level == LogLevel::Debug && !verbose) return;
        std::string str = std::vformat(message, std::make_format_args(format_items...));
        const char *tag = level == LogLevel::Info    ? "info"
                          : level == LogLevel::Debug ? "debug"
                          : level == LogLevel::Warn  ? "warn"
                                                     : "error";
        std::fprintf(stderr, "[%s] %s\n", tag, str.c_str());
        std::fflush(stderr);
    }

    void NotifyRtpStream(int pt, uint16_t ssrc, int port, const std::string &codec) {
        std::fprintf(stderr, "[info] RTP stream live: codec=%s payload-type=%d ssrc=%u -> udp://127.0.0.1:%d\n",
                     codec.c_str(), pt, ssrc, port);
        std::fflush(stderr);
    }

    void ShowTip(std::string msg) {
        std::fprintf(stderr, "[info] %s\n", msg.c_str());
        std::fflush(stderr);
    }

    void UpdateCount() {
        // Periodic stats keepalive on stdout - one line the supervisor can
        // parse ("stats wifi=<n> wfb=<n> rtp=<n>").
        const long long now = rtpPktCount_ + wifiFrameCount_;
        if (now - lastStats_ < 512) return;
        lastStats_ = now;
        std::printf("stats wifi=%lld wfb=%lld rtp=%lld\n", wifiFrameCount_, wfbngFrameCount_, rtpPktCount_);
        std::fflush(stdout);
    }

    void EmitWifiStopped() {
        std::fprintf(stderr, "[warn] wifi receive stopped\n");
        std::fflush(stderr);
        wifiStopped = true;
    }

private:
    long long lastStats_ = 0;
};
