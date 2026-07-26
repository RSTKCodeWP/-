#pragma once

// MSP (MultiWii Serial Protocol) client for the Betaflight flight controller
// running on the EMAX Nanohawk 1S (STM32 USB CDC, VID_0483/PID_5740).
//
// Protocol reference (Betaflight MSP V1 wire format):
//   Request : '$' 'M' '<' <size:u8> <cmd:u8> [payload…] <checksum:u8>
//   Response: '$' 'M' '>' <size:u8> <cmd:u8> [payload…] <checksum:u8>
//   Checksum: XOR of size ^ cmd ^ payload[0] ^ … ^ payload[n-1]
//
// Command codes extracted from:
//   external/betaflight/msp/msp_protocol.h          (Betaflight GPL-3.0 source)
//   external/betaflight/msp/msp_protocol_v2_betaflight.h
// Original betaflight source: D:\DroneAI\betaflight-master\src\main\msp\

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace nanohawk::msp {

// ── MSP V1 command codes (subset used by nanohawk-agent) ─────────────────────
// Source: external/betaflight/msp/msp_protocol.h
enum class Cmd : uint8_t {
    ApiVersion =   1,   // out: protocol + API major/minor version
    FcVariant  =   2,   // out: 4-char FC identifier e.g. "BTFL"
    FcVersion  =   3,   // out: firmware version (major, minor, patch)
    BoardInfo  =   4,   // out: board identifier + hardware revision

    Status     = 101,   // out: cycleTime, errors, sensors, flight modes
    RawImu     = 102,   // out: raw gyro/accel/mag (9 values × int16)
    Rc         = 105,   // out: 8+ RC channel values (uint16, µs)
    Attitude   = 108,   // out: roll/pitch (decidegrees), yaw (degrees)
    Altitude   = 109,   // out: altitude (cm), variometer (cm/s)
    Analog     = 110,   // out: battery V, mAh drawn, RSSI, current

    SetRawRc   = 200,   // in:  override 8 RC channels (uint16 × 8, µs)
                        //      Requires: Betaflight receiver type = MSP
};

// ── Telemetry structs ─────────────────────────────────────────────────────────

struct Attitude {
    float rollDeg{0};   // positive = right bank
    float pitchDeg{0};  // positive = nose up
    float yawDeg{0};    // 0–360, clockwise from north
};

struct Analog {
    float    batteryVolts{0};  // pack voltage
    uint16_t mAhDrawn{0};      // milliamp-hours consumed
    uint16_t rssi{0};          // 0–1023 (1023 = 100 %)
    float    amperage{0};      // instantaneous current draw (amps)
};

// 8-channel RC frame; values in microseconds (1000–2000).
// Betaflight default AETR channel order: Roll, Pitch, Throttle, Yaw, Arm, …
struct RcChannels {
    uint16_t ch[8]{1500, 1500, 1000, 1500, 1000, 1000, 1000, 1000};
    //              roll  pitch thr   yaw   arm   aux2  aux3  aux4
};

// ── MspClient ────────────────────────────────────────────────────────────────

// Communicates with the Betaflight FC over USB serial using MSP V1.
//
// Typical usage:
//   MspClient fc("COM3");
//   std::string err;
//   fc.connect(err);            // open serial port
//   fc.identify(variant, err);  // returns "BTFL"
//   fc.readAnalog(batt, err);   // battery voltage etc.
//   fc.readAttitude(att, err);  // roll / pitch / yaw
//
// For RC override (autonomous flight control via MSP):
//   → In Betaflight Configurator, set Receiver = MSP.
//   → Then setRawRc() / arm() / disarm() override stick inputs.
class MspClient {
public:
    explicit MspClient(std::string port, int baud = 115200);
    ~MspClient();

    MspClient(MspClient&&) noexcept;
    MspClient& operator=(MspClient&&) noexcept;

    MspClient(const MspClient&)            = delete;
    MspClient& operator=(const MspClient&) = delete;

    // Open the serial port; configures baud rate, timeouts, flushes buffers.
    [[nodiscard]] bool connect(std::string& error);
    void               disconnect();
    [[nodiscard]] bool isConnected() const;

    // ── Identification ────────────────────────────────────────────────────────

    // MSP_FC_VARIANT (cmd 2): fills fcVariant with "BTFL" for Betaflight.
    [[nodiscard]] bool identify(std::string& fcVariant, std::string& error);

    // MSP_FC_VERSION (cmd 3): fills major/minor/patch.
    [[nodiscard]] bool version(uint8_t& major, uint8_t& minor,
                               uint8_t& patch, std::string& error);

    // ── Telemetry ─────────────────────────────────────────────────────────────

    // MSP_ATTITUDE (cmd 108): roll/pitch in decidegrees → degrees, yaw in degrees.
    [[nodiscard]] bool readAttitude(Attitude& out, std::string& error);

    // MSP_ANALOG (cmd 110): battery voltage, mAh drawn, RSSI, current.
    [[nodiscard]] bool readAnalog(Analog& out, std::string& error);

    // MSP_RC (cmd 105): live RC channel values as seen by the FC.
    [[nodiscard]] bool readRc(RcChannels& out, std::string& error);

    // ── RC override (autonomous control) ─────────────────────────────────────

    // MSP_SET_RAW_RC (cmd 200): push 8 RC channel values to the FC.
    // NOTE: only takes effect when Betaflight receiver type is set to "MSP".
    [[nodiscard]] bool setRawRc(const RcChannels& channels, std::string& error);

    // Convenience: sets arm switch high (ch[4]=1900), throttle low (ch[2]=1000).
    [[nodiscard]] bool arm(std::string& error);

    // Convenience: sets arm switch low (ch[4]=1000), all others to safe defaults.
    [[nodiscard]] bool disarm(std::string& error);

private:
    struct Impl;

    std::string            port_;
    int                    baud_;
    std::unique_ptr<Impl>  impl_;

    // Low-level framing helpers.
    [[nodiscard]] bool sendRequest(uint8_t cmd,
                                   const std::vector<uint8_t>& payload,
                                   std::string& error);

    [[nodiscard]] bool readResponse(uint8_t               expectedCmd,
                                    std::vector<uint8_t>& payload,
                                    std::string&          error);

    [[nodiscard]] bool transaction(uint8_t                     cmd,
                                   const std::vector<uint8_t>& req,
                                   std::vector<uint8_t>&       resp,
                                   std::string&                error);
};

} // namespace nanohawk::msp
