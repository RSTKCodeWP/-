#pragma once
// =============================================================================
//  client_logic.h — CLIENT CAR only
//
//  The client car does not hold master state.
//  It forwards events to the host for validation and executes host commands.
//  Its local state is a mirror of what the host sends in UIState broadcasts.
// =============================================================================

#include "types.h"

// ---------------------------------------------------------------------------
// Initialisation
// ---------------------------------------------------------------------------

void client_init();

// Receive and store the NFC token table sent by host during setup phase
void client_receive_nfc_table(const PktNfcTable* pkt);

// ---------------------------------------------------------------------------
// Packet handlers — called when specific packets arrive from HOST
// ---------------------------------------------------------------------------

// Apply a good power effect locally (PWM, LED, buzzer)
void client_on_execute(const PktExecute* pkt);

// Apply a bad power effect locally (PWM caps, firmware mode)
void client_on_apply_bad(const PktApplyBad* pkt);

// Clear an active bad power (cure complete or timeout)
void client_on_clear_bad(PowerType bad);

// Freeze motors — hardware kill via STBY pin
void client_on_freeze();

// Unfreeze motors
void client_on_resume();

// Match ended — freeze motors, set phase to FINISHED
void client_on_match_end(const PktMatchEnd* pkt);

// Countdown tick received from host
void client_on_countdown(uint8_t tick);

// Update mirrored local state from host's UIState broadcast
void client_on_ui_state(const UIState* ui);

// ---------------------------------------------------------------------------
// Sensor event forwarders — call from Core 0 after hardware signals
// ---------------------------------------------------------------------------

// PN532 detected a tag during race → look up in local table → send PKT_TAG_DETECTED to host
void client_forward_tag(const uint8_t* token, PowerType localPower);

// Rear IR receiver triggered → send PKT_HIT_DETECTED to host
void client_forward_hit();

// Side IR receiver triggered (lap gate) → send PKT_LAP_CROSS to host
void client_forward_lap();

// Accelerometer crossed threshold → send PKT_IMPACT to host
void client_forward_impact(float gForce);

// Own station PN532 tag read → send PKT_STATION_DET to host
void client_forward_station(PowerType stationType);

// ---------------------------------------------------------------------------
// Periodic — call every loop tick from Core 0
// ---------------------------------------------------------------------------

// Expire local timed effects (boost PWM restore after durationMs, etc.)
// These are also cleared when host sends CLEAR-BAD, but we keep local timers
// as failsafe in case host packet is lost.
void client_tick(uint32_t nowMs);

// ---------------------------------------------------------------------------
// Drive input from RC — apply with active bad-power modifiers
// ---------------------------------------------------------------------------

// Apply throttle/steering from RC, respecting current bad power state
void client_apply_drive(int8_t throttle, int8_t steering);

// ---------------------------------------------------------------------------
// Bad power modifiers (internal state, exposed for hw_motor_set / hw_servo_set)
// ---------------------------------------------------------------------------

// Returns effective throttle after bad power modifier
int8_t client_throttle_modified(int8_t raw);

// Returns effective steering after bad power modifier
int8_t client_steering_modified(int8_t raw);
