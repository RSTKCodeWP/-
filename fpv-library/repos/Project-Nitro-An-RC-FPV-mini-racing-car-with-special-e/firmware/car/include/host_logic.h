#pragma once
// =============================================================================
//  host_logic.h — HOST CAR only
//
//  The host car is the sole authority for all game events.
//  All validation and state mutation happens here.
//  Client car and both RCs are pure consumers of host broadcasts.
//
//  Functions are called sequentially from the Core 0 event-processing task
//  after packets are dequeued from the ESP-NOW receive queue.
// =============================================================================

#include "types.h"

// ---------------------------------------------------------------------------
// Initialisation
// ---------------------------------------------------------------------------

// Reset MatchState to defaults, clear NFC table, generate new session key
void host_init();

// ---------------------------------------------------------------------------
// NFC Setup Phase (HOST only, PHASE_NFC_SCAN)
// ---------------------------------------------------------------------------

// Randomise power pool for this session, generate session key
void host_nfc_setup_begin(uint8_t expectedTagCount);

// Called when PN532 has read a new tag during setup scan.
// Assigns a power from pool, generates token, writes to tag.
// Returns false if NFC write fails or pool is empty.
bool host_nfc_register_tag(const uint8_t* uid, uint8_t uidLen);

// Returns number of tags registered so far
uint8_t host_nfc_tag_count();

// Send the full encrypted NFC table to client car via ESP-NOW
void host_nfc_send_table();

// ---------------------------------------------------------------------------
// Race start / countdown
// ---------------------------------------------------------------------------

// Transition from LOBBY → COUNTDOWN, then fire countdown packets 3-2-1-GO
// After GO: transition to RACING, record matchStartMs
void host_start_race(RaceMode mode, uint8_t targetLaps, uint32_t timeLimitMs);

// ---------------------------------------------------------------------------
// Event validators — called when the matching packet arrives
// ---------------------------------------------------------------------------

// RC pressed SHOOT.
// Validates bullet count > 0, decrements, opens shoot window, relays SHOOT to own car.
// Returns false if invalid (0 bullets).
bool host_on_shoot(uint8_t carId, uint32_t timestamp);

// Car's rear IR receiver fired.
// Validates SHOOT window (< HIT_WINDOW_MS), shield check, applies damage.
// Returns false if invalid.
bool host_on_hit_detected(uint8_t victimCarId, uint32_t timestamp);

// Car drove over a NFC tag.
// Validates token in table, cooldown, proximity anti-cheat.
// Applies/queues power, updates table cooldowns.
// Returns false if denied.
bool host_on_tag_detected(uint8_t carId, const uint8_t* token, PowerType claimedPower, uint32_t timestamp);

// RC pressed a power slot button to use a good power.
// Validates inventory, removes from slot, sends EXECUTE to car.
// Returns false if not in inventory.
bool host_on_use_power(uint8_t carId, PowerType power);

// Car's side IR receiver fired (finish line beam broken).
// Validates lap debounce, increments lap, checks win condition.
bool host_on_lap_cross(uint8_t carId, uint32_t timestamp);

// Accelerometer threshold exceeded.
// Validates cooldown, classifies event (solo crash vs car-to-car), applies damage.
bool host_on_impact(uint8_t carId, float gForce, uint32_t timestamp);

// Car arrived at own station and PN532 is reading station tag continuously.
// Starts or continues the cure timer for that car's active bad power.
// If car stops reporting station (call stops arriving), host_on_station_lost() cancels it.
void host_on_station_present(uint8_t carId, PowerType stationType);

// Car moved away from station before cure completed
void host_on_station_lost(uint8_t carId);

// ---------------------------------------------------------------------------
// Periodic tasks — call from Core 0 every loop tick
// ---------------------------------------------------------------------------

// Check all timed states: shield expiry, bad power fallback timeout, station cure,
// boost duration, time-race countdown, heartbeat monitoring.
// Emits appropriate packets when timers expire.
void host_tick(uint32_t nowMs);

// Broadcast authoritative UIState to both remotes every HEARTBEAT_MS
void host_broadcast_ui_state(uint32_t nowMs);

// ---------------------------------------------------------------------------
// Match end
// ---------------------------------------------------------------------------

// Trigger MATCH_END sequence: freeze all, compose log, broadcast results.
// winner = 1 or 2
void host_end_match(uint8_t winner, const char* reason);

// ---------------------------------------------------------------------------
// Utility — read-only access to master state (e.g. for building UIState)
// ---------------------------------------------------------------------------

const MatchState* host_get_match_state();
