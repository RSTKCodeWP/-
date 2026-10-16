#pragma once

#include "esp_err.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

esp_err_t vrx_udp_init(void);

/** Send raw frame to VRX Ctrl UDP (9001). Returns bytes sent or -1. */
int vrx_udp_send(const uint8_t *frame, size_t len);

/** Fire-and-forget wireless status query. */
esp_err_t vrx_udp_request_status(void);

/** Simulate a menu key on the VRX. */
esp_err_t vrx_udp_send_key(const char *name);

bool vrx_udp_network_ready(void);
