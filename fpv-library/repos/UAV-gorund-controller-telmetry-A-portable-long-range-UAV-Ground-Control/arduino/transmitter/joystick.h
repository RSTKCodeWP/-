// joystick.h

#ifndef JOYSTICK_H
#define JOYSTICK_H

#include "config.h"

void initJoystick();
void readJoystick(ControlPacket &packet);

#endif