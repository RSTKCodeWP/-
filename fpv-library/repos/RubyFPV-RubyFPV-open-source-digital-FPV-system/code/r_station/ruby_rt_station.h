#pragma once

void broadcast_router_ready();
void send_message_to_central(u32 uPacketType, u32 uParam, bool bTelemetryToo);
void send_adaptive_video_paused_to_central(u32 uVehicleId, bool bPaused);

void send_alarm_to_central(u32 uAlarm, u32 uFlags1, u32 uFlags2);

void reasign_radio_links(bool bSilent);

void video_processors_init();
void video_processors_cleanup();

void log_ipc_send_central_error(u8* pPacket, int iLength);
u32  router_get_last_time_checked_for_video_packets();
bool router_is_eof();
