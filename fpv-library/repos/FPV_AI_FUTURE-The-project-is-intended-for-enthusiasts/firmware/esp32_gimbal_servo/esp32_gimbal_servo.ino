// ESP32 gimbal servo slave — the Pi's dumb, jitter-free PWM output stage.
//
// Receives "S <channel> <pulse_us>\n" over USB serial from the Pi (seeker_core.pi5_io.
// make_esp32_serial_servo_writer) and drives 2 servos with the ESP32's hardware timers (LEDC via the
// ESP32Servo library). The control loop stays on the Pi; this MCU only outputs clean servo pulses.
//
// FAILSAFE: if no command arrives for FAILSAFE_MS, both servos are centred (safe hold) — a dropped
// USB link or a crashed host can never leave the gimbal slewing into a stop.
//
// Wiring: PAN servo signal -> GPIO18 (channel 0), TILT -> GPIO19 (channel 1). Servos on their OWN
// 5–6 V BEC (NOT the ESP32/Pi rail); common ground between BEC, ESP32 and Pi. Never wire motors here.
//
// Build: Arduino IDE + "esp32" board package + the "ESP32Servo" library. Flash, note the serial port
// (e.g. /dev/ttyUSB0), pass it to make_esp32_serial_servo_writer(port=...).

#include <ESP32Servo.h>

static const int PIN_PAN   = 18;     // channel 0
static const int PIN_TILT  = 19;     // channel 1
static const int US_MIN    = 900;    // clamp (match the servo's mechanical range)
static const int US_MAX    = 2100;
static const int US_CENTER = 1500;
static const unsigned long FAILSAFE_MS = 300;

Servo pan, tilt;
unsigned long last_cmd = 0;

void applyUs(int ch, int us) {
  us = constrain(us, US_MIN, US_MAX);
  if (ch == 0)      pan.writeMicroseconds(us);
  else if (ch == 1) tilt.writeMicroseconds(us);
}

void setup() {
  Serial.begin(115200);
  pan.setPeriodHertz(50);
  tilt.setPeriodHertz(50);
  pan.attach(PIN_PAN, US_MIN, US_MAX);
  tilt.attach(PIN_TILT, US_MIN, US_MAX);
  applyUs(0, US_CENTER);
  applyUs(1, US_CENTER);
  last_cmd = millis();
}

void loop() {
  static char buf[32];
  static int n = 0;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      buf[n] = 0; n = 0;
      int ch, us;
      if (sscanf(buf, "S %d %d", &ch, &us) == 2) {
        applyUs(ch, us);
        last_cmd = millis();
      }
    } else if (n < 31) {
      buf[n++] = c;
    }
  }
  if (millis() - last_cmd > FAILSAFE_MS) {   // comms lost -> centre (safe)
    applyUs(0, US_CENTER);
    applyUs(1, US_CENTER);
  }
}
