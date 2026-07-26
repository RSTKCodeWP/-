// =============================================================================
//  main.cpp — FPV Racer v2.0 Car Firmware
//
//  ESP32 dual-core task layout:
//
//    Core 0 (app_cpu):  setup(), loop()
//      • ESP-NOW packet dispatch
//      • Host logic / client logic (game state)
//      • NFC polling (100ms)
//      • Accelerometer processing
//      • UIState broadcast (host, 200ms)
//      • Phase state machine
//
//    Core 1 (pro_cpu):  driveTask
//      • Motor + servo (consumes DriveCmd queue, 50Hz)
//      • IR TX (on semaphore signal)
//      • IR RX polling (continuous)
//      • Lap-gate IR polling (continuous)
//
//  FreeRTOS primitives:
//    xQueueDriveCmd   — Core 0 → Core 1: (throttle, steering)
//    xSemaphoreIrFire — Core 0 → Core 1: fire IR burst
//    xQueueRxPkts     — ESP-NOW ISR → Core 0: raw incoming packets
//
// =============================================================================

#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>

#include "types.h"
#include "hardware.h"
#include "comms.h"
#include "host_logic.h"
#include "client_logic.h"

// ---------------------------------------------------------------------------
// Determine role at compile time
// ---------------------------------------------------------------------------
// CAR_ID is defined in types.h (1 or 2, set per board before flashing)
// Role assignment happens during pairing: first to receive RACE_LOOKING wins HOST
// We track runtime role in g_isHost.
static bool g_isHost = false;

// ---------------------------------------------------------------------------
// FreeRTOS handles
// ---------------------------------------------------------------------------

struct DriveCmd { int8_t throttle; int8_t steering; };

static QueueHandle_t  xQueueDriveCmd;
static SemaphoreHandle_t xSemaphoreIrFire;

// ---------------------------------------------------------------------------
// Global phase (shared, but only written from Core 0)
// ---------------------------------------------------------------------------

static volatile CarPhase g_phase       = PHASE_IDLE;
static volatile bool     g_rcConnected = false;
static uint32_t          g_lastNfcMs   = 0;
static uint32_t          g_lastStationMs = 0; // debounce station-lost detection
static uint8_t           g_ownMac[6];

// ---------------------------------------------------------------------------
// Core 1 Drive Task
//   Priority: high (configMAX_PRIORITIES - 1)
//   Stack:    4096 bytes
// ---------------------------------------------------------------------------

void driveTask(void* pvParameters) {
    hw_motor_init();
    hw_ir_rx_init();

    DriveCmd cmd = {0, 0};

    while (true) {
        // ── Apply drive command ─────────────────────────────────────────────
        if (xQueueReceive(xQueueDriveCmd, &cmd, 0) == pdTRUE) {
            // Drive modifiers are applied inside client_apply_drive()
            // (host car calls same path — it is also a driveable car)
            if (g_isHost) {
                // Host car applies modifiers locally too
                // (host PlayerState bad power is checked in client modifier logic
                //  since the host car physically executes drive the same way)
                hw_motor_set(client_throttle_modified(cmd.throttle));
                hw_servo_set(client_steering_modified(cmd.steering));
            } else {
                client_apply_drive(cmd.throttle, cmd.steering);
            }
        }

        // ── IR fire on semaphore ────────────────────────────────────────────
        if (xSemaphoreTake(xSemaphoreIrFire, 0) == pdTRUE) {
            hw_ir_fire(); // blocks for IR_BURST_MS ms — acceptable on Core 1
        }

        // ── IR rear-hit detection ───────────────────────────────────────────
        if (hw_ir_rear_hit_pending()) {
            // Signal Core 0 via a minimal queue
            // (reuse DriveCmd queue slot won't work — use a flag instead)
            // Simple atomic flag — Core 0 polls it
            extern volatile bool g_hitPending;
            g_hitPending = true;
        }

        // ── Lap gate IR detection ───────────────────────────────────────────
        if (hw_ir_lap_pending()) {
            extern volatile bool g_lapPending;
            g_lapPending = true;
        }

        vTaskDelay(pdMS_TO_TICKS(20)); // 50Hz drive loop
    }
}

// ---------------------------------------------------------------------------
// Shared flags (Core 1 sets, Core 0 clears)
// ---------------------------------------------------------------------------

volatile bool g_hitPending = false;
volatile bool g_lapPending = false;

// ---------------------------------------------------------------------------
// Pairing state machine (run inside loop() during CONNECTING phase)
// ---------------------------------------------------------------------------

static uint8_t g_oppMac[6]    = {0};
static uint8_t g_oppRcMac[6]  = {0};
static uint8_t g_ownRcMac[6]  = {0};
static bool    g_peersKnown   = false;

static void run_pairing() {
    static uint32_t lookingStart = 0;
    if (lookingStart == 0) {
        lookingStart = millis();
        comms_start_looking();
        Serial.println("[PAIR] Broadcasting RACE_LOOKING...");
    }

    // Did we receive a RACE_LOOKING from another car?
    uint8_t senderMac[6];
    if (comms_got_looking(senderMac)) {
        // First to see a peer: if we have no opponent yet, accept
        if (!g_peersKnown) {
            memcpy(g_oppMac, senderMac, 6);
            comms_stop_looking();
            comms_add_peer(PEER_OPP_CAR, g_oppMac);
            comms_send_accept(g_oppMac);

            // The car that sends ACCEPT becomes HOST
            g_isHost = true;
            Serial.println("[PAIR] Sent ACCEPT — we are HOST");
            g_peersKnown = true;
            g_phase      = PHASE_LOBBY;

            if (g_isHost) {
                host_init();
                // Move to NFC setup scan
                Serial.println("[HOST] Starting NFC tag scan...");
                host_nfc_setup_begin(10); // scan up to 10 tags
                g_phase = PHASE_NFC_SCAN;
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Core 0 packet dispatcher
// Called every loop() for each packet in the ESP-NOW receive queue
// ---------------------------------------------------------------------------

static void dispatch_packet(const IncomingPacket& pkt) {
    if (pkt.len < sizeof(PktHeader)) return;
    const PktHeader* hdr = reinterpret_cast<const PktHeader*>(pkt.data);
    comms_heartbeat_update(hdr->sender == CAR_ID ? PEER_OWN_RC : PEER_OPP_CAR);

    // ── Track RC MAC on first DRIVE packet ─────────────────────────────────
    if (hdr->type == PKT_DRIVE && !g_rcConnected) {
        memcpy(g_ownRcMac, pkt.senderMac, 6);
        comms_add_peer(PEER_OWN_RC, g_ownRcMac);
        g_rcConnected = true;
        Serial.println("[MAIN] Own RC connected");
    }

    switch (hdr->type) {

        // ── Drive input from own RC ─────────────────────────────────────────
        case PKT_DRIVE: {
            if (g_phase != PHASE_RACING && g_phase != PHASE_FREE_DRIVE) break;
            const PktDrive* d = reinterpret_cast<const PktDrive*>(pkt.data);
            DriveCmd cmd = { d->throttle, d->steering };
            xQueueOverwrite(xQueueDriveCmd, &cmd); // always take latest
            comms_heartbeat_update(PEER_OWN_RC);
            break;
        }

        // ── RC pressed SHOOT ────────────────────────────────────────────────
        case PKT_SHOOT: {
            if (g_phase != PHASE_RACING) break;
            bool ok = false;
            if (g_isHost) {
                ok = host_on_shoot(CAR_ID, hdr->ts);
            } else {
                // Forward to host — host validates and relays EXECUTE back
                comms_send(PEER_OPP_CAR, pkt.data, pkt.len);
                ok = true; // optimistic — host may deny
            }
            if (ok) {
                // Signal Core 1 to fire IR burst
                xSemaphoreGive(xSemaphoreIrFire);
            }
            break;
        }

        // ── RC pressed USE-POWER ────────────────────────────────────────────
        case PKT_USE_POWER: {
            if (g_phase != PHASE_RACING) break;
            const PktUsePower* u = reinterpret_cast<const PktUsePower*>(pkt.data);
            if (g_isHost) {
                host_on_use_power(CAR_ID, u->powerType);
            } else {
                comms_send(PEER_OPP_CAR, pkt.data, pkt.len);
            }
            break;
        }

        // ── Events received by HOST from client car ─────────────────────────
        case PKT_HIT_DETECTED: {
            if (!g_isHost) break;
            host_on_hit_detected(hdr->sender, hdr->ts);
            break;
        }
        case PKT_TAG_DETECTED: {
            if (!g_isHost) break;
            const PktTagDetected* t = reinterpret_cast<const PktTagDetected*>(pkt.data);
            host_on_tag_detected(hdr->sender, t->token, t->powerType, hdr->ts);
            break;
        }
        case PKT_LAP_CROSS: {
            if (!g_isHost) break;
            host_on_lap_cross(hdr->sender, hdr->ts);
            break;
        }
        case PKT_IMPACT: {
            if (!g_isHost) break;
            const PktImpact* im = reinterpret_cast<const PktImpact*>(pkt.data);
            host_on_impact(hdr->sender, im->gForce, hdr->ts);
            break;
        }
        case PKT_STATION_DET: {
            if (!g_isHost) break;
            const PktStationDetected* s = reinterpret_cast<const PktStationDetected*>(pkt.data);
            host_on_station_present(hdr->sender, s->stationType);
            g_lastStationMs = millis();
            break;
        }

        // ── Events received by CLIENT car from host ─────────────────────────
        case PKT_EXECUTE: {
            if (g_isHost) break; // host handles its own car internally
            client_on_execute(reinterpret_cast<const PktExecute*>(pkt.data));
            break;
        }
        case PKT_APPLY_BAD: {
            client_on_apply_bad(reinterpret_cast<const PktApplyBad*>(pkt.data));
            break;
        }
        case PKT_CLEAR_BAD: {
            client_on_clear_bad(PWR_NONE); // clear whatever is active
            break;
        }
        case PKT_GLOBAL_FREEZE: {
            hw_motor_kill();
            break;
        }
        case PKT_GLOBAL_RESUME: {
            hw_motor_enable();
            break;
        }
        case PKT_COUNTDOWN: {
            const PktCountdown* cd = reinterpret_cast<const PktCountdown*>(pkt.data);
            client_on_countdown(cd->tick);
            if (cd->tick == 0) g_phase = PHASE_RACING;
            break;
        }
        case PKT_MATCH_END: {
            const PktMatchEnd* me = reinterpret_cast<const PktMatchEnd*>(pkt.data);
            client_on_match_end(me);
            g_phase = PHASE_FINISHED;
            break;
        }
        case PKT_UI_STATE: {
            const PktUIState* us = reinterpret_cast<const PktUIState*>(pkt.data);
            client_on_ui_state(&us->ui);
            break;
        }
        case PKT_NFC_TABLE: {
            // Client receives NFC table from host during setup
            if (!g_isHost) {
                client_receive_nfc_table(reinterpret_cast<const PktNfcTable*>(pkt.data));
                g_phase = PHASE_LOBBY;
            }
            break;
        }
        case PKT_NFC_ACK: {
            // Host sees client acknowledged NFC table
            if (g_isHost) {
                Serial.println("[HOST] Client confirmed NFC table received");
                g_phase = PHASE_LOBBY;
                // Here you'd wait for RC button press to start race
            }
            break;
        }
        case PKT_RACE_LOOKING: {
            if (g_phase == PHASE_CONNECTING) {
                // Handled by comms_got_looking() — already queued internally
            }
            break;
        }
        case PKT_RACE_ACCEPT: {
            // We are the client (they sent accept, they became host)
            if (!g_peersKnown) {
                memcpy(g_oppMac, pkt.senderMac, 6);
                comms_stop_looking();
                comms_add_peer(PEER_OPP_CAR, g_oppMac);
                g_isHost     = false;
                g_peersKnown = true;
                g_phase      = PHASE_LOBBY;
                client_init();
                Serial.println("[PAIR] ACCEPT received — we are CLIENT");
            }
            break;
        }

        // ── Shoot forwarded from client RC to host ──────────────────────────
        // (handled above in PKT_SHOOT case — host validates)

        default:
            break;
    }
}

// ---------------------------------------------------------------------------
// NFC polling (Core 0, called from loop)
// ---------------------------------------------------------------------------

static void poll_nfc() {
    uint32_t nowMs = millis();
    if (nowMs - g_lastNfcMs < NFC_POLL_MS) return;
    g_lastNfcMs = nowMs;

    uint8_t token[16], uid[7];
    uint8_t uidLen = 0;

    if (hw_nfc_poll(token, uid, &uidLen)) {
        if (g_phase == PHASE_NFC_SCAN && g_isHost) {
            // Setup scan: register this physical tag
            host_nfc_register_tag(uid, uidLen);

        } else if (g_phase == PHASE_RACING) {
            // Determine if it's a power tag or a station tag
            // Station tags have a well-known UID byte pattern set during track setup
            // For now we check the token's power byte after decrypt
            uint8_t plain[16];
            // TODO: pass session key from host_logic — for algorithm clarity use a stub
            // In real firmware: crypto_xor(token, g_sessionKey, plain);
            memcpy(plain, token, 16); // placeholder

            PowerType power = (PowerType)plain[8];

            if (power == PWR_STATION_P1 || power == PWR_STATION_P2) {
                // Station tag — report continuously until car leaves
                if (g_isHost) {
                    host_on_station_present(CAR_ID, power);
                    g_lastStationMs = nowMs;
                } else {
                    client_forward_station(power);
                    g_lastStationMs = nowMs;
                }
            } else {
                // Power tag
                if (g_isHost) {
                    host_on_tag_detected(CAR_ID, token, power, nowMs);
                } else {
                    client_forward_tag(token, power);
                }
            }
        }
    } else {
        // No tag seen — detect station-lost after 500ms silence
        if (g_lastStationMs != 0 && (nowMs - g_lastStationMs) > 500) {
            g_lastStationMs = 0;
            if (g_isHost) {
                host_on_station_lost(CAR_ID);
            }
            // Client: host detects station-lost via silence of PKT_STATION_DET
        }
    }
}

// ---------------------------------------------------------------------------
// Accelerometer polling (Core 0, interrupt-driven via flag)
// ---------------------------------------------------------------------------

static volatile bool g_accelPending = false;
static float         g_accelGforce  = 0.0f;
static uint32_t      g_accelStart   = 0;

void IRAM_ATTR accel_isr() {
    // ISR: just set a flag, Core 0 reads the value
    g_accelPending = true;
}

static void poll_accel() {
    if (!g_accelPending) return;
    g_accelPending = false;

    float g = hw_accel_read_g();

    if (g >= ACCEL_THRESHOLD_G) {
        if (g_accelStart == 0) {
            g_accelStart = millis();
            g_accelGforce = g;
        } else {
            // Keep max G during window
            if (g > g_accelGforce) g_accelGforce = g;
            if ((millis() - g_accelStart) >= ACCEL_DURATION_MS) {
                // Sustained threshold — confirmed impact
                g_accelStart = 0;
                if (g_isHost) {
                    host_on_impact(CAR_ID, g_accelGforce, millis());
                } else {
                    client_forward_impact(g_accelGforce);
                }
                g_accelGforce = 0;
            }
        }
    } else {
        g_accelStart  = 0; // reset if G drops below threshold
        g_accelGforce = 0;
    }
}

// ---------------------------------------------------------------------------
// NFC setup scan completion check (HOST, PHASE_NFC_SCAN)
// ---------------------------------------------------------------------------

static bool g_nfcDone = false;

static void check_nfc_setup_done() {
    if (!g_isHost || g_phase != PHASE_NFC_SCAN) return;
    // Manual trigger: RC sends a "done scanning" button press
    // For the algorithm we auto-complete once no new tag is seen for 3s
    static uint32_t lastNewTagMs = 0;
    static uint8_t  lastTagCount = 0;

    uint8_t cur = host_nfc_tag_count();
    if (cur != lastTagCount) {
        lastTagCount = cur;
        lastNewTagMs = millis();
    }

    if (cur > 0 && (millis() - lastNewTagMs) > 3000 && !g_nfcDone) {
        g_nfcDone = true;
        host_nfc_send_table();
        Serial.printf("[HOST] NFC setup done. %d tags registered.\n", cur);
        g_phase = PHASE_LOBBY;
    }
}

// ---------------------------------------------------------------------------
// setup()
// ---------------------------------------------------------------------------

void setup() {
    Serial.begin(115200);
    Serial.printf("\n[BOOT] FPV Racer v2.0 — CAR %d\n", CAR_ID);

    // Hardware init
    hw_accel_init();
    hw_nfc_init();
    pinMode(PIN_MPU_INT, INPUT);
    attachInterrupt(digitalPinToInterrupt(PIN_MPU_INT), accel_isr, RISING);

    // Comms init — ESP-NOW
    comms_init(g_ownMac);
    Serial.printf("[BOOT] MAC: %02X:%02X:%02X:%02X:%02X:%02X\n",
                  g_ownMac[0], g_ownMac[1], g_ownMac[2],
                  g_ownMac[3], g_ownMac[4], g_ownMac[5]);

    // Client logic always init (host car runs both host_logic + client_logic
    // for its own drive modifiers)
    client_init();

    // FreeRTOS primitives
    xQueueDriveCmd    = xQueueCreate(1, sizeof(DriveCmd));   // depth 1 — only latest
    xSemaphoreIrFire  = xSemaphoreCreateBinary();

    // Start Core 1 drive task
    xTaskCreatePinnedToCore(
        driveTask,          // task function
        "driveTask",        // name
        4096,               // stack bytes
        nullptr,            // params
        configMAX_PRIORITIES - 1, // priority
        nullptr,            // handle
        1                   // Core 1
    );

    g_phase = PHASE_CONNECTING;
    comms_start_looking();
    Serial.println("[BOOT] Setup complete. Waiting for peer...");
}

// ---------------------------------------------------------------------------
// loop() — Core 0
// ---------------------------------------------------------------------------

void loop() {
    uint32_t nowMs = millis();

    // ── 1. Drain ESP-NOW receive queue ──────────────────────────────────────
    IncomingPacket pkt;
    while (comms_recv(&pkt)) {
        dispatch_packet(pkt);
    }

    // ── 2. Phase-specific logic ─────────────────────────────────────────────
    switch (g_phase) {

        case PHASE_CONNECTING:
            run_pairing();
            break;

        case PHASE_NFC_SCAN:
            poll_nfc();
            check_nfc_setup_done();
            break;

        case PHASE_LOBBY:
            // Wait for race-start signal from RC
            // (RC sends PKT_SHOOT with a special "start" flag, or a dedicated button)
            // For clarity: host starts race automatically once both sides are LOBBY
            if (g_isHost && g_peersKnown && !g_nfcDone) {
                // NFC setup was skipped (e.g. free drive) — just start
            }
            // Actual race-start is triggered by host_start_race() from RC command
            break;

        case PHASE_FREE_DRIVE:
            // RC drives its paired car with no game logic
            break;

        case PHASE_RACING:
            // NFC polling
            poll_nfc();

            // Accelerometer
            poll_accel();

            // Core 1 flags: hit and lap
            if (g_hitPending) {
                g_hitPending = false;
                if (g_isHost) {
                    host_on_hit_detected(CAR_ID, nowMs);
                } else {
                    client_forward_hit();
                }
            }

            if (g_lapPending) {
                g_lapPending = false;
                if (g_isHost) {
                    host_on_lap_cross(CAR_ID, nowMs);
                } else {
                    client_forward_lap();
                }
            }

            // Host periodic tick (state timers, UIState broadcast)
            if (g_isHost) {
                host_tick(nowMs);
            } else {
                client_tick(nowMs);
            }
            break;

        case PHASE_FINISHED:
            // Sit idle — display results handled by RC
            break;

        default:
            break;
    }

    // Yield to FreeRTOS — do not busy-spin unnecessarily
    vTaskDelay(1);
}
