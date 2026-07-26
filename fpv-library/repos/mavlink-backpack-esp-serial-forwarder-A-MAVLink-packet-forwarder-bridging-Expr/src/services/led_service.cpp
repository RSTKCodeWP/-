#include "led_service.h"
#include <Arduino.h>

LedService::LedService(unsigned int p, unsigned long i) : pin(p), interval(i), previousMillis(0), state(false) {}

void LedService::setup() {
  pinMode(pin, OUTPUT);
}

void LedService::update(bool isConnected) {
  if (!isConnected) {
    turnOn();
    return;
  }

  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;
    state = !state;
    digitalWrite(pin, state);
  }
}

void LedService::turnOn() {
  state = true;
  digitalWrite(pin, HIGH);
}

void LedService::turnOff() {
  state = false;
  digitalWrite(pin, LOW);
}   