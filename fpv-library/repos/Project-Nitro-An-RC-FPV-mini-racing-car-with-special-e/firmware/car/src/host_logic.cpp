// =============================================================================
//  host_logic.cpp — HOST CAR: master game state, event validation, broadcasting
// =============================================================================

#include "host_logic.h"
#include "comms.h"
#include "hardware.h"
#include <Arduino.h>
#include <string.h>
#include <stdlib.h>

// ---------------------------------------------------------------------------
// Private state
// ---------------------------------------------------------------------------

static MatchState g_match;
static NfcTag     g_tags[MAX_TAGS];
static uint8_t    g_tagCount = 0;
static uint8_t    g_sessionKey[SESSION_KEY_LEN];

// Power pool: 4 good + 4 bad types, shuffled each session
static PowerType  g_powerPool[8] = {
    PWR_BOOST, PWR_SHIELD, PWR_REGEN, PWR_BULLETS,
    BAD_SLOWNESS, BAD_RANDOM_CTRL, BAD_DAMAGE, BAD_DRIFT
};

// Last time a UIState was broadcast
static uint32_t g_lastBroadcastMs = 0;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

static PlayerState& P(uint8_t carId) { return g_match.p[carId - 1]; }

static void shuffle_power_pool() {
    // Fisher-Yates shuffle
    for (int i = 7; i > 0; i--) {
        int j = esp_random() % (i + 1);
        PowerType tmp = g_powerPool[i];
        g_powerPool[i] = g_powerPool[j];
        g_powerPool[j] = tmp;
    }
}

static int find_tag(const uint8_t* token) {
    for (int i = 0; i < g_tagCount; i++) {
        if (memcmp(g_tags[i].token, token, 16) == 0) return i;
    }
    return -1;
}

static bool inventory_add(PlayerState& p, PowerType power) {
    for (int i = 0; i < 4; i++) {
        if (p.inventory[i] == PWR_NONE) {
            p.inventory[i] = power;
            return true;
        }
    }
    return false; // full — discard
}

static bool inventory_remove(PlayerState& p, PowerType power) {
    for (int i = 0; i < 4; i++) {
        if (p.inventory[i] == power) {
            p.inventory[i] = PWR_NONE;
            return true;
        }
    }
    return false;
}

static void send_to_both_rcs(const void* data, size_t len) {
    comms_send(PEER_OWN_RC,  data, len);
    comms_send(PEER_OPP_RC,  data, len);
}

static void send_global_freeze() {
    PktHeader pkt = { PKT_GLOBAL_FREEZE, CAR_ID, (uint32_t)millis() };
    comms_broadcast(&pkt, sizeof(pkt));
    hw_motor_kill(); // freeze ourselves too
}

static void log_event(EventType type, uint8_t actor, uint8_t target,
                      uint8_t v1, uint8_t v2) {
    LogEntry e = {
        .t         = (uint32_t)millis() - g_match.matchStartMs,
        .eventType = type,
        .actor     = actor,
        .target    = target,
        .value1    = v1,
        .value2    = v2
    };
    sd_log_append(e);
}

static void check_win_condition() {
    if (g_match.phase != PHASE_RACING) return;

    if (g_match.mode == MODE_LAP_RACE) {
        for (int i = 0; i < 2; i++) {
            if (g_match.p[i].laps >= g_match.targetLaps) {
                host_end_match(i + 1, "laps_complete");
                return;
            }
        }
    }
    // TIME_RACE: handled in host_tick when timer expires
}

// Build UIState for player carId (1 or 2) — perspective is from that player
static UIState build_ui_state(uint8_t carId) {
    PlayerState& me  = P(carId);
    PlayerState& opp = P(carId == 1 ? 2 : 1);
    UIState ui = {};
    ui.phase     = (uint8_t)g_match.phase;
    ui.mode      = (uint8_t)g_match.mode;
    ui.myHealth  = me.health;
    ui.oppHealth = opp.health;
    ui.myBullets = me.bullets;
    ui.myLaps    = me.laps;
    ui.oppLaps   = opp.laps;
    ui.myScore   = me.score;
    ui.oppScore  = opp.score;
    for (int i = 0; i < 4; i++) ui.activePower[i] = (uint8_t)me.inventory[i];
    ui.badPower  = (uint8_t)me.badPower;

    uint32_t nowMs = millis();
    if (g_match.mode == MODE_TIME_RACE && g_match.phase == PHASE_RACING) {
        uint32_t elapsed = nowMs - g_match.matchStartMs;
        uint32_t rem = (elapsed < g_match.timeLimitMs) ?
                       (g_match.timeLimitMs - elapsed) / 1000 : 0;
        ui.countdown = (uint16_t)rem;
    }
    ui.matchTimeMs = (g_match.phase == PHASE_RACING) ?
                     (nowMs - g_match.matchStartMs) : 0;

    uint8_t flags = 0;
    if (me.shieldActive)   flags |= 0x01;
    if (g_match.phase == PHASE_FINISHED) flags |= 0x04;
    ui.flags = flags;
    return ui;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

void host_init() {
    memset(&g_match, 0, sizeof(g_match));
    memset(g_tags,   0, sizeof(g_tags));
    g_tagCount = 0;
    g_match.phase = PHASE_IDLE;

    // Default player health
    g_match.p[0].health = 100;
    g_match.p[1].health = 100;
}

// ---------------------------------------------------------------------------
// NFC Setup
// ---------------------------------------------------------------------------

void host_nfc_setup_begin(uint8_t expectedTagCount) {
    g_tagCount = 0;
    crypto_gen_session_key(g_sessionKey);
    shuffle_power_pool();
    g_match.phase = PHASE_NFC_SCAN;
    Serial.printf("[HOST] NFC setup begin. Expecting %d tags.\n", expectedTagCount);
}

bool host_nfc_register_tag(const uint8_t* uid, uint8_t uidLen) {
    if (g_tagCount >= MAX_TAGS) return false;

    // Assign next power from shuffled pool (cycle if more tags than pool size)
    PowerType assignedPower = g_powerPool[g_tagCount % 8];

    // Build plaintext token: 8-byte UID padded + power byte + padding
    uint8_t plaintext[16] = {0};
    memcpy(plaintext, uid, uidLen > 8 ? 8 : uidLen);
    plaintext[8] = (uint8_t)assignedPower;
    // bytes 9-15: session salt bytes
    for (int i = 9; i < 16; i++) plaintext[i] = g_sessionKey[i];

    // Encrypt with session key
    uint8_t token[16];
    crypto_xor(plaintext, g_sessionKey, token);

    // Write token to physical tag
    if (!hw_nfc_write_token(token)) {
        Serial.println("[HOST] NFC write FAILED");
        return false;
    }

    // Store in master table
    memcpy(g_tags[g_tagCount].token, token, 16);
    g_tags[g_tagCount].power = assignedPower;
    g_tags[g_tagCount].lastTriggerByP1Ms = 0;
    g_tags[g_tagCount].lastTriggerByP2Ms = 0;
    g_tagCount++;

    Serial.printf("[HOST] Tag %d registered: power=%d\n", g_tagCount, assignedPower);
    return true;
}

uint8_t host_nfc_tag_count() { return g_tagCount; }

void host_nfc_send_table() {
    PktNfcTable pkt;
    pkt.hdr = { PKT_NFC_TABLE, CAR_ID, (uint32_t)millis() };
    pkt.count = g_tagCount;
    for (int i = 0; i < g_tagCount; i++) {
        memcpy(pkt.entries[i].token, g_tags[i].token, 16);
        pkt.entries[i].power = g_tags[i].power;
    }
    comms_send(PEER_OPP_CAR, &pkt, sizeof(pkt));
    Serial.println("[HOST] NFC table sent to client.");
}

// ---------------------------------------------------------------------------
// Race start
// ---------------------------------------------------------------------------

void host_start_race(RaceMode mode, uint8_t targetLaps, uint32_t timeLimitMs) {
    g_match.mode        = mode;
    g_match.targetLaps  = targetLaps;
    g_match.timeLimitMs = timeLimitMs;
    g_match.phase       = PHASE_COUNTDOWN;

    // Reset player race stats (keep health from pre-race if desired — here we reset)
    for (int i = 0; i < 2; i++) {
        g_match.p[i].health   = 100;
        g_match.p[i].bullets  = 0;
        g_match.p[i].laps     = 0;
        g_match.p[i].score    = 0;
        g_match.p[i].shieldActive    = false;
        g_match.p[i].badPower        = PWR_NONE;
        g_match.p[i].stationCuring   = false;
        for (int j = 0; j < 4; j++) g_match.p[i].inventory[j] = PWR_NONE;
    }

    hw_motor_enable(); // ensure unfrozen

    // Broadcast 3-2-1-GO with 1-second spacing
    for (int8_t tick = 3; tick >= 0; tick--) {
        PktCountdown cd;
        cd.hdr  = { PKT_COUNTDOWN, CAR_ID, (uint32_t)millis() };
        cd.tick = (uint8_t)tick;
        comms_broadcast(&cd, sizeof(cd));
        hw_buzzer_beep(tick > 0 ? 800 : 1200, 200);
        if (tick > 0) delay(1000);
    }

    g_match.matchStartMs = millis();
    g_match.phase        = PHASE_RACING;

    char fname[32];
    snprintf(fname, sizeof(fname), "/match_%lu.log", g_match.matchStartMs);
    sd_log_open(fname);
    Serial.println("[HOST] RACE STARTED");
}

// ---------------------------------------------------------------------------
// Event validators
// ---------------------------------------------------------------------------

bool host_on_shoot(uint8_t carId, uint32_t timestamp) {
    if (g_match.phase != PHASE_RACING) return false;
    PlayerState& p = P(carId);

    if (p.bullets == 0) {
        // DENY — no bullets
        PktHeader deny = { PKT_DENY, CAR_ID, (uint32_t)millis() };
        comms_send(carId == CAR_ID ? PEER_OWN_RC : PEER_OPP_RC, &deny, sizeof(deny));
        return false;
    }

    p.bullets--;
    p.shootWindowMs = timestamp; // open hit-validation window

    // Broadcast updated bullet count
    PktHeader bulUpd = { PKT_BULLET_UPD, CAR_ID, (uint32_t)millis() };
    comms_send(carId == CAR_ID ? PEER_OWN_RC : PEER_OPP_RC, &bulUpd, sizeof(bulUpd));

    log_event(EVT_SHOOT, carId, 0, p.bullets, 0);
    Serial.printf("[HOST] P%d SHOOT validated. Bullets left: %d\n", carId, p.bullets);
    return true;
}

bool host_on_hit_detected(uint8_t victimCarId, uint32_t timestamp) {
    if (g_match.phase != PHASE_RACING) return false;

    uint8_t shooterCarId = (victimCarId == 1) ? 2 : 1;
    PlayerState& shooter = P(shooterCarId);
    PlayerState& victim  = P(victimCarId);

    // Validate: was there a SHOOT event from shooter within HIT_WINDOW_MS?
    if (shooter.shootWindowMs == 0 ||
        (timestamp - shooter.shootWindowMs) > HIT_WINDOW_MS) {
        Serial.printf("[HOST] HIT from P%d DENIED — no valid shoot window\n", victimCarId);
        return false;
    }
    shooter.shootWindowMs = 0; // consume window (one hit per shot)

    // Shield check
    if (victim.shieldActive) {
        PktHeader abs = { PKT_SHIELD_ABS, CAR_ID, (uint32_t)millis() };
        send_to_both_rcs(&abs, sizeof(abs));
        Serial.printf("[HOST] P%d shield absorbed IR hit\n", victimCarId);
        log_event(EVT_HIT, shooterCarId, victimCarId, 0, 1 /*shielded*/);
        return true;
    }

    // Apply damage
    int newHealth = (int)victim.health - 10;
    victim.health = (uint8_t)(newHealth < HEALTH_FLOOR ? HEALTH_FLOOR : newHealth);
    shooter.score += 5;

    // Broadcast health update to both RCs
    PktHealthUpdate hupd;
    hupd.hdr    = { PKT_HEALTH_UPD, CAR_ID, (uint32_t)millis() };
    hupd.p1Health = g_match.p[0].health;
    hupd.p2Health = g_match.p[1].health;
    hupd.delta  = -10;
    hupd.victim = victimCarId;
    send_to_both_rcs(&hupd, sizeof(hupd));

    log_event(EVT_HIT, shooterCarId, victimCarId, 10, 0);
    log_event(EVT_DAMAGE, shooterCarId, victimCarId, 10, victim.health);

    hw_buzzer_beep(400, 150); // hit feedback on host car
    Serial.printf("[HOST] P%d HIT P%d. P%d health=%d\n",
                  shooterCarId, victimCarId, victimCarId, victim.health);
    return true;
}

bool host_on_tag_detected(uint8_t carId, const uint8_t* token,
                           PowerType claimedPower, uint32_t timestamp) {
    if (g_match.phase != PHASE_RACING) return false;

    PlayerState& p = P(carId);
    uint32_t nowMs = millis();

    // Anti-cheat: two tags from same car too close together?
    static uint32_t s_lastTagTime[2] = {0, 0};
    if (s_lastTagTime[carId - 1] != 0 &&
        (nowMs - s_lastTagTime[carId - 1]) < TAG_PROXIMITY_MS) {
        Serial.printf("[HOST] PROXIMITY CHEAT detected by P%d — FREEZE\n", carId);
        send_global_freeze();
        return false;
    }
    s_lastTagTime[carId - 1] = nowMs;

    // Find token in master table
    int idx = find_tag(token);
    if (idx < 0) {
        Serial.printf("[HOST] TAG DENIED — token not in session table\n");
        PktHeader deny = { PKT_DENY, CAR_ID, (uint32_t)millis() };
        comms_send(carId == CAR_ID ? PEER_OWN_RC : PEER_OPP_RC, &deny, sizeof(deny));
        return false;
    }

    // Per-car per-tag cooldown check
    uint32_t& lastTrigger = (carId == 1) ?
                             g_tags[idx].lastTriggerByP1Ms :
                             g_tags[idx].lastTriggerByP2Ms;
    if (lastTrigger != 0 && (nowMs - lastTrigger) < TAG_COOLDOWN_MS) {
        Serial.printf("[HOST] TAG DENIED — cooldown active for P%d tag %d\n", carId, idx);
        return false;
    }
    lastTrigger = nowMs;

    PowerType power = g_tags[idx].power;
    log_event(EVT_TAG, carId, 0, (uint8_t)power, idx);

    if (isBadPower(power)) {
        // Apply immediately
        if (power == BAD_DAMAGE) {
            // Damage is a health event — check shield
            if (p.shieldActive) {
                PktHeader abs = { PKT_SHIELD_ABS, CAR_ID, (uint32_t)millis() };
                send_to_both_rcs(&abs, sizeof(abs));
            } else {
                int newH = (int)p.health - 20;
                p.health = (uint8_t)(newH < HEALTH_FLOOR ? HEALTH_FLOOR : newH);
                PktHealthUpdate hupd;
                hupd.hdr      = { PKT_HEALTH_UPD, CAR_ID, (uint32_t)millis() };
                hupd.p1Health = g_match.p[0].health;
                hupd.p2Health = g_match.p[1].health;
                hupd.delta    = -20;
                hupd.victim   = carId;
                send_to_both_rcs(&hupd, sizeof(hupd));
                log_event(EVT_DAMAGE, 0, carId, 20, p.health);
            }
        } else {
            // Timed bad power — send APPLY_BAD to affected car and its RC
            uint32_t timeout = 0;
            switch(power) {
                case BAD_SLOWNESS:    timeout = 30000; break;
                case BAD_RANDOM_CTRL: timeout = 20000; break;
                case BAD_DRIFT:       timeout = 25000; break;
                default: break;
            }
            p.badPower         = power;
            p.badPowerExpiryMs = nowMs + timeout;

            PktApplyBad apkt;
            apkt.hdr       = { PKT_APPLY_BAD, CAR_ID, (uint32_t)millis() };
            apkt.badType   = power;
            apkt.timeoutMs = timeout;
            comms_send(carId == CAR_ID ? PEER_OPP_CAR : PEER_OPP_CAR, &apkt, sizeof(apkt));
            // also notify RC
            comms_send(carId == CAR_ID ? PEER_OWN_RC : PEER_OPP_RC, &apkt, sizeof(apkt));
            log_event(EVT_BAD_POWER, 0, carId, (uint8_t)power, 0);
        }
    } else if (power == PWR_BULLETS) {
        // Bullets: auto-grant, no manual activation
        p.bullets = (uint8_t)min((int)p.bullets + 3, (int)MAX_BULLETS);
        PktHeader bulUpd = { PKT_BULLET_UPD, CAR_ID, (uint32_t)millis() };
        comms_send(carId == CAR_ID ? PEER_OWN_RC : PEER_OPP_RC, &bulUpd, sizeof(bulUpd));
        log_event(EVT_POWER_GAIN, carId, 0, (uint8_t)power, p.bullets);
    } else {
        // Good power — place in inventory, send GRANT to RC
        bool added = inventory_add(p, power);
        if (added) {
            PktHeader grant = { PKT_GRANT, CAR_ID, (uint32_t)millis() };
            comms_send(carId == CAR_ID ? PEER_OWN_RC : PEER_OPP_RC, &grant, sizeof(grant));
            log_event(EVT_POWER_GAIN, carId, 0, (uint8_t)power, 0);
        }
    }

    Serial.printf("[HOST] P%d TAG GRANTED: power=%d\n", carId, power);
    return true;
}

bool host_on_use_power(uint8_t carId, PowerType power) {
    if (g_match.phase != PHASE_RACING) return false;
    PlayerState& p = P(carId);

    if (!inventory_remove(p, power)) {
        PktHeader deny = { PKT_DENY, CAR_ID, (uint32_t)millis() };
        comms_send(carId == CAR_ID ? PEER_OWN_RC : PEER_OPP_RC, &deny, sizeof(deny));
        return false;
    }

    uint32_t nowMs = millis();
    PktExecute exec;
    exec.hdr = { PKT_EXECUTE, CAR_ID, nowMs };
    exec.powerType = power;

    switch (power) {
        case PWR_BOOST:
            exec.durationMs = 3000;
            break;
        case PWR_SHIELD:
            exec.durationMs = 5000 + (esp_random() % 3001); // 5000-8000ms random
            p.shieldActive    = true;
            p.shieldExpiryMs  = nowMs + exec.durationMs;
            break;
        case PWR_REGEN:
            exec.durationMs = 0;
            p.health = (uint8_t)min((int)p.health + 25, 100);
            // broadcast health update
            PktHealthUpdate hupd;
            hupd.hdr      = { PKT_HEALTH_UPD, CAR_ID, nowMs };
            hupd.p1Health = g_match.p[0].health;
            hupd.p2Health = g_match.p[1].health;
            hupd.delta    = +25;
            hupd.victim   = carId;
            send_to_both_rcs(&hupd, sizeof(hupd));
            break;
        default:
            break;
    }

    // Send EXECUTE to the car (own or opponent)
    if (carId == CAR_ID) {
        // We are the car — execute locally (signal Core 1)
        // In real FreeRTOS firmware this posts to a queue read by Core 1
        // For algorithm clarity we call the handler directly
    } else {
        comms_send(PEER_OPP_CAR, &exec, sizeof(exec));
    }

    // Also notify RC
    comms_send(carId == CAR_ID ? PEER_OWN_RC : PEER_OPP_RC, &exec, sizeof(exec));
    log_event(EVT_POWER_USE, carId, 0, (uint8_t)power, 0);

    Serial.printf("[HOST] P%d EXECUTE power=%d duration=%lu\n",
                  carId, power, exec.durationMs);
    return true;
}

bool host_on_lap_cross(uint8_t carId, uint32_t timestamp) {
    if (g_match.phase != PHASE_RACING) return false;
    PlayerState& p = P(carId);
    uint32_t nowMs = millis();

    // Lap debounce
    if (p.lastLapMs != 0 && (nowMs - p.lastLapMs) < LAP_DEBOUNCE_MS) {
        return false;
    }
    p.lastLapMs = nowMs;
    p.laps++;
    p.score += 10; // lap bonus

    // Broadcast lap update
    PktHeader lupd = { PKT_LAP_UPD, CAR_ID, nowMs };
    comms_broadcast(&lupd, sizeof(lupd));

    log_event(EVT_LAP, carId, 0, p.laps, 0);
    Serial.printf("[HOST] P%d LAP %d completed\n", carId, p.laps);

    check_win_condition();
    return true;
}

bool host_on_impact(uint8_t carId, float gForce, uint32_t timestamp) {
    if (g_match.phase != PHASE_RACING) return false;
    PlayerState& p = P(carId);
    uint32_t nowMs = millis();

    // Cooldown check
    if (p.lastImpactMs != 0 && (nowMs - p.lastImpactMs) < ACCEL_COOLDOWN_MS) {
        return false;
    }
    p.lastImpactMs = nowMs;

    // Check if opponent also spiked within 100ms → car-to-car collision
    uint8_t oppId = (carId == 1) ? 2 : 1;
    PlayerState& opp = P(oppId);
    bool carTocar = (opp.lastImpactMs != 0 &&
                     (nowMs - opp.lastImpactMs) < 100);

    int dmg = carTocar ? 5 : 5; // both 5% — different events
    if (p.shieldActive) {
        Serial.printf("[HOST] P%d shield absorbed impact\n", carId);
        return true;
    }

    int newH = (int)p.health - dmg;
    p.health = (uint8_t)(newH < HEALTH_FLOOR ? HEALTH_FLOOR : newH);

    PktHealthUpdate hupd;
    hupd.hdr      = { PKT_HEALTH_UPD, CAR_ID, nowMs };
    hupd.p1Health = g_match.p[0].health;
    hupd.p2Health = g_match.p[1].health;
    hupd.delta    = (int8_t)-dmg;
    hupd.victim   = carId;
    send_to_both_rcs(&hupd, sizeof(hupd));

    log_event(EVT_IMPACT, carId, carTocar ? oppId : 0, (uint8_t)(gForce * 10), p.health);
    Serial.printf("[HOST] P%d IMPACT %.2fg -%d%% HP=%d\n", carId, gForce, dmg, p.health);
    return true;
}

void host_on_station_present(uint8_t carId, PowerType stationType) {
    if (g_match.phase != PHASE_RACING) return;

    // Validate: correct station for this car?
    bool valid = (carId == 1 && stationType == PWR_STATION_P1) ||
                 (carId == 2 && stationType == PWR_STATION_P2);
    if (!valid) {
        PktHeader deny = { PKT_DENY, CAR_ID, (uint32_t)millis() };
        comms_send(carId == CAR_ID ? PEER_OWN_RC : PEER_OPP_RC, &deny, sizeof(deny));
        return;
    }

    PlayerState& p = P(carId);
    if (p.badPower == PWR_NONE) return; // nothing to cure

    uint32_t nowMs = millis();
    if (!p.stationCuring) {
        // Start cure timer
        p.stationCuring      = true;
        p.stationCureStartMs = nowMs;
        // Cure duration per bad power
        switch (p.badPower) {
            case BAD_SLOWNESS:    p.stationCureDurationMs = 1000; break;
            case BAD_RANDOM_CTRL: p.stationCureDurationMs = 2000; break;
            case BAD_DRIFT:       p.stationCureDurationMs = 1500; break;
            default:              p.stationCureDurationMs = 1000; break;
        }
        Serial.printf("[HOST] P%d cure started for bad=%d\n", carId, p.badPower);
    }
    // Completion is checked in host_tick()
}

void host_on_station_lost(uint8_t carId) {
    PlayerState& p = P(carId);
    if (!p.stationCuring) return;

    p.stationCuring = false;
    PktHeader cancel = { PKT_CURE_CANCEL, CAR_ID, (uint32_t)millis() };
    comms_send(carId == CAR_ID ? PEER_OWN_RC : PEER_OPP_RC, &cancel, sizeof(cancel));
    Serial.printf("[HOST] P%d cure CANCELLED — left station\n", carId);
}

// ---------------------------------------------------------------------------
// Tick — called every Core 0 loop iteration
// ---------------------------------------------------------------------------

void host_tick(uint32_t nowMs) {
    for (int i = 0; i < 2; i++) {
        PlayerState& p = g_match.p[i];
        uint8_t carId = i + 1;

        // Shield expiry
        if (p.shieldActive && nowMs >= p.shieldExpiryMs) {
            p.shieldActive = false;
            Serial.printf("[HOST] P%d shield expired\n", carId);
        }

        // Bad power fallback timeout
        if (p.badPower != PWR_NONE && nowMs >= p.badPowerExpiryMs) {
            PowerType cleared = p.badPower;
            p.badPower       = PWR_NONE;
            p.stationCuring  = false;
            PktHeader clr = { PKT_CLEAR_BAD, CAR_ID, nowMs };
            comms_send(carId == CAR_ID ? PEER_OWN_RC : PEER_OPP_RC, &clr, sizeof(clr));
            if (carId != CAR_ID) comms_send(PEER_OPP_CAR, &clr, sizeof(clr));
            Serial.printf("[HOST] P%d bad power %d auto-expired\n", carId, cleared);
        }

        // Station cure completion
        if (p.stationCuring &&
            (nowMs - p.stationCureStartMs) >= p.stationCureDurationMs) {
            PowerType cleared = p.badPower;
            p.badPower      = PWR_NONE;
            p.stationCuring = false;
            PktHeader clr = { PKT_CLEAR_BAD, CAR_ID, nowMs };
            comms_send(carId == CAR_ID ? PEER_OWN_RC : PEER_OPP_RC, &clr, sizeof(clr));
            if (carId != CAR_ID) comms_send(PEER_OPP_CAR, &clr, sizeof(clr));
            log_event(EVT_STATION, carId, 0, (uint8_t)cleared, 0);
            Serial.printf("[HOST] P%d cured bad=%d at station\n", carId, cleared);
        }
    }

    // Time race countdown
    if (g_match.phase == PHASE_RACING && g_match.mode == MODE_TIME_RACE) {
        uint32_t elapsed = nowMs - g_match.matchStartMs;
        if (elapsed >= g_match.timeLimitMs) {
            // Time up — winner is whoever has more laps, then score
            uint8_t winner;
            if (g_match.p[0].laps > g_match.p[1].laps) winner = 1;
            else if (g_match.p[1].laps > g_match.p[0].laps) winner = 2;
            else winner = (g_match.p[0].score >= g_match.p[1].score) ? 1 : 2;
            host_end_match(winner, "time_expired");
        }
    }

    // Heartbeat monitoring — pause if a device drops
    if (g_match.phase == PHASE_RACING) {
        bool ownRcLost  = comms_peer_lost(PEER_OWN_RC,  600);
        bool oppCarLost = comms_peer_lost(PEER_OPP_CAR, 600);
        bool oppRcLost  = comms_peer_lost(PEER_OPP_RC,  600);
        if (ownRcLost || oppCarLost || oppRcLost) {
            Serial.println("[HOST] Peer lost — broadcasting PAUSE");
            PktHeader frz = { PKT_GLOBAL_FREEZE, CAR_ID, nowMs };
            comms_broadcast(&frz, sizeof(frz));
            hw_motor_kill();
            // TODO: 10-second reconnect window before forfeiture
        }
    }

    // UIState broadcast every HEARTBEAT_MS
    if ((nowMs - g_lastBroadcastMs) >= HEARTBEAT_MS) {
        host_broadcast_ui_state(nowMs);
        g_lastBroadcastMs = nowMs;
    }
}

void host_broadcast_ui_state(uint32_t nowMs) {
    // Build and send per-player perspective UIState to each RC
    {
        UIState ui = build_ui_state(CAR_ID); // our RC
        PktUIState pkt;
        pkt.hdr = { PKT_UI_STATE, CAR_ID, nowMs };
        pkt.ui  = ui;
        comms_send(PEER_OWN_RC, &pkt, sizeof(pkt));
    }
    {
        uint8_t oppId = (CAR_ID == 1) ? 2 : 1;
        UIState ui = build_ui_state(oppId); // opponent RC
        PktUIState pkt;
        pkt.hdr = { PKT_UI_STATE, CAR_ID, nowMs };
        pkt.ui  = ui;
        comms_send(PEER_OPP_RC, &pkt, sizeof(pkt));
    }

    // Also send to opponent car so it can mirror state
    PktUIState pkt;
    pkt.hdr = { PKT_UI_STATE, CAR_ID, nowMs };
    pkt.ui  = build_ui_state(CAR_ID == 1 ? 2 : 1);
    comms_send(PEER_OPP_CAR, &pkt, sizeof(pkt));
}

void host_end_match(uint8_t winner, const char* reason) {
    if (g_match.phase == PHASE_FINISHED) return;
    g_match.phase = PHASE_FINISHED;

    send_global_freeze();

    PktMatchEnd end;
    end.hdr           = { PKT_MATCH_END, CAR_ID, (uint32_t)millis() };
    end.winner        = winner;
    end.p1Score       = g_match.p[0].score;
    end.p2Score       = g_match.p[1].score;
    end.p1Laps        = g_match.p[0].laps;
    end.p2Laps        = g_match.p[1].laps;
    end.p1HealthFinal = g_match.p[0].health;
    end.p2HealthFinal = g_match.p[1].health;
    comms_broadcast(&end, sizeof(end));

    log_event(EVT_WIN, winner, 0, end.p1Score >> 8, (uint8_t)end.p1Score);
    sd_log_close();

    hw_buzzer_beep(1400, 600);
    Serial.printf("[HOST] MATCH END — winner P%d (%s)\n", winner, reason);
}

const MatchState* host_get_match_state() { return &g_match; }
