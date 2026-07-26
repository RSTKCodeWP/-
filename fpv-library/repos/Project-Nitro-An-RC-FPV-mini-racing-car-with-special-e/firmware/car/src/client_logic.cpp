// =============================================================================
//  client_logic.cpp — CLIENT CAR: mirrors host state, executes commands
// =============================================================================

#include "client_logic.h"
#include "comms.h"
#include "hardware.h"
#include <Arduino.h>
#include <string.h>

// ---------------------------------------------------------------------------
// Private state
// ---------------------------------------------------------------------------

static CarPhase  g_phase      = PHASE_IDLE;
static PowerType g_badPower   = PWR_NONE;
static uint32_t  g_badExpiry  = 0;
static bool      g_frozen     = false;

// Local NFC table (received from host during setup)
static NfcTag    g_localTags[MAX_TAGS];
static uint8_t   g_localTagCount = 0;

// Boost end time
static uint32_t  g_boostExpiry = 0;

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

void client_init() {
    g_phase         = PHASE_IDLE;
    g_badPower      = PWR_NONE;
    g_badExpiry     = 0;
    g_frozen        = false;
    g_localTagCount = 0;
}

// ---------------------------------------------------------------------------
// NFC table
// ---------------------------------------------------------------------------

void client_receive_nfc_table(const PktNfcTable* pkt) {
    g_localTagCount = pkt->count;
    for (int i = 0; i < g_localTagCount; i++) {
        memcpy(g_localTags[i].token, pkt->entries[i].token, 16);
        g_localTags[i].power = pkt->entries[i].power;
    }
    // ACK to host
    PktHeader ack = { PKT_NFC_ACK, CAR_ID, (uint32_t)millis() };
    comms_send(PEER_OPP_CAR, &ack, sizeof(ack));
    Serial.printf("[CLIENT] NFC table received: %d tags\n", g_localTagCount);
}

static PowerType lookup_local_tag(const uint8_t* token) {
    for (int i = 0; i < g_localTagCount; i++) {
        if (memcmp(g_localTags[i].token, token, 16) == 0)
            return g_localTags[i].power;
    }
    return PWR_NONE;
}

// ---------------------------------------------------------------------------
// Host command handlers
// ---------------------------------------------------------------------------

void client_on_execute(const PktExecute* pkt) {
    switch (pkt->powerType) {
        case PWR_BOOST:
            // Core 1 will read g_boostExpiry and apply +30% throttle cap lift
            g_boostExpiry = millis() + pkt->durationMs;
            hw_buzzer_beep(1000, 100);
            hw_led_flash(2, 100);
            Serial.println("[CLIENT] BOOST activated");
            break;
        case PWR_SHIELD:
            hw_led_flash(3, 200);
            hw_buzzer_beep(900, 150);
            Serial.println("[CLIENT] SHIELD activated");
            break;
        case PWR_REGEN:
            hw_buzzer_beep(1100, 200);
            hw_led_flash(4, 100);
            Serial.println("[CLIENT] REGEN applied");
            break;
        default:
            break;
    }
}

void client_on_apply_bad(const PktApplyBad* pkt) {
    g_badPower  = pkt->badType;
    g_badExpiry = millis() + pkt->timeoutMs;
    hw_buzzer_beep(300, 400);
    hw_led_flash(5, 80);
    Serial.printf("[CLIENT] BAD POWER applied: %d\n", pkt->badType);
}

void client_on_clear_bad(PowerType bad) {
    if (g_badPower == bad) {
        g_badPower = PWR_NONE;
        hw_buzzer_beep(1200, 150);
        Serial.println("[CLIENT] Bad power cleared");
    }
}

void client_on_freeze() {
    g_frozen = true;
    hw_motor_kill();
    Serial.println("[CLIENT] FROZEN");
}

void client_on_resume() {
    g_frozen = false;
    hw_motor_enable();
    Serial.println("[CLIENT] RESUMED");
}

void client_on_match_end(const PktMatchEnd* pkt) {
    g_phase  = PHASE_FINISHED;
    g_frozen = true;
    hw_motor_kill();
    hw_buzzer_beep(1400, 600);
    Serial.printf("[CLIENT] MATCH END. Winner: P%d\n", pkt->winner);
}

void client_on_countdown(uint8_t tick) {
    if (tick == 0) {
        // GO
        g_phase  = PHASE_RACING;
        g_frozen = false;
        hw_motor_enable();
        hw_buzzer_beep(1400, 300);
    } else {
        hw_buzzer_beep(800, 150);
    }
    Serial.printf("[CLIENT] COUNTDOWN tick=%d\n", tick);
}

void client_on_ui_state(const UIState* ui) {
    g_phase = (CarPhase)ui->phase;
    // Mirror bad power state in case a packet was lost
    g_badPower = (PowerType)ui->badPower;
}

// ---------------------------------------------------------------------------
// Sensor forwarders
// ---------------------------------------------------------------------------

void client_forward_tag(const uint8_t* token, PowerType localPower) {
    PktTagDetected pkt;
    pkt.hdr       = { PKT_TAG_DETECTED, CAR_ID, (uint32_t)millis() };
    memcpy(pkt.token, token, 16);
    pkt.powerType = localPower;
    comms_send(PEER_OPP_CAR, &pkt, sizeof(pkt)); // host is opponent car
    Serial.printf("[CLIENT] TAG forwarded to host, claimed power=%d\n", localPower);
}

void client_forward_hit() {
    PktHitDetected pkt;
    pkt.hdr = { PKT_HIT_DETECTED, CAR_ID, (uint32_t)millis() };
    comms_send(PEER_OPP_CAR, &pkt, sizeof(pkt));
    Serial.println("[CLIENT] HIT forwarded to host");
}

void client_forward_lap() {
    PktLapCross pkt;
    pkt.hdr = { PKT_LAP_CROSS, CAR_ID, (uint32_t)millis() };
    comms_send(PEER_OPP_CAR, &pkt, sizeof(pkt));
    Serial.println("[CLIENT] LAP CROSS forwarded to host");
}

void client_forward_impact(float gForce) {
    PktImpact pkt;
    pkt.hdr    = { PKT_IMPACT, CAR_ID, (uint32_t)millis() };
    pkt.gForce = gForce;
    comms_send(PEER_OPP_CAR, &pkt, sizeof(pkt));
    Serial.printf("[CLIENT] IMPACT forwarded: %.2fg\n", gForce);
}

void client_forward_station(PowerType stationType) {
    PktStationDetected pkt;
    pkt.hdr         = { PKT_STATION_DET, CAR_ID, (uint32_t)millis() };
    pkt.stationType = stationType;
    comms_send(PEER_OPP_CAR, &pkt, sizeof(pkt));
}

// ---------------------------------------------------------------------------
// Drive with bad power modifier
// ---------------------------------------------------------------------------

int8_t client_throttle_modified(int8_t raw) {
    if (g_frozen) return 0;
    switch (g_badPower) {
        case BAD_SLOWNESS:
            return (int8_t)(raw * 40 / 100); // cap at 40%
        case BAD_RANDOM_CTRL:
            // Randomly invert or zero
            if (esp_random() % 5 == 0) return (int8_t)(-raw);
            if (esp_random() % 4 == 0) return 0;
            return raw;
        default:
            // Apply boost if active
            if (millis() < g_boostExpiry)
                return (int8_t)min((int)raw * 130 / 100, 100);
            return raw;
    }
}

int8_t client_steering_modified(int8_t raw) {
    if (g_frozen) return 0;
    switch (g_badPower) {
        case BAD_DRIFT:
            return (int8_t)(raw * 150 / 100 > 100 ? 100 : raw * 150 / 100);
        case BAD_RANDOM_CTRL:
            if (esp_random() % 5 == 0) return (int8_t)(-raw);
            return raw;
        default:
            return raw;
    }
}

void client_apply_drive(int8_t throttle, int8_t steering) {
    hw_motor_set(client_throttle_modified(throttle));
    hw_servo_set(client_steering_modified(steering));
}

// ---------------------------------------------------------------------------
// Periodic tick
// ---------------------------------------------------------------------------

void client_tick(uint32_t nowMs) {
    // Local bad power failsafe expiry (in case CLEAR_BAD was lost)
    if (g_badPower != PWR_NONE && g_badExpiry != 0 && nowMs >= g_badExpiry) {
        g_badPower = PWR_NONE;
        Serial.println("[CLIENT] Bad power local-expired");
    }
    // Boost expiry
    if (g_boostExpiry != 0 && nowMs >= g_boostExpiry) {
        g_boostExpiry = 0;
    }
}
