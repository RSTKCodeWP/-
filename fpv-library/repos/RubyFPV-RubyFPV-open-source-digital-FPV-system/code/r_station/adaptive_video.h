#pragma once

void adaptive_video_init();
void adaptive_video_reset_state(u32 uVehicleId);
void adaptive_video_pause(u32 uMilisec);
bool adaptive_video_is_paused();
u32  adaptive_video_get_last_paused_time();
void adaptive_video_reset_time_for_vehicle(u32 uVehicleId);

void adaptive_video_on_new_vehicle(int iRuntimeIndex);
void adaptive_video_on_vehicle_video_params_changed(u32 uVehicleId, video_parameters_t* pOldVideoParams, type_video_link_profile* pOldVideoProfiles);
void adaptive_video_enable_test_mode(bool bEnableTestMode);

void adaptive_video_received_vehicle_msg_ack(u32 uRequestId, u32 uVehicleId, int iInterfaceIndex);
void adaptive_video_periodic_loop(bool bForceSyncNow);
