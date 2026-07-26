// =============================================================================
//  hardware.cpp — Hardware driver stubs
//
//  These are skeleton implementations.
//  Fill in each function using your specific sensor libraries.
//  All pin numbers are defined in types.h.
// =============================================================================

#include "hardware.h"
#include <Arduino.h>
#include <Wire.h>
// #include <Adafruit_PN532.h>    // uncomment when wired
// #include <Adafruit_MPU6050.h>  // uncomment when wired
// #include <ESP32Servo.h>        // uncomment when wired
// #include <SD.h>                // uncomment when wired

// ---------------------------------------------------------------------------
// Motor + Servo
// ---------------------------------------------------------------------------

// static Servo g_servo;  // uncomment

void hw_motor_init() {
    pinMode(PIN_MOTOR_STBY, OUTPUT);
    pinMode(PIN_MOTOR_IN1,  OUTPUT);
    pinMode(PIN_MOTOR_IN2,  OUTPUT);
    ledcSetup(LEDC_MOTOR_CH, LEDC_MOTOR_FREQ, LEDC_RES);
    ledcAttachPin(PIN_MOTOR_PWM, LEDC_MOTOR_CH);

    // g_servo.attach(PIN_SERVO);  // uncomment
    hw_motor_enable();
    Serial.println("[HW] Motor+Servo init OK");
}

void hw_motor_set(int8_t throttle) {
    // clamp
    throttle = constrain(throttle, -100, 100);
    uint8_t pwm = (uint8_t)(abs(throttle) * 255 / 100);

    if (throttle > 0) {
        digitalWrite(PIN_MOTOR_IN1, HIGH);
        digitalWrite(PIN_MOTOR_IN2, LOW);
    } else if (throttle < 0) {
        digitalWrite(PIN_MOTOR_IN1, LOW);
        digitalWrite(PIN_MOTOR_IN2, HIGH);
    } else {
        // Brake
        digitalWrite(PIN_MOTOR_IN1, LOW);
        digitalWrite(PIN_MOTOR_IN2, LOW);
    }
    ledcWrite(LEDC_MOTOR_CH, pwm);
}

void hw_servo_set(int8_t steering) {
    // Map -100..+100 to servo angle 50..130 (centre = 90)
    int angle = 90 + (steering * 40 / 100);
    angle = constrain(angle, 50, 130);
    // g_servo.write(angle);  // uncomment
}

void hw_motor_kill()   { digitalWrite(PIN_MOTOR_STBY, LOW);  }
void hw_motor_enable() { digitalWrite(PIN_MOTOR_STBY, HIGH); }

// ---------------------------------------------------------------------------
// IR TX
// ---------------------------------------------------------------------------

void hw_ir_fire() {
    // 38kHz burst for IR_BURST_MS ms via LEDC
    ledcSetup(LEDC_IR_CH, LEDC_IR_FREQ, LEDC_RES);
    ledcAttachPin(PIN_IR_TX1, LEDC_IR_CH);
    ledcAttachPin(PIN_IR_TX2, LEDC_IR_CH);
    ledcWrite(LEDC_IR_CH, 127); // 50% duty
    delay(IR_BURST_MS);
    ledcWrite(LEDC_IR_CH, 0);
    ledcDetachPin(PIN_IR_TX1);
    ledcDetachPin(PIN_IR_TX2);
}

// ---------------------------------------------------------------------------
// IR RX (interrupt-driven)
// ---------------------------------------------------------------------------

static volatile bool s_rearHit = false;
static volatile bool s_lapTrig = false;

void IRAM_ATTR isr_rear1() { s_rearHit = true; }
void IRAM_ATTR isr_rear2() { s_rearHit = true; }
void IRAM_ATTR isr_side1() { s_lapTrig = true; }
void IRAM_ATTR isr_side2() { s_lapTrig = true; }

void hw_ir_rx_init() {
    pinMode(PIN_IR_RX_REAR1, INPUT_PULLUP);
    pinMode(PIN_IR_RX_REAR2, INPUT_PULLUP);
    pinMode(PIN_IR_RX_SIDE1, INPUT_PULLUP);
    pinMode(PIN_IR_RX_SIDE2, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(PIN_IR_RX_REAR1), isr_rear1, FALLING);
    attachInterrupt(digitalPinToInterrupt(PIN_IR_RX_REAR2), isr_rear2, FALLING);
    attachInterrupt(digitalPinToInterrupt(PIN_IR_RX_SIDE1), isr_side1, FALLING);
    attachInterrupt(digitalPinToInterrupt(PIN_IR_RX_SIDE2), isr_side2, FALLING);
}

bool hw_ir_rear_hit_pending() {
    if (s_rearHit) { s_rearHit = false; return true; }
    return false;
}

bool hw_ir_lap_pending() {
    if (s_lapTrig) { s_lapTrig = false; return true; }
    return false;
}

// ---------------------------------------------------------------------------
// Accelerometer (MPU6050)
// ---------------------------------------------------------------------------

// static Adafruit_MPU6050 g_mpu;  // uncomment
static volatile bool s_accelReady = false;

void hw_accel_init() {
    Wire.begin(PIN_MPU_SDA, PIN_MPU_SCL);
    // if (!g_mpu.begin()) { Serial.println("[HW] MPU6050 not found!"); }
    // g_mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    // g_mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    Serial.println("[HW] Accel init OK (stub)");
}

float hw_accel_read_g() {
    // sensors_event_t a, g, temp;
    // g_mpu.getEvent(&a, &g, &temp);
    // float ax = a.acceleration.x / 9.81f;
    // float ay = a.acceleration.y / 9.81f;
    // float az = a.acceleration.z / 9.81f;
    // return sqrtf(ax*ax + ay*ay + az*az) - 1.0f;
    return 0.0f; // stub
}

// ---------------------------------------------------------------------------
// NFC (PN532)
// ---------------------------------------------------------------------------

// static Adafruit_PN532 g_nfc(PIN_NFC_SDA, PIN_NFC_SCL);  // uncomment

void hw_nfc_init() {
    // g_nfc.begin();
    // g_nfc.SAMConfig();
    Serial.println("[HW] NFC init OK (stub)");
}

bool hw_nfc_poll(uint8_t* token, uint8_t* uid, uint8_t* uidLen) {
    // uint8_t len = 0;
    // if (g_nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &len)) {
    //     *uidLen = len;
    //     // Read NDEF data from page 4 (NTAG213)
    //     g_nfc.ntag2xx_ReadPage(4, token);
    //     g_nfc.ntag2xx_ReadPage(5, token + 4);
    //     g_nfc.ntag2xx_ReadPage(6, token + 8);
    //     g_nfc.ntag2xx_ReadPage(7, token + 12);
    //     return true;
    // }
    return false; // stub
}

bool hw_nfc_write_token(const uint8_t* token) {
    // Write 16 bytes across pages 4-7 of NTAG213
    // for (int p = 0; p < 4; p++) {
    //     if (!g_nfc.ntag2xx_WritePage(4 + p, (uint8_t*)token + p * 4)) return false;
    // }
    return true; // stub
}

// ---------------------------------------------------------------------------
// Crypto
// ---------------------------------------------------------------------------

void crypto_gen_session_key(uint8_t* keyOut) {
    for (int i = 0; i < SESSION_KEY_LEN; i++) {
        keyOut[i] = (uint8_t)(esp_random() & 0xFF);
    }
}

void crypto_xor(const uint8_t* in, const uint8_t* key, uint8_t* out) {
    for (int i = 0; i < 16; i++) out[i] = in[i] ^ key[i];
}

// ---------------------------------------------------------------------------
// Buzzer / LED
// ---------------------------------------------------------------------------

void hw_buzzer_beep(uint16_t freqHz, uint16_t durationMs) {
    ledcSetup(2, freqHz, 8);
    ledcAttachPin(PIN_BUZZER, 2);
    ledcWrite(2, 127);
    delay(durationMs);
    ledcWrite(2, 0);
    ledcDetachPin(PIN_BUZZER);
}

void hw_led_set(bool on) { digitalWrite(PIN_LED, on ? HIGH : LOW); }

void hw_led_flash(uint8_t times, uint16_t periodMs) {
    for (int i = 0; i < times; i++) {
        hw_led_set(true);
        delay(periodMs / 2);
        hw_led_set(false);
        delay(periodMs / 2);
    }
}

// ---------------------------------------------------------------------------
// SD Card
// ---------------------------------------------------------------------------

static File g_logFile; // uncomment: #include <SD.h>

bool sd_log_open(const char* filename) {
    // if (!SD.begin()) return false;
    // g_logFile = SD.open(filename, FILE_WRITE);
    // return g_logFile;
    Serial.printf("[SD] Log open: %s (stub)\n", filename);
    return true;
}

void sd_log_append(const LogEntry& entry) {
    // if (g_logFile) g_logFile.write((uint8_t*)&entry, sizeof(entry));
    Serial.printf("[SD] LOG t=%lu type=%d actor=%d target=%d v1=%d v2=%d\n",
                  entry.t, entry.eventType, entry.actor,
                  entry.target, entry.value1, entry.value2);
}

void sd_log_close() {
    // if (g_logFile) g_logFile.close();
    Serial.println("[SD] Log closed");
}
