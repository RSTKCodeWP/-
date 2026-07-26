#pragma once
#include "rc_types.h"

void display_init();
void display_force_full_redraw();
void display_push_log(const char* msg);
void display_set_bad_timer(uint32_t durationMs);

// Screens
void display_splash();
void display_idle(bool carConnected, uint8_t battPct);
void display_looking(uint8_t dotAnim);
void display_accept_request(uint8_t fromRcId);
void display_nfc_setup(uint8_t done, uint8_t total, bool isHost);
void display_lobby(bool p1Ready, bool p2Ready, uint8_t mode,
                   uint8_t laps, uint16_t timeSec, uint8_t tagCount, bool isHost);
void display_countdown(uint8_t tick);
void display_racing(const RCGameState& gs, uint32_t nowMs);
void display_results(const PktMatchEnd* end, uint8_t myRcId);

// Dirty flags — call after updating state to trigger partial repaint
void display_dirty_hp();
void display_dirty_powers();
void display_dirty_bad();
void display_dirty_log();
void display_dirty_header();
void display_dirty_full();
