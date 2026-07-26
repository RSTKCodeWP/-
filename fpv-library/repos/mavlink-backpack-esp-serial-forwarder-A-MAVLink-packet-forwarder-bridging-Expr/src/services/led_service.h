#ifndef LEDSERVICE_H
#define LEDSERVICE_H

class LedService {
  bool state;
  unsigned int pin;
  unsigned long interval;
  unsigned long previousMillis;

public:
  LedService(unsigned int pin, unsigned long interval);
  void setup();
  void update(bool isConnected);
  void turnOn();
  void turnOff();
};

#endif