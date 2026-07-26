#pragma once

#define SERIAL_BAUD 460800
#define DEBUG_OUT Serial

#ifdef DEBUG_OUT
#define DEBUG_INIT DEBUG_OUT.begin(SERIAL_BAUD);
#include "debuglogger.h"
#else
#define DEBUG_INIT
#define DEBUG(...)
#endif
