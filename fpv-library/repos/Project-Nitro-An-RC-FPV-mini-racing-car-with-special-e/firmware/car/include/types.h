#pragma once
// =============================================================================
//  FPV Racer v2.0 — Car Firmware
//  types.h  — All shared enums, packet structs, and constants
//
//  Compatible with: ESP32 (30-pin), Arduino/PlatformIO framework
//  Networking:      ESP-NOW (no router)
//  Authors:         Generated for Hackclub Fallout Program
// =============================================================================

#include <stdint.h>

// ---------------------------------------------------------------------------
// Compile-time configuration
// ---------------------------------------------------------------------------
#define CAR_ID            1          // 1 = P1, 2 = P2 — set per-board before flash
#define NFC_POLL_MS       100        // PN532 polling interval during race
#define HEARTBEAT_MS      200        // heartbeat + state-sync interval
#define DRIVE_TIMEOUT_MS  300        // declare RC lost if no DRIVE packet received
#define HIT_WINDOW_MS     1500       // valid SHOOT→HIT validation window
#define ACCEL_COOLDOWN_MS 1500       // min ms between crash-damage events
#define LAP_DEBOUNCE_MS   3000       // min ms between LAP-CROSS events per car
#define TAG_COOLDOWN_MS   5000       // min ms before same car can re-trigger same tag
#define TAG_PROXIMITY_MS  800        // GLOBAL-FREEZE if two tags in this window
#define ACCEL_THRESHOLD_G 0.85f      // g-force threshold for crash detection
#define ACCEL_DURATION_MS 20         // must sustain threshold for this long
#define IR_BURST_MS       1000       // duration of IR shot beam
#define IR_FREQUENCY      38000      // 38kHz — TSOP38238 carrier
#define SHOOT_COOLDOWN_MS 500        // min ms between shots
#define HEALTH_FLOOR      5          // minimum health % (KO not implemented)
#define MAX_TAGS          20         // max NFC tags per session
#define MAX_BULLETS       9
#define SESSION_KEY_LEN   16

// ---------------------------------------------------------------------------
// Pin assignments (adjust to your wiring)
// ---------------------------------------------------------------------------
#define PIN_MOTOR_IN1     25
#define PIN_MOTOR_IN2     26
#define PIN_MOTOR_PWM     27
#define PIN_MOTOR_STBY    14
#define PIN_SERVO         13

#define PIN_IR_TX1        32         // Front IR emitter 1
#define PIN_IR_TX2        33         // Front IR emitter 2
#define PIN_IR_RX_REAR1   34         // Rear IR receiver 1 (weapon hit)
#define PIN_IR_RX_REAR2   35         // Rear IR receiver 2 (weapon hit)
#define PIN_IR_RX_SIDE1   36         // Side IR receiver (finish gate)
#define PIN_IR_RX_SIDE2   39         // Side IR receiver (finish gate)

#define PIN_MPU_SDA       21
#define PIN_MPU_SCL       22
#define PIN_MPU_INT       23         // MPU6050 interrupt

#define PIN_NFC_SDA       21         // Shared I2C bus — PN532
#define PIN_NFC_SCL       22

#define PIN_BUZZER        18
#define PIN_LED           19

// Motor PWM LEDC channels
#define LEDC_MOTOR_CH     0
#define LEDC_IR_CH        1
#define LEDC_MOTOR_FREQ   20000      // 20kHz — inaudible
#define LEDC_IR_FREQ      38000
#define LEDC_RES          8          // 8-bit resolution (0-255)

// ---------------------------------------------------------------------------
// State machine phases
// ---------------------------------------------------------------------------
enum CarPhase : uint8_t {
    PHASE_IDLE        = 0,
    PHASE_FREE_DRIVE  = 1,
    PHASE_CONNECTING  = 2,
    PHASE_NFC_SCAN    = 3,   // HOST only: scanning setup tags
    PHASE_LOBBY       = 4,
    PHASE_COUNTDOWN   = 5,
    PHASE_RACING      = 6,
    PHASE_FINISHED    = 7,
};

enum RaceMode : uint8_t {
    MODE_LAP_RACE  = 0,
    MODE_TIME_RACE = 1,
};

// ---------------------------------------------------------------------------
// Power types
// ---------------------------------------------------------------------------
enum PowerType : uint8_t {
    PWR_NONE        = 0,
    // Good powers
    PWR_BOOST       = 1,
    PWR_SHIELD      = 2,
    PWR_REGEN       = 3,
    PWR_BULLETS     = 4,
    // Bad powers
    BAD_SLOWNESS    = 5,
    BAD_RANDOM_CTRL = 6,
    BAD_DAMAGE      = 7,
    BAD_DRIFT       = 8,
    // Special
    PWR_STATION_P1  = 9,
    PWR_STATION_P2  = 10,
};

static inline bool isBadPower(PowerType p) {
    return p >= BAD_SLOWNESS && p <= BAD_DRIFT;
}
static inline bool isGoodPower(PowerType p) {
    return p >= PWR_BOOST && p <= PWR_BULLETS;
}

// ---------------------------------------------------------------------------
// Event types  (used in LogEntry and ESP-NOW packets)
// ---------------------------------------------------------------------------
enum EventType : uint8_t {
    EVT_SHOOT         = 0,
    EVT_HIT           = 1,
    EVT_DAMAGE        = 2,
    EVT_LAP           = 3,
    EVT_TAG           = 4,
    EVT_POWER_GAIN    = 5,
    EVT_POWER_USE     = 6,
    EVT_BAD_POWER     = 7,
    EVT_STATION       = 8,
    EVT_PAUSE         = 9,
    EVT_RESUME        = 10,
    EVT_WIN           = 11,
    EVT_FREEZE        = 12,
    EVT_IMPACT        = 13,
};

// ---------------------------------------------------------------------------
// ESP-NOW packet type tags
// ---------------------------------------------------------------------------
enum PacketType : uint8_t {
    PKT_DRIVE         = 0x01,   // RC → Car  (50Hz)
    PKT_SHOOT         = 0x02,   // RC → Host + own Car
    PKT_USE_POWER     = 0x03,   // RC → Host
    PKT_TAG_DETECTED  = 0x04,   // Car → Host
    PKT_HIT_DETECTED  = 0x05,   // Car → Host
    PKT_LAP_CROSS     = 0x06,   // Car → Host
    PKT_IMPACT        = 0x07,   // Car → Host
    PKT_STATION_DET   = 0x08,   // Car → Host
    PKT_SHOT_FIRED    = 0x09,   // Car → Host (confirms physical TX)
    PKT_HEARTBEAT     = 0x0A,   // Car ↔ Host / RC → Car

    // Host → All
    PKT_UI_STATE      = 0x10,
    PKT_EXECUTE       = 0x11,   // Host → Car: execute good power
    PKT_APPLY_BAD     = 0x12,   // Host → Car + RC: apply bad power
    PKT_CLEAR_BAD     = 0x13,   // Host → Car + RC: cure complete
    PKT_GRANT         = 0x14,   // Host → RC: power collected
    PKT_DENY          = 0x15,   // Host → Car/RC: event rejected
    PKT_GLOBAL_FREEZE = 0x16,   // Host → All: freeze motors
    PKT_GLOBAL_RESUME = 0x17,   // Host → All: unfreeze
    PKT_MATCH_END     = 0x18,   // Host → All
    PKT_COUNTDOWN     = 0x19,   // Host → All: 3-2-1-GO
    PKT_HEALTH_UPD    = 0x1A,   // Host → RC: damage result
    PKT_BULLET_UPD    = 0x1B,   // Host → RC: bullet count
    PKT_SHIELD_ABS    = 0x1C,   // Host → RC: shield absorbed hit
    PKT_CURE_CANCEL   = 0x1D,   // Host → Car + RC: station cure failed
    PKT_LAP_UPD       = 0x1E,   // Host → All: lap count changed

    // Pairing / lobby
    PKT_RACE_LOOKING  = 0x20,
    PKT_RACE_ACCEPT   = 0x21,
    PKT_RACE_SETTINGS = 0x22,
    PKT_READY         = 0x23,
    PKT_START         = 0x24,
    PKT_NFC_TABLE     = 0x25,   // Host → Client: encrypted token table
    PKT_NFC_ACK       = 0x26,   // Client → Host: table received OK
};

// ---------------------------------------------------------------------------
// ESP-NOW packet structs  (keep all ≤ 250 bytes — ESP-NOW limit)
// ---------------------------------------------------------------------------

// Header at start of every packet
struct PktHeader {
    PacketType type;
    uint8_t    sender;   // CAR_ID of originator
    uint32_t   ts;       // millis() timestamp at send
};

struct PktDrive {
    PktHeader hdr;       // type = PKT_DRIVE
    int8_t    throttle;  // -100 to +100
    int8_t    steering;  // -100 to +100
};

struct PktShoot {
    PktHeader hdr;       // type = PKT_SHOOT
    // sender in hdr identifies which car
};

struct PktTagDetected {
    PktHeader  hdr;      // type = PKT_TAG_DETECTED
    uint8_t    token[16];
    PowerType  powerType;
};

struct PktHitDetected {
    PktHeader hdr;       // type = PKT_HIT_DETECTED
    // sender in hdr identifies victim
};

struct PktLapCross {
    PktHeader hdr;       // type = PKT_LAP_CROSS
};

struct PktImpact {
    PktHeader hdr;       // type = PKT_IMPACT
    float     gForce;
};

struct PktStationDetected {
    PktHeader  hdr;      // type = PKT_STATION_DET
    PowerType  stationType; // PWR_STATION_P1 or PWR_STATION_P2
};

struct PktUsePower {
    PktHeader hdr;       // type = PKT_USE_POWER
    PowerType powerType;
};

struct PktExecute {
    PktHeader hdr;       // type = PKT_EXECUTE
    PowerType powerType;
    uint32_t  durationMs; // for timed powers (BOOST=3000, SHIELD=5000-8000)
};

struct PktApplyBad {
    PktHeader hdr;       // type = PKT_APPLY_BAD
    PowerType badType;
    uint32_t  timeoutMs; // fallback auto-cure timeout
};

struct PktHealthUpdate {
    PktHeader hdr;       // type = PKT_HEALTH_UPD
    uint8_t   p1Health;
    uint8_t   p2Health;
    int8_t    delta;     // signed change this event
    uint8_t   victim;    // 1 or 2
};

// Full UIState broadcast every 200ms from host
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
    uint8_t  activePower[4]; // inventory slots (PowerType)
    uint8_t  badPower;       // PowerType
    uint16_t countdown;      // seconds remaining (time race) or countdown ticks
    uint32_t matchTimeMs;
    uint8_t  flags;          // bit0=shield, bit1=paused, bit2=frozen, bit3=ready
};

struct PktUIState {
    PktHeader hdr;       // type = PKT_UI_STATE
    UIState   ui;
};

struct PktMatchEnd {
    PktHeader hdr;       // type = PKT_MATCH_END
    uint8_t   winner;    // 1 or 2
    uint16_t  p1Score;
    uint16_t  p2Score;
    uint8_t   p1Laps;
    uint8_t   p2Laps;
    uint8_t   p1HealthFinal;
    uint8_t   p2HealthFinal;
};

struct PktCountdown {
    PktHeader hdr;       // type = PKT_COUNTDOWN
    uint8_t   tick;      // 3, 2, 1, 0 (0 = GO)
};

// NFC table sent from host to client after setup phase
// Each entry: token (16 bytes) + power type
struct NfcTableEntry {
    uint8_t   token[16];
    PowerType power;
    uint8_t   uid[7];    // original tag UID
    uint8_t   uidLen;
};

struct PktNfcTable {
    PktHeader    hdr;    // type = PKT_NFC_TABLE
    uint8_t      count;
    NfcTableEntry entries[MAX_TAGS];
};

// ---------------------------------------------------------------------------
// Master game structs  (host RAM only)
// ---------------------------------------------------------------------------
struct PlayerState {
    uint8_t   health;           // 0-100
    uint8_t   bullets;          // 0-9
    uint8_t   laps;
    uint16_t  score;
    bool      shieldActive;
    uint32_t  shieldExpiryMs;
    PowerType badPower;         // PWR_NONE if none active
    uint32_t  badPowerExpiryMs; // fallback auto-cure
    PowerType inventory[4];     // good power slots
    uint32_t  lastLapMs;        // for lap debounce
    uint32_t  lastImpactMs;     // for accel cooldown
    uint32_t  shootWindowMs;    // timestamp of last SHOOT — hit validation
    bool      stationCuring;    // true if cure timer running
    uint32_t  stationCureStartMs;
    float     stationCureDurationMs;
};

struct MatchState {
    CarPhase   phase;
    RaceMode   mode;
    uint8_t    targetLaps;
    uint32_t   timeLimitMs;
    uint32_t   matchStartMs;
    PlayerState p[2];           // p[0]=P1, p[1]=P2
};

struct NfcTag {
    uint8_t   token[16];
    PowerType power;
    uint32_t  lastTriggerByP1Ms;
    uint32_t  lastTriggerByP2Ms;
};

// Log entry (append to SD card on host)
struct LogEntry {
    uint32_t  t;
    EventType eventType;
    uint8_t   actor;    // 1 or 2
    uint8_t   target;   // 1, 2, or 0
    uint8_t   value1;
    uint8_t   value2;
};
