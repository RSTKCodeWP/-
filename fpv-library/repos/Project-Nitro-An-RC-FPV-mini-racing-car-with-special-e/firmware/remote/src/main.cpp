// =============================================================================
//  main.cpp — FPV Racer v2.0 RC Firmware
//
//  ESP32 30-pin, 2.8" ILI9341 TFT (SPI), 12 buttons
//
//  Core 0 (app_cpu): loop() — ESP-NOW receive, phase state machine,
//                             button events, display updates
//  Core 1 (pro_cpu): driveTask — 50Hz drive packet sender
//
//  Power-on sequence:
//    1. MCU wakes → PWR_LATCH HIGH (holds own power via P-MOSFET)
//    2. Splash screen
//    3. Attempt to connect to paired car (stored MAC in NVS)
//    4. RC_IDLE / RC_FREE_DRIVE
//    5. CONNECT button → RC_LOOKING → pairing → lobby → race
// =============================================================================

#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <Preferences.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>

#include "rc_types.h"
#include "buttons.h"
#include "rc_display.h"

// ---------------------------------------------------------------------------
// Global state
// ---------------------------------------------------------------------------
static RCPhase      g_phase       = RC_IDLE;
static RCGameState  g_gs          = {};
static bool         g_carConnected= false;
static bool         g_isHost      = false; // RC paired to host car?

// Peer MACs
static uint8_t g_ownMac[6]    = {};
static uint8_t g_carMac[6]    = {};      // paired car
static uint8_t g_oppCarMac[6] = {};      // opponent car (host for validation)
static uint8_t g_oppRcMac[6]  = {};      // opponent RC
static bool    g_peersKnown   = false;

// Lobby settings (host RC only)
static uint8_t  g_lobbyMode  = 0;   // 0=LAP, 1=TIME
static uint8_t  g_lobbyLaps  = 5;
static uint16_t g_lobbyTimeSec = 180;
static uint8_t  g_lobbyTags  = 10;
static bool     g_myReady    = false;
static bool     g_oppReady   = false;

// Battery %
static uint8_t  g_battPct    = 100;

// Match end packet
static PktMatchEnd g_matchEnd = {};

// ---------------------------------------------------------------------------
// FreeRTOS
// ---------------------------------------------------------------------------
static QueueHandle_t     xRxQueue;      // ESP-NOW → Core 0
static SemaphoreHandle_t xDriveSem;     // Core 0 → Core 1: ok to send drive

// Drive command (written by Core 0, read by Core 1)
static volatile int8_t g_driveThrottle = 0;
static volatile int8_t g_driveSteering = 0;

// Last shoot time
static uint32_t g_lastShootMs = 0;

// Looking animation
static uint8_t  g_lookingDot  = 0;
static uint32_t g_lookingMs   = 0;
static uint32_t g_lookingStartMs = 0;

// NFC setup state (mirrored from car via UI updates)
static uint8_t g_nfcDone  = 0;
static uint8_t g_nfcTotal = 10;

// ---------------------------------------------------------------------------
// ESP-NOW helpers
// ---------------------------------------------------------------------------

static esp_now_peer_info_t s_peer = {};

static void espnow_add_peer(const uint8_t* mac) {
    memcpy(s_peer.peer_addr, mac, 6);
    s_peer.channel = 0;
    s_peer.encrypt = false;
    if (!esp_now_is_peer_exist(mac))
        esp_now_add_peer(&s_peer);
}

static void espnow_send(const uint8_t* mac, const void* data, size_t len) {
    if (esp_now_is_peer_exist(mac))
        esp_now_send(mac, (const uint8_t*)data, len);
}

static void espnow_broadcast(const void* data, size_t len) {
    // ESP-NOW broadcast MAC
    static const uint8_t bcast[6] = {0xFF,0xFF,0xFF,0xFF,0xFF,0xFF};
    esp_now_send(bcast, (const uint8_t*)data, len);
}

// ESP-NOW receive ISR — enqueue raw packet
static void on_recv(const uint8_t* mac, const uint8_t* data, int len) {
    IncomingPacket pkt;
    memcpy(pkt.senderMac, mac, 6);
    pkt.len = (len > 250) ? 250 : len;
    memcpy(pkt.data, data, pkt.len);
    xQueueSendFromISR(xRxQueue, &pkt, nullptr);
}

// ---------------------------------------------------------------------------
// Battery ADC (read when buttons known idle)
// ---------------------------------------------------------------------------
static uint8_t read_battery_pct() {
    // Voltage divider: 100kΩ + 100kΩ → pin 34, Vref 3.3V
    // LiPo: 4.2V = 100%, 3.0V = 0%
    // At pin: 4.2V → 2.1V → ADC = 2610; 3.0V → 1.5V → ADC = 1861
    int raw = analogRead(PIN_BATT_ADC);
    int mv  = (int)((long)raw * 3300 / 4095) * 2; // × 2 for divider
    int pct = (mv - 3000) * 100 / (4200 - 3000);
    return (uint8_t)constrain(pct, 0, 100);
}

// ---------------------------------------------------------------------------
// Send drive packet (called from Core 1 driveTask at 50Hz)
// ---------------------------------------------------------------------------
static void send_drive(int8_t thr, int8_t str) {
    if (!g_carConnected) return;
    if (g_phase != RC_RACING && g_phase != RC_FREE_DRIVE) return;
    PktDrive pkt;
    pkt.hdr = { PKT_DRIVE, RC_ID, (uint32_t)millis() };
    pkt.throttle = thr;
    pkt.steering = str;
    espnow_send(g_carMac, &pkt, sizeof(pkt));
}

// ---------------------------------------------------------------------------
// Core 1 — Drive Task (50Hz)
// ---------------------------------------------------------------------------
static void driveTask(void* pv) {
    while (true) {
        int8_t thr = 0, str = 0;

        // Read held buttons for throttle
        if (buttons_held(BTN_ID_UP))    thr =  80;
        if (buttons_held(BTN_ID_DOWN))  thr = -60;
        if (buttons_held(BTN_ID_LEFT))  str = -80;
        if (buttons_held(BTN_ID_RIGHT)) str =  80;

        // Diagonal combination — reduce throttle for tighter turns
        if (str != 0 && thr != 0) thr = (int8_t)(thr * 80 / 100);

        g_driveThrottle = thr;
        g_driveSteering = str;
        send_drive(thr, str);

        vTaskDelay(pdMS_TO_TICKS(DRIVE_RATE_MS)); // 50Hz
    }
}

// ---------------------------------------------------------------------------
// Packet dispatcher (Core 0)
// ---------------------------------------------------------------------------
static void dispatch(const IncomingPacket& raw) {
    if (raw.len < sizeof(PktHeader)) return;
    const PktHeader* hdr = (const PktHeader*)raw.data;
    uint32_t now = millis();

    switch (hdr->type) {

        // ── UI state from host car — primary game state update ─────────────
        case PKT_UI_STATE: {
            const PktUIState* us = (const PktUIState*)raw.data;
            bool hpChanged  = (us->ui.myHealth  != g_gs.myHealth  ||
                               us->ui.oppHealth != g_gs.oppHealth);
            bool lapChanged = (us->ui.myLaps    != g_gs.myLaps);
            bool invChanged = false;
            for (int i = 0; i < 4; i++)
                if ((PowerType)us->ui.activePower[i] != g_gs.inventory[i])
                    invChanged = true;
            bool badChanged = (us->ui.badPower != (uint8_t)g_gs.badPower);
            bool timChanged = (us->ui.countdown != g_gs.countdown);

            // Copy state
            g_gs.myHealth  = us->ui.myHealth;
            g_gs.oppHealth = us->ui.oppHealth;
            g_gs.myBullets = us->ui.myBullets;
            g_gs.myLaps    = us->ui.myLaps;
            g_gs.oppLaps   = us->ui.oppLaps;
            g_gs.myScore   = us->ui.myScore;
            g_gs.oppScore  = us->ui.oppScore;
            g_gs.badPower  = (PowerType)us->ui.badPower;
            g_gs.countdown = us->ui.countdown;
            g_gs.matchTimeMs = us->ui.matchTimeMs;
            g_gs.flags     = us->ui.flags;
            for (int i = 0; i < 4; i++)
                g_gs.inventory[i] = (PowerType)us->ui.activePower[i];

            if (hpChanged)  display_dirty_hp();
            if (invChanged) display_dirty_powers();
            if (badChanged) display_dirty_bad();
            if (timChanged || lapChanged) display_dirty_header();
            break;
        }

        // ── Health update ───────────────────────────────────────────────────
        case PKT_HEALTH_UPD: {
            struct { PktHeader h; uint8_t p1hp; uint8_t p2hp; int8_t delta; uint8_t victim; } *hu =
                (decltype(hu))raw.data;
            g_gs.myHealth  = (RC_ID == 1) ? hu->p1hp : hu->p2hp;
            g_gs.oppHealth = (RC_ID == 1) ? hu->p2hp : hu->p1hp;
            display_dirty_hp();

            // Log message
            char msg[32];
            if (hu->delta < 0) {
                snprintf(msg, sizeof(msg), "HIT -%d HP!", -hu->delta);
                display_push_log(msg);
                // Buzzer beep — TODO: hw_buzzer_beep(400, 100)
            } else {
                snprintf(msg, sizeof(msg), "REGEN +%d HP", hu->delta);
                display_push_log(msg);
            }
            break;
        }

        // ── Bullet count update ─────────────────────────────────────────────
        case PKT_BULLET_UPD: {
            // Bullets embedded in next UIState; force redraw now
            display_dirty_powers();
            break;
        }

        // ── Power granted (tag pickup) ──────────────────────────────────────
        case PKT_GRANT: {
            display_dirty_powers();
            display_push_log("TAG! Power gained");
            // Buzzer: 1000Hz 80ms — TODO
            break;
        }

        // ── Host denied event ───────────────────────────────────────────────
        case PKT_DENY: {
            display_push_log("Action DENIED");
            // Buzzer: 200Hz 200ms — TODO
            break;
        }

        // ── Shield absorbed ─────────────────────────────────────────────────
        case PKT_SHIELD_ABS: {
            display_push_log("SHIELD absorbed hit!");
            display_dirty_hp();
            break;
        }

        // ── Apply bad power ─────────────────────────────────────────────────
        case PKT_APPLY_BAD: {
            const PktApplyBad* ab = (const PktApplyBad*)raw.data;
            g_gs.badPower = ab->badType;
            display_set_bad_timer(ab->timeoutMs);
            display_dirty_bad();
            char msg[32];
            snprintf(msg, sizeof(msg), "BAD: %s!", power_name_rc(ab->badType));
            display_push_log(msg);
            // Buzzer: 300Hz 400ms — TODO
            break;
        }

        // ── Clear bad power ─────────────────────────────────────────────────
        case PKT_CLEAR_BAD: {
            g_gs.badPower = PWR_NONE;
            display_set_bad_timer(0);
            display_dirty_bad();
            display_push_log("Bad power CURED");
            break;
        }

        // ── Execute good power (feedback only — car does the physics) ────────
        case PKT_EXECUTE: {
            struct { PktHeader h; uint8_t pwr; uint32_t dur; } *ex = (decltype(ex))raw.data;
            char msg[32];
            snprintf(msg, sizeof(msg), "POWER: %s!", power_name_rc((PowerType)ex->pwr));
            display_push_log(msg);
            display_dirty_powers();
            break;
        }

        // ── Global freeze ────────────────────────────────────────────────────
        case PKT_GLOBAL_FREEZE: {
            g_gs.flags |= 0x04;
            display_dirty_full();
            display_push_log("!! FROZEN !!");
            break;
        }
        case PKT_GLOBAL_RESUME: {
            g_gs.flags &= ~0x04;
            display_dirty_full();
            display_push_log("Resumed");
            break;
        }

        // ── Countdown from host ───────────────────────────────────────────────
        case PKT_COUNTDOWN: {
            const PktCountdown* cd = (const PktCountdown*)raw.data;
            g_phase = RC_COUNTDOWN;
            display_countdown(cd->tick);
            if (cd->tick == 0) {
                g_phase = RC_RACING;
                g_gs.phase = 6;
                display_force_full_redraw();
            }
            break;
        }

        // ── Lap update ───────────────────────────────────────────────────────
        case PKT_LAP_UPD: {
            display_dirty_header();
            display_push_log("LAP complete +10");
            break;
        }

        // ── Match end ────────────────────────────────────────────────────────
        case PKT_MATCH_END: {
            g_matchEnd = *(const PktMatchEnd*)raw.data;
            g_phase = RC_FINISHED;
            display_results(&g_matchEnd, RC_ID);
            break;
        }

        // ── Pairing: opponent RC is looking ──────────────────────────────────
        case PKT_RACE_LOOKING: {
            if (g_phase != RC_IDLE && g_phase != RC_FREE_DRIVE) break;
            const PktRaceLooking* lk = (const PktRaceLooking*)raw.data;
            // Show "Accept?" prompt — store their mac
            memcpy(g_oppRcMac, lk->rcMac, 6);
            memcpy(g_oppCarMac, lk->carMac, 6);
            g_phase = RC_WAIT_ACCEPT;
            display_accept_request(lk->hdr.sender);
            break;
        }

        // ── Pairing: opponent accepted our LOOKING ────────────────────────────
        case PKT_RACE_ACCEPT: {
            if (g_phase != RC_LOOKING) break;
            const PktRaceAccept* ac = (const PktRaceAccept*)raw.data;
            memcpy(g_oppRcMac,  ac->rcMac,  6);
            memcpy(g_oppCarMac, ac->carMac, 6);
            espnow_add_peer(g_oppRcMac);
            espnow_add_peer(g_oppCarMac);
            g_peersKnown = true;
            g_isHost     = true; // we initiated → we're the host-side RC
            g_phase      = RC_NFC_SETUP;
            display_force_full_redraw();
            break;
        }

        // ── Settings sync from host RC ────────────────────────────────────────
        case PKT_RACE_SETTINGS: {
            const PktRaceSettings* rs = (const PktRaceSettings*)raw.data;
            g_lobbyMode    = rs->mode;
            g_lobbyLaps    = rs->targetLaps;
            g_lobbyTimeSec = rs->timeLimitS;
            g_lobbyTags    = rs->tagCount;
            display_dirty_full();
            break;
        }

        // ── Ready / Start ─────────────────────────────────────────────────────
        case PKT_READY: {
            g_oppReady = true;
            display_dirty_full();
            break;
        }

        // ── Car heartbeat — confirms connection ───────────────────────────────
        case PKT_HEARTBEAT: {
            g_carConnected = true;
            break;
        }

        default: break;
    }
}

// Helper — power name for RC side (mirrors car firmware's power_name)
static const char* power_name_rc(PowerType p) {
    switch(p) {
        case PWR_BOOST:       return "BOOST";
        case PWR_SHIELD:      return "SHIELD";
        case PWR_REGEN:       return "REGEN";
        case PWR_BULLETS:     return "AMMO+3";
        case BAD_SLOWNESS:    return "SLOW";
        case BAD_RANDOM_CTRL: return "CHAOS";
        case BAD_DAMAGE:      return "DAMAGE";
        case BAD_DRIFT:       return "DRIFT";
        default:              return "???";
    }
}

// ---------------------------------------------------------------------------
// Button event handler (all phases)
// ---------------------------------------------------------------------------
static void handle_button(const BtnEvent& ev) {
    uint32_t now = millis();

    switch (g_phase) {

        // ── IDLE / FREE DRIVE ────────────────────────────────────────────────
        case RC_IDLE:
        case RC_FREE_DRIVE:
            if (ev.btn == BTN_ID_CONNECT && ev.type == BTN_SHORT) {
                // Start looking for race
                g_phase = RC_LOOKING;
                g_lookingStartMs = now;
                g_lookingDot = 0;
                display_force_full_redraw();
            }
            if (ev.btn == BTN_ID_ONOFF && ev.type == BTN_LONG) {
                // Power off — release latch
                digitalWrite(PWR_LATCH, LOW);
            }
            break;

        // ── LOOKING ──────────────────────────────────────────────────────────
        case RC_LOOKING:
            if (ev.btn == BTN_ID_BACK && ev.type == BTN_SHORT) {
                g_phase = RC_IDLE;
                display_force_full_redraw();
            }
            break;

        // ── WAIT ACCEPT (opponent found us) ──────────────────────────────────
        case RC_WAIT_ACCEPT:
            if (ev.btn == BTN_ID_OK && ev.type == BTN_SHORT) {
                // Accept the race
                PktRaceAccept ac;
                ac.hdr = { PKT_RACE_ACCEPT, RC_ID, now };
                memcpy(ac.rcMac,  g_ownMac,  6);
                memcpy(ac.carMac, g_carMac,  6);
                espnow_add_peer(g_oppRcMac);
                espnow_add_peer(g_oppCarMac);
                espnow_send(g_oppRcMac, &ac, sizeof(ac));
                g_peersKnown = true;
                g_isHost     = false; // we accepted → we're the client-side RC
                g_phase      = RC_NFC_SETUP;
                display_force_full_redraw();
            }
            if (ev.btn == BTN_ID_BACK && ev.type == BTN_SHORT) {
                g_phase = RC_IDLE;
                display_force_full_redraw();
            }
            break;

        // ── NFC SETUP ────────────────────────────────────────────────────────
        case RC_NFC_SETUP:
            // No button action — wait for car to finish and advance to lobby
            // (host car advances g_phase to LOBBY via car firmware → no RC button needed)
            // RC advances when it receives the NFC_ACK broadcast (or a lobby packet)
            break;

        // ── LOBBY ────────────────────────────────────────────────────────────
        case RC_LOBBY:
            if (g_isHost) {
                // Mode / laps selection
                if (ev.btn == BTN_ID_LEFT && ev.type == BTN_SHORT) {
                    g_lobbyMode = 0; broadcast_settings();
                }
                if (ev.btn == BTN_ID_RIGHT && ev.type == BTN_SHORT) {
                    g_lobbyMode = 1; broadcast_settings();
                }
                if (ev.btn == BTN_ID_UP && ev.type == BTN_SHORT) {
                    if (g_lobbyMode == 0) { if (g_lobbyLaps < 10) g_lobbyLaps++; }
                    else { if (g_lobbyTimeSec < 600) g_lobbyTimeSec += 30; }
                    broadcast_settings();
                }
                if (ev.btn == BTN_ID_DOWN && ev.type == BTN_SHORT) {
                    if (g_lobbyMode == 0) { if (g_lobbyLaps > 1) g_lobbyLaps--; }
                    else { if (g_lobbyTimeSec > 60) g_lobbyTimeSec -= 30; }
                    broadcast_settings();
                }
                if (ev.btn == BTN_ID_OK && ev.type == BTN_SHORT) {
                    // Send START to car
                    PktHeader start = { PKT_START, RC_ID, now };
                    espnow_send(g_carMac, &start, sizeof(start));
                    espnow_send(g_oppCarMac, &start, sizeof(start));
                }
            }
            // Ready toggle
            if (ev.btn == BTN_ID_CONNECT && ev.type == BTN_SHORT) {
                g_myReady = !g_myReady;
                PktHeader rdy = { PKT_READY, RC_ID, now };
                espnow_send(g_oppRcMac, &rdy, sizeof(rdy));
                display_dirty_full();
            }
            break;

        // ── RACING ───────────────────────────────────────────────────────────
        case RC_RACING: {
            // SHOOT
            if (ev.btn == BTN_ID_SHOOT && ev.type == BTN_SHORT) {
                if ((now - g_lastShootMs) >= SHOOT_COOLDOWN_MS) {
                    g_lastShootMs = now;
                    PktShoot sh;
                    sh.hdr = { PKT_SHOOT, RC_ID, now };
                    // Send to own car (car relays to host if not host)
                    espnow_send(g_carMac, &sh, sizeof(sh));
                    // Also directly to host car for validation
                    if (!g_isHost) espnow_send(g_oppCarMac, &sh, sizeof(sh));
                }
            }
            // Power slots (BOOST / SHIELD / HEALTH = REGEN)
            // BTN_BOOST → slot 0  BTN_SHIELD → slot 1  BTN_HEALTH → slot 2
            // (4th slot uses OK button)
            auto use_slot = [&](uint8_t slot) {
                if (slot >= 4) return;
                PowerType p = g_gs.inventory[slot];
                if (p == PWR_NONE) return;
                PktUsePower up;
                up.hdr = { PKT_USE_POWER, RC_ID, now };
                up.powerType = p;
                // Send to host car
                uint8_t* hostMac = g_isHost ? g_carMac : g_oppCarMac;
                espnow_send(hostMac, &up, sizeof(up));
            };

            if (ev.btn == BTN_ID_BOOST  && ev.type == BTN_SHORT) use_slot(0);
            if (ev.btn == BTN_ID_SHIELD && ev.type == BTN_SHORT) use_slot(1);
            if (ev.btn == BTN_ID_HEALTH && ev.type == BTN_SHORT) use_slot(2);
            if (ev.btn == BTN_ID_OK     && ev.type == BTN_SHORT) use_slot(3);

            // BACK = pause request (send to host)
            if (ev.btn == BTN_ID_BACK && ev.type == BTN_SHORT) {
                PktHeader pause = { PKT_GLOBAL_FREEZE, RC_ID, now };
                espnow_send(g_isHost ? g_carMac : g_oppCarMac,
                            &pause, sizeof(pause));
            }
            break;
        }

        // ── FINISHED ─────────────────────────────────────────────────────────
        case RC_FINISHED:
            if (ev.btn == BTN_ID_CONNECT && ev.type == BTN_SHORT) {
                // Reset for new race
                g_phase      = RC_IDLE;
                g_peersKnown = false;
                g_myReady    = false;
                g_oppReady   = false;
                memset(&g_gs, 0, sizeof(g_gs));
                display_force_full_redraw();
            }
            break;

        default: break;
    }
}

// Broadcast lobby settings to opponent RC
static void broadcast_settings() {
    PktRaceSettings rs;
    rs.hdr = { PKT_RACE_SETTINGS, RC_ID, (uint32_t)millis() };
    rs.mode       = g_lobbyMode;
    rs.targetLaps = g_lobbyLaps;
    rs.timeLimitS = g_lobbyTimeSec;
    rs.tagCount   = g_lobbyTags;
    espnow_send(g_oppRcMac, &rs, sizeof(rs));
    display_dirty_full();
}

// ---------------------------------------------------------------------------
// setup()
// ---------------------------------------------------------------------------
void setup() {
    Serial.begin(115200);

    // Hold own power immediately
    pinMode(PWR_LATCH, OUTPUT);
    digitalWrite(PWR_LATCH, HIGH);

    Serial.printf("\n[RC BOOT] FPV Racer RC %d\n", RC_ID);

    // Display
    display_init();
    display_splash();

    // Buttons
    buttons_init();

    // LED
    pinMode(PIN_LED_R, OUTPUT);
    pinMode(PIN_LED_G, OUTPUT);
    pinMode(PIN_LED_B, OUTPUT);
    digitalWrite(PIN_LED_B, HIGH); // blue = booting

    // ESP-NOW
    WiFi.mode(WIFI_STA);
    WiFi.macAddress(g_ownMac);
    esp_now_init();
    esp_now_register_recv_cb(on_recv);

    // Add broadcast peer
    static const uint8_t bcast[6] = {0xFF,0xFF,0xFF,0xFF,0xFF,0xFF};
    espnow_add_peer(bcast);

    // Load paired car MAC from NVS (Preferences)
    Preferences prefs;
    prefs.begin("rc_cfg", true);
    prefs.getBytes("car_mac", g_carMac, 6);
    prefs.end();

    bool hasMac = false;
    for (int i = 0; i < 6; i++) if (g_carMac[i] != 0) hasMac = true;
    if (hasMac) {
        espnow_add_peer(g_carMac);
        // Send heartbeat — car will respond
        PktHeader hb = { PKT_HEARTBEAT, RC_ID, (uint32_t)millis() };
        espnow_send(g_carMac, &hb, sizeof(hb));
    }

    // Read battery
    g_battPct = read_battery_pct();

    // FreeRTOS
    xRxQueue  = xQueueCreate(32, sizeof(IncomingPacket));
    xDriveSem = xSemaphoreCreateBinary();

    // Core 1 drive task
    xTaskCreatePinnedToCore(
        driveTask, "drive", 4096, nullptr,
        configMAX_PRIORITIES - 1, nullptr, 1);

    g_phase = RC_IDLE;
    display_force_full_redraw();
    digitalWrite(PIN_LED_B, LOW);
    digitalWrite(PIN_LED_G, HIGH); // green = ready
    Serial.println("[RC] Setup complete");
}

// ---------------------------------------------------------------------------
// loop() — Core 0
// ---------------------------------------------------------------------------
void loop() {
    uint32_t now = millis();

    // ── 1. Drain ESP-NOW receive queue ───────────────────────────────────────
    IncomingPacket pkt;
    while (xQueueReceive(xRxQueue, &pkt, 0) == pdTRUE) {
        dispatch(pkt);
    }

    // ── 2. Button events ─────────────────────────────────────────────────────
    buttons_tick();
    BtnEvent ev;
    while (buttons_poll(&ev)) {
        handle_button(ev);
    }

    // ── 3. Phase-specific periodic logic ─────────────────────────────────────
    switch (g_phase) {

        case RC_IDLE:
        case RC_FREE_DRIVE:
            display_idle(g_carConnected, g_battPct);
            // Heartbeat to car every 500ms
            if ((now % 500) < 20 && g_carMac[0] != 0) {
                PktHeader hb = { PKT_HEARTBEAT, RC_ID, now };
                espnow_send(g_carMac, &hb, sizeof(hb));
            }
            break;

        case RC_LOOKING:
            // Broadcast RACE_LOOKING every 500ms
            if ((now - g_lookingMs) >= LOOKING_INTERVAL_MS) {
                g_lookingMs = now;
                PktRaceLooking lk;
                lk.hdr = { PKT_RACE_LOOKING, RC_ID, now };
                memcpy(lk.rcMac,  g_ownMac, 6);
                memcpy(lk.carMac, g_carMac, 6);
                espnow_broadcast(&lk, sizeof(lk));
                g_lookingDot++;
            }
            display_looking(g_lookingDot);
            break;

        case RC_NFC_SETUP:
            display_nfc_setup(g_nfcDone, g_nfcTotal, g_isHost);
            break;

        case RC_LOBBY:
            display_lobby(g_myReady, g_oppReady, g_lobbyMode,
                          g_lobbyLaps, g_lobbyTimeSec, g_lobbyTags, g_isHost);
            break;

        case RC_RACING:
            display_racing(g_gs, now);
            break;

        case RC_FINISHED:
            // display_results already called once in dispatch
            break;

        default: break;
    }

    // ── 4. Connection LED ─────────────────────────────────────────────────────
    if (!g_carConnected) {
        // Slow blink red
        digitalWrite(PIN_LED_R, (now / 500) % 2 == 0);
        digitalWrite(PIN_LED_G, LOW);
    } else if (g_phase == RC_RACING) {
        if (g_gs.badPower != PWR_NONE) {
            // Fast blink red
            digitalWrite(PIN_LED_R, (now / 100) % 2 == 0);
            digitalWrite(PIN_LED_G, LOW);
        } else if (g_gs.flags & 0x01) { // shield
            digitalWrite(PIN_LED_R, LOW);
            digitalWrite(PIN_LED_B, (now / 200) % 2 == 0);
        } else {
            digitalWrite(PIN_LED_R, LOW);
            digitalWrite(PIN_LED_G, HIGH);
        }
    }

    vTaskDelay(1);
}
