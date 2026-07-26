// Minimal host stub of <Arduino.h> so the pure protocol parsers
// (src/protocols/*.cpp) can be compiled and unit-tested with a desktop
// compiler. The parsers only need fixed-width integer types and the C
// string routines (memcpy/memset) — no hardware, Serial, or String.
#ifndef ARDUINO_H_HOST_STUB
#define ARDUINO_H_HOST_STUB

#include <stdint.h>
#include <string.h>
#include <stddef.h>

#endif // ARDUINO_H_HOST_STUB
