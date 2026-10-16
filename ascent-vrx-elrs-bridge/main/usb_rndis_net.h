#pragma once

#include "esp_err.h"

#include <stdbool.h>

esp_err_t usb_rndis_net_start(void);

bool usb_rndis_net_ready(void);

/** Human-readable local IPv4 string (static buffer). */
const char *usb_rndis_net_ip_str(void);
