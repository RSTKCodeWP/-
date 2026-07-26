#pragma once
// =============================================================================
//  rc_types.h — Remote Controller Firmware
//  FPV Racer v2.0 — Hackclub Fallout Program
//
//  ESP32 (30-pin) + 2.8" TFT (ILI9341, SPI) + 12 buttons
//
//  Button map (physical → function):
//   D-PAD:   UP / DOWN / LEFT / RIGHT
//   ACTION:  OK / BACK
//   GAME:    SHOOT / BOOST / HEALTH(REGEN) / SHIELD
//   SYSTEM:  ON-OFF (power latch) / CONNECT (Find Race / Car connect)
// =============================================================================

#include <stdint.h>

// ---------------------------------------------------------------------------
// Which RC this is (1 or 2) — set per-board before flash
// ---------------------------------------------------------------------------
#define RC_ID  1   // 1 = P1 remote, 2 = P2 remote

// ---------------------------------------------------------------------------
// Pin assignments — ESP32 30-pin
// ---------------------------------------------------------------------------

// ── SPI TFT (ILI9341 2.8") ───────────────────────────────────────────────
#define TFT_CS    5
#define TFT_DC    2
#define TFT_RST   4
#define TFT_MOSI  23
#define TFT_CLK   18
#define TFT_MISO  19    // optional — ILI9341 can run write-only

// ── Buttons (active LOW — internal pull-up) ───────────────────────────────
// D-Pad
#define BTN_UP      13
#define BTN_DOWN    12
#define BTN_LEFT    14
#define BTN_RIGHT   27

// Action
#define BTN_OK      26
#define BTN_BACK    25

// Game actions
#define BTN_SHOOT   33
#define BTN_BOOST   32
#define BTN_HEALTH  35   // input-only pin — no internal pull-up → use external 10kΩ
#define BTN_SHIELD  34   // input-only pin — no internal pull-up → use external 10kΩ

// System
#define BTN_ONOFF   39   // input-only — power latch button (hold 2s to power off)
#define BTN_CONNECT 36   // input-only — Find Race / Connect

// ── Power latch ───────────────────────────────────────────────────────────
// A P-channel MOSFET latches the supply when the MCU drives this HIGH.
// On boot: ESP32 wakes → immediately drives HIGH → holds its own power.
// On shutdown: drives LOW → power cut.
#define PWR_LATCH   15

// ── Buzzer + LED ─────────────────────────────────────────────────────────
#define PIN_BUZZER  21
#define PIN_LED_R   22   // RGB status LED (red channel)
#define PIN_LED_G   0    // RGB status LED (green channel) — boot strapping OK
#define PIN_LED_B   16   // RGB status LED (blue channel)

// ── Battery ADC ──────────────────────────────────────────────────────────
#define PIN_BATT_ADC  34   // shared with BTN_HEALTH when not pressed (mux in HW)
// Note: in the physical PCB, a voltage divider (100kΩ + 100kΩ) feeds
// the LiPo+ line into this pin. Read only when buttons are known released.

// ---------------------------------------------------------------------------
// Timing constants
// ---------------------------------------------------------------------------
#define DRIVE_RATE_MS       20      // 50Hz drive loop
#define UI_REFRESH_MS       100     // TFT partial refresh rate
#define HEARTBEAT_MS        200     // RC → car heartbeat interval
#define LOOKING_INTERVAL_MS 500     // RACE_LOOKING broadcast interval
#define DEBOUNCE_MS         40      // button debounce window
#define LONG_PRESS_MS       2000    // power-off hold duration
#define SHOOT_COOLDOWN_MS   500     // prevent double-tap shoot
#define RECONNECT_TIMEOUT_MS 10000  // auto-reconnect window before forfeit

// ---------------------------------------------------------------------------
// UI constants  (ILI9341 — 240×320 pixels, landscape = 320×240)
// ---------------------------------------------------------------------------
#define SCREEN_W  320
#define SCREEN_H  240

// Colour palette (RGB565)
#define COL_BG         0x0841   // very dark navy
#define COL_PANEL      0x1082   // dark panel
#define COL_ACCENT     0x07FF   // cyan
#define COL_WHITE      0xFFFF
#define COL_GREEN      0x07E0
#define COL_RED        0xF800
#define COL_YELLOW     0xFFE0
#define COL_ORANGE     0xFD20
#define COL_GREY       0x8410
#define COL_SHIELD_BLU 0x001F
#define COL_BAD_RED    0xF9A0
#define COL_HP_GREEN   0x07E0
#define COL_HP_ORANGE  0xFC60
#define COL_HP_RED     0xF800

// ---------------------------------------------------------------------------
// Shared types (reuse from car firmware — same struct layout)
// ---------------------------------------------------------------------------

enum RCPhase : uint8_t {
    RC_IDLE        = 0,
    RC_FREE_DRIVE  = 1,
    RC_CONNECTING  = 2,
    RC_LOOKING     = 3,    // broadcasting RACE_LOOKING
    RC_WAIT_ACCEPT = 4,    // received looking, showing "Accept?" prompt
    RC_NFC_SETUP   = 5,
    RC_LOBBY       = 6,
    RC_COUNTDOWN   = 7,
    RC_RACING      = 8,
    RC_FINISHED    = 9,
    RC_PAUSED      = 10,
};

enum PowerType : uint8_t {
    PWR_NONE        = 0,
    PWR_BOOST       = 1,
    PWR_SHIELD      = 2,
    PWR_REGEN       = 3,
    PWR_BULLETS     = 4,
    BAD_SLOWNESS    = 5,
    BAD_RANDOM_CTRL = 6,
    BAD_DAMAGE      = 7,
    BAD_DRIFT       = 8,
    PWR_STATION_P1  = 9,
    PWR_STATION_P2  = 10,
};

// UI state mirrored from host broadcasts
struct RCGameState {
    uint8_t   phase;
    uint8_t   mode;         // 0=LAP, 1=TIME
    uint8_t   myHealth;     // 0-100
    uint8_t   oppHealth;
    uint8_t   myBullets;
    uint8_t   myLaps;
    uint8_t   oppLaps;
    uint16_t  myScore;
    uint16_t  oppScore;
    PowerType inventory[4]; // active good power slots
    PowerType badPower;
    uint16_t  countdown;    // seconds or countdown tick
    uint32_t  matchTimeMs;
    uint8_t   flags;        // bit0=shield, bit1=paused, bit2=frozen, bit3=ready
};

// Compact log entry for on-screen history ring buffer
struct RCLogEntry {
    char text[32];
};

#define LOG_RING_SIZE 10

// ---------------------------------------------------------------------------
// ESP-NOW packet types (subset used by RC — full list in car firmware types.h)
// ---------------------------------------------------------------------------
enum PacketType : uint8_t {
    PKT_DRIVE         = 0x01,
    PKT_SHOOT         = 0x02,
    PKT_USE_POWER     = 0x03,
    PKT_HEARTBEAT     = 0x0A,
    PKT_UI_STATE      = 0x10,
    PKT_EXECUTE       = 0x11,
    PKT_APPLY_BAD     = 0x12,
    PKT_CLEAR_BAD     = 0x13,
    PKT_GRANT         = 0x14,
    PKT_DENY          = 0x15,
    PKT_GLOBAL_FREEZE = 0x16,
    PKT_GLOBAL_RESUME = 0x17,
    PKT_MATCH_END     = 0x18,
    PKT_COUNTDOWN     = 0x19,
    PKT_HEALTH_UPD    = 0x1A,
    PKT_BULLET_UPD    = 0x1B,
    PKT_SHIELD_ABS    = 0x1C,
    PKT_LAP_UPD       = 0x1E,
    PKT_RACE_LOOKING  = 0x20,
    PKT_RACE_ACCEPT   = 0x21,
    PKT_RACE_SETTINGS = 0x22,
    PKT_READY         = 0x23,
    PKT_START         = 0x24,
};

struct PktHeader {
    PacketType type;
    uint8_t    sender;    // RC_ID
    uint32_t   ts;
};

struct PktDrive {
    PktHeader hdr;
    int8_t    throttle;  // -100 to +100
    int8_t    steering;  // -100 to +100
};

struct PktShoot {
    PktHeader hdr;
};

struct PktUsePower {
    PktHeader hdr;
    PowerType powerType;
};

struct PktRaceLooking {
    PktHeader hdr;
    uint8_t   rcMac[6];
    uint8_t   carMac[6];
};

struct PktRaceAccept {
    PktHeader hdr;
    uint8_t   rcMac[6];
    uint8_t   carMac[6];
};

struct PktRaceSettings {
    PktHeader hdr;
    uint8_t   mode;        // 0=LAP, 1=TIME
    uint8_t   targetLaps;
    uint16_t  timeLimitS;
    uint8_t   tagCount;
};

struct UIState {
    uint8_t  phase;
    uint8_t  mode;
    uint8_t  myHealth;
    uint8_t  oppHealth;
    uint8_t  myBullets;
    uint8_t  myLaps;
    uint8_t  oppLaps;
    uint16_t myScore;
    uint16_t oppScore;
    uint8_t  activePower[4];
    uint8_t  badPower;
    uint16_t countdown;
    uint32_t matchTimeMs;
    uint8_t  flags;
};

struct PktUIState {
    PktHeader hdr;
    UIState   ui;
};

struct PktMatchEnd {
    PktHeader hdr;
    uint8_t   winner;
    uint16_t  p1Score;
    uint16_t  p2Score;
    uint8_t   p1Laps;
    uint8_t   p2Laps;
    uint8_t   p1HealthFinal;
    uint8_t   p2HealthFinal;
};

struct PktApplyBad {
    PktHeader hdr;
    PowerType badType;
    uint32_t  timeoutMs;
};

struct PktCountdown {
    PktHeader hdr;
    uint8_t   tick;
};

struct IncomingPacket {
    uint8_t  senderMac[6];
    uint8_t  data[250];
    uint8_t  len;
};
