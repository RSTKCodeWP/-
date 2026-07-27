#pragma once

void adaptive_video_init();
void adaptive_video_reset_to_defaults();
void adaptive_video_reset_requested_keyframe();
void adaptive_video_save_state();
void adaptive_video_load_state();
int  adaptive_video_get_current_dr_boost(int iRadioInterfaceIndex);
int  adaptive_video_get_current_keyframe_ms();
bool adaptive_video_is_on_lower_video_bitrate();

void adaptive_video_on_uplink_lost();
void adaptive_video_on_uplink_recovered();
void adaptive_video_on_end_of_frame();
void adaptive_video_check_update_params();
void adaptive_video_periodic_loop();
void adaptive_video_on_message_from_controller(u32 uRequestId, u8 uFlags, u32 uVideoBitrate, u16 uECScheme, u8 uStreamIndex, int iRadioDatarate, int iKeyframeMs, u8 uDRBoost);
