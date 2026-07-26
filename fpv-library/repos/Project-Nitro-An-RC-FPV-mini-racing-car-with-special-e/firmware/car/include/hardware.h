#pragma once
// =============================================================================
//  hardware.h — Motor, servo, IR, accelerometer, NFC, buzzer drivers
//
//  All hardware is accessed only through these functions.
//  Core 1 owns: motor, servo, IR TX.
//  Core 0 owns: NFC, buzzer, LED.
//  ISR context owns: IR RX, accelerometer interrupt.
// =============================================================================

#include "types.h"
#include <Arduino.h>

// ---------------------------------------------------------------------------
// Motor + Servo
// ---------------------------------------------------------------------------

// Call once from Core 1 setup
void hw_motor_init();

// throttle: -100 (full reverse) to +100 (full forward), 0 = stop
// Applies bad-power modifiers (SLOWNESS, RANDOM, DRIFT) if active
void hw_motor_set(int8_t throttle);

// steering: -100 (full left) to +100 (full right), 0 = centre
// Applies boost steering sensitivity reduction and drift amplification if active
void hw_servo_set(int8_t steering);

// Hard-kill motors (GLOBAL-FREEZE). Use hw_motor_enable() to re-enable.
// Pulls STBY pin LOW — TB6612FNG hardware kill, cannot be overridden in software.
void hw_motor_kill();
void hw_motor_enable();

// ---------------------------------------------------------------------------
// IR Weapon TX
// ---------------------------------------------------------------------------

// Fire 38kHz burst for IR_BURST_MS ms (blocking in caller's task)
// Should only be called from Core 1 via a binary semaphore signal
void hw_ir_fire();

// ---------------------------------------------------------------------------
// IR Weapon / Finish Gate RX (interrupt-driven)
// ---------------------------------------------------------------------------

// Call once in setup — attaches ISR to all 4 IR receiver pins
void hw_ir_rx_init();

// Polled by game logic: returns true once per rear-receiver hit detection
// Resets internal flag after read
bool hw_ir_rear_hit_pending();

// Polled by game logic: returns true once per side-receiver (lap gate) trigger
bool hw_ir_lap_pending();

// ---------------------------------------------------------------------------
// Accelerometer (MPU6050)
// ---------------------------------------------------------------------------

// Init I2C + MPU6050, enable data-ready interrupt on PIN_MPU_INT
void hw_accel_init();

// Reads latest sample from MPU6050 — called from ISR-triggered task
// Returns resultant G above 1g:  sqrt(ax²+ay²+az²) - 1.0f
// Returns 0.0f if no new data
float hw_accel_read_g();

// ---------------------------------------------------------------------------
// NFC (PN532 via I2C)
// ---------------------------------------------------------------------------

// Init PN532
void hw_nfc_init();

// Poll for a tag — returns true and fills token[] (16 bytes) if a tag was read
// token is the decrypted content read from the tag's NDEF payload
// Also fills uid[] and uidLen for raw UID access during setup scanning
bool hw_nfc_poll(uint8_t* token, uint8_t* uid, uint8_t* uidLen);

// During NFC setup phase (HOST only):
// Write an encrypted token to the currently presented tag
// Returns true on success
bool hw_nfc_write_token(const uint8_t* token);

// ---------------------------------------------------------------------------
// NFC Token Crypto (simple XOR session-key cipher)
// ---------------------------------------------------------------------------

// Generate a random 16-byte session key (uses esp_random())
void crypto_gen_session_key(uint8_t* keyOut);

// XOR-encrypt or XOR-decrypt a 16-byte block (symmetric — same function)
void crypto_xor(const uint8_t* in, const uint8_t* key, uint8_t* out);

// ---------------------------------------------------------------------------
// Buzzer / LED
// ---------------------------------------------------------------------------

void hw_buzzer_beep(uint16_t freqHz, uint16_t durationMs);  // blocking
void hw_led_set(bool on);
void hw_led_flash(uint8_t times, uint16_t periodMs);         // non-blocking via timer

// ---------------------------------------------------------------------------
// SD Card logging (HOST only)
// ---------------------------------------------------------------------------

// Open or create a new match log file on SD card
// filename = e.g. "/match_001.log"
bool sd_log_open(const char* filename);
void sd_log_append(const LogEntry& entry);
void sd_log_close();
