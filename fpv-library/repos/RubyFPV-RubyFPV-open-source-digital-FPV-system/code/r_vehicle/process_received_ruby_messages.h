#pragma once
#include "../base/base.h"
#include "../radio/radiopackets2.h"

int process_received_ruby_message_from_controller(int iInterfaceIndex, u8* pPacketBuffer);
